"""The local FDT latency screen must measure the real chat path without retaining payloads."""

# ruff: noqa: INP001

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from benchmarks.coaching.fdt_latency.run import run

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_tcp_screen_records_authoritative_fdt_latency_without_model_text(tmp_path: Path) -> None:
    """Each measured reply is a real forecast receipt with no model-generation phase."""
    output = tmp_path / "fdt-latency.safe.json"

    report = await run(output, rounds=1, conditions=(1, 2))
    serialized = json.dumps(report, ensure_ascii=False)

    assert output.exists()
    assert report["scope"] == {
        "transport": "local_tcp",
        "customer_prediction_accuracy_measured": False,
        "model_generation_measured": False,
        "fdt_mode": "forecast",
        "horizon_days": 30,
        "paths": 400,
    }
    conditions = report["conditions"]
    assert isinstance(conditions, list)
    assert [row["concurrency"] for row in conditions] == [1, 2]
    assert all(
        row["requests"] == row["numeric_contract_ok"]
        and row["model_or_generation_phase_observations"] == 0
        and row["fdt_phase_observations"] == row["requests"]
        for row in conditions
    )
    assert "앞으로 잔액" not in serialized
    assert "r49-fdt-token" not in serialized
