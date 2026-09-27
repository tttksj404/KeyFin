"""Point, interval and account-cluster paired errors for the same frozen target."""

import math
import random
from collections.abc import Sequence
from statistics import fmean
from typing import TypedDict

from .contracts import Prediction


class Metrics(TypedDict):
    count: int
    actual_sum: float
    mae_czk: float
    wape: float | None
    mean_bias_czk: float
    coverage80: float
    width_czk: float
    wis80: float


class Confidence(TypedDict):
    accounts: int
    bootstrap_repetitions: int
    seed: int
    paired_mae_difference_95: tuple[float, float]
    paired_wape_difference_95: tuple[float, float] | None


def score(actual: Sequence[float], rows: tuple[Prediction, ...]) -> Metrics:
    """Jointly report coverage and sharpness; an arbitrarily wide band cannot win silently."""
    if not len(actual) or len(actual) != len(rows):
        raise ValueError("Targets and forecasts must be nonempty and aligned")
    if any(not math.isfinite(value) or value < 0 for value in actual):
        raise ValueError("Targets must be finite nonnegative amounts")
    pairs = tuple(zip(rows, actual, strict=True))
    errors = tuple(row.point - value for row, value in pairs)
    absolute = tuple(abs(value) for value in errors)
    total = float(sum(actual))
    wis = tuple((0.5 * abs(row.point - value) + 0.1 * (
        row.upper - row.lower + 10 * (max(row.lower - value, 0) + max(value - row.upper, 0)))) / 1.5
        for row, value in pairs)
    return Metrics(count=len(rows), actual_sum=total, mae_czk=fmean(absolute),
                   wape=sum(absolute) / total if total else None, mean_bias_czk=fmean(errors),
                   coverage80=fmean(row.lower <= value <= row.upper for row, value in pairs),
                   width_czk=fmean(row.upper - row.lower for row in rows), wis80=fmean(wis))


def calibration_radius(scores: tuple[float, ...]) -> float:
    """Finite calibration rank; insufficient or invalid samples are not a zero radius."""
    if not scores or any(not math.isfinite(value) or value < 0 for value in scores):
        raise ValueError("Calibration scores must be finite nonnegative observations")
    rank = math.ceil((len(scores) + 1) * 0.8)
    if rank > len(scores):
        raise ValueError("Insufficient calibration observations")
    return sorted(scores)[rank - 1]


def expand(row: Prediction, reference: float, radius: float) -> Prediction:
    """Use an observed-only reference scale and the previously frozen point."""
    amount = max(row.point, reference, 1.0) * radius
    return row.model_copy(update={"lower": max(0.0, row.lower - amount), "upper": row.upper + amount})


def percentile(values: Sequence[float], probability: float) -> float:
    """Linearly interpolate a percentile, matching the standard empirical definition."""
    if not values or not 0 <= probability <= 1:
        raise ValueError("Invalid percentile inputs")
    ordered = sorted(values)
    rank = (len(ordered) - 1) * probability
    lower, upper = math.floor(rank), math.ceil(rank)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (rank - lower)


def paired_confidence(
    accounts: tuple[str, ...], actual: Sequence[float], selected: Sequence[float], baseline: Sequence[float],
) -> Confidence:
    """Re-sample whole accounts, retaining correlated dates within each account."""
    if not len(actual) or not (len(accounts) == len(actual) == len(selected) == len(baseline)):
        raise ValueError("Bootstrap rows must align")
    if any(not math.isfinite(value) for values in (actual, selected, baseline) for value in values):
        raise ValueError("Bootstrap rows must be finite")
    unique = sorted(set(accounts))
    groups: list[tuple[int, float, float]] = []
    for account in unique:
        indices = [i for i, value in enumerate(accounts) if value == account]
        error = sum(abs(selected[i] - actual[i]) - abs(baseline[i] - actual[i]) for i in indices)
        groups.append((len(indices), sum(actual[i] for i in indices), error))
    generator = random.Random(715)  # noqa: S311 -- reproducible bootstrap, no secret generation.
    maes: list[float] = []
    wapes: list[float] = []
    for _ in range(2000):
        draw = generator.choices(groups, k=len(groups))
        count, total, error = (sum(row[index] for row in draw) for index in range(3))
        maes.append(error / count)
        if total > 0:
            wapes.append(error / total)
    return Confidence(accounts=len(unique), bootstrap_repetitions=2000, seed=715,
                      paired_mae_difference_95=(percentile(maes, 0.025), percentile(maes, 0.975)),
                      paired_wape_difference_95=(percentile(wapes, 0.025), percentile(wapes, 0.975))
                      if len(wapes) == 2000 else None)
