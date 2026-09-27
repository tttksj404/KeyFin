"""Leakage and period boundaries use controlled raw transactions."""

from datetime import date

from benchmarks.forecast.data import build_cases, observed_series

from .fixtures import daily_rows


def test_future_spike_changes_truth_but_never_model_history() -> None:
    # Given fixed observed spending and one later, unusually large purchase.
    rows = daily_rows(date(2026, 9, 3), days=90)
    changed = tuple(row.model_copy(update={"amount_krw": 9_000_000})
                    if row.transaction_date == date(2026, 8, 2) else row for row in rows)
    # When creating the first August forecast from either ledger.
    cases, truth = build_cases(rows, "evaluation")
    modified, later_truth = build_cases(changed, "evaluation")
    earlier = [case for case in cases if case.cutoff == date(2026, 8, 1)]
    later = [case for case in modified if case.cutoff == date(2026, 8, 1)]
    # Then the model inputs are identical while the separate outcomes differ.
    assert earlier == later
    assert truth != later_truth


def test_month_end_uses_observed_close_and_includes_last_future_day() -> None:
    # Given one thousand won spending every day across August.
    rows = daily_rows(date(2026, 9, 3), days=90)
    # When selecting the August 15 month-end forecast.
    cases, truth = build_cases(rows, "evaluation")
    case = next(case for case in cases if case.cutoff == date(2026, 8, 15)
                and case.family == "month_end" and case.envelope == "외식")
    outcome = next(item for item in truth if item.case_id == case.case_id)
    # Then August 16..31 contributes sixteen thousand won.
    assert case.horizon == 16
    assert case.end_date == date(2026, 8, 31)
    assert outcome.actual == 16_000


def test_training_array_ends_at_its_declared_cutoff() -> None:
    # Given transactions extending after the training cutoff.
    rows = daily_rows(date(2026, 9, 3), days=90)
    # When creating training input for June 30.
    values = observed_series(rows, date(2026, 6, 30))
    # Then the explicit last date and array length agree with only the past.
    assert all(value.last_date == date(2026, 6, 30) for value in values)
    assert all(len(value.daily) == (value.last_date-value.first_date).days+1 for value in values)


def test_budget_excluded_purchase_remains_in_history_and_future_consumption_truth() -> None:
    # Given a normal purchase that is excluded only from the monthly budget balance.
    rows = daily_rows(date(2026, 9, 3), days=90)
    tagged = tuple(
        row.model_copy(update={"amount_krw": 2_000, "exclude_tag": "DUTCH"})
        if row.transaction_date == date(2026, 8, 1)
        else row.model_copy(update={"amount_krw": 3_000, "exclude_tag": "DUTCH"})
        if row.transaction_date == date(2026, 8, 2)
        else row
        for row in rows
    )

    # When the August 1 forecast treats August 1 as observed and August 2 onward as truth.
    history = next(
        series for series in observed_series(tagged, date(2026, 8, 1)) if series.envelope == "외식"
    )
    _, truth = build_cases(tagged, "evaluation")
    outcome = next(row for row in truth if row.case_id.endswith("/2026-08-01/days7/외식"))

    # Then both purchases are total variable consumption, even though neither is budget usage.
    assert history.daily[-1] == 2_000
    assert outcome.actual == 9_000
