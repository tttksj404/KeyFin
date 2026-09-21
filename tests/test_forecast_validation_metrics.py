# ruff: noqa: INP001
"""Small arithmetic oracles; expected answers never call the product calculator."""

import pytest
from pydantic import ValidationError

from coaching_service.forecast_validation_contracts import Quantiles
from coaching_service.forecast_validation_metrics import calculate_metrics


def test_metrics_match_independent_hand_calculation() -> None:
    # Given: errors -40 and +10, and one observation above the 80% interval.
    forecasts = (Quantiles(p10=40, p50=60, p90=80), Quantiles(p10=40, p50=60, p90=80))
    # When: compare the frozen distributions with actual totals 100 and 50.
    metrics = calculate_metrics(forecasts, (100, 50), (70.0, 70.0))
    # Then: interval scores are 240 and 40; WIS are 44/1.5 and 9/1.5.
    assert metrics.sample_count == 2
    assert metrics.mae_krw == 25
    assert metrics.bias_krw == -15
    assert metrics.wape == pytest.approx(1 / 3)
    assert metrics.wis80_krw == pytest.approx(53 / 3)
    assert metrics.coverage80 == 0.5
    assert metrics.mean_interval_width_krw == 40
    assert metrics.baseline_mae_krw == 25
    assert metrics.baseline_bias_krw == -5


def test_zero_actual_does_not_produce_a_percentage() -> None:
    # Given / When: a fully observed zero-spend interval is a valid outcome.
    result = calculate_metrics((Quantiles(p10=0, p50=10, p90=20),), (0,), (5.0,))
    # Then: the denominator remains explicitly unavailable.
    assert result.wape is None
    assert result.baseline_wape is None
    assert result.mae_krw == 10
    assert result.coverage80 == 1


def test_missing_samples_are_rejected() -> None:
    # Given / When / Then: absence is never a perfect zero-error evaluation.
    with pytest.raises(ValueError, match="nonempty_aligned_samples"):
        calculate_metrics((), (), ())


@pytest.mark.parametrize("values", [(20, 10, 30), (-1, 0, 1), (0, 1, float("inf"))])
def test_invalid_quantiles_are_rejected(values: tuple[float, float, float]) -> None:
    # Given / When / Then: unordered, negative and nonfinite money cannot be frozen.
    with pytest.raises(ValidationError):
        Quantiles(p10=values[0], p50=values[1], p90=values[2])
