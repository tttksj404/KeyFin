# ruff: noqa: INP001
"""CI regression test for the backend-serialized FDT payload contract.

The Java ``FdtBootstrap`` serializer sends every transaction field as a string
except ``amount_krw`` (an integer), and translates its own domain events into
the raw ``exclude_tag``/``transaction_type`` vocabulary that ``fdt.ingest``
expects (for example RESTORE -> DEPOSIT + exclude_tag=NONE). This test builds
one representative backend-shaped snapshot + transaction batch and exercises
the real ``fdt.ingest.normalize`` + ``fdt.Twin`` construction path -- no
mocks -- so a future change to the vendored FDT mapping/ingest rules that
silently breaks this contract fails CI instead of production.
"""

from __future__ import annotations

from fdt import Twin
from fdt.errors import FDTError
from fdt.ingest import Transaction, normalize
from fdt.mapping import ENVELOPES

AS_OF = "2026-09-20"
DUE_AFTER_AS_OF = "2026-10-05"

_ACCOUNT_ID = "acc-1"
_CARD_ID = "card-1"


def _row(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "user_id": "user-1",
        "transaction_id": "tx-default",
        "source": "LIVE",
        "transaction_type": "CARD",
        "transaction_date": "2026-09-01",
        "transaction_time": "12:00:00",
        "category": "기타",
        "subcategory": "기타",
        "merchant": "merchant",
        "merchant_id": "0000000000",
        "amount_krw": 1000,
        "account_id": "",
        "card_id": _CARD_ID,
        "confirm_status": "CONFIRMED",
        "status": "NORMAL",
        "exclude_tag": "NONE",
    }
    base.update(overrides)
    return base


def _snapshot() -> dict[str, object]:
    return {
        "as_of": AS_OF,
        "source": "LIVE",
        "accounts": [{"account_id": _ACCOUNT_ID, "balance_krw": 3_000_000}],
        "cards": [
            {
                "card_id": _CARD_ID,
                "kind": "CREDIT",
                "settlement_account_id": _ACCOUNT_ID,
                "opening_payable_krw": 80_000,
                "payment_delay_days": 15,
            }
        ],
        "known_bills": [
            {"bill_id": "bill-1", "card_id": _CARD_ID, "due_date": DUE_AFTER_AS_OF, "amount_krw": 80_000},
        ],
        "schedules": [
            {
                "rule_id": "fixed-1",
                "kind": "fixed_expense",
                "amount_krw": 500_000,
                "fixed_group": "주거",
                "account_id": _ACCOUNT_ID,
                "frequency": "MONTHLY",
                "day_of_month": 25,
                "next_date": DUE_AFTER_AS_OF,
            },
            {
                "rule_id": "debt-1",
                "kind": "debt_service",
                "amount_krw": 200_000,
                "account_id": _ACCOUNT_ID,
                "frequency": "MONTHLY",
                "day_of_month": 10,
                "next_date": DUE_AFTER_AS_OF,
            },
        ],
        "reserve_krw": 200_000,
        "budgets": dict.fromkeys(ENVELOPES, 300_000),
        "coverage": {"all_assets_reported": False, "all_liabilities_reported": False},
    }


def _rows() -> list[dict[str, object]]:
    return [
        # Card tx: category 식비 / subcategory 카페 -> exact subcategory mapping.
        _row(
            transaction_id="tx-card-cafe",
            category="식비",
            subcategory="카페",
            merchant="스타벅스",
            merchant_id="1234567890",
            amount_krw=5_000,
        ),
        # 마트 subcategory 장보기 must route to 편의점·마트·잡화.
        _row(
            transaction_id="tx-mart",
            category="쇼핑",
            subcategory="장보기",
            merchant="이마트",
            merchant_id="2222222222",
            amount_krw=30_000,
        ),
        # DUTCH: amount stored in full, budget_amount_krw forced to 0.
        _row(
            transaction_id="tx-dutch",
            category="식비",
            subcategory="음식점",
            merchant="고기집",
            merchant_id="3333333333",
            amount_krw=40_000,
            exclude_tag="DUTCH",
        ),
        # DEPOSIT + exclude_tag NONE mirrors backend RESTORE -> DEPOSIT translation.
        _row(
            transaction_id="tx-deposit",
            transaction_type="DEPOSIT",
            category="소득",
            subcategory="급여",
            merchant="",
            merchant_id="",
            amount_krw=2_000_000,
            account_id=_ACCOUNT_ID,
            card_id="",
        ),
        # TRANSFER_OUT + exclude_tag NONE: third-party transfer stays an expense.
        _row(
            transaction_id="tx-transfer-out",
            transaction_type="TRANSFER_OUT",
            category="사회·경조",
            subcategory="경조사",
            merchant="",
            merchant_id="",
            amount_krw=100_000,
            account_id=_ACCOUNT_ID,
            card_id="",
        ),
        # TRANSFER + exclude_tag SELF_TRANSFER routes to internal_transfer (not spend).
        _row(
            transaction_id="tx-self-transfer",
            transaction_type="TRANSFER",
            category="이체",
            subcategory="계좌이체",
            merchant="",
            merchant_id="",
            amount_krw=50_000,
            account_id=_ACCOUNT_ID,
            card_id="",
            to_account_id=_ACCOUNT_ID,
            exclude_tag="SELF_TRANSFER",
        ),
        # Unmapped card merchant: unknown category/subcategory must not crash.
        _row(
            transaction_id="tx-unmapped",
            category="미분류",
            subcategory="미분류",
            merchant="미상",
            merchant_id="raw:가맹점명",
            amount_krw=8_000,
        ),
        # PENDING confirm_status transaction.
        _row(
            transaction_id="tx-pending",
            category="식비",
            subcategory="배달",
            merchant="배달앱",
            merchant_id="4444444444",
            amount_krw=15_000,
            confirm_status="PENDING",
        ),
        # 해외 결제 (overseas payment) -- envelope per the real mapping module, not guessed.
        _row(
            transaction_id="tx-overseas",
            category="사회·경조",
            subcategory="해외 결제",
            merchant="Amazon",
            merchant_id="5555555555",
            amount_krw=60_000,
        ),
    ]


