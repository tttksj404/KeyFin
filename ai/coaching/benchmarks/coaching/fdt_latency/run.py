"""Measure real local HTTP latency for a model-free authoritative FDT forecast.

The screen creates isolated users and sessions before timing starts. It therefore
measures authentication, session turn persistence, deterministic FDT execution,
rendering, and response serialization without retaining prompts, Twin payloads,
or individual response values in the report.
"""

from __future__ import annotations

import argparse
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
from anyio.lowlevel import checkpoint

from benchmarks.coaching.chat_response.load import parse_server_timing
from benchmarks.coaching.e2e.e2e_runtime import serve
from coaching_service.api import create_app
from coaching_service.settings import Client, Settings
from tests.test_engine import fixture

if TYPE_CHECKING:
    from collections.abc import Sequence

    from coaching_service.llm_contract import EvidenceInput

_MAX_CONCURRENCY: Final = 8
_TOKEN_PREFIX: Final = "r49-fdt-latency-benchmark-token-"  # noqa: S105 - fixed local benchmark namespace.
_PHASES: Final = ("fdt", "fdt_compute", "fdt_wait")


@dataclass(frozen=True, slots=True)
class Slot:
    """One pre-created user session and a unique deterministic calculation seed."""

    token: str
    session_id: str
    seed: int


@dataclass(frozen=True, slots=True)
class Observation:
    """Payload-free request observation retained only until aggregate scoring finishes."""

    client_ms: float
    timing: dict[str, float]


class ModelMustNotRun:
    """Fail the screen if a complete FDT receipt ever enters model generation."""

    deterministic_finance_fast_path: Final[bool] = True

    @staticmethod
    async def write(_: EvidenceInput) -> NoReturn:
        raise AssertionError("fdt_latency_model_write_called")

    @staticmethod
    async def judge(_: EvidenceInput) -> NoReturn:
        raise AssertionError("fdt_latency_model_judge_called")

    @staticmethod
    async def route(_: EvidenceInput) -> NoReturn:
        raise AssertionError("fdt_latency_model_route_called")


def write_report(output: Path, report: dict[str, object]) -> None:
    """Persist only the aggregate screen result outside the request event loop."""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def percentile(samples: Sequence[float], quantile: float) -> float:
    """Return a nearest-rank percentile so the report never interpolates a sample."""
    if not samples:
        raise ValueError("fdt_latency_samples_missing")
    index = max(0, min(len(samples) - 1, math.ceil(len(samples) * quantile) - 1))
    return sorted(samples)[index]


async def create_session(client: httpx2.AsyncClient, base: str, token: str, key: str) -> str:
    """Create the session outside the timed turn so storage setup is not FDT latency."""
    response = await client.post(
        base + "/v1/sessions",
        json={},
        headers={"Authorization": "Bearer " + token, "Idempotency-Key": key},
    )
    if response.status_code != 200:
        raise RuntimeError("fdt_latency_session_http")
    value = response.json().get("id")
    if not isinstance(value, str):
        raise TypeError("fdt_latency_session_contract")
    return value


async def turn(client: httpx2.AsyncClient, base: str, slot: Slot) -> Observation:
    """Run one actual forecast response and retain only timing phases after contract checks."""
    started = time.perf_counter()
    response = await client.post(
        base + "/v1/sessions/" + slot.session_id + "/messages",
        json={
            "question": "앞으로 잔액 예측해줘",
            "analysis": {"mode": "forecast", "horizon_days": 30, "paths": 400, "seed": slot.seed},
        },
        headers={
            "Authorization": "Bearer " + slot.token,
            "Idempotency-Key": "r49-fdt-turn-" + str(slot.seed),
            "X-Coaching-Trace": "1",
        },
    )
    elapsed = (time.perf_counter() - started) * 1000
    if response.status_code != 200:
        raise RuntimeError("fdt_latency_turn_http")
    body = response.json()
    receipt = body.get("receipt")
    numeric = receipt.get("numeric_result") if isinstance(receipt, dict) else None
    if (
        body.get("model") != "not_called"
        or body.get("wording_source") != "template"
        or not isinstance(numeric, dict)
        or numeric.get("mode") != "forecast"
    ):
        raise RuntimeError("fdt_latency_response_contract")
    timing = parse_server_timing(response.headers.get("server-timing"))
    if not all(phase in timing for phase in _PHASES):
        raise RuntimeError("fdt_latency_trace_missing")
    if "model" in timing or "generation" in timing:
        raise RuntimeError("fdt_latency_unexpected_model_phase")
    return Observation(elapsed, timing)


async def wave(client: httpx2.AsyncClient, base: str, slots: Sequence[Slot]) -> tuple[Observation, ...]:
    """Release one pre-built request wave together without retaining input payloads."""
    start = anyio.Event()
    observations: list[Observation] = []

    async def send(slot: Slot) -> None:
        await start.wait()
        observations.append(await turn(client, base, slot))

    async with anyio.create_task_group() as group:
        for slot in slots:
            group.start_soon(send, slot)
        await checkpoint()
        start.set()
    return tuple(observations)


