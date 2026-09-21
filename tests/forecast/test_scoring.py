"""Closed-form score checks, separate from model forecasts."""

from datetime import date

import pytest

from benchmarks.forecast.contracts import Forecast, ForecastCase
from benchmarks.forecast.scoring import interval_score, radius, scale, summarize


def test_interval_score_penalizes_a_missed_lower_bound() -> None:
    # Given an 80% interval [100, 200] and actual spend 50.
    # When scoring its width and lower-tail miss.
    actual = interval_score(50, 100, 200)
    # Then width 100 plus 10 * miss 50 is 600.
    assert actual == 600


def test_wape_uses_total_spending_and_wis_rewards_sharp_correct_intervals() -> None:
    # Given two explicit forecasts with absolute errors 10 and 20.
    rows = [Forecast(case_id="a", model="closed", point=90, lower=80, upper=120),
            Forecast(case_id="b", model="closed", point=220, lower=180, upper=240)]
    # When scoring against literal outcomes.
    result = summarize(rows, {"a": 100.0, "b": 200.0})
    # Then WAPE is 30/300, not an average of arbitrary percent errors.
    assert result.wape == pytest.approx(0.1)
    assert result.coverage80 == 1
    assert result.wis == pytest.approx(((5 + 4)/1.5 + (10 + 6)/1.5)/2)


def test_calibration_uses_finite_sample_order_statistic() -> None:
    # Given nine scores in shuffled order.
    scores = [9.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
    # When taking ceil((n+1)*.8)-th order statistic.
    found = radius(scores)
    # Then the eighth score is used, without linear interpolation.
    assert found == 8


def test_scale_uses_history_only_and_a_floor_for_zero_consumption() -> None:
    # Given only observed zeros and a seven-day horizon.
    case = ForecastCase(case_id="zero", user="u", envelope="기타", split="development",
                        family="days7", first_date=date(2026, 7, 1), cutoff=date(2026, 7, 2),
                        end_date=date(2026, 7, 9), horizon=7, history=(0, 0))
    # When constructing the error scale from the case and point.
    found = scale(case, 0)
    # Then no future truth is needed and division remains defined.
    assert found == 1000
