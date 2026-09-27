from pydantic import JsonValue

from .ingest import Transaction

class Twin:
    model: dict[str, JsonValue]
    transactions: list[Transaction]
    user_id: str
    twin_id: str
    revision: int
    content_digest: str
    as_of: str
    snapshot: dict[str, JsonValue] | None
    def __init__(self, transactions: list[Transaction], as_of: str,
                 snapshot: dict[str, JsonValue] | None = ...) -> None: ...
    @classmethod
    def from_dict(cls, value: dict[str, JsonValue]) -> Twin: ...
    def to_dict(self) -> dict[str, JsonValue]: ...
    def cash_requirements(self) -> list[str]: ...
