"""Explicit synthetic inputs and arithmetic independent of the product engine."""

from datetime import date, timedelta
from typing import Final

from pydantic import TypeAdapter

from coaching_service.schemas import Bootstrap, Frozen, JsonDocument

FIRST_PAYMENT: Final = 50000
SECOND_PAYMENT: Final = 12000
OPENING_CASH: Final = 1500000
OPENING_ENVELOPE: Final = 100000


class Scenario(Frozen):
    owner: str
    day: date
    bootstrap: Bootstrap

    def snapshot(self, spent: int) -> JsonDocument:
        return JsonDocument(
            {
                "as_of": self.day.isoformat(),
                "source": "LIVE",
                "accounts": [{"account_id": "cash-account", "balance_krw": OPENING_CASH - spent}],
                "cards": [],
                "known_bills": [],
                "reserve_krw": 100000,
                "budgets": {"기타": 300000},
            }
        )

    def event(self, revision: int, name: str, amount: int, spent: int) -> JsonDocument:
        return JsonDocument(
            {
                "expected_revision": revision,
                "event": {
                    "type": "transaction",
                    "event_id": "event-" + name,
                    "user_id": self.owner,
                    "transaction": transaction(self.owner, self.day, name, amount).root,
                },
                "snapshot_event": {
                    "type": "snapshot",
                    "event_id": "snapshot-" + name,
                    "user_id": self.owner,
                    "snapshot": self.snapshot(spent).root,
                },
            }
        )

    def cancel(self, revision: int) -> JsonDocument:
        return JsonDocument(
            {
                "expected_revision": revision,
                "event": {
                    "type": "cancel_transaction",
                    "event_id": "cancel-first",
                    "user_id": self.owner,
                    "transaction_id": "first",
                },
                "snapshot_event": {
                    "type": "snapshot",
                    "event_id": "snapshot-refund",
                    "user_id": self.owner,
                    "snapshot": self.snapshot(SECOND_PAYMENT).root,
                },
            }
        )


def transaction(owner: str, day: date, name: str, amount: int) -> JsonDocument:
    return JsonDocument(
        {
            "user_id": owner,
            "transaction_id": name,
            "source": "LIVE",
            "transaction_type": "WITHDRAW",
            "transaction_date": day.isoformat(),
            "transaction_time": "12:00",
            "category": "기타",
            "subcategory": "기타",
            "merchant": "SYNTHETIC FLOW",
            "merchant_id": "synthetic-flow",
            "amount_krw": amount,
            "account_id": "cash-account",
            "card_id": "",
            "confirm_status": "CONFIRMED",
            "status": "NORMAL",
        }
    )


def scenario(owner: str, day: date) -> Scenario:
    """Ninety observed days end before the reference date; no future rows are supplied."""
    data = Bootstrap(
        as_of=day,
        transactions=tuple(
            transaction(owner, day - timedelta(days=n), f"history-{n}", 1000) for n in range(90, 0, -1)
        ),
        envelopes=(),
    )
    fixture = Scenario(owner=owner, day=day, bootstrap=data)
    return fixture.model_copy(
        update={
            "bootstrap": Bootstrap.model_validate(
                {
                    **data.model_dump(mode="json"),
                    "snapshot": fixture.snapshot(0).root,
                    "envelopes": [{"envelope": "기타", "balance_krw": OPENING_ENVELOPE}],
                }
            )
        }
    )


def expected_month_spend(fixture: Scenario, *, canceled: bool) -> int:
    """Sum raw input rows by Gregorian month, then apply two purchases and one reversal."""
    month = fixture.day.isoformat()[:7]
    history = sum(
        TypeAdapter(int).validate_python(row.root["amount_krw"], strict=True)
        for row in fixture.bootstrap.transactions
        if str(row.root["transaction_date"]).startswith(month)
    )
    return history + SECOND_PAYMENT + (0 if canceled else FIRST_PAYMENT)
