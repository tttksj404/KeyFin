from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

import fdt.engine as upstream
import numpy as np
import pytest
from test_engine import fixture

from coaching_service.chart_engine import daily_forecast
from coaching_service.engine import EngineAdapter
from coaching_service.errors import ServiceError
from coaching_service.schemas import JsonDocument


def samples() -> SimpleNamespace:
    # Three independent, hand-specified paths: mean first cell=3, median=1.
    amounts = np.zeros((3, 2, 7), dtype=np.int64)
    amounts[:, 0, 0] = (0, 1, 8)
    amounts[:, 0, 2] = (0, 2, 4)
    pending = np.array([[1, 0], [2, 0], [3, 0]])
    return SimpleNamespace(
        dates=[date(2026, 9, 4), date(2026, 9, 5)],
        by_envelope=amounts,
        pending=pending,
        consumption=amounts.sum(axis=2) + pending,
    )


def test_daily_values_are_path_means_with_real_zero_days_and_pending_excluded() -> None:
    result = daily_forecast(samples(), 3)
    assert result.statistic == "empirical_path_mean"
    assert result.points[0].date == date(2026, 9, 4)
    assert result.points[0].amounts_krw == (3, 0, 2, 0, 0, 0, 0)
    assert result.points[1].date == date(2026, 9, 5)
    assert result.points[1].amounts_krw == (0,) * 7


@pytest.mark.parametrize("defect", ["shape", "negative", "nonfinite", "conservation"])
def test_invalid_simulations_are_rejected_instead_of_hiding_future_bars(defect: str) -> None:
    sim = samples()
    match defect:
        case "shape":
            sim.by_envelope = sim.by_envelope[:, :, :6]
        case "negative":
            sim.by_envelope[0, 0, 0] = -1
        case "nonfinite":
            sim.by_envelope = sim.by_envelope.astype(float)
            sim.by_envelope[0, 0, 0] = np.nan
        case "conservation":
            sim.consumption[0, 0] += 1
    with pytest.raises(ServiceError, match="chart_daily_") as caught:
        daily_forecast(sim, 3)
    assert caught.value.status == 502


def test_chart_uses_one_simulation_and_preserves_original_numeric_result() -> None:
    adapter = EngineAdapter()
    twin = adapter.create(fixture(), "demo")
    request = JsonDocument.model_validate({"mode": "forecast", "horizon_days": 21, "paths": 400, "seed": 42})
    original = adapter.numeric(twin, request)
    with patch.object(upstream, "simulate", wraps=upstream.simulate) as simulate:
        numeric, daily = adapter.chart_numeric(twin, request)
        assert simulate.call_count == 1
    assert numeric == original
    assert adapter.chart_numeric(twin, request) == (numeric, daily)
    assert len(daily.points) == 21
    assert daily.points[0].date == date(2026, 9, 10)
    assert daily.points[-1].date == date(2026, 9, 30)
