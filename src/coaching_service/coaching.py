"""Reusable orchestration of real engine evidence and model language."""

import time
from datetime import date, timedelta
from typing import Final, Protocol
from uuid import uuid4

import anyio
from pydantic import ValidationError

from coaching_service.engine import ENGINE_COMMIT, EngineAdapter
from coaching_service.evidence import LIMITED_CONTEXT, bounded_evidence, context_limited
from coaching_service.llm_contract import EvidenceInput, Judgment, Routing, Wording
from coaching_service.llm_prompt import TEMPLATE_TEXT
from coaching_service.numeric_rendering import purchase_verdict_text
from coaching_service.periods import ResolvedPeriod, ThroughDate, resolve_period
from coaching_service.rendering import authoritative_text, deterministic_advice
from coaching_service.repository import Repository, write
from coaching_service.request_timing import measure_fdt, run_measured_fdt
from coaching_service.schemas import (
    Coaching,
    JsonDocument,
    Notification,
    PaymentFacts,
    Receipt,
    ReviewRequest,
    Tone,
    TwinIdentity,
)
from coaching_service.store import Write

_NUMERIC_FOLLOW_UP: Final[dict[str, str]] = {
    "forecast": "예측 조건에 포함하지 않은 예정 결제나 소득 변동이 있으면 알려 주세요.",
    "risk": "위험을 함께 확인할 계좌 잔액이나 예정 결제 정보가 있으면 알려 주세요.",
    "goal": "목표 조건에 포함할 소득·지출 계획이 있으면 알려 주세요.",
    "what_if": "비교할 가정에 포함할 소비 계획이 있으면 알려 주세요.",
    "optimize": "비교할 제약 조건이나 유지할 지출 항목이 있으면 알려 주세요.",
}
_REVIEW_FOLLOW_UP: Final = "확인할 예정 결제, 소득 변동, 또는 지출 계획이 있으면 알려 주세요."
_HISTORICAL_FOLLOW_UP: Final = "이전 코칭의 원인과 현재 봉투 장부를 분리해 확인했습니다."


class LanguageModel(Protocol):
    async def write(self, evidence: EvidenceInput) -> Wording: ...
    async def judge(self, evidence: EvidenceInput) -> Judgment: ...
    async def route(self, evidence: EvidenceInput) -> Routing: ...


class CoachingCore:
    def __init__(
        self, repository: Repository, model: LanguageModel, *, fdt_max_concurrency: int = 2
    ) -> None:
        """Keep the FDT worker limit explicit and independently configurable.

        This limit guards CPU-bound simulations only. It does not change a single
        calculation's paths, seed, period, or result; callers with a different
        measured deployment capacity can provide a bounded replacement value.
        """
        if not 1 <= fdt_max_concurrency <= 8:
            raise ValueError("fdt_max_concurrency_out_of_range")
        self.repository: Repository = repository
        self.model: LanguageModel = model
        self.engine: EngineAdapter = EngineAdapter()
        self.engine_limit: anyio.CapacityLimiter = anyio.CapacityLimiter(fdt_max_concurrency)

    async def twin(self, owner: str) -> JsonDocument:
        return JsonDocument.model_validate_json(await self.repository.load(owner, "twin"))

    async def receipt(self, twin: JsonDocument, request: ReviewRequest) -> Receipt:
        period = resolve_period(request.on_date, ThroughDate(end_date=request.through_date), "review")
        raw_request = JsonDocument.model_validate_json(request.model_dump_json(exclude_none=True))
        # Only the deterministic FDT review enters this stage. Repository, rendering,
        # and language-model time remain visible as separate request-timing components.
        with measure_fdt():
            result = await anyio.to_thread.run_sync(
                run_measured_fdt,
                lambda: self.engine.review(twin, raw_request),
                limiter=self.engine_limit,
            )
        identity = await anyio.to_thread.run_sync(self.engine.identity, twin)
        return Receipt(
            engine_commit=ENGINE_COMMIT,
            identity=identity,
            request=raw_request,
            result=result,
            trigger="requested_review",
            period=period,
        )

    async def numeric_receipt(
        self,
        twin: JsonDocument,
        identity: TwinIdentity,
        request: JsonDocument,
        period: ResolvedPeriod,
        *,
        replay: bool,
    ) -> Receipt:
        """Execute one requested FDT mode without first duplicating it as a review.

        The numeric result already contains the quantities, warnings, and period
        assumptions rendered to the user by ``numeric_text``.  A coaching review is
        a separate Monte-Carlo projection, so running it before the same explicit
        forecast/risk/goal request only adds latency and does not validate the
        numeric result.  The receipt records that the review was intentionally not
        executed instead of presenting an empty review as a successful calculation.
        """
        with measure_fdt():
            numeric_result = await anyio.to_thread.run_sync(
                run_measured_fdt,
                lambda: self.engine.numeric(twin, request),
                limiter=self.engine_limit,
            )
        return Receipt(
            engine_commit=ENGINE_COMMIT,
            identity=identity,
            request=JsonDocument(
                {
                    "on_date": identity.as_of,
                    "through_date": period.forecast_end.isoformat(),
                    "replay": replay,
                }
            ),
            result=JsonDocument({"status": "not_run", "reason": "numeric_operation"}),
            trigger="numeric_dialogue",
            numeric_request=request,
            numeric_result=numeric_result,
            period=period,
        )

    async def payment_receipt(self, twin: JsonDocument, facts: PaymentFacts | None) -> Receipt:
        identity = await anyio.to_thread.run_sync(self.engine.identity, twin)
        day = date.fromisoformat(identity.as_of)
        review = ReviewRequest(on_date=day, through_date=day + timedelta(days=7))
        receipt = await self.receipt(twin, review)
        return receipt.model_copy(update={"payment": facts})

    async def compose(
        self, receipt: Receipt, evidence: EvidenceInput, *, tone: Tone | None = None
    ) -> Coaching:
        """금액·날짜는 검증된 receipt로 작성하고 LLM은 보조 안내만 덧붙인다.

        근거가 한도를 넘거나 문장을 채택하지 못해도 금융 결과를 바꾸지 않는다.
        대체 문구의 출처·원인은 응답에 남겨 실제 모델 성공과 구분한다.
        예산 초과·근접·부족 예측 조언은 엔진 사실만으로 만든 결정형 문장이며 LLM이
        만들지 않는다. tone은 이 문장의 어투만 고르고 발동 조건은 바꾸지 않는다.
        """
        pieces = [authoritative_text(receipt), *purchase_verdict_text(receipt)]
        advice = deterministic_advice(receipt, tone=tone)
        if advice is not None:
            pieces.append(advice)
        answer_text = "\n".join(pieces)
        receipt_wording = authoritative_fdt_wording(receipt)
        if receipt_wording is not None:
            wording = receipt_wording
        else:
            wording_input = supplementary_evidence(evidence, answer_text)
            wording = (
                Wording(
                    text=TEMPLATE_TEXT, source="template", model="not_called", fallback_reason="context_limit"
                )
                if context_limited(wording_input)
                else await self.model.write(wording_input)
            )
        return Coaching(
            id=uuid4().hex,
            text=answer_text + "\n\n" + wording.text,
            wording_source=wording.source,
            model=wording.model,
            fallback_reason=wording.fallback_reason,
            receipt=receipt,
            created_at=time.time(),
        )


