from pydantic import JsonValue

class Transaction:
    id: str
    source: str
    user_id: str
    date: str
    time: str
    envelope: str | None
    amount_krw: int
    budget_amount_krw: int
    kind: str
    active: bool
    pending: bool
    raw: dict[str, JsonValue]

def normalize(row: dict[str, JsonValue]) -> Transaction: ...