def summarize(observations: Sequence[Observation], concurrency: int, rounds: int) -> dict[str, object]:
    """Aggregate request and server timings without keeping a user-level row."""
    if not observations:
        raise ValueError("fdt_latency_observations_missing")
    clients = [row.client_ms for row in observations]
    phase_values = {
        phase: [row.timing[phase] for row in observations]
        for phase in _PHASES
    }
    return {
        "concurrency": concurrency,
        "rounds": rounds,
        "requests": len(observations),
        "numeric_contract_ok": len(observations),
        "client_p50_ms": round(statistics.median(clients), 3),
        "client_p95_ms": round(percentile(clients, 0.95), 3),
        "client_max_ms": round(max(clients), 3),
        "fdt_phase_observations": len(observations),
        "fdt_phases_ms": {
            phase: {
                "p50": round(statistics.median(values), 3),
                "p95": round(percentile(values, 0.95), 3),
            }
            for phase, values in phase_values.items()
        },
        "model_or_generation_phase_observations": 0,
    }


async def run(output: Path, *, rounds: int, conditions: Sequence[int]) -> dict[str, object]:
    """Run the isolated FDT TCP screen and write a payload-free aggregate report."""
    if await anyio.to_thread.run_sync(output.exists):
        raise FileExistsError("fdt_latency_output_exists")
    if rounds < 1:
        raise ValueError("fdt_latency_rounds_invalid")
    if (
        not conditions
        or len(set(conditions)) != len(conditions)
        or any(value < 1 or value > _MAX_CONCURRENCY for value in conditions)
    ):
        raise ValueError("fdt_latency_concurrency_invalid")
    maximum = max(conditions)
    tokens = tuple(_TOKEN_PREFIX + str(index).zfill(2) for index in range(maximum))
    clients = tuple(
        Client(user_id="fdt-latency-" + str(index), token=token)
        for index, token in enumerate(tokens)
    )
    with tempfile.TemporaryDirectory(prefix="keyfin-r49-fdt-latency-") as directory:
        settings = Settings(database=Path(directory) / "coaching.sqlite3", clients=clients, persona="plain")
        app = create_app(settings, ModelMustNotRun())
        async with serve(app) as base, httpx2.AsyncClient(trust_env=False, timeout=30) as client:
            for index, token in enumerate(tokens):
                bootstrap = await client.post(
                    base + "/v1/twin",
                    json=fixture("fdt-latency-" + str(index)).model_dump(mode="json"),
                    headers={
                        "Authorization": "Bearer " + token,
                        "Idempotency-Key": "r49-fdt-bootstrap-" + str(index),
                    },
                )
                if bootstrap.status_code != 200:
                    raise RuntimeError("fdt_latency_bootstrap_http")
            summaries: list[dict[str, object]] = []
            for condition in conditions:
                slots: list[Slot] = []
                for ordinal in range(rounds * condition):
                    owner = ordinal % condition
                    session = await create_session(
                        client, base, tokens[owner], f"r49-fdt-session-{condition}-{ordinal}",
                    )
                    slots.append(Slot(tokens[owner], session, 10_000 + condition * 100 + ordinal))
                observations: list[Observation] = []
                for offset in range(0, len(slots), condition):
                    observations.extend(await wave(client, base, slots[offset:offset + condition]))
                summaries.append(summarize(observations, condition, rounds))
    report: dict[str, object] = {
        "schema": "r49-fdt-local-tcp-latency/1",
        "conditions": summaries,
        "scope": {
            "transport": "local_tcp",
            "customer_prediction_accuracy_measured": False,
            "model_generation_measured": False,
            "fdt_mode": "forecast",
            "horizon_days": 30,
            "paths": 400,
        },
    }
    await anyio.to_thread.run_sync(write_report, output, report)
    return report


def arguments() -> argparse.Namespace:
    """Parse a small explicit benchmark configuration."""
    parser = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument("--output", required=True, type=Path)
    _ = parser.add_argument("--rounds", default=8, type=int)
    _ = parser.add_argument("--concurrency", default=(1, 4, 8), nargs="+", type=int)
    return parser.parse_args()


def main() -> None:
    """Write the aggregate artifact and print no prompt, token, or response content."""
    options = arguments()

    async def invoke() -> dict[str, object]:
        return await run(
            options.output,
            rounds=options.rounds,
            conditions=tuple(options.concurrency),
        )

    report = anyio.run(invoke)
    conditions = report["conditions"]
    if not isinstance(conditions, list):
        raise TypeError("fdt_latency_report_conditions_invalid")
    print(json.dumps({"conditions": len(conditions)}))  # noqa: T201 - aggregate CLI confirmation only.


if __name__ == "__main__":
    main()
