"""Read raw transaction fields independently of FDT normalize/forecast functions.

The explicit rules below are a reviewable target definition, not an independently
approved human oracle. Never import the engine's classifier to score its outputs.
"""

import re
from datetime import date, datetime, time
from hashlib import sha256
from typing import Annotated, ClassVar, Final, Literal
from zoneinfo import ZoneInfo

from pydantic import AfterValidator, BaseModel, BeforeValidator, ConfigDict, Field, JsonValue

from coaching_service.errors import ServiceError
from coaching_service.forecast_validation_contracts import Amount, Baseline
from coaching_service.periods import DateOnly
from coaching_service.schemas import Frozen, JsonDocument

SEOUL: Final = ZoneInfo("Asia/Seoul")
FIXED_SUBCATEGORIES: Final = frozenset(
    {
        "월세",
        "관리비",
        "전기요금",
        "가스요금",
        "수도요금",
        "통신",
        "인터넷",
        "실손보험",
        "사회보험",
        "자동차세",
        "구독",
        "코워킹",
    }
)


def integer_amount(value: JsonValue) -> JsonValue:
    """Parse stored raw string amounts without decimals or coercion of booleans."""
    if isinstance(value, str) and re.fullmatch(r"[0-9]+", value):
        return int(value)
    return value


def valid_time(value: str) -> str:
    """Check hour/minute ranges without accepting timestamps or timezone conversion."""
    _ = time.fromisoformat(value)
    return value


class RawTransaction(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="ignore")
    transaction_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    transaction_date: DateOnly
    transaction_time: Annotated[str, Field(pattern=r"^\d{2}:\d{2}(:\d{2})?$"), AfterValidator(valid_time)]
    transaction_type: Literal[
        "CARD",
        "WITHDRAW",
        "DEPOSIT",
        "TRANSFER_IN",
        "TRANSFER_OUT",
        "TRANSFER",
        "CARD_BILL",
        "CARD_SETTLEMENT",
    ]
    amount_krw: Annotated[Amount, BeforeValidator(integer_amount)]
    category: str
    subcategory: str
    direction: Literal["INCOME", "EXPENSE", "TRANSFER", ""] | None = None
    exclude_tag: Literal[
        "NONE", "SELF_TRANSFER", "INTERNAL_TRANSFER", "DUTCH", "EMERGENCY", "CARRYOVER", "BUDGET_EXCLUDED"
    ]
    status: Literal["NORMAL", "CANCELED"]
    confirm_status: Literal["AUTO", "CONFIRMED", "PENDING"]


class StoredTransaction(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore", frozen=True)
    raw: RawTransaction


class RawTwin(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore", frozen=True)
    as_of: DateOnly
    transactions: tuple[StoredTransaction, ...] = Field(min_length=1)


class ObservedTotal(Frozen):
    total_krw: Amount
    transaction_count: int = Field(ge=0)


def source_digest(source: JsonDocument) -> str:
    """Hash the complete persisted document, preserving discarded classifier fields too."""
    return sha256(source.model_dump_json().encode()).hexdigest()


def raw_rows(twin: JsonDocument, owner: str) -> tuple[RawTransaction, ...]:
    parsed = RawTwin.model_validate(twin.root)
    rows = tuple(row.raw for row in parsed.transactions)
    if any(row.user_id != owner for row in rows):
        raise ServiceError("validation_owner_mismatch", 403)
    if len({row.transaction_id for row in rows}) != len(rows):
        raise ServiceError("validation_duplicate_transaction")
    if any(row.transaction_date > parsed.as_of for row in rows):
        raise ServiceError("validation_transaction_after_cutoff")
    return rows


def consumption_amount(row: RawTransaction) -> int | None:
    """Purchase-time variable consumption; None means unresolved consumption.

    Third-party outgoing transfers and DUTCH/EMERGENCY/CARRYOVER/BUDGET_EXCLUDED
    purchases are consumption even when excluded from an envelope budget. Card settlement,
    self-transfer, ATM, loan payment and confirmed fixed bills are not this target.
    """
    direction = row.direction or (
        "INCOME"
        if row.transaction_type in {"DEPOSIT", "TRANSFER_IN"}
        else "TRANSFER"
        if row.transaction_type == "TRANSFER"
        else "EXPENSE"
    )
    excluded = (
        row.status == "CANCELED"
        or row.transaction_type in {"CARD_BILL", "CARD_SETTLEMENT"}
        or row.subcategory in {"ATM 출금", "대출 상환"}
        or row.exclude_tag in {"SELF_TRANSFER", "INTERNAL_TRANSFER"}
        or direction == "TRANSFER"
        or (row.transaction_type in {"TRANSFER", "TRANSFER_OUT"} and row.category == "저축·투자")
        or (row.transaction_type in {"DEPOSIT", "TRANSFER_IN"} and direction == "INCOME")
    )
    if excluded:
        return 0
    if row.confirm_status == "PENDING":
        return None
    return 0 if row.subcategory in FIXED_SUBCATEGORIES else row.amount_krw


def observed_total(rows: tuple[RawTransaction, ...], start: date, end: date) -> ObservedTotal:
    selected = tuple(row for row in rows if start <= row.transaction_date <= end)
    amounts = tuple(consumption_amount(row) for row in selected)
    if None in amounts:
        raise ServiceError("validation_unresolved_transactions", 409)
    return ObservedTotal(
        total_krw=sum(value for value in amounts if value is not None),
        transaction_count=sum(value is not None and value > 0 for value in amounts),
    )


def baseline_for(rows: tuple[RawTransaction, ...], cutoff: date, horizon: int) -> Baseline:
    start = min(row.transaction_date for row in rows)
    if start > cutoff:
        raise ServiceError("validation_history_missing")
    total = observed_total(rows, start, cutoff)
    days = (cutoff - start).days + 1
    return Baseline(
        history_start=start,
        history_end=cutoff,
        history_calendar_days=days,
        history_total_krw=total.total_krw,
        prediction_krw=total.total_krw / days * horizon,
    )


def has_future_records(rows: tuple[RawTransaction, ...], timestamp: float) -> bool:
    """Reject future transaction timestamps against the actual registration clock."""
    return any(
        datetime.fromisoformat(f"{row.transaction_date}T{row.transaction_time}")
        .replace(tzinfo=SEOUL)
        .timestamp()
        > timestamp
        for row in rows
    )
