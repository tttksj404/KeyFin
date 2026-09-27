import pytest

from coaching_service.payments import Ledger, reduce_payment
from coaching_service.schemas import Envelope, TransactionView


def transaction(amount: int, *, active: bool = True) -> TransactionView:
    return TransactionView(
        id="t",
        source="LIVE",
        date="2026-09-09",
        time="12:01",
        envelope="기타",
        amount_krw=amount,
        budget_amount_krw=amount if active else 0,
        kind="expense",
        active=active,
        pending=False,
    )


@pytest.mark.parametrize(
    ("amount", "reason"),
    [
        (49999, "p1_ambiguous"),
        (50000, "p0_half_balance"),
        (50001, "p0_half_balance"),
        (33334, "below_trigger"),
    ],
)
def test_exact_pre_debit_boundary(amount: int, reason: str) -> None:
    ledger = Ledger(envelopes=(Envelope(envelope="기타", balance_krw=100000),))
    tx = transaction(amount)
    result = reduce_payment(ledger, tx, (tx,))
    assert result.reason == reason
    assert result.facts is not None
    assert result.facts.balance_before_krw == 100000
    assert result.facts.balance_after_krw == 100000 - amount


def test_repeated_transaction_and_cancel_refund_once() -> None:
    ledger = Ledger(envelopes=(Envelope(envelope="기타", balance_krw=100000),))
    tx = transaction(50000)
    first = reduce_payment(ledger, tx, (tx,))
    repeat = reduce_payment(first.ledger, tx, (tx,))
    assert repeat.ledger == first.ledger
    assert repeat.reason == "duplicate_transaction"
    canceled = reduce_payment(first.ledger, transaction(50000, active=False), ())
    assert canceled.ledger.envelopes[0].balance_krw == 100000
    assert reduce_payment(canceled.ledger, transaction(50000, active=False), ()).ledger == canceled.ledger
