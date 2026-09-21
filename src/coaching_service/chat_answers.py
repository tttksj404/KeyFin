"""Typed non-forecast answers; a concept reply never pretends to carry an FDT receipt."""

import time
from typing import Literal
from uuid import uuid4

from pydantic import Field

from coaching_service.finance_knowledge import reference_document, selected_finance_wording
from coaching_service.llm_contract import FinanceWording, Routing, Wording
from coaching_service.schemas import Frozen, JsonDocument


class FinanceQuestion(Frozen):
    question: str = Field(min_length=1, max_length=2000)


class ChatAnswer(Frozen):
    id: str
    answer_type: Literal[
        "finance_education", "spending_history", "personal_context", "data_request", "scope_response"
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
