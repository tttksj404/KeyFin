from datetime import date

import pytest

from benchmarks.forecast.contracts import Forecast, ForecastCase
from benchmarks.forecast.scoring import summarize
from benchmarks.forecast.selection import calibrate, choose


def test_selection_uses_development_error_and_respects_both_baselines() -> None:
    truth = {"july": 100.0}
    candidates = {name: [Forecast(case_id="july", model=name, point=point)]
                  for name, point in (("fdt", 120), ("all_mean", 110), ("candidate", 101))}
    assert choose(candidates, truth) == "candidate"


def test_calibration_records_only_provided_development_cases() -> None:
    case = ForecastCase(case_id="july", user="other", envelope="food", split="development",
                        family="days7", first_date=date(2026, 6, 30), cutoff=date(2026, 7, 1),
                        end_date=date(2026, 7, 8), horizon=7, history=(100.0, 100.0))
    row = Forecast(case_id="july", model="all_mean", point=700)
    result = calibrate("heldout", "days7", [row], {"july": case}, {"july": 1400})
    assert result.score_case_ids == ("july",)
    assert result.radius == 0.7


@pytest.mark.parametrize(("candidate_point", "expected"), [(0, "candidate"), (3, "all_mean")])
def test_zero_actual_selection_uses_mae_and_both_baseline_ceilings(
    candidate_point: int, expected: str,
) -> None:
    # Given nonempty zero-spending outcomes and forecasts with different absolute errors.
    truth = {"zero": 0.0}
    candidates = {name: [Forecast(case_id="zero", model=name, point=point)]
                  for name, point in (("fdt", 2), ("all_mean", 1), ("candidate", candidate_point))}
    # When selecting with undefined WAPE.
    selected = choose(candidates, truth)
    # Then MAE chooses a candidate only if it clears both baselines; WAPE stays unavailable.
    assert selected == expected
    assert all(summarize(rows, truth).wape is None for rows in candidates.values())


@pytest.mark.parametrize("candidates", [{}, {"fdt": [], "all_mean": []}])
def test_selection_rejects_empty_inputs_explicitly(candidates: dict[str, list[Forecast]]) -> None:
    # Given no usable prediction rows.
    # When model selection is requested.
    # Then a boundary error explains the missing data before summary arithmetic runs.
    with pytest.raises(ValueError, match="nonempty"):
        choose(candidates, {})
