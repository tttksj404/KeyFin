# ruff: noqa: INP001
"""Hand-specified calendar oracles; no FDT or AI decides expected dates."""

from datetime import UTC, date, datetime, timedelta

import pytest
from pydantic import ValidationError

from coaching_service.errors import ServiceError
from coaching_service.period_request import turn_period
from coaching_service.periods import MonthEnd, NextMonthEnd, RollingDays, ThroughDate, resolve_period
from coaching_service.schemas import JsonDocument, TurnRequest


@pytest.mark.parametrize(
    ("reference", "days", "inclusive", "end", "future_days"),
    [
        ("2026-09-10", 30, False, "2026-10-10", 30),
        ("2026-09-10", 30, True, "2026-10-09", 29),
        ("2028-02-28", 2, False, "2028-03-01", 2),
        ("2028-02-28", 2, True, "2028-02-29", 1),
        ("2027-02-28", 1, False, "2027-03-01", 1),
        ("2026-12-31", 30, False, "2027-01-30", 30),
        ("2026-09-10", 90, False, "2026-12-09", 90),
    ],
)
def test_inclusion_changes_forecast_count_without_repeating_observed_day(
    reference: str, days: int, inclusive: bool, end: str, future_days: int
) -> None:
    period = resolve_period(
        date.fromisoformat(reference), RollingDays(days=days, include_reference_date=inclusive), "request"
    )
    assert period.forecast_end.isoformat() == end
    assert period.forecast_days == future_days
    assert period.window_calendar_days == days
    assert period.reference_in_window == inclusive


@pytest.mark.parametrize(
    ("reference", "end", "future_days", "month_days"),
    [
        ("2026-01-01", "2026-01-31", 30, 31),
        ("2027-02-01", "2027-02-28", 27, 28),
        ("2028-02-01", "2028-02-29", 28, 29),
        ("2026-04-01", "2026-04-30", 29, 30),
        ("2026-09-10", "2026-09-30", 20, 30),
        ("2026-12-20", "2026-12-31", 11, 31),
        ("1900-02-27", "1900-02-28", 1, 28),
        ("2000-02-28", "2000-02-29", 1, 29),
    ],
)
def test_calendar_month_and_unobserved_remainder_are_different(
    reference: str, end: str, future_days: int, month_days: int
) -> None:
    period = resolve_period(date.fromisoformat(reference), MonthEnd(), "request")
    assert period.forecast_end.isoformat() == end
    assert period.forecast_days == future_days
    assert period.window_calendar_days == month_days
    assert period.window_start.day == 1
    assert period.budget_future_coverage_complete


def test_all_4800_months_of_gregorian_cycle_against_arithmetic_oracle() -> None:
    lengths = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
    for year in range(2000, 2400):
        leap = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
        for month, ordinary_days in enumerate(lengths, 1):
            expected = ordinary_days + int(month == 2 and leap)
            period = resolve_period(date(year, month, 1), MonthEnd(), "request")
            assert period.window_end == date(year, month, expected)
            assert period.window_calendar_days == expected
            assert period.forecast_days == expected - 1


@pytest.mark.parametrize(
    ("reference", "window_start", "end", "future_days", "window_days"),
    [
        ("2026-09-10", "2026-10-01", "2026-10-31", 51, 31),
        ("2026-12-20", "2027-01-01", "2027-01-31", 42, 31),
        ("2028-01-30", "2028-02-01", "2028-02-29", 30, 29),
    ],
)
def test_next_calendar_month_end_keeps_requested_window_separate_from_forecast_span(
    reference: str, window_start: str, end: str, future_days: int, window_days: int
) -> None:
    """Next-month wording requests a calendar month, while simulation starts after day close."""
    period = resolve_period(date.fromisoformat(reference), NextMonthEnd(), "question")
    assert period.kind == "next_month_end"
    assert period.window_start.isoformat() == window_start
    assert period.window_end.isoformat() == end
    assert period.forecast_start == date.fromisoformat(reference) + timedelta(days=1)
    assert period.forecast_end.isoformat() == end
    assert period.forecast_days == future_days
    assert period.window_calendar_days == window_days
    assert not period.reference_in_window


@pytest.mark.parametrize(
    ("reference", "end", "code"),
    [
        ("2026-09-10", "2026-09-09", "period_ends_before_reference"),
        ("2026-09-10", "2026-09-10", "period_has_no_future_days"),
        ("2026-09-10", "2026-12-10", "period_exceeds_90_future_days"),
        ("9999-12-31", "9999-12-31", "period_date_out_of_range"),
    ],
)
def test_invalid_future_windows_fail_without_clipping(reference: str, end: str, code: str) -> None:
    with pytest.raises(ServiceError, match=code):
        resolve_period(
            date.fromisoformat(reference), ThroughDate(end_date=date.fromisoformat(end)), "request"
        )


def test_closed_month_and_one_inclusive_day_do_not_invent_tomorrow() -> None:
    for spec in (MonthEnd(), RollingDays(days=1, include_reference_date=True)):
        with pytest.raises(ServiceError, match="period_has_no_future_days"):
            resolve_period(date(2028, 2, 29), spec, "request")


