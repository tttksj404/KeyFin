"""One atomic financial event, decision receipt, coaching log, and outbox commit."""

import anyio

from coaching_service.coaching import CoachingCore, coaching_writes, evidence_for
from coaching_service.errors import ServiceError
from coaching_service.evidence import context_limited
from coaching_service.forecast_validation_ingestion import ingestion_writes
from coaching_service.llm_contract import Judgment
from coaching_service.payments import Detection, Ledger, reconcile_cancellation, reduce_payment
from coaching_service.repository import Mutation, document, write
from coaching_service.schemas import (
    BUDGET_CONFIG_KEY,
    Bootstrap,
    BudgetConfig,
    EventRequest,
    EventResult,
    JsonDocument,
)
from coaching_service.store import Operation


class Events:
    def __init__(self, core: CoachingCore) -> None:
        self.core: CoachingCore = core

    async def bootstrap(self, op: Operation, request: Bootstrap) -> JsonDocument:
        async def action() -> Mutation:
            if len({row.envelope for row in request.envelopes}) != len(request.envelopes):
                raise ServiceError("duplicate_envelope")
            twin = await anyio.to_thread.run_sync(self.core.engine.create, request, op.owner)
            identity = await anyio.to_thread.run_sync(self.core.engine.identity, twin)
            ingress = await ingestion_writes(self.core.repository, op.owner, identity, op.digest)
            # 예산 시작일은 고정 FDT snapshot이 아니라 서비스측 별도 키에 보관한다.
            # 생략하면 기록하지 않아 기간 계산이 1일로 폴백(기존 동작)한다.
            budget_config = (
                (write(BUDGET_CONFIG_KEY, BudgetConfig(start_day=request.budget_start_day)),)
                if request.budget_start_day is not None
                else ()
            )
            return Mutation(
                result=document(identity),
                writes=(
                    write("twin", twin),
                    write("ledger", Ledger(envelopes=request.envelopes)),
                    *budget_config,
                    *ingress,
                ),
            )

        return await self.core.repository.mutate(op, action)

    async def apply(self, op: Operation, request: EventRequest) -> JsonDocument:
        """revision을 확인하고 Twin·원장·코칭·outbox 변경을 검증한 뒤 한 번에 저장한다.

        중간 단계는 메모리의 Mutation만 만든다. 결제·취소 처리 중 예외가 발생하면
        일부 원장이나 완료 키를 남기지 않도록 Repository가 마지막 commit을 맡는다.
        """
        async def action() -> Mutation:
            before = await self.core.twin(op.owner)
            identity = await anyio.to_thread.run_sync(self.core.engine.identity, before)
            if identity.revision != request.expected_revision:
                raise ServiceError("revision_conflict", 409)
            after = await anyio.to_thread.run_sync(
                self.core.engine.update, before, request.event, request.snapshot_event
            )
            detection = await self.detect(op.owner, before, after, request)
            identity = await anyio.to_thread.run_sync(self.core.engine.identity, after)
            ingress = await ingestion_writes(self.core.repository, op.owner, identity, op.digest)
            result = EventResult(identity=identity, detection=detection.reason, payment=detection.facts)
            changes = (write("twin", after), write("ledger", detection.ledger), *ingress)
            if detection.reason not in {"p0_half_balance", "p1_ambiguous"}:
                return Mutation(result=document(result), writes=changes)
            receipt = await self.core.payment_receipt(after, detection.facts)
            receipt = receipt.model_copy(update={"trigger": detection.reason})
            if detection.reason == "p1_ambiguous":
                evidence = evidence_for(receipt)
                judgment = (
                    Judgment(
                        decision="needs_data",
                        reason_code="insufficient_context",
                        confidence=0.0,
                        source="template",
                        fallback_reason="context_limit",
                    )
                    if context_limited(evidence)
                    else await self.core.model.judge(evidence)
                )
                result = result.model_copy(update={"judgment": document(judgment)})
                # 0.8은 알림 채택 정책이다. 모델의 자체 confidence를 실제 정확도나
                # 교정된 확률로 해석하지 않으며 fallback 판단으로 알림을 만들지 않는다.
                if judgment.decision != "coach" or judgment.confidence < 0.8 or judgment.source != "llm":
                    return Mutation(result=document(result), writes=changes)
                receipt = receipt.model_copy(update={"trigger": "p1_context_concern"})
            coaching = await self.core.compose(receipt, evidence_for(receipt))
            result = result.model_copy(update={"coaching": coaching})
            return Mutation(
                result=document(result), writes=(*changes, *coaching_writes(coaching, notify=True))
            )

        return await self.core.repository.mutate(op, action)

    async def detect(
        self, owner: str, before: JsonDocument, after: JsonDocument, request: EventRequest
    ) -> Detection:
        event = request.event
        ledger = Ledger.model_validate_json(await self.core.repository.load(owner, "ledger"))
        kind = event.root.get("type")
        if kind == "snapshot":
            return Detection(ledger=ledger, reason="snapshot_updated")
        raw = event.root.get("transaction")
        transaction_id = (
            raw.get("transaction_id") if isinstance(raw, dict) else event.root.get("transaction_id")
        )
        transactions = await anyio.to_thread.run_sync(self.core.engine.transactions, after)
        transaction = next((row for row in transactions if row.id == transaction_id), None)
        if transaction is None:
            raise ServiceError("event_transaction_not_found")
        old_rows = await anyio.to_thread.run_sync(self.core.engine.transactions, before)
        old = next((row for row in old_rows if row.id == transaction.id), None)
        if old == transaction:
            return Detection(ledger=ledger, reason="duplicate_transaction")
        if request.cancellation_balance is not None:
            if kind != "cancel_transaction":
                raise ServiceError("cancellation_balance_requires_cancel_event")
            return reconcile_cancellation(ledger, transaction, request.cancellation_balance)
        if (
            old is not None
            and old.active
            and not transaction.active
            and old.budget_amount_krw > 0
            and not any(row.transaction_id == old.id for row in ledger.debits)
        ):
            raise ServiceError("cancel_requires_authoritative_envelope_balance", 409)
        return reduce_payment(ledger, transaction, transactions)