def coaching_writes(coaching: Coaching, *, notify: bool) -> tuple[Write, ...]:
    log = write("coaching/" + coaching.id, coaching)
    if not notify:
        return (log,)
    notification = Notification(
        event_id=uuid4().hex, coaching_id=coaching.id, text=coaching.text, created_at=coaching.created_at
    )
    return log, write("outbox/" + notification.event_id, notification)


def evidence_for(receipt: Receipt) -> EvidenceInput:
    return bounded_evidence(receipt)


def authoritative_fdt_wording(receipt: Receipt) -> Wording | None:
    """Keep complete FDT conversations independent of the optional language-model queue.

    ``authoritative_text`` has already checked the full numeric result against the
    Twin revision, request digest, period, and mode. A second model call is allowed
    to ask only a generic follow-up and cannot improve the financial result, so it
    must not delay an interactive prediction, risk, goal, what-if, or optimization
    response. A regular FDT review likewise already carries its checked next action
    and user warnings. Payment-triggered coaching keeps its existing wording path
    because it is tied to a separate payment-event conversation.
    """
    if receipt.trigger == "historical_coaching_followup":
        return Wording(text=_HISTORICAL_FOLLOW_UP, source="template", model="not_called")
    if receipt.numeric_request is not None and receipt.numeric_result is not None:
        mode = receipt.numeric_request.root.get("mode")
        follow_up = _NUMERIC_FOLLOW_UP.get(mode) if isinstance(mode, str) else None
        if follow_up is not None:
            return Wording(
                text=follow_up,
                source="template",
                model="not_called",
            )
    if receipt.trigger == "requested_review" and receipt.payment is None:
        return Wording(
            text=_REVIEW_FOLLOW_UP,
            source="template",
            model="not_called",
        )
    return None


def supplementary_evidence(evidence: EvidenceInput, answer_text: str) -> EvidenceInput:
    """Give the follow-up writer the exact displayed facts once, not both full analyses.

    Financial values have already passed the receipt renderer. The writer cannot
    recalculate them and needs only the displayed facts and recent conversation.
    The complete, immutable receipt is still returned and stored by compose().
    Tokenizer preflight remains mandatory: a character bound is not a token bound.
    """
    if context_limited(evidence):
        return evidence
    try:
        return EvidenceInput(
            question=evidence.question,
            history=evidence.history[-2:],
            facts_json=JsonDocument(
                {"basis": "displayed_receipt", "authoritative_answer": answer_text}
            ).model_dump_json(),
        )
    except ValidationError:
        return EvidenceInput(question=evidence.question, facts_json=LIMITED_CONTEXT)