@pytest.mark.parametrize("end", ["2027-02-29", "2028-02-30", "2028-02-29T00:00:00+09:00", "20280229", 0])
def test_target_requires_iso_date_without_timestamp_coercion(end: str | int) -> None:
    with pytest.raises(ValidationError, match="date_only"):
        ThroughDate.model_validate({"end_date": end})


def test_datetime_is_not_silently_converted_to_local_calendar_date() -> None:
    with pytest.raises(ValidationError, match="date_only"):
        ThroughDate.model_validate({"end_date": datetime(2028, 2, 28, 15, tzinfo=UTC)})


@pytest.mark.parametrize(
    ("question", "days"),
    [
        ("앞으로 30일 예측해줘", 30), ("30일 뒤 잔액", 30), ("기준일부터 30일 예측", 29),
        ("기준일 포함 30일 예측", 29), ("이번 달 예산", 20), ("2026-10-10까지 예측", 30),
        # A period-less question follows the budget cycle (same as "이번 달"), so the
        # answer's period matches the chart, which always draws the budget month.
        ("이전 코칭을 설명해줘", 20),
        ("30일 뒤 잔액이 10만원 이상일지 예측", 30),
        ("30일 뒤 전망해줘", 30), ("이번 달 초과 위험", 20),
    ],
)
def test_question_period_is_grounded_before_model_call(question: str, days: int) -> None:
    assert turn_period(date(2026, 9, 10), question, None, None).forecast_days == days


def test_period_less_default_follows_budget_cycle_and_its_start_day() -> None:
    # "예산 위험해?" names no period: it covers the rest of the budget cycle.
    resolved = turn_period(date(2026, 9, 22), "예산 위험해?", None, None)
    assert (resolved.source, resolved.kind) == ("default", "month_end")
    assert (resolved.forecast_start, resolved.forecast_end) == (date(2026, 9, 23), date(2026, 9, 30))
    # A custom budget start day moves the cycle end with it (cycle 9/15 to 10/14).
    custom = turn_period(date(2026, 9, 22), "예산 위험해?", None, None, budget_start_day=15)
    assert custom.forecast_end == date(2026, 10, 14)


def test_period_less_default_on_cycle_last_day_keeps_seven_days() -> None:
    # On the cycle's last day the budget month has no future day (422), so the
    # period-less default falls back to the 7-day rolling window instead.
    resolved = turn_period(date(2026, 9, 30), "예산 위험해?", None, None)
    assert (resolved.source, resolved.kind, resolved.forecast_days) == ("default", "rolling_days", 7)


def test_question_period_distinguishes_current_and_next_calendar_months() -> None:
    reference = date(2026, 9, 10)
    current = turn_period(reference, "이번 달 말에 잔액을 예측해줘", None, None)
    next_month = turn_period(reference, "다음 달 잔액을 예측해줘", None, None)

    assert (current.kind, current.window_end.isoformat(), current.forecast_days) == (
        "month_end", "2026-09-30", 20,
    )
    assert (next_month.kind, next_month.window_start.isoformat(), next_month.window_end.isoformat()) == (
        "next_month_end", "2026-10-01", "2026-10-31",
    )
    assert next_month.forecast_days == 51


@pytest.mark.parametrize(
    "question",
    [
        "한 달 뒤", "1개월 뒤", "다음 주 예산", "목표일까지", "9월 30일까지", "30일에 결제해",
        "30일 뒤 말고 90일 뒤", "30일 이내", "-30일 뒤", "1.5일 뒤", "1000일 뒤", "30영업일 뒤",
        "음력 윤달 말까지", "2026-09-11부터 2026-10-10까지", "30일 전", "30일 이후", "91일 뒤",
        "이번 달 초 잔액", "이번 달 중순 잔액", "이틀 뒤", "열흘 뒤", "올해 말까지",
    ],
)
def test_unsupported_or_ambiguous_question_never_silently_defaults(question: str) -> None:
    with pytest.raises(ServiceError):
        turn_period(date(2026, 9, 10), question, None, None)


def test_explicit_period_and_numeric_horizon_must_agree() -> None:
    request = TurnRequest.model_validate(
        {"question": "목표일까지 예측", "period": {"kind": "through_date", "end_date": "2026-10-10"}}
    )
    assert turn_period(date(2026, 9, 10), request.question, request.period, None).forecast_days == 30
    for question, analysis in [
        ("90일 뒤 예측", None),
        ("예측", JsonDocument({"mode": "forecast", "horizon_days": 7})),
    ]:
        with pytest.raises(ServiceError, match="period_conflict"):
            turn_period(date(2026, 9, 10), question, RollingDays(days=30), analysis)


def test_legacy_numeric_horizon_default_remains_90_and_is_disclosed() -> None:
    period = turn_period(date(2026, 9, 10), "예측", None, JsonDocument({"mode": "forecast"}))
    assert period.forecast_days == 90
    assert period.source == "analysis"
