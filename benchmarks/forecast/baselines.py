"""Fixed arithmetic candidates with no fitted future outcomes."""

from datetime import timedelta
from statistics import mean

from .contracts import Forecast, ForecastCase


def predict(case: ForecastCase) -> tuple[Forecast, ...]:
    overall = mean(case.history)
    recent = mean(case.history[-28:])
    by_weekday = [tuple(value for offset, value in enumerate(case.history)
                        if (case.first_date + timedelta(days=offset)).weekday() == weekday)
                  for weekday in range(7)]
    weekday_mean = [mean(values) if values else overall for values in by_weekday]
    seasonal = sum((overall + weekday_mean[(case.cutoff + timedelta(days=i)).weekday()])/2
                   for i in range(1, case.horizon + 1))
    return tuple(Forecast(case_id=case.case_id, model=name, point=point) for name, point in (
        ("all_mean", overall * case.horizon), ("recent28", recent * case.horizon),
        ("weekday_shrink", seasonal),
    ))