def _build_twin() -> Twin:
    transactions = [normalize(row) for row in _rows()]
    return Twin(transactions, AS_OF, _snapshot())


def test_ingest_and_twin_construction_succeed_without_fdt_error() -> None:
    try:
        twin = _build_twin()
    except FDTError as error:  # pragma: no cover - failure path documents itself via message.
        message = f"backend-shaped payload rejected by FDT: {error}"
        raise AssertionError(message) from error
    assert twin.transactions
    assert {t.id for t in twin.transactions} == {
        "tx-card-cafe", "tx-mart", "tx-dutch", "tx-deposit", "tx-transfer-out",
        "tx-self-transfer", "tx-unmapped", "tx-pending", "tx-overseas",
    }


def _by_id(twin: Twin, transaction_id: str) -> Transaction:
    return next(t for t in twin.transactions if t.id == transaction_id)


def test_card_cafe_transaction_maps_to_food_envelope() -> None:
    twin = _build_twin()
    tx = _by_id(twin, "tx-card-cafe")
    assert tx.kind == "expense"
    assert tx.envelope == "외식"
    assert tx.subcategory == "카페"
    assert tx.mapping_fallback is False


def test_mart_subcategory_routes_to_convenience_mart_envelope() -> None:
    twin = _build_twin()
    tx = _by_id(twin, "tx-mart")
    assert tx.envelope == "편의점·마트·잡화"
    assert tx.subcategory == "마트"


def test_dutch_expense_keeps_full_amount_but_zeroes_budget() -> None:
    twin = _build_twin()
    tx = _by_id(twin, "tx-dutch")
    assert tx.kind == "expense"
    assert tx.amount_krw == 40_000
    assert tx.budget_amount_krw == 0
    assert tx.exclude_tag == "DUTCH"


def test_deposit_with_none_exclude_tag_counts_as_income_not_expense() -> None:
    twin = _build_twin()
    tx = _by_id(twin, "tx-deposit")
    assert tx.kind == "income"
    assert tx.kind != "expense"


def test_transfer_out_with_none_exclude_tag_stays_an_expense() -> None:
    twin = _build_twin()
    tx = _by_id(twin, "tx-transfer-out")
    assert tx.kind == "expense"
    assert tx.envelope == "기타"


def test_self_transfer_routes_to_internal_transfer_and_is_not_spend() -> None:
    twin = _build_twin()
    tx = _by_id(twin, "tx-self-transfer")
    assert tx.kind == "internal_transfer"
    assert tx.kind != "expense"
    assert tx.budget_amount_krw == 0


def test_unmapped_merchant_falls_back_sanely_without_crashing() -> None:
    twin = _build_twin()
    tx = _by_id(twin, "tx-unmapped")
    assert tx.kind == "expense"
    assert tx.envelope == "기타"
    assert tx.mapping_fallback is True
    assert tx.subcategory == "미분류"


def test_pending_confirm_status_transaction_has_no_envelope_and_no_budget() -> None:
    twin = _build_twin()
    tx = _by_id(twin, "tx-pending")
    assert tx.pending is True
    assert tx.envelope is None
    assert tx.budget_amount_krw == 0


def test_overseas_payment_maps_to_the_real_mapping_module_envelope() -> None:
    twin = _build_twin()
    tx = _by_id(twin, "tx-overseas")
    assert tx.envelope == "기타"
    assert tx.subcategory == "해외 결제"
