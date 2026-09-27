"""Quality-gated concurrent chat measurement against one isolated deployed API.

The runner deliberately retains only aggregate timings and fixed case IDs.  It
never writes an endpoint, credential, prompt, transaction, or response body to
its report.  A candidate can therefore be compared with a baseline using the
same fixture and case set without turning benchmark artifacts into a source of
customer data.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import os
import re
import statistics
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final, Literal

import httpx2

from benchmarks.coaching.chat_response.cases import CASES, ChatCase
from benchmarks.coaching.chat_response.run import api_origin, safe_output, twin_payload
from benchmarks.coaching.chat_response.score import (
    data_request_passed,
    finance_passed,
    history_passed,
    numeric_passed,
)
from coaching_service.chat_answers import ChatAnswer
from coaching_service.schemas import Coaching, Frozen, JsonDocument

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence
    from datetime import date

Phase = Literal["without_twin", "with_twin"]
_MAX_CONCURRENCY: Final = 8
_TIMING: Final = re.compile(r"^\s*(?P<name>[a-z_]+)\s*;\s*dur=(?P<duration>\d+(?:\.\d+)?)\s*$")
_KNOWN_TIMINGS: Final = frozenset((
    "api", "fdt", "fdt_compute", "fdt_wait", "model", "limiter", "tokenize", "generation",
))


class Arguments(Frozen):
    api_url: str
    fixture: Path
    output: Path
    token_env: str
    timeout_seconds: float
    rounds: int
    concurrency: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class Observation:
    """One response-ready observation without retaining its source payload."""

    latency_ms: float
    http_ok: bool
    semantic_ok: bool
    timing: dict[str, float]


@dataclass(frozen=True, slots=True)
class Target:
    """One isolated API and condition identity shared by its request wave."""

    client: httpx2.AsyncClient
    base: str
    token: str
    as_of: date
    phase: Phase
    condition: int


@dataclass(frozen=True, slots=True)
class WaveSlot:
    """All immutable state needed to issue one synchronized message request."""

    session_id: str
    case: ChatCase
    ordinal: int
    barrier: asyncio.Barrier
    round_index: int
    slot: int


def percentile(samples: Sequence[float], quantile: float) -> float:
    """Return nearest-rank percentiles so reports do not interpolate unseen requests."""
    if not samples:
        raise ValueError("load_latency_samples_missing")
    index = max(0, min(len(samples) - 1, math.ceil(len(samples) * quantile) - 1))
    return sorted(samples)[index]


def parse_server_timing(value: str | None) -> dict[str, float]:
    """Read only the documented aggregate timing fields from an opt-in header."""
    if value is None:
        return {}
    result: dict[str, float] = {}
    for item in value.split(","):
        matched = _TIMING.fullmatch(item)
        if matched is None:
            continue
        name = matched["name"]
        if name in _KNOWN_TIMINGS:
            result[name] = float(matched["duration"])
    return result


def case_digest(cases: Iterable[ChatCase]) -> str:
    """Identify the fixed semantic contract without writing user question text."""
    rows = [
        (case.id, case.setup, case.expected_kind, case.expected_status, case.reference_id, case.markers)
        for case in cases
    ]
    return hashlib.sha256(
        json.dumps(rows, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def answer_from_body(body: JsonDocument) -> Coaching | ChatAnswer:
    """Parse the typed service response before using it as a quality observation."""
    return (
        ChatAnswer.model_validate(body.root)
        if "answer_type" in body.root
        else Coaching.model_validate(body.root)
    )


def semantic_passed(case: ChatCase, body: JsonDocument, ordinal: int, as_of: date) -> bool:
    """Reuse the fixed sequential-suite contract for an individual concurrent reply."""
    try:
        answer = answer_from_body(body)
    except ValueError:
        return False
    match case.expected_kind:
        case "finance":
            return isinstance(answer, ChatAnswer) and finance_passed(case, answer)
        case "data_request":
            return isinstance(answer, ChatAnswer) and data_request_passed(answer)
        case "history":
            return isinstance(answer, ChatAnswer) and history_passed(answer)
        case "forecast" | "risk":
            return isinstance(answer, Coaching) and numeric_passed(case, answer, ordinal, as_of)


async def create_sessions(target: Target, count: int) -> tuple[str, ...]:
    """Pre-create one empty session per request so message latency has one boundary."""
    sessions: list[str] = []
    for index in range(count):
        response = await target.client.post(
            target.base + "/v1/sessions",
            json={},
            headers={
                "Authorization": "Bearer " + target.token,
                "Idempotency-Key": (
                    f"load-session-{target.phase}-{target.condition}-{index}-{uuid.uuid4().hex}"
                ),
            },
        )
        if response.status_code != 200:
            message = f"load_session_http_{response.status_code}"
            raise RuntimeError(message)
        identifier = response.json().get("id")
        if not isinstance(identifier, str):
            raise TypeError("load_session_contract")
        sessions.append(identifier)
    return tuple(sessions)


async def one_message(target: Target, wave: WaveSlot) -> Observation:
    """Start with the wave and keep only final contract and timing observations."""
    await wave.barrier.wait()
    started = time.perf_counter()
    response = await target.client.post(
        target.base + "/v1/sessions/" + wave.session_id + "/messages",
        json={"question": wave.case.question},
        headers={
            "Authorization": "Bearer " + target.token,
            "Idempotency-Key": (
                "load-message-"
                f"{target.phase}-{target.condition}-{wave.round_index}-{wave.slot}-{uuid.uuid4().hex}"
            ),
            "X-Coaching-Trace": "1",
        },
    )
    latency_ms = (time.perf_counter() - started) * 1000
    try:
        body = JsonDocument.model_validate_json(response.content)
    except ValueError:
        body = None
    return Observation(
        latency_ms=latency_ms,
        http_ok=response.status_code == 200,
        semantic_ok=response.status_code == 200 and body is not None and semantic_passed(
            wave.case, body, wave.ordinal, target.as_of,
        ),
        timing=parse_server_timing(response.headers.get("server-timing")),
    )


async def measure_condition(
    target: Target, cases: Sequence[ChatCase], concurrency: int, rounds: int,
) -> dict[str, object]:
    """Measure one arrival wave size after enough rounds to cover every fixed case."""
    if not cases:
        raise ValueError("load_cases_missing")
    effective_rounds = max(rounds, math.ceil(len(cases) / concurrency))
    sessions = await create_sessions(target, concurrency * effective_rounds)
    observations: list[Observation] = []
    case_positions = {case.id: index for index, case in enumerate(CASES)}
    for round_index in range(effective_rounds):
        barrier = asyncio.Barrier(concurrency)
        selected = tuple(
            cases[(round_index * concurrency + slot) % len(cases)] for slot in range(concurrency)
        )
        slots = tuple(
            WaveSlot(
                session_id=sessions[round_index * concurrency + slot],
                case=case,
                ordinal=case_positions[case.id],
                barrier=barrier,
                round_index=round_index,
                slot=slot,
            )
            for slot, case in enumerate(selected)
        )
        observations.extend(await asyncio.gather(*(one_message(target, slot) for slot in slots)))
    latencies = [row.latency_ms for row in observations]
    timing_counts = {
        name: sum(name in row.timing for row in observations)
        for name in sorted(_KNOWN_TIMINGS - {"api"})
    }
    return {
        "phase": target.phase,
        "concurrency": concurrency,
        "rounds": effective_rounds,
        "requests": len(observations),
        "http_ok": sum(row.http_ok for row in observations),
        "semantic_ok": sum(row.semantic_ok for row in observations),
        "p50_ms": round(statistics.median(latencies), 3),
        "p95_ms": round(percentile(latencies, 0.95), 3),
        "max_ms": round(max(latencies), 3),
        "timing_phase_observations": timing_counts,
    }


async def run(options: Arguments) -> dict[str, object]:
    """Run both Twin states on a fresh isolated user and save a non-sensitive report."""
    if options.rounds < 1:
        raise ValueError("load_rounds_invalid")
    if (
        not options.concurrency
        or any(value < 1 or value > _MAX_CONCURRENCY for value in options.concurrency)
        or len(set(options.concurrency)) != len(options.concurrency)
    ):
        raise ValueError("load_concurrency_invalid")
    token = os.environ.get(options.token_env)
    if not token:
        raise ValueError("load_token_missing")
    base = api_origin(options.api_url)
    fixture = twin_payload(options.fixture)
    destination = safe_output(options.output)
    before_twin = tuple(case for case in CASES if case.setup == "without_twin")
    after_twin = tuple(case for case in CASES if case.setup == "with_twin")
    if not before_twin or not after_twin:
        raise RuntimeError("load_phase_case_catalog_invalid")
    async with httpx2.AsyncClient(timeout=options.timeout_seconds, trust_env=False) as client:
        initial = await client.get(base + "/v1/twin", headers={"Authorization": "Bearer " + token})
        if initial.status_code != 404:
            raise RuntimeError("load_requires_isolated_user_without_twin")
        conditions = [
            await measure_condition(
                Target(client, base, token, fixture.as_of, "without_twin", concurrency),
                before_twin,
                concurrency,
                options.rounds,
            )
            for concurrency in options.concurrency
        ]
        bootstrap = await client.post(
            base + "/v1/twin",
            json=fixture.model_dump(mode="json"),
            headers={
                "Authorization": "Bearer " + token,
                "Idempotency-Key": "load-bootstrap-" + uuid.uuid4().hex,
            },
        )
        if bootstrap.status_code != 200:
            message = f"load_twin_bootstrap_http_{bootstrap.status_code}"
            raise RuntimeError(message)
        conditions.extend(
            await measure_condition(
                Target(client, base, token, fixture.as_of, "with_twin", concurrency),
                after_twin,
                concurrency,
                options.rounds,
            )
            for concurrency in options.concurrency
        )
    report: dict[str, object] = {
        "schema": "chat-response-load/1",
        "api_origin_sha256": hashlib.sha256(base.encode("utf-8")).hexdigest(),
        "fixture_sha256": hashlib.sha256(options.fixture.read_bytes()).hexdigest(),
        "case_catalog_sha256": case_digest(CASES),
        "minimum_rounds": options.rounds,
        "conditions": conditions,
        "scope": {
            "transport": "isolated_deployed_api",
            "response_quality": "fixed_synthetic_contract_only",
            "model_generation_verified_only_when_generation_timing_observed": True,
            "customer_prediction_accuracy_measured": False,
        },
    }
    serialized = json.dumps(report, ensure_ascii=False, indent=2)
    if token in serialized or base in serialized:
        raise RuntimeError("load_report_sensitive_value")
    (destination / "report.safe.json").write_text(serialized, encoding="utf-8")
    return report


def arguments() -> Arguments:
    parser = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument("--api-url", required=True, help="Isolated API origin without credentials")
    _ = parser.add_argument("--fixture", type=Path, required=True, help="Credential-free Twin bootstrap JSON")
    _ = parser.add_argument("--output", type=Path, required=True, help="New directory below artifacts/")
    _ = parser.add_argument("--token-env", default="COACHING_CHAT_TOKEN")
    _ = parser.add_argument("--timeout-seconds", type=float, default=45.0)
    _ = parser.add_argument("--rounds", type=int, default=20)
    _ = parser.add_argument("--concurrency", type=int, nargs="+", default=[1, 4, 8])
    return Arguments.model_validate(vars(parser.parse_args()))


def main() -> None:
    report = asyncio.run(run(arguments()))
    conditions = report["conditions"]
    if not isinstance(conditions, list):
        raise TypeError("load_report_conditions_invalid")
    # CLI output intentionally contains counts only; inspect the safe artifact for timing aggregates.
    print(json.dumps({"conditions": len(conditions), "case_count": len(CASES)}))  # noqa: T201


if __name__ == "__main__":
    main()
