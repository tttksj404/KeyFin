"""Measure real local HTTP latency for the model-free catalog response path.

The screen deliberately uses a model object that raises if called.  It therefore
measures API authentication, session persistence, pinned-source retrieval and
response serialization, but not model generation, FDT calculation, deployment
networking, or customer-data prediction accuracy.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import statistics
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final, NoReturn

import anyio
import httpx2

from benchmarks.coaching.e2e.e2e_runtime import serve
from benchmarks.coaching.knowledge_response.cases import CONCEPTS
from coaching_service.api import create_app
from coaching_service.settings import Client, Settings

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from coaching_service.llm_contract import EvidenceInput

_MAX_CONCURRENCY: Final = 8
_TOKEN_PREFIX: Final = "benchmark-direct-catalog-token-"  # noqa: S105 - fixed non-secret test namespace.


@dataclass(frozen=True, slots=True)
class DirectCase:
    """One model-free education answer and every ordered catalog reference it needs."""

    id: str
    question: str
    reference_ids: tuple[str, ...]


def direct_cases() -> tuple[DirectCase, ...]:
    """Keep comparison questions explicit rather than deriving them from production aliases."""
    singles: list[DirectCase] = []
    for row in CONCEPTS:
        if row.reference_id is None:
            raise ValueError("direct_catalog_single_reference_missing")
        singles.append(DirectCase(row.id, row.question, (row.reference_id,)))
    # These are independently written, stable education comparisons.  They
    # verify the new two-source renderer without turning a personal choice or
    # current return into a model-free answer.
    comparisons = (
        DirectCase("compare-etf-bonds", "ETF와 채권의 차이를 비교해줘.", ("etf", "bonds")),
        DirectCase(
            "compare-revolving-loan-components",
            "리볼빙과 대출 원리금 상환의 차이는?",
            ("revolving", "loan_principal_interest"),
        ),
        DirectCase(
            "compare-etf-diversification",
            "ETF와 분산투자의 차이를 알려줘.",
            ("etf", "diversification"),
        ),
    )
    return tuple(singles) + comparisons


DIRECT_CASES: Final = direct_cases()


class ModelMustNotRun:
    """Expose the evaluated shortcut capability and fail if any inference is attempted."""

    deterministic_finance_fast_path: Final[bool] = True

    @staticmethod
    async def write(_: EvidenceInput) -> NoReturn:
        raise AssertionError("direct_catalog_latency_model_write_called")

    @staticmethod
    async def judge(_: EvidenceInput) -> NoReturn:
        raise AssertionError("direct_catalog_latency_model_judge_called")

    @staticmethod
    async def route(_: EvidenceInput) -> NoReturn:
        raise AssertionError("direct_catalog_latency_model_route_called")


def percentile(samples: Sequence[float], quantile: float) -> float:
    """Return a nearest-rank percentile for the recorded client round trips."""
    if not samples:
        raise ValueError("latency_samples_missing")
    index = max(0, min(len(samples) - 1, math.ceil(len(samples) * quantile) - 1))
    return sorted(samples)[index]


def case_digest(cases: Iterable[DirectCase]) -> str:
    """Identify the fixed screen without writing raw user-question text to an artifact."""
    return hashlib.sha256(
        json.dumps([(row.id, row.reference_ids) for row in cases], separators=(",", ":")).encode()
    ).hexdigest()


def check_response(response: httpx2.Response, expected: DirectCase) -> None:
    """Verify source, reference and acceleration boundary before retaining a latency."""
    if response.status_code != 200:
        message = f"direct_catalog_http_{response.status_code}"
        raise RuntimeError(message)
    body = response.json()
    if (
        body.get("answer_type") != "finance_education"
        or body.get("status") != "answered"
        or body.get("wording_source") != "template"
        or body.get("model") != "not_called"
    ):
        raise RuntimeError("direct_catalog_response_contract")
    evidence = body.get("evidence")
    references = evidence.get("references") if isinstance(evidence, dict) else None
    if not isinstance(references, list):
        raise TypeError("direct_catalog_reference_contract")
    reference_ids: list[str] = []
    for row in references:
        if not isinstance(row, dict) or not isinstance(identifier := row.get("id"), str):
            raise TypeError("direct_catalog_reference_contract")
        reference_ids.append(identifier)
    if tuple(reference_ids) != expected.reference_ids:
        raise RuntimeError("direct_catalog_reference_contract")
    timing = response.headers.get("server-timing", "")
    if "model;dur=" in timing or "fdt;dur=" in timing:
        raise RuntimeError("direct_catalog_unexpected_compute_phase")


async def create_sessions(
    client: httpx2.AsyncClient,
    base: str,
    tokens: Sequence[str],
    count: int,
    condition: int,
) -> list[str]:
    """Pre-create empty sessions so measured requests contain exactly one user turn."""
    sessions: list[str] = []
    for index in range(count):
        response = await client.post(
            base + "/v1/sessions",
            json={},
            headers={
                "Authorization": "Bearer " + tokens[index % condition],
                "Idempotency-Key": f"direct-session-{condition}-{index}",
            },
        )
        if response.status_code != 200:
            message = f"direct_catalog_session_{response.status_code}"
            raise RuntimeError(message)
        identifier = response.json().get("id")
        if not isinstance(identifier, str):
            raise TypeError("direct_catalog_session_contract")
        sessions.append(identifier)
    return sessions


async def measure_condition(
    client: httpx2.AsyncClient,
    base: str,
    tokens: Sequence[str],
    *,
    concurrency: int,
    rounds: int,
) -> dict[str, int | float]:
    """Issue synchronized waves from separate owners; no session receives history."""
    cases = DIRECT_CASES
    # A latency condition is also a source-fidelity screen.  Do not publish a
    # 30-case denominator if C1 happened to sample only the first few entries.
    # Keep the requested repeat count as a lower bound and add only enough waves
    # to cover every fixed single- and two-subject case once.
    effective_rounds = max(rounds, math.ceil(len(cases) / concurrency))
    sessions = await create_sessions(client, base, tokens, concurrency * effective_rounds, concurrency)
    samples: list[float] = []
    for round_index in range(effective_rounds):
        async def send(slot: int, *, index: int = round_index) -> float:
            case = cases[(index * concurrency + slot) % len(cases)]
            started = time.perf_counter()
            response = await client.post(
                base + f"/v1/sessions/{sessions[index * concurrency + slot]}/messages",
                json={"question": case.question},
                headers={
                    "Authorization": "Bearer " + tokens[slot],
                    "Idempotency-Key": f"direct-message-{concurrency}-{index}-{slot}",
                    "X-Coaching-Trace": "1",
                },
            )
            elapsed = (time.perf_counter() - started) * 1000
            check_response(response, case)
            return elapsed

        samples.extend(await asyncio.gather(*(send(slot) for slot in range(concurrency))))
    return {
        "concurrency": concurrency,
        "rounds": effective_rounds,
        "requests": len(samples),
        "p50_ms": round(statistics.median(samples), 3),
        "p95_ms": round(percentile(samples, 0.95), 3),
        "max_ms": round(max(samples), 3),
        "errors": 0,
        "model_calls": 0,
        "fdt_calls": 0,
    }


async def run(output: Path, *, rounds: int, conditions: Sequence[int]) -> dict[str, object]:
    """Run a fresh loopback screen and write only aggregate, non-customer evidence."""
    if await anyio.to_thread.run_sync(output.exists):
        raise FileExistsError("direct_catalog_latency_output_exists")
    if rounds < 1:
        raise ValueError("direct_catalog_latency_rounds_invalid")
    if not conditions or any(value < 1 or value > _MAX_CONCURRENCY for value in conditions):
        raise ValueError("direct_catalog_latency_concurrency_invalid")
    tokens = tuple(_TOKEN_PREFIX + str(index).zfill(2) for index in range(_MAX_CONCURRENCY))
    with tempfile.TemporaryDirectory(prefix="keyfin-direct-catalog-") as directory:
        app = create_app(
            Settings(
                database=Path(directory) / "coaching.sqlite3",
                clients=tuple(
                    Client(user_id=f"direct-{index}", token=token)
                    for index, token in enumerate(tokens)
                ),
            ),
            ModelMustNotRun(),
        )
        async with serve(app) as base, httpx2.AsyncClient(trust_env=False) as client:
            results = [
                await measure_condition(client, base, tokens, concurrency=concurrency, rounds=rounds)
                for concurrency in conditions
            ]
    report: dict[str, object] = {
        "schema": "r26-direct-catalog-tcp-latency/2",
        "case_count": len(DIRECT_CASES),
        "case_ids_sha256": case_digest(DIRECT_CASES),
        "minimum_rounds": rounds,
        "conditions": results,
        "scope": {
            "transport": "local_tcp",
            "source_pinned": True,
            "model_generation_measured": False,
            "fdt_measured": False,
            "customer_prediction_accuracy_measured": False,
        },
    }
    await anyio.to_thread.run_sync(lambda: output.parent.mkdir(parents=True, exist_ok=True))
    await anyio.to_thread.run_sync(
        lambda: output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    )
    return report


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--rounds", type=int, default=20)
    parser.add_argument("--concurrency", type=int, nargs="+", default=[1, 4, 8])
    return parser.parse_args()


def main() -> None:
    options = arguments()
    report = asyncio.run(run(options.output, rounds=options.rounds, conditions=tuple(options.concurrency)))
    print(  # noqa: T201 - CLI prints aggregate counts only, never requests or tokens.
        "DIRECT_CATALOG_LATENCY_WRITTEN "
        + json.dumps({"conditions": len(report["conditions"]), "case_count": report["case_count"]})
    )


if __name__ == "__main__":
    main()
