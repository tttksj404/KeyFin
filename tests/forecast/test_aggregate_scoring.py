"""Selection and calibration tests intentionally reverse the holdout ordering."""

import numpy as np
import pytest

from benchmarks.forecast.aggregate import scoring
from benchmarks.forecast.aggregate.contracts import Prediction


def row(point: float, lower: float = 0, upper: float = 0) -> Prediction:
    return Prediction(case_id="case", model="candidate", point=point,
                      lower=lower or point, upper=upper or point)


def test_wis_penalizes_wide_intervals_even_when_coverage_is_perfect() -> None:
    # Given: both intervals contain the actual amount with an identical point forecast.
    actual = np.asarray([100.0])
    # When: score a narrow and a much wider interval.
    narrow = scoring.score(actual, (row(100, 90, 110),))
    wide = scoring.score(actual, (row(100, 10, 190),))
    # Then: reporting coverage alone would conceal the inferior wide interval.
    assert narrow["coverage80"] == wide["coverage80"] == 1.0
    assert narrow["wis80"] == pytest.approx(2.0 / 1.5)
    assert wide["wis80"] > narrow["wis80"]


def test_calibration_uses_finite_sample_order_statistic_not_interpolated_quantile() -> None:
    # Given: four calibration scores; ceil((4+1)*.8) selects the largest, not 80% interpolation.
    # When: compute the frozen 80% calibration rank.
    radius = scoring.calibration_radius((0.0, 1.0, 2.0, 9.0))
    # Then: the radius is the observed fourth score.
    assert radius == 9.0


def test_zero_actual_outflow_keeps_wape_undefined() -> None:
    # Given/When: no actual outflow, but a positive forecast.
    result = scoring.score(np.asarray([0.0]), (row(10),))
    # Then: this is an error and not a 100% accuracy score.
    assert result["wape"] is None
    assert result["mae_czk"] == 10.0


def test_empty_or_nonfinite_targets_cannot_report_success() -> None:
    # Given/When/Then: missing or invalid observations are not zero-valued observations.
    with pytest.raises(ValueError, match="nonempty"):
        scoring.score(np.asarray([]), ())
    with pytest.raises(ValueError, match="finite"):
        scoring.score(np.asarray([float("nan")]), (row(10),))
