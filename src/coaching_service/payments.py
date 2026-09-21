"""Envelope debits are distinct from account snapshots and monthly budget estimates."""

from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from pydantic import ValidationError

from coaching_service.errors import ServiceError
from coaching_service.schemas import Envelope, Frozen, PaymentFacts, TransactionView


class Debit(Frozen):
    transaction_id: str
    envelope: str
    amount_krw: int
    canceled: bool = False


class Ledger(Frozen):
    envelopes: tuple[Envelope, ...]
    debits: tuple[Debit, ...] = ()


class Detection(Frozen):
    ledger: Ledger
    reason: str
    facts: PaymentFacts | None = None


def changed_balance(account: Envelope, delta: int) -> Envelope:
    """차감·환불 모두 Envelope의 같은 잔액 한도를 적용한다.

    검증을 생략하는 model_copy로 금액을 바꾸면 다음 요청에서 원장을 읽지 못할 수
    있으므로 새 객체를 검증한다. 한도 초과는 저장 전에 422이며 재시도 키도 남기지 않는다.
    """
    try:
        return Envelope(envelope=account.envelope, balance_krw=account.balance_krw + delta)
    except ValidationError as exc:
        raise ServiceError("envelope_balance_limit") from exc


def reduce_payment(
    ledger: Ledger, transaction: TransactionView, transactions: tuple[TransactionView, ...]
) -> Detection:
    """활성 상태의 비-pending 봉투 결제를 한 번 차감하고 취소는 한 번 환불한다.

    계좌 스냅샷이나 월 예산을 잔액으로 대신 쓰지 않는다. 이 함수는 DB를 쓰지 않으며
    원장·Twin·코칭을 한 번에 저장할 책임은 호출자의 Repository에 있다.
    """
    old = next((row for row in ledger.debits if row.transaction_id == transaction.id), None)
    if old is not None:
        if (
            transaction.active
            and not old.canceled
            and (transaction.envelope != old.envelope or transaction.budget_amount_krw != old.amount_krw)
        ):
            raise ServiceError("reclassification_requires_ledger_reconciliation", 409)
        if old.canceled or transaction.active:
            return Detection(ledger=ledger, reason="duplicate_transaction")
        updated = tuple(
            changed_balance(row, old.amount_krw)
            if row.envelope == old.envelope
            else row
            for row in ledger.envelopes
        )
        debits = tuple(
            row.model_copy(update={"canceled": True}) if row == old else row for row in ledger.debits
        )
        return Detection(ledger=Ledger(envelopes=updated, debits=debits), reason="cancellation_refunded")
    if not transaction.active or transaction.pending or transaction.budget_amount_krw <= 0:
        return Detection(ledger=ledger, reason="not_confirmed_envelope_debit")
    account = next((row for row in ledger.envelopes if row.envelope == transaction.envelope), None)
    if account is None:
        return Detection(ledger=ledger, reason="envelope_balance_missing")
    before = account.balance_krw
    debited = changed_balance(account, -transaction.budget_amount_krw)
    after = debited.balance_krw
    updated = tuple(
        debited if row == account else row for row in ledger.envelopes
    )
    debit = Debit(
        transaction_id=transaction.id, envelope=account.envelope, amount_krw=transaction.budget_amount_krw
    )
    new_ledger = Ledger(envelopes=updated, debits=(*ledger.debits, debit))
    monday = date.fromisoformat(transaction.date) - timedelta(
        days=date.fromisoformat(transaction.date).weekday()
    )
    count = sum(
        row.active
        and row.source == "LIVE"
        and not row.pending
        and row.budget_amount_krw > 0
        and row.envelope == transaction.envelope
        and monday.isoformat() <= row.date <= transaction.date
        and (row.date < transaction.date or row.time <= transaction.time)
        for row in transactions
    )
    percent = (
        str((Decimal(after) * 100 / before).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))
        if before > 0
        else None
    )
    facts = PaymentFacts(
        transaction_id=transaction.id,
        envelope=account.envelope,
        amount_krw=debit.amount_krw,
        balance_before_krw=before,
        balance_after_krw=after,
        remaining_percent=percent,
        weekly_count=count,
    )
    if before <= 0:
        reason = "nonpositive_balance_needs_data"
    # 잔액 대비 50%는 즉시 코칭, 40% 또는 주간 5회 이상+20%는 판단 요청이다.
    # 정수 곱셈으로 경계를 판정하여 표시용 소수점 반올림이 분기를 바꾸지 않게 한다.
    elif debit.amount_krw * 2 >= before:
        reason = "p0_half_balance"
    elif debit.amount_krw * 5 >= before * 2 or (count >= 5 and debit.amount_krw * 5 >= before):
        reason = "p1_ambiguous"
    else:
        reason = "below_trigger"
    return Detection(ledger=new_ledger, reason=reason, facts=facts)


def reconcile_cancellation(ledger: Ledger, transaction: TransactionView, balance: Envelope) -> Detection:
    """추적하지 못한 결제 취소는 같은 봉투의 외부 확정 잔액으로 조정한다.

    추측한 환불액을 더하지 않으며 취소 기록을 남겨 중복 환불을 막는다.
    반환 원장을 실제 저장하는 시점은 다른 변경과 함께 Repository가 결정한다.
    """
    if balance.envelope != transaction.envelope:
        raise ServiceError("cancellation_envelope_mismatch")
    accounts = tuple(row for row in ledger.envelopes if row.envelope != balance.envelope)
    debits = tuple(row for row in ledger.debits if row.transaction_id != transaction.id)
    debit = Debit(transaction_id=transaction.id, envelope=balance.envelope, amount_krw=0, canceled=True)
    return Detection(
        ledger=Ledger(envelopes=(*accounts, balance), debits=(*debits, debit)),
        reason="cancellation_reconciled",
    )
