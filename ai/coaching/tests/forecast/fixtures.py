"""Fixed daily spending for closed-form period and leakage tests."""

from datetime import date, timedelta

from benchmarks.forecast.ledger_adapter.contracts import LedgerRow


def daily_rows(cutoff: date, days: int = 90) -> tuple[LedgerRow, ...]:
    return tuple(LedgerRow(
        user_id="cpu-synthetic", transaction_id=f"day-{offset}", source="SEED",
        transaction_type="WITHDRAW", transaction_date=cutoff - timedelta(days=days - offset - 1),
        transaction_time="12:00", category="식비", subcategory="점심", merchant="synthetic",
        merchant_id=f"independent-day-{offset}", amount_krw=1000, account_id="a", card_id="",
        confirm_status="CONFIRMED", status="NORMAL",
    ) for offset in range(days))
