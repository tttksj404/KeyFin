"""Validated service contracts; original FDT JSON stays lossless."""

from typing import Annotated, ClassVar, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, JsonValue, RootModel, model_validator

from coaching_service.periods import DateOnly, PeriodSpec, ResolvedPeriod

Identifier = Annotated[str, Field(min_length=1, max_length=120, pattern=r"^[\w.-]+$")]
Money = Annotated[int, Field(strict=True, ge=-(10**12), le=10**12)]
Tone = Literal["direct", "encouraging"]


class Frozen(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")


class JsonDocument(RootModel[dict[str, JsonValue]]):
    """An opaque, original engine document validated by the upstream engine."""


class Envelope(Frozen):
    envelope: str = Field(min_length=1, max_length=40)
    balance_krw: Money


class Bootstrap(Frozen):
    as_of: DateOnly
    transactions: tuple[JsonDocument, ...] = Field(min_length=1, max_length=10000)
    snapshot: JsonDocument | None = None
    envelopes: tuple[Envelope, ...] = Field(max_length=7)


class TwinIdentity(Frozen):
    user_id: str
    twin_id: str
    revision: int
    input_digest: str
    as_of: str


class TransactionView(Frozen):
    id: str
    source: str
    date: str
    time: str
    envelope: str | None
    amount_krw: int
    budget_amount_krw: int
    kind: str
    active: bool
    pending: bool


class ReviewRequest(Frozen):
    on_date: DateOnly
    through_date: DateOnly
    paths: int = Field(default=100, ge=20, le=2000)
    seed: int = Field(default=42, ge=0, le=4294967295)
    replay: bool = False
    protected_cash_krw: Money | None = None
    changes: tuple[JsonDocument, ...] = Field(default=(), max_length=6)


class EventRequest(Frozen):
    expected_revision: int = Field(ge=0)
    event: JsonDocument
    cancellation_balance: Envelope | None = None
    snapshot_event: JsonDocument | None = None


class PaymentFacts(Frozen):
    transaction_id: str
    envelope: str
    amount_krw: int
    balance_before_krw: int
    balance_after_krw: int
    remaining_percent: str | None
    weekly_count: int
    basis: Literal["service_envelope_ledger"] = "service_envelope_ledger"


class HistoricalCoaching(Frozen):
    coaching_id: str
    created_at: float
    payment: PaymentFacts | None
    trigger: str
    engine_result: JsonDocument
    transaction_status: Literal["active", "canceled", "not_found", "not_applicable"]


class Receipt(Frozen):
    engine_commit: str
    identity: TwinIdentity
    request: JsonDocument
    result: JsonDocument
    payment: PaymentFacts | None = None
    trigger: str
    original_coaching_id: str | None = None
    numeric_request: JsonDocument | None = None
    numeric_result: JsonDocument | None = None
    routing: JsonDocument | None = None
    historical: HistoricalCoaching | None = None
    current_envelopes: tuple[Envelope, ...] = ()
    period: ResolvedPeriod | None = None


class Coaching(Frozen):
    id: str
    text: str
    wording_source: Literal["llm", "template"]
    model: str
    fallback_reason: str | None
    receipt: Receipt
    created_at: float


class EventResult(Frozen):
    identity: TwinIdentity
    detection: str
    payment: PaymentFacts | None = None
    coaching: Coaching | None = None
    judgment: JsonDocument | None = None


class SessionRequest(Frozen):
    coaching_id: Identifier | None = None


class TurnRequest(Frozen):
    question: str = Field(min_length=1, max_length=2000)
    analysis: JsonDocument | None = None
    period: PeriodSpec | None = None
    # None keeps the existing encouraging-by-default deterministic advice wording.
    # This never changes which engine facts trigger advice, only its register.
    tone: Tone | None = None


class AnswerReference(Frozen):
    """본문에서 추정하지 않고, 같은 트랜잭션에 저장한 원본 답변을 가리킨다."""

    kind: Literal["chat", "coaching"]
    id: Identifier


class Message(Frozen):
    role: Literal["user", "assistant"]
    content: str
    # 과거 메시지는 원본을 확정할 수 없으므로 null로 읽고 이관하지 않는다.
    response: AnswerReference | None = None

    @model_validator(mode="after")
    def assistant_reference_only(self) -> Self:
        if self.role == "user" and self.response is not None:
            raise ValueError("user_message_cannot_reference_answer")
        return self


class Session(Frozen):
    id: str
    coaching_id: str | None = None
    created_at: float
    expires_at: float
    messages: tuple[Message, ...] = ()


class Notification(Frozen):
    event_id: str
    type: Literal["COACHING"] = "COACHING"
    coaching_id: str
    text: str
    created_at: float
    acknowledged: bool = False


class NotificationList(Frozen):
    items: tuple[Notification, ...]


class DeleteResult(Frozen):
    deleted: bool
