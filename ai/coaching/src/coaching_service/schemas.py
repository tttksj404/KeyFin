"""Validated service contracts; original FDT JSON stays lossless."""

from typing import Annotated, ClassVar, Final, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, JsonValue, RootModel, model_validator

from coaching_service.periods import DateOnly, PeriodSpec, ResolvedPeriod

Identifier = Annotated[str, Field(min_length=1, max_length=120, pattern=r"^[\w.-]+$")]
Money = Annotated[int, Field(strict=True, ge=-(10**12), le=10**12)]
Tone = Literal["direct", "encouraging"]
# 예산 주기 시작일. 1~28만 허용해 말일 없는 달(2월 등)의 모호함을 원천 차단한다.
# 계약은 1급 정수를 받고, 저장·기간 계산은 없을 때 1일로 폴백해 기존 동작과 같다.
BudgetStartDay = Annotated[int, Field(strict=True, ge=1, le=28)]


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
    # 선택적 예산 주기 시작일. as_of·envelopes처럼 최상위에 실어 서비스가 보관하며,
    # 고정 FDT snapshot(additionalProperties:false)은 건드리지 않는다. 생략하면
    # 서비스 저장이 없어 기간 계산이 1일로 폴백해 기존 호출자 동작이 그대로 유지된다.
    budget_start_day: BudgetStartDay | None = None


class BudgetConfig(Frozen):
    """예산 주기 시작일의 서비스측 영속 상태. Twin/원장과 분리해 이벤트마다 재구성되지 않는다.

    부트스트랩에서 ``Bootstrap.budget_start_day`` 가 있을 때만 한 번 기록하고, 기간
    계산은 없으면 1일로 폴백한다. FDT snapshot 스키마를 바꾸지 않으려는 선택이다.
    """

    start_day: BudgetStartDay = 1


BUDGET_CONFIG_KEY: Final = "budget/config"


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


class ChartPurchaseHint(Frozen):
    """구매검토 대화가 차트 요청에 실을 예정 구매. 봉투·금액·날짜만 전달한다.

    ``POST /v1/charts/budget-forecast`` 본문의 ``purchase`` 블록과 같은 모양이라
    앱이 그대로 보내면 구매 전/후 누적선을 겹쳐 그린다. 계좌·카드는 담지 않는다.
    """

    envelope: str = Field(min_length=1, max_length=40)
    amount_krw: Annotated[int, Field(ge=1)]
    on_date: DateOnly


class ChartHint(Frozen):
    """예측·구매검토 대화가 안내하는 budget-forecast 차트 요청 본문.

    앱이 시각화를 원할 때 그대로 ``POST /v1/charts/budget-forecast`` 로 보내면
    이 대화와 같은 예산 주기의 차트를 얻는다. 별도 시뮬레이션이나 차트 저장을 하지
    않으며, ``period_start`` 는 사용자가 설정한 예산 시작일(없으면 1일) 기준으로
    대화 기준일이 속한 주기의 시작일이라 그 기준일을 포함하는 유효한 예산 주기다.
    ``purchase`` 는 구매검토 대화에서 예정 구매가
    기준일 이후·예산 월 안에 있을 때만 채우고, 그 외에는 ``None`` 을 유지한다.
    """

    endpoint: Literal["/v1/charts/budget-forecast"] = "/v1/charts/budget-forecast"
    period_start: DateOnly
    question: str | None = None
    purchase: ChartPurchaseHint | None = None


class EnvelopeSpendRow(Frozen):
    """봉투별 예측 소비 분위수. 엔진 datasets['envelopes']에서 그대로 온다."""

    envelope: str = Field(min_length=1, max_length=40)
    p10_krw: Money
    p50_krw: Money
    p90_krw: Money


class BudgetRiskRow(Frozen):
    """봉투별 이번 달 예산 대비 예측 소비와 초과 확률. 엔진 datasets['budget_risk']."""

    envelope: str = Field(min_length=1, max_length=40)
    budget_krw: Money
    observed_used_krw: Money
    projected_used_p50_krw: Money
    p_over_budget: Annotated[float, Field(ge=0.0, le=1.0)]


class NumericRows(Frozen):
    """위험·가정 대화의 봉투별 구조화 행. 소비 조회 rows처럼 앱이 표로 렌더한다.

    text는 그대로 두고, 엔진이 이미 계산한 봉투별 수치만 1급 필드로 노출한다.
    ``envelope_spend`` 는 두 모드 모두, ``budget_risk`` 는 위험 대화에서 스냅샷에
    예산이 있을 때만 채운다. 값을 만들지 않으며 근거 없는 행은 비운다.
    """

    mode: Literal["risk", "what_if"]
    envelope_spend: tuple[EnvelopeSpendRow, ...] = ()
    budget_risk: tuple[BudgetRiskRow, ...] = ()


class Coaching(Frozen):
    id: str
    text: str
    wording_source: Literal["llm", "template"]
    model: str
    fallback_reason: str | None
    receipt: Receipt
    created_at: float
    # 예측·구매검토 대화에서만 채우는 선택적 힌트. 다른 대화는 None을 유지한다.
    chart_hint: ChartHint | None = None
    # 위험·가정 수치 대화에서만 채우는 봉투별 구조화 행. 같은 수치는 receipt의
    # numeric_result.datasets에도 그대로 있어 계약 보증이 이중으로 남는다.
    numeric_rows: NumericRows | None = None
    # 대화 턴에서 봉투가 둘 이상일 때 봉투별 장부 잔액을 문장 대신 표 행으로 싣는다.
    # 본문에는 표 설명 한 줄만 남고, 결제 알림·과거 코칭 후속은 비어 있다.
    envelope_balances: tuple[Envelope, ...] = ()


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


class PendingClarification(Frozen):
    """한 번의 needs_clarification 되묻기가 남긴 최소 컨텍스트(구매·소비 전용).

    각 턴이 현재 질문만 재파싱해 되묻기 뒤의 짧은 후속("30만원", "이번달")이
    유실되던 문제를 막는다. 부분 파싱 구조체 대신 지금까지의 질문 텍스트만
    저장해 단일 파서(``natural_purchase``/``spending_answer``)를 그대로 진실의
    원천으로 재사용한다. 다음 턴에서 후속이 순수 조각이면 이 텍스트에 병합해
    재해석하고, 완결된 다른 질문이면 병합하지 않고 폐기한다. ``code`` 는 앱과
    진단을 위한 누락 필드 코드다. 이 컨텍스트는 세션에 같은 뮤테이션으로
    저장되어 재시도에도 턴 결과와 어긋나지 않는다.
    """

    kind: Literal["purchase", "spending", "goal", "what_if"]
    question: str = Field(min_length=1, max_length=4000)
    code: str = Field(min_length=1, max_length=120)


class Session(Frozen):
    id: str
    coaching_id: str | None = None
    created_at: float
    expires_at: float
    messages: tuple[Message, ...] = ()
    # 되묻기 직후에만 채우는 병합용 컨텍스트. 해소·주제 전환 시 None으로 지운다.
    pending_clarification: PendingClarification | None = None


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
