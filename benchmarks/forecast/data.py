"""Observed-only model inputs and independently aggregated future outcome files."""

from datetime import date, timedelta
from typing import Final, assert_never

from coaching_service.periods import MonthEnd, RollingDays, ThroughDate, resolve_period

from benchmarks.forecast.ledger_adapter.contracts import LedgerRow
from benchmarks.forecast.ledger_adapter.ledger import ENVELOPES, envelope

from .contracts import Family, ForecastCase, Series, Split, Truth
from .truth import settled_consumption_envelope

FAMILIES: Final[tuple[Family, ...]] = ("days7", "target14", "days30", "month_end")
TRAINING_END: Final = date(2026, 6, 30)


def observed_series(rows: tuple[LedgerRow, ...], cutoff: date) -> tuple[Series, ...]:
    observed = tuple(row for row in rows if row.transaction_date <= cutoff)
    start = min(row.transaction_date for row in observed)
    dates = tuple(start + timedelta(days=i) for i in range((cutoff - start).days + 1))
    totals = {name: dict.fromkeys(dates, 0.0) for name in ENVELOPES}
    for row in observed:
        name = envelope(row)
        # FDT learns total variable consumption.  Budget exclusion tags change
        # envelope-balance usage, not the purchase-time consumption target.
        if name is not None:
            totals[name][row.transaction_date] += row.amount_krw
    return tuple(Series(user=observed[0].user_id, envelope=name, first_date=start,
                        last_date=cutoff, daily=tuple(totals[name][day] for day in dates))
                 for name in ENVELOPES)


def end_for(cutoff: date, family: Family) -> date:
    match family:
        case "days7":
            spec = RollingDays(days=7)
        case "days30":
            spec = RollingDays(days=30)
        case "target14":
            spec = ThroughDate(end_date=cutoff + timedelta(days=14))
        case "month_end":
            spec = MonthEnd()
        case unreachable:
            assert_never(unreachable)
    return resolve_period(cutoff, spec, "request").forecast_end


def build_cases(
    rows: tuple[LedgerRow, ...], split: Split,
) -> tuple[tuple[ForecastCase, ...], tuple[Truth, ...]]:
    match split:
        case "development":
            month, limit = 7, date(2026, 7, 31)
        case "evaluation":
            month, limit = 8, max(row.transaction_date for row in rows)
        case unreachable:
            assert_never(unreachable)
    cases, outcomes = [], []
    for day in (1, 8, 15, 22):
        cutoff = date(2026, month, day)
        histories = observed_series(rows, cutoff)
        for family in FAMILIES:
            end = end_for(cutoff, family)
            if end > limit:
                continue
            for series in histories:
                identifier = f"{series.user}/{cutoff}/{family}/{series.envelope}"
                cases.append(ForecastCase(
                    case_id=identifier, user=series.user, envelope=series.envelope, split=split,
                    family=family, first_date=series.first_date, cutoff=cutoff, end_date=end,
                    horizon=(end-cutoff).days, history=series.daily,
                ))
                # Future truth uses the separately implemented settled-outcome
                # calculator, so the model's FDT classifier cannot define its
                # own answer key.
                total = sum(
                    row.amount_krw for row in rows
                    if cutoff < row.transaction_date <= end
                    and settled_consumption_envelope(row) == series.envelope
                )
                outcomes.append(Truth(case_id=identifier, actual=total))
    return tuple(cases), tuple(outcomes)
