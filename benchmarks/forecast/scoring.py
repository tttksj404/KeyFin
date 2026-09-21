"""Financial error and interval scores consume saved forecasts and separate truth."""

import math
from collections.abc import Mapping, Sequence
from statistics import mean

from .contracts import Forecast, ForecastCase, MetricSet


def interval_score(actual: float, lower: float, upper: float) -> float:
    return upper - lower + 10 * max(lower - actual, 0) + 10 * max(actual - upper, 0)


def scale(case: ForecastCase, point: float) -> float:
    return max(point, mean(case.history) * case.horizon, 1000)


def radius(scores: Sequence[float]) -> float:
    ordered = sorted(scores)
    return ordered[min(math.ceil((len(ordered) + 1) * 0.8), len(ordered)) - 1]


def summarize(rows: Sequence[Forecast], truth: Mapping[str, float]) -> MetricSet:
    actual = [truth[row.case_id] for row in rows]
    errors = [abs(row.point - y) for row, y in zip(rows, actual, strict=True)]
    intervals = [(row, y) for row, y in zip(rows, actual, strict=True)
                 if row.lower is not None and row.upper is not None]
    scores: list[float] = []
    widths: list[float] = []
    coverage: list[bool] = []
    for row, y in intervals:
        if row.lower is not None and row.upper is not None:
            scores.append((0.5 * abs(row.point - y) + 0.1 * interval_score(y, row.lower, row.upper))/1.5)
            widths.append(row.upper - row.lower)
            coverage.append(row.lower <= y <= row.upper)
    denominator = sum(actual)
    interval_actual = sum(y for _, y in intervals)
    return MetricSet(
        count=len(rows), actual_sum=denominator,
        wape=sum(errors)/denominator if denominator else None,
        mae=mean(errors), mean_bias=mean(row.point - y for row, y in zip(rows, actual, strict=True)),
        interval_count=len(intervals), coverage80=mean(coverage) if coverage else None,
        mean_width=mean(widths) if widths else None, wis=mean(scores) if scores else None,
        normalized_wis=sum(scores)/interval_actual if interval_actual else None,
    )


def expanded(row: Forecast, case: ForecastCase, correction: float) -> Forecast:
    lower = row.lower if row.lower is not None else row.point
    upper = row.upper if row.upper is not None else row.point
    adjustment = correction * scale(case, row.point)
    return row.model_copy(update={"lower": max(0, lower - adjustment), "upper": upper + adjustment})


def excess(row: Forecast, case: ForecastCase, actual: float) -> float:
    lower = row.lower if row.lower is not None else row.point
    upper = row.upper if row.upper is not None else row.point
    return max(lower - actual, actual - upper, 0) / scale(case, row.point)
