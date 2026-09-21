# ruff: noqa: INP001
"""제품의 FDT 분류기를 가져오지 않고 손계산 기대값으로 월 정답을 시험한다."""

from datetime import date

import pytest
from pydantic import ValidationError
from test_forecast_validation_month_support import plan_body
from test_forecast_validation_observations import raw

from coaching_service.errors import ServiceError
from coaching_service.forecast_validation_month_contracts import MonthlyBudgetRequest, month_end
from coaching_service.forecast_validation_month_observations import observed_envelopes, window_digest


def test_hand_calculated_consumption_and_budget_targets_treat_cancellation_and_returns_separately() -> None:
    rows = (
        raw(transaction_id="purchase", amount_krw=50000),
        raw(transaction_id="bill", amount_krw=50000, transaction_type="CARD_SETTLEMENT"),
        raw(transaction_id="canceled", amount_krw=8000, status="CANCELED"),
        raw(transaction_id="return", amount_krw=8000, transaction_type="DEPOSIT", subcategory="환불"),
        raw(transaction_id="dutch", amount_krw=3000, exclude_tag="DUTCH"),
        raw(transaction_id="rent", amount_krw=90000, subcategory="월세"),
        raw(transaction_id="before", amount_krw=1000, transaction_date="2026-08-31"),
        raw(transaction_id="after", amount_krw=2000, transaction_date="2026-10-01"),
    )
    result = observed_envelopes(rows, date(2026, 9, 1), date(2026, 9, 30))
    assert result[0].consumption_krw == 53000
    assert result[0].budget_used_krw == 50000
    assert result[0].consumption_count == 2
    assert sum(row.consumption_krw for row in result[1:]) == 0


def test_pending_is_unknown_instead_of_zero_even_when_budget_excluded() -> None:
    with pytest.raises(ServiceError, match="validation_unresolved_transactions"):
        observed_envelopes((raw(confirm_status="PENDING", exclude_tag="EMERGENCY"),),
                           date(2026, 9, 1), date(2026, 9, 30))


def test_same_total_reclassification_changes_month_digest() -> None:
    food = raw(transaction_id="same", amount_krw=5000)
    transport = raw(transaction_id="same", amount_krw=5000, subcategory="택시")
    start, end = date(2026, 9, 1), date(2026, 9, 30)
    assert window_digest((food,), start, end) != window_digest((transport,), start, end)
    assert observed_envelopes((food,), start, end)[0].consumption_krw == 5000
    assert observed_envelopes((transport,), start, end)[1].consumption_krw == 5000


@pytest.mark.parametrize(("day", "expected"), [
    (date(2028, 2, 1), date(2028, 2, 29)), (date(2027, 2, 1), date(2027, 2, 28)),
    (date(2026, 12, 1), date(2026, 12, 31)),
])
def test_month_plan_uses_the_actual_calendar_end(day: date, expected: date) -> None:
    assert month_end(day) == expected


@pytest.mark.parametrize("amount", [-1, True, 1.5, "100", 10**12 + 1])
def test_original_budget_rejects_invalid_money(amount: object) -> None:
    body = plan_body()
    allocations = body["allocations"]
    assert isinstance(allocations, list)
    body["allocations"] = [{**allocations[0], "original_budget_krw": amount}, *allocations[1:]]
    with pytest.raises(ValidationError):
        MonthlyBudgetRequest.model_validate(body)


def test_plan_requires_all_seven_distinct_envelopes_and_actual_month_start() -> None:
    body = plan_body()
    allocations = body["allocations"]
    assert isinstance(allocations, list)
    for patch in ({"allocations": allocations[:-1]}, {"allocations": [allocations[0]] * 7},
                  {"month_start": "2026-09-02"}):
        with pytest.raises(ValidationError):
            MonthlyBudgetRequest.model_validate({**body, **patch})


@pytest.mark.parametrize("stamp", [True, "1788166800", float("nan"), float("inf"), -1])
def test_approval_timestamp_is_a_finite_number_and_never_a_boolean(stamp: object) -> None:
    with pytest.raises(ValidationError):
        MonthlyBudgetRequest.model_validate({**plan_body(), "approved_at": stamp})
