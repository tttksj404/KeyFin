"""Aggregation and user isolation oracles independent of neural implementations."""

from datetime import date

import numpy as np

from benchmarks.forecast.contracts import ForecastCase, Series
from benchmarks.forecast.neural_io import endpoint, training_inputs


def test_cumulative_endpoint_subtracts_observed_spending_once() -> None:
    # Given observed cumulative spending 30 and future endpoint quantiles [35, 45, 60].
    case = ForecastCase(case_id="case", user="u", envelope="기타", split="evaluation",
                        family="days7", first_date=date(2026, 7, 1), cutoff=date(2026, 7, 2),
                        end_date=date(2026, 7, 9), horizon=7, history=(10, 20))
    # When converting the single cumulative endpoint.
    result = endpoint(case, np.asarray([35.0, 45.0, 60.0]), "oracle", "u")
    # Then future total quantiles are [5, 15, 30], with no daily-quantile summation.
    assert (result.lower, result.point, result.upper) == (5, 15, 30)


def test_training_never_includes_the_excluded_user() -> None:
    # Given distinctive amounts for the training and excluded user.
    series = [Series(user=name, envelope="기타", first_date=date(2026, 6, 1),
                     last_date=date(2026, 6, 2), daily=amounts)
              for name, amounts in (("train", (1, 2)), ("excluded", (90, 900)))]
    # When the fold selects only non-target users.
    selected = training_inputs(series, "excluded")
    # Then the cumulative training array contains only the training user's [1, 3].
    assert len(selected) == 1
    assert selected[0].tolist() == [1, 3]
