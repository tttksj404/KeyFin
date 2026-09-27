"""Frozen observed-only aggregate arithmetic candidates."""

from calendar import monthrange
from datetime import date, timedelta
from statistics import fmean, median
from typing import Final

from benchmarks.forecast.public_bank.baselines import BASELINES
from benchmarks.forecast.public_bank.baselines import predict as original_predict
from benchmarks.forecast.public_bank.contracts import Case as OriginalCase

from .contracts import Case, Prediction

EXTRA: Final = ("block_median", "block_trimmed", "monthly_rate_median",
                "calendar_median", "calendar_median_shrink")
NEURAL: Final = ("chronos_aggregate_base", "chronos_aggregate_ft128_lr1e6",
                 "chronos_aggregate_ft256_lr3e6")


def rolling_sums(values: tuple[float, ...], horizon: int) -> tuple[float, ...]:
    """Emit only complete trailing windows; no padding and no future data."""
    if horizon < 1 or horizon > len(values):
        raise ValueError("Invalid aggregation window")
    total = sum(values[:horizon])
    result = [total]
    for index in range(horizon, len(values)):
        total += values[index] - values[index - horizon]
        result.append(max(0.0, total))
    return tuple(result)


def shifted(day: date, months: int) -> date | None:
    """Missing February dates are absent, never duplicated onto month-end."""
    serial = day.year * 12 + day.month - 1 + months
    year, month = divmod(serial, 12)
    if day.day > monthrange(year, month + 1)[1]:
        return None
    return date(year, month + 1, day.day)


def seasonal_points(case: Case) -> tuple[float, float]:
    """Use at most six complete historical months and analogous calendar windows."""
    observed = {case.first_date + timedelta(days=i): value for i, value in enumerate(case.history)}
    first = case.cutoff.replace(day=1)
    is_complete = case.cutoff.day == monthrange(case.cutoff.year, case.cutoff.month)[1]
    complete_end = case.cutoff if is_complete else first - timedelta(days=1)
    rates: list[float] = []
    for offset in range(6):
        start = shifted(complete_end.replace(day=1), -offset)
        if start is None:
            raise ValueError("First day cannot be absent")
        days = monthrange(start.year, start.month)[1]
        if start >= case.first_date:
            rates.append(sum(observed[start + timedelta(days=i)] for i in range(days)) / days)
    future = [case.cutoff + timedelta(days=i) for i in range(1, case.horizon + 1)]
    analogous: list[float] = []
    for offset in range(1, 13):
        dates = {value for day in future if (value := shifted(day, -offset)) is not None}
        if dates and min(dates) >= case.first_date and max(dates) <= case.cutoff:
            analogous.append(sum(observed[day] for day in dates) * case.horizon / len(dates))
        if len(analogous) == 6:
            break
    if not rates or not analogous:
        raise ValueError("Observed history cannot support complete seasonal windows")
    return float(median(rates) * case.horizon), float(median(analogous))


def predict(case: Case) -> tuple[Prediction, ...]:
    """Keep the original six references unchanged and add five robust aggregate estimates."""
    compatible = OriginalCase.model_validate({**case.model_dump(), "split": "development"})
    original = original_predict(compatible)
    size = len(case.history)
    blocks = sorted(sum(case.history[size - offset - case.horizon:size - offset])
                    for offset in range(0, size - case.horizon + 1, case.horizon))
    trim = int(len(blocks) * 0.2)
    middle = blocks[trim:len(blocks) - trim]
    rate, calendar = seasonal_points(case)
    recent90 = next(row.point for row in original if row.model == "recent90")
    points = (float(median(blocks)), fmean(middle), rate, calendar,
              (calendar + recent90) / 2)
    rows = [Prediction(case_id=row.case_id, model=row.model,
                       point=row.point, lower=row.point, upper=row.point)
            for row in original]
    rows.extend(Prediction(case_id=case.case_id, model=name, point=value, lower=value, upper=value)
                for name, value in zip(EXTRA, points, strict=True))
    if {row.model for row in rows} != set(BASELINES + EXTRA):
        raise ValueError("Incomplete frozen arithmetic candidates")
    return tuple(rows)
