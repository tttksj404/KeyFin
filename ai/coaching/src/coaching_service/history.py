"""Keep a historical coaching cause separate from the present ledger and engine result."""

from coaching_service.schemas import Coaching, HistoricalCoaching, TransactionView


def historical_context(original: Coaching, transactions: tuple[TransactionView, ...]) -> HistoricalCoaching:
    past = original.receipt.historical
    if past is None:
        past = HistoricalCoaching(
            coaching_id=original.id,
            created_at=original.created_at,
            payment=original.receipt.payment,
            trigger=original.receipt.trigger,
            engine_result=original.receipt.result,
            transaction_status="not_applicable",
        )
    if past.payment is None:
        return past
    row = next((row for row in transactions if row.id == past.payment.transaction_id), None)
    status = "not_found" if row is None else "active" if row.active else "canceled"
    return past.model_copy(update={"transaction_status": status})
