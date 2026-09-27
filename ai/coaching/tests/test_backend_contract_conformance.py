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

import numpy as np
from fdt import Twin
from fdt.errors import FDTError
from fdt.ingest import Transaction, normalize
from fdt.mapping import ENVELOPES
from fdt.simulation import generate_bundle, simulate

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
        # BUDGET_EXCLUDED: a real third-party outflow the user keeps out of budget
        # envelopes. Stays an expense (counted as spending), amount stored in full,
        # budget_amount_krw forced to 0 -- NOT an internal_transfer, NOT savings_out.
        _row(
            transaction_id="tx-budget-excluded",
            transaction_type="TRANSFER_OUT",
            category="사회·경조",
            subcategory="경조사",
            merchant="",
            merchant_id="",
            amount_krw=70_000,
            account_id=_ACCOUNT_ID,
            card_id="",
            exclude_tag="BUDGET_EXCLUDED",
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
        "tx-budget-excluded",
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


def test_budget_excluded_stays_a_spending_expense_with_zero_budget() -> None:
    # A budget-excluded third-party outflow is real spending kept out of the budget
    # envelope: expense kind, full amount, budget 0, and never an internal_transfer.
    twin = _build_twin()
    tx = _by_id(twin, "tx-budget-excluded")
    assert tx.kind == "expense"
    assert tx.kind != "internal_transfer"
    assert tx.amount_krw == 70_000
    assert tx.budget_amount_krw == 0
    assert tx.exclude_tag == "BUDGET_EXCLUDED"


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


# --- Regression: unknown-destination internal_transfer must not block/crash the
# absolute cash path (vendored FDT model.cash_requirements + simulation net-zero).

_INTERNAL_TRANSFER_MISSING = "internal_transfer.to_account_id"


def _rows_with_self_transfer_dest(to_account_id: object) -> list[dict[str, object]]:
    """The full conformance batch, with the SELF_TRANSFER row's ``to_account_id``
    replaced (``None``/absent, a named-but-unknown id, or the valid account)."""
    rows: list[dict[str, object]] = []
    for row in _rows():
        if row["transaction_id"] != "tx-self-transfer":
            rows.append(row)
            continue
        patched = dict(row)
        if to_account_id is None:
            patched.pop("to_account_id", None)
        else:
            patched["to_account_id"] = to_account_id
        rows.append(patched)
    return rows


def _rows_without_self_transfer() -> list[dict[str, object]]:
    return [row for row in _rows() if row["transaction_id"] != "tx-self-transfer"]


def _twin_from_rows(rows: list[dict[str, object]]) -> Twin:
    return Twin([normalize(row) for row in rows], AS_OF, _snapshot())


def test_unknown_destination_self_transfer_does_not_block_absolute_path() -> None:
    # A SELF_TRANSFER whose destination account is absent (to_account_id=None)
    # is net-zero on total cash: it must NOT be flagged as missing input, and the
    # forecast-ready snapshot must still yield an absolute (non-None) managed cash.
    twin = _twin_from_rows(_rows_with_self_transfer_dest(None))
    tx = _by_id(twin, "tx-self-transfer")
    assert tx.kind == "internal_transfer"
    assert tx.to_account_id is None

    assert _INTERNAL_TRANSFER_MISSING not in twin.cash_requirements()

    state = twin.inspect()["state"]
    assert state["absolute_cash_ready"] is True
    assert state["managed_cash_krw"] is not None

    bundle = generate_bundle(twin, 30, 64, 7)
    sim = simulate(twin, bundle)
    assert sim.cash_total is not None


def test_unknown_destination_self_transfer_is_net_zero_on_total_cash() -> None:
    # Total cash with the unknown-destination internal_transfer present must equal
    # the total cash of the identical scenario WITHOUT that transfer (net-zero).
    twin_with = _twin_from_rows(_rows_with_self_transfer_dest(None))
    twin_without = _twin_from_rows(_rows_without_self_transfer())

    sim_with = simulate(twin_with, generate_bundle(twin_with, 30, 64, 7))
    sim_without = simulate(twin_without, generate_bundle(twin_without, 30, 64, 7))

    assert sim_with.cash_total is not None
    assert sim_without.cash_total is not None
    # Opening total-cash basis matches, and the full daily total-cash path matches.
    assert int(sim_with.cash_total[0, 0]) == int(sim_without.cash_total[0, 0])
    assert np.array_equal(sim_with.cash_total, sim_without.cash_total)


def test_named_but_unknown_transfer_destination_still_flags_missing_input() -> None:
    # Regression pin: a destination that is NAMED but not in snapshot.accounts is a
    # genuine inconsistency and must still block the absolute path.
    twin = _twin_from_rows(_rows_with_self_transfer_dest("acc-does-not-exist"))
    tx = _by_id(twin, "tx-self-transfer")
    assert tx.kind == "internal_transfer"
    assert tx.to_account_id == "acc-does-not-exist"

    assert _INTERNAL_TRANSFER_MISSING in twin.cash_requirements()
    assert twin.inspect()["state"]["absolute_cash_ready"] is False


def test_valid_transfer_destination_is_not_flagged_and_simulates() -> None:
    # Sanity: to_account_id present and in snapshot.accounts -> not flagged, and the
    # forecast still resolves to an absolute cash path.
    twin = _twin_from_rows(_rows_with_self_transfer_dest(_ACCOUNT_ID))
    tx = _by_id(twin, "tx-self-transfer")
    assert tx.to_account_id == _ACCOUNT_ID

    assert _INTERNAL_TRANSFER_MISSING not in twin.cash_requirements()
    sim = simulate(twin, generate_bundle(twin, 30, 64, 7))
    assert sim.cash_total is not None
