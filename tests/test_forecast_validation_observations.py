# ruff: noqa: INP001
"""Raw-field accounting checks do not import FDT's normalization or simulation."""

from datetime import date

import pytest
from pydantic import ValidationError

from coaching_service.errors import ServiceError
from coaching_service.forecast_validation_observations import (
    RawTransaction,
    baseline_for,
    consumption_amount,
    observed_total,
    raw_rows,
)
from coaching_service.schemas import JsonDocument


def raw(**changes: str | int) -> RawTransaction:
    return RawTransaction.model_validate(
        {
            "transaction_id": "one",
            "user_id": "demo",
            "transaction_date": "2026-09-10",
            "transaction_time": "12:00",
            "transaction_type": "CARD",
            "amount_krw": "50000",
            "category": "식비",
            "subcategory": "점심",
            "exclude_tag": "NONE",
            "status": "NORMAL",
            "confirm_status": "CONFIRMED",
            **changes,
        }
    )


@pytest.mark.parametrize(
    ("changes", "expected"),
    [
        ({}, 50000),
        ({"transaction_type": "CARD_SETTLEMENT"}, 0),
        ({"transaction_type": "CARD_BILL"}, 0),
        ({"transaction_type": "TRANSFER_OUT", "exclude_tag": "SELF_TRANSFER"}, 0),
        ({"transaction_type": "TRANSFER_OUT", "exclude_tag": "INTERNAL_TRANSFER"}, 0),
        ({"transaction_type": "TRANSFER"}, 0),
        ({"transaction_type": "TRANSFER_OUT", "direction": "TRANSFER"}, 0),
        ({"transaction_type": "TRANSFER_OUT", "subcategory": "경조사"}, 50000),
        ({"transaction_type": "TRANSFER_OUT", "category": "저축·투자"}, 0),
        ({"transaction_type": "TRANSFER_IN"}, 0),
        ({"transaction_type": "DEPOSIT"}, 0),
        ({"subcategory": "월세"}, 0),
        ({"subcategory": "실손보험"}, 0),
        ({"subcategory": "ATM 출금"}, 0),
        ({"subcategory": "대출 상환"}, 0),
        ({"exclude_tag": "DUTCH"}, 50000),
        ({"exclude_tag": "EMERGENCY"}, 50000),
        ({"exclude_tag": "CARRYOVER"}, 50000),
        ({"confirm_status": "PENDING"}, None),
        ({"status": "CANCELED"}, 0),
    ],
)
def test_purchase_time_consumption_definition(changes: dict[str, str], expected: int | None) -> None:
    # Given / When / Then: each raw financial label has an explicit target treatment.
    assert consumption_amount(raw(**changes)) == expected


def test_purchase_and_card_settlement_are_not_double_counted() -> None:
    # Given: a 50,000 purchase plus the later 50,000 card payment.
    rows = (raw(), raw(transaction_id="settlement", transaction_type="CARD_SETTLEMENT"))
    # When / Then: purchase-time consumption remains 50,000, with one counted purchase.
    result = observed_total(rows, date(2026, 9, 10), date(2026, 9, 10))
    assert result.total_krw == 50000
    assert result.transaction_count == 1


def test_engine_preserved_null_direction_uses_transaction_type() -> None:
    # Given / When / Then: FDT preserves an absent raw direction as null.
    transaction = RawTransaction.model_validate({**raw().model_dump(), "direction": None})
    assert consumption_amount(transaction) == 50000


def test_pending_is_not_an_observed_zero() -> None:
    # Given / When / Then: a pending purchase blocks settlement instead of disappearing.
    with pytest.raises(ServiceError, match="validation_unresolved_transactions"):
        observed_total((raw(confirm_status="PENDING"),), date(2026, 9, 10), date(2026, 9, 10))


def test_calendar_baseline_counts_missing_calendar_days_and_ignores_fixed() -> None:
    # Given: 30,000 variable + 90,000 rent across a leap-year February's 29 days.
    rows = (
        raw(amount_krw=30000, transaction_date="2028-02-01"),
        raw(transaction_id="rent", amount_krw=90000, subcategory="월세", transaction_date="2028-02-29"),
    )
    # When / Then: a 7-day baseline uses 30,000 / 29 * 7; it does not divide by two transactions.
    result = baseline_for(rows, date(2028, 2, 29), 7)
    assert result.history_calendar_days == 29
    assert result.history_total_krw == 30000
    assert result.prediction_krw == pytest.approx(30000 / 29 * 7)


def test_baseline_keeps_the_same_full_history_as_current_team_engine() -> None:
    # Given: the current team FDT uses its full observed calendar, including >365 days.
    rows = (raw(amount_krw=36600, transaction_date="2028-01-01"),)
    # When / Then: this baseline preserves 366 observed days rather than applying a hidden cutoff.
    result = baseline_for(rows, date(2028, 12, 31), 7)
    assert result.history_calendar_days == 366
    assert result.prediction_krw == 700


@pytest.mark.parametrize("value", [True, 1.1, "1.1", "-1", float("nan"), float("inf")])
def test_non_integer_or_nonfinite_money_is_rejected(value: str | float) -> None:
    # Given / When / Then: raw source amounts cannot be coerced to plausible integers.
    with pytest.raises(ValidationError):
        RawTransaction.model_validate({**raw().model_dump(), "amount_krw": value})


@pytest.mark.parametrize("value", ["2028-02-30", "2026-9-1", "2026-09-10T00:00:00"])
def test_strict_calendar_dates(value: str) -> None:
    with pytest.raises(ValidationError):
        raw(transaction_date=value)


@pytest.mark.parametrize("value", ["25:00", "10:99", "12:00:61", "2026-09-10T12:00:00"])
def test_strict_transaction_times(value: str) -> None:
    with pytest.raises(ValidationError):
        raw(transaction_time=value)


def test_duplicate_input_ids_are_rejected() -> None:
    # Given / When / Then: duplicate raw rows never inflate baseline or observed totals.
    row = JsonDocument.model_validate_json(raw().model_dump_json())
    twin = JsonDocument({"as_of": "2026-09-10", "transactions": [{"raw": row.root}, {"raw": row.root}]})
    with pytest.raises(ServiceError, match="validation_duplicate_transaction"):
        raw_rows(twin, "demo")
