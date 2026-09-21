"""인증된 백엔드의 원래 월 편성 자료를 예측과 별도로 불변 저장한다."""

from collections.abc import Callable
from datetime import datetime, time
from uuid import uuid4

import anyio
from pydantic import ValidationError

from coaching_service.errors import ServiceError
from coaching_service.forecast_validation_month_contracts import (
    MonthlyBudgetPlan,
    MonthlyBudgetRequest,
    month_end,
)
from coaching_service.forecast_validation_observations import SEOUL, source_digest
from coaching_service.repository import Mutation, Repository, document, write
from coaching_service.schemas import JsonDocument
from coaching_service.store import Operation


class MonthlyBudgets:
    def __init__(self, repository: Repository, clock: Callable[[], float]) -> None:
        self.repository: Repository = repository
        self.clock: Callable[[], float] = clock

    async def get(self, owner: str, plan_id: str) -> MonthlyBudgetPlan:
        try:
            return MonthlyBudgetPlan.model_validate_json(
                await self.repository.load(owner, "forecast-budget/" + plan_id)
            )
        except ValidationError:
            raise ServiceError("validation_saved_budget_invalid", 409) from None

    async def register(self, op: Operation, request: MonthlyBudgetRequest) -> JsonDocument:
        async def action() -> Mutation:
            month_key = "forecast-budget-month/" + request.month_start.isoformat()
            if await anyio.to_thread.run_sync(self.repository.store.load, op.owner, month_key) is not None:
                raise ServiceError("validation_month_budget_already_registered", 409)
            now = self.clock()
            start = datetime.combine(request.month_start, time.min, SEOUL).timestamp()
            if request.approved_at > min(now, start):
                raise ServiceError("validation_original_budget_approval_too_late", 409)
            # 승인시각은 백엔드 주장일 뿐이다. 실제 수신시각은 서비스가 기록한다.
            plan = MonthlyBudgetPlan(
                id=uuid4().hex, month_start=request.month_start, month_end=month_end(request.month_start),
                approved_at=request.approved_at, received_at=now, data_origin=request.data_origin,
                source_reference=request.source_reference, source_digest=source_digest(document(request)),
                allocations=request.allocations, received_before_month_start=now <= start,
            )
            return Mutation(
                result=document(plan),
                writes=(
                    write("forecast-budget/" + plan.id, plan),
                    write(month_key, JsonDocument({"id": plan.id})),
                ),
            )

        return await self.repository.mutate(op, action)
