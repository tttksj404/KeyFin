"""Six frozen, observed-only account-outflow reference models."""

from collections import defaultdict
from datetime import timedelta
from statistics import fmean
from typing import Final

from .contracts import Case, Prediction

BASELINES: Final = (
    "recent28", "recent90", "recent365", "weekday_shrink", "calendar_day", "calendar_shrink",
)


def predict(case: Case) -> tuple[Prediction, ...]:
    values = case.history
    weekdays: defaultdict[int, list[float]] = defaultdict(list)
    monthdays: defaultdict[int, list[float]] = defaultdict(list)
    for index, value in enumerate(values):
        day = case.first_date + timedelta(days=index)
        weekdays[day.weekday()].append(value)
        monthdays[day.day].append(value)
    mean = fmean(values)
    recent = fmean(values[-90:])
    future = [case.cutoff + timedelta(days=offset) for offset in range(1, case.horizon + 1)]
    points = [fmean(values[-window:]) * case.horizon for window in (28, 90, 365)]
    points.append(sum((fmean(weekdays[day.weekday()]) + mean) / 2 for day in future))
    calendar = sum(fmean(monthdays[day.day]) for day in future)
    points.extend((calendar, (calendar + recent * case.horizon) / 2))
    return tuple(Prediction(case_id=case.case_id, model=name, point=point)
                 for name, point in zip(BASELINES, points, strict=True))
