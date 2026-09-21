"""Account-cluster uncertainty, with paired comparisons on the same accounts."""

from dataclasses import dataclass
from typing import TypeAlias

import numpy as np
from numpy.typing import NDArray

from .contracts import Frozen

Array: TypeAlias = NDArray[np.float64]


class Metrics(Frozen):
    count: int
    actual_sum: float
    mae_czk: float
    wape: float | None
    mean_bias_czk: float


class Confidence(Frozen):
    accounts: int
    bootstrap_repetitions: int = 2000
    seed: int = 712
    mae_czk_95: tuple[float, float]
    wape_95: tuple[float, float] | None
    mean_bias_czk_95: tuple[float, float]
    paired_wape_difference_95: tuple[float, float] | None


@dataclass(frozen=True, slots=True)
class Sample:
    accounts: tuple[str, ...]
    actual: Array
    predicted: Array
    baseline: Array


def metrics(actual: Array, predicted: Array) -> Metrics:
    if len(actual) == 0 or actual.shape != predicted.shape:
        raise ValueError("Metric arrays must be nonempty and aligned")
    if not np.isfinite(actual).all() or not np.isfinite(predicted).all():
        raise ValueError("Metric arrays must contain finite values")
    errors = predicted - actual
    total = float(actual.sum())
    return Metrics(count=len(actual), actual_sum=total, mae_czk=float(np.abs(errors).mean()),
                   wape=float(np.abs(errors).sum() / total) if total else None,
                   mean_bias_czk=float(errors.mean()))


def interval(values: Array) -> tuple[float, float]:
    lower, upper = np.quantile(values, [0.025, 0.975])
    return float(lower), float(upper)


def confidence(sample: Sample) -> Confidence:
    """Resample accounts, retaining every observed forecast date for each account."""
    if len(sample.accounts) != len(sample.actual):
        raise ValueError("Bootstrap account labels are misaligned")
    accounts = sorted(set(sample.accounts))
    rows = []
    for account in accounts:
        mask = np.asarray([key == account for key in sample.accounts])
        actual = sample.actual[mask]
        errors = sample.predicted[mask] - actual
        reference = sample.baseline[mask] - actual
        rows.append((mask.sum(), actual.sum(), np.abs(errors).sum(), errors.sum(), np.abs(reference).sum()))
    grouped = np.asarray(rows, dtype=np.float64)
    random = np.random.default_rng(712)
    indices = random.integers(0, len(accounts), size=(2000, len(accounts)))
    draws = grouped[indices].sum(axis=1)
    nonzero = draws[:, 1] > 0
    wape = interval(draws[:, 2] / draws[:, 1]) if nonzero.all() else None
    difference = interval((draws[:, 2] - draws[:, 4]) / draws[:, 1]) if nonzero.all() else None
    return Confidence(accounts=len(accounts), mae_czk_95=interval(draws[:, 2] / draws[:, 0]),
                      wape_95=wape, mean_bias_czk_95=interval(draws[:, 3] / draws[:, 0]),
                      paired_wape_difference_95=difference)
