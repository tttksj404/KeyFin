"""Pure forecast conversion; daily marginal quantiles never become aggregate intervals."""

from collections.abc import Sequence

import numpy as np
from numpy.typing import NDArray

from .contracts import Forecast, ForecastCase, Series


def contexts(cases: Sequence[ForecastCase], *, cumulative: bool) -> list[NDArray[np.float32]]:
    values = [np.asarray(case.history, dtype=np.float32) for case in cases]
    return [np.cumsum(value) for value in values] if cumulative else values


def training_inputs(series: Sequence[Series], excluded_user: str) -> list[NDArray[np.float32]]:
    return [np.cumsum(np.asarray(row.daily, dtype=np.float32)) for row in series if row.user != excluded_user]


def endpoint(case: ForecastCase, quantiles: NDArray[np.float64], model: str, fold: str) -> Forecast:
    # Three marginal quantiles at one cumulative endpoint are a distribution for the same total.
    values = np.maximum(np.sort(quantiles) - sum(case.history), 0)
    return Forecast(case_id=case.case_id, model=model, fold=fold,
                    lower=float(values[0]), point=float(values[1]), upper=float(values[2]))
