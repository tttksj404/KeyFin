"""Typed non-forecast answers; a concept reply never pretends to carry an FDT receipt."""

import time
from typing import Literal
from uuid import uuid4

from pydantic import Field

from coaching_service.finance_knowledge import reference_document, selected_finance_wording
from coaching_service.llm_contract import FinanceWording, Routing, Wording
from coaching_service.schemas import Frozen, JsonDocument
from coaching_service.spending_history import SpendingRow


class FinanceQuestion(Frozen):
    question: str = Field(min_length=1, max_length=2000)


class ChatAnswer(Frozen):
    id: str
    answer_type: Literal[
        "finance_education", "spending_history", "personal_context", "data_request",
        "scope_response", "purchase_review", "period_review",
    ]
    status: Literal[
        "answered", "needs_source", "needs_data", "out_of_scope", "unavailable", "needs_clarification"
    ]
    text: str
    wording_source: Literal["llm", "template", "engine"]
    model: str
    fallback_reason: str | None = None
    evidence: JsonDocument
    created_at: float
    # 소비 조회(spending_history) 응답에서만 채우는 1급 필드. 나머지 answer_type은
    # 기본값을 유지해 값이 없으며, 같은 데이터는 evidence.spending에도 그대로 남는다.
    rows: tuple[SpendingRow, ...] = ()
    total_krw: int | None = None


def knowledge_answer(wording: Wording) -> ChatAnswer:
    """Record actual selection acceptance independently of HTTP success."""
    parsed = (
        wording
        if isinstance(wording, FinanceWording)
        else selected_finance_wording(None, wording.model, "invalid_finance_selection")
    )
    return ChatAnswer(
        id=uuid4().hex,
        answer_type="finance_education",
        status=parsed.answer_status,
        text=parsed.text,
        wording_source=parsed.source,
        model=parsed.model,
        fallback_reason=parsed.fallback_reason,
        evidence=JsonDocument.model_validate_json(reference_document(parsed.reference_ids)),
        created_at=time.time(),
    )


def missing_twin_answer(route: Routing) -> ChatAnswer:
    if route.fallback_reason is not None:
        return routing_unavailable_answer(route)
    return ChatAnswer(
        id=uuid4().hex,
        answer_type="data_request",
        status="needs_data",
        text=(
            "개인 지출·잔액·미래 예측을 확인할 거래 자료가 아직 연결되지 않았습니다. "
            "거래와 잔액을 연동한 뒤 다시 질문해 주세요. 일반 금융 개념은 바로 질문할 수 있습니다."
        ),
        wording_source="template",
        model="not_called",
        fallback_reason="twin_not_connected",
        evidence=JsonDocument({"data_status": "twin_not_connected"}),
        created_at=time.time(),
    )


def out_of_scope_answer() -> ChatAnswer:
    """Handle a non-financial question without requesting personal transactions."""
    return ChatAnswer(
        id=uuid4().hex,
        answer_type="scope_response",
        status="out_of_scope",
        text="금융 개념과 연결된 소비·예측 질문을 도와드릴 수 있습니다. 금융과 관련된 질문을 입력해 주세요.",
        wording_source="template",
        model="not_called",
        fallback_reason="non_financial_question",
        evidence=JsonDocument({"scope": "finance_coaching"}),
        created_at=time.time(),
    )


# 구매 검토 되묻기: 필수 정보가 빠졌을 때 금액을 추정하지 않고 후속 질문을
# 200 needs_clarification 한 턴으로 돌려준다. 소비 조회의 needs_clarification과
# 같은 방식(정상 저장되는 한 턴, 모델 미호출)으로 처리한다. 문구는 앱 계약에서
# 합의한 그대로이며 숫자를 포함하지 않아 기존 안전 가드 범위 밖이다.
_PURCHASE_CLARIFICATIONS: dict[str, str] = {
    "purchase_amount_required": (
        "얼마짜리 구매인지 금액을 알려주시면 이번 예산에 미치는 영향을 확인해 드릴게요."
    ),
    "purchase_envelope_required": "어떤 항목의 지출인지 알려주시면 해당 봉투 기준으로 살펴볼게요.",
    "purchase_payment_method_required": (
        "현금·계좌 결제인지 카드 결제인지 알려주세요. "
        "카드라면 결제 예정일도 함께 알려주시면 정확히 반영할 수 있어요."
    ),
    "purchase_card_payment_date_required": (
        "카드로 결제하신다면 결제(출금) 예정일을 연-월-일 날짜로 알려주세요. "
        "현금·계좌 결제라면 그대로 확인해 드릴게요."
    ),
    "purchase_installment_unsupported": (
        "할부 구매는 아직 지원하지 않아요. 일시불 기준으로 다시 여쭤봐 주시면 확인해 드릴게요."
    ),
    "purchase_date_required": (
        "언제 구매할 예정인지 알려주세요. 오늘·내일·이번주처럼 시점을 알려주시면 그 기준으로 확인해 드릴게요."
    ),
    "purchase_date_out_of_period": (
        "그 날짜는 지금 점검하는 예산 기간 밖이라 이번 예산으로는 판단하기 어려워요. "
        "이번 기간 안의 날짜로 알려주시면 확인해 드릴게요."
    ),
}


