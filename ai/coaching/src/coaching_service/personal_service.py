"""개인 현황은 기존 소유자 잠금·멱등성·삭제 트랜잭션 안에서 저장한다."""

import time
from datetime import UTC, datetime
from typing import Final, assert_never
from uuid import uuid4
from zoneinfo import ZoneInfo

import anyio

from coaching_service.chat_answers import ChatAnswer
from coaching_service.errors import ServiceError
from coaching_service.payments import Ledger
from coaching_service.personal_contract import (
    PersonalContext,
    PersonalInput,
    PersonalRow,
    PersonalSummary,
    PersonalTopic,
)
from coaching_service.personal_query import (
    filtered_personal_topic,
    has_unmatched_fragment,
    select_personal_topic,
    select_personal_topics,
)
from coaching_service.personal_snapshot import snapshot_summary
from coaching_service.personal_summary import LABELS, context_summary, missing
from coaching_service.repository import Mutation, Repository, document, write
from coaching_service.schemas import JsonDocument
from coaching_service.store import Operation

CONTEXT_KEY: Final = "personal/context"


async def save_personal_context(repository: Repository, op: Operation, body: PersonalInput) -> JsonDocument:
    async def action() -> Mutation:
        stored = await anyio.to_thread.run_sync(repository.store.load, op.owner, CONTEXT_KEY)
        previous = PersonalContext.model_validate_json(stored) if stored is not None else None
        revision = previous.revision if previous is not None else 0
        if revision != body.expected_revision:
            raise ServiceError("personal_revision_conflict", 409)
        if previous is not None and body.as_of < previous.as_of:
            raise ServiceError("personal_snapshot_older_than_stored", 409)
        now = datetime.now(UTC)
        if body.as_of > now.astimezone(ZoneInfo("Asia/Seoul")).date():
            raise ServiceError("personal_as_of_in_future", 422)
        context = PersonalContext.model_validate(
            body.model_dump() | {"revision": revision + 1, "received_at": now}
        )
        return Mutation(result=document(context), writes=(write(CONTEXT_KEY, context),))

    return await repository.mutate(op, action)


_UNSUPPORTED_TOPIC_TEXT: Final = (
    "계좌 잔액·자산·부채·보험·월 소득·월 고정비·예정 결제·목표·봉투 예산 잔액 중 하나를 질문해 주세요. "
    "특정 기관·기간·항목의 필터나 두 항목의 비교는 아직 지원하지 않습니다."
)
_UNMATCHED_FRAGMENT_NOTE: Final = (
    "그중 일부 항목은 계좌 잔액·자산·부채·보험·월 소득·월 고정비·예정 결제·목표·봉투 예산 잔액에 "
    "해당하지 않아 이 조회로는 답하지 않습니다."
)


async def summary_for_topic(repository: Repository, owner: str, topic: PersonalTopic) -> PersonalSummary:
    """한 등록 주제의 현황만 조회한다. 복수 주제 질문도 이 함수를 그대로 재사용한다."""
    match topic:
        case "accounts" | "assets" | "debts" | "payments":
            stored = await anyio.to_thread.run_sync(repository.store.load, owner, "twin")
            return (
                snapshot_summary(JsonDocument.model_validate_json(stored), topic)
                if stored is not None
                else missing(topic)
            )
        case "insurance" | "income" | "fixed_costs" | "goals":
            stored = await anyio.to_thread.run_sync(repository.store.load, owner, CONTEXT_KEY)
            return (
                context_summary(PersonalContext.model_validate_json(stored), topic)
                if stored is not None
                else missing(topic)
            )
        case "budget":
            stored = await anyio.to_thread.run_sync(repository.store.load, owner, "ledger")
            if stored is None:
                return missing(topic)
            return _budget_summary(Ledger.model_validate_json(stored))
        case unreachable:
            assert_never(unreachable)


def _budget_summary(ledger: Ledger) -> PersonalSummary:
    """봉투(envelope)별 예산 잔액을 결제 이벤트가 갱신한 ledger에서 그대로 읽는다."""
    if not ledger.envelopes:
        return missing("budget")
    rows = tuple(
        PersonalRow(id="envelope/" + row.envelope, label=row.envelope, amount_krw=row.balance_krw)
        for row in ledger.envelopes
    )
    total = sum(row.amount_krw for row in rows)
    row_text = " ".join(f"{row.label}: {row.amount_krw:,}원." for row in rows)
    return PersonalSummary(
        topic="budget",
        status="answered",
        text=f"{LABELS['budget']} 합계는 {total:,}원입니다. {row_text}".strip(),
        coverage="complete",
        total_krw=total,
        total_label=LABELS["budget"],
        rows=rows,
        warnings=(
            "이 봉투 잔액은 결제 이벤트로 갱신된 값이며 계좌 잔액과는 별도로 관리됩니다.",
            "예측 계산에 반영되었다는 뜻은 아닙니다.",
        ),
    )


_KIND_NOTE: Final[dict[str, str]] = {
    "accounts": "계좌 종류별로 골라 보여 드리지는 못해 연결된 계좌를 모두 보여 드려요.",
    "debts": "대출 종류별로 골라 보여 드리지는 못해 보고된 대출을 모두 보여 드려요.",
}


async def personal_summary(repository: Repository, owner: str, question: str) -> PersonalSummary:
    topic = select_personal_topic(question)
    if topic is not None:
        return await summary_for_topic(repository, owner, topic)
    filtered = filtered_personal_topic(question)
    if filtered is not None:
        summary = await summary_for_topic(repository, owner, filtered)
        note = _KIND_NOTE.get(filtered)
        if note is None:
            return summary
        return summary.model_copy(update={"text": note + " " + summary.text})
    topics = select_personal_topics(question)
    if not topics:
        return PersonalSummary(topic=None, status="needs_clarification", text=_UNSUPPORTED_TOPIC_TEXT)
    summaries = tuple([await summary_for_topic(repository, owner, item) for item in topics])
    pieces = [summary.text for summary in summaries]
    if has_unmatched_fragment(question):
        pieces.append(_UNMATCHED_FRAGMENT_NOTE)
    return PersonalSummary(
        topic=None,
        status="answered" if any(summary.status == "answered" for summary in summaries) else "needs_data",
        text="\n\n".join(pieces),
    )


async def personal_answer(repository: Repository, owner: str, question: str) -> ChatAnswer:
    """세션 측은 반환값을 기존 answer/{id} 및 session과 같은 Mutation으로 저장한다."""
    summary = await personal_summary(repository, owner, question)
    return ChatAnswer(
        id=uuid4().hex,
        answer_type="personal_context",
        status=summary.status,
        text=summary.text,
        wording_source="engine",
        model="not_called",
        evidence=document(summary),
        created_at=time.time(),
    )