def purchase_clarification_answer(code: str) -> ChatAnswer | None:
    """구매 검토 되묻기 코드를 200 needs_clarification 답변으로 만든다.

    합의된 되묻기 문구가 없는 알 수 없는 코드에는 ``None`` 을
    돌려 호출부가 기존 4xx 계약을 그대로 유지하게 한다. ``fallback_reason`` 과
    ``evidence`` 에 원 코드를 남겨 앱이 어떤 필드가 필요한지 기계적으로 읽을 수 있다.
    """
    text = _PURCHASE_CLARIFICATIONS.get(code)
    if text is None:
        return None
    return ChatAnswer(
        id=uuid4().hex,
        answer_type="purchase_review",
        status="needs_clarification",
        text=text,
        wording_source="engine",
        model="not_called",
        fallback_reason=code,
        evidence=JsonDocument({"purchase": {"clarification": code}}),
        created_at=time.time(),
    )


# 기간 되묻기: 대화(/messages) 턴에서 기간이 모호·충돌하거나 지원하지 않는 형식일 때
# 503으로 떨어뜨리는 대신 구매 되묻기와 같은 방식(모델 미호출, 정상 저장되는 한 턴)으로
# 200 needs_clarification 을 돌려준다. 예측검증 API·차트 엔드포인트의 기간 오류 코드는
# 이 표에 없어 기존 4xx 계약을 그대로 유지한다(범위 가드). 문구는 숫자를 포함하지 않아
# 기존 안전 가드 범위 밖이며, ``fallback_reason``·``evidence`` 에 원 코드를 남긴다.
_PERIOD_CLARIFICATIONS: dict[str, str] = {
    "period_clarification_required": (
        "언제 기준인지 알려주세요. 지난달·이번 달·오늘·어제·현재까지 중에서 "
        "말씀해 주시면 그 기간으로 확인해 드릴게요."
    ),
    "invalid_question_period": (
        "언제 기준인지 알려주세요. 지난달·이번 달·오늘·어제·현재까지 중에서 "
        "말씀해 주시면 그 기간으로 확인해 드릴게요."
    ),
    "period_conflict": (
        "기간이 두 가지로 읽혀요. 한 가지 기간만 알려주시면 그 기준으로 살펴볼게요."
    ),
    "period_unsupported_calendar": (
        "그 기간 형식은 아직 지원하지 않아요. 지난달·이번 달·오늘·어제·현재까지로 알려주세요."
    ),
    "goal_amount_required": (
        "얼마를 모을지 알려주세요. 목표 금액과 기한을 알려주시면 모을 수 있을지 계산해 드릴게요."
    ),
    "goal_period_required": (
        "언제까지 모을지 알려주세요. 이번 달 말이나 다음 달처럼 기간을 알려주시면 "
        "모을 수 있을지 계산해 드릴게요."
    ),
    "goal_period_unsupported": (
        "그 기간은 아직 계산하지 못해요. 이번 달 말이나 다음 달처럼 기간을 알려주시면 "
        "모을 수 있을지 계산해 드릴게요."
    ),
    "spending_period_unsupported": (
        "그 기간 형식은 아직 지원하지 않아요. 지난달·이번 달·오늘·어제·현재까지로 알려주세요."
    ),
    "what_if_scope_unsupported": (
        "주 단위나 특정 날짜까지의 기간, 두 봉투를 함께 바꾸는 계산은 아직 못 해요. '이번 달 외식 20% "
        "줄이면 어떻게 될까?'처럼 이번 달이나 다음 달, 봉투 하나로 물어봐 주세요."
    ),
    "what_if_percent_required": (
        "줄일 금액 대신 비율로 알려주세요. 예를 들어 '이번 달 외식 20% 줄이면 어떻게 될까?'처럼 "
        "물으시면 지금처럼 쓸 때와 비교해 드릴게요."
    ),
    "period_not_supported_for_intent": (
        "이 질문에는 그 기간을 적용하기 어려워요. 다른 기간으로 다시 여쭤봐 주세요."
    ),
}


def period_clarification_answer(code: str) -> ChatAnswer | None:
    """대화 턴의 기간 되묻기 코드를 200 needs_clarification 답변으로 만든다.

    합의된 되묻기 문구가 있는 대화 턴 전용 코드에만 답변을 만들고, 그 밖의 코드
    (예측검증·차트 기간 오류 등)에는 ``None`` 을 돌려 호출부가 기존 4xx 계약을 그대로
    유지하게 한다. 구매 되묻기와 동일한 메커니즘이며 ``fallback_reason``·``evidence`` 에
    원 코드를 남겨 앱이 어떤 기간이 필요한지 기계적으로 읽을 수 있다.
    """
    text = _PERIOD_CLARIFICATIONS.get(code)
    if text is None:
        return None
    return ChatAnswer(
        id=uuid4().hex,
        answer_type="period_review",
        status="needs_clarification",
        text=text,
        wording_source="engine",
        model="not_called",
        fallback_reason=code,
        evidence=JsonDocument({"period": {"clarification": code}}),
        created_at=time.time(),
    )


def routing_unavailable_answer(route: Routing) -> ChatAnswer:
    """Preserve a failed intent call instead of misreporting missing customer data."""
    return ChatAnswer(
        id=uuid4().hex,
        answer_type="scope_response",
        status="unavailable",
        text="지금은 질문의 의도를 확인하지 못했습니다. 잠시 후 다시 질문해 주세요.",
        wording_source="template",
        model="not_called",
        fallback_reason=route.fallback_reason,
        evidence=JsonDocument({"routing": route.model_dump(mode="json")}),
        created_at=time.time(),
    )
