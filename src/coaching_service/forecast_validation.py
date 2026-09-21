"""Immutable forecast registration and later, backend-attested outcome settlement."""

import time
from collections.abc import Callable
from datetime import datetime, timedelta
from datetime import time as day_time

import anyio
from pydantic import ValidationError

from coaching_service.coaching import CoachingCore
from coaching_service.errors import ServiceError
from coaching_service.forecast_validation_budgets import MonthlyBudgets
from coaching_service.forecast_validation_contracts import (
    MetricReport,
    MetricRequest,
    ObservationRequest,
    Registration,
    RegistrationRequest,
    Settlement,
)
from coaching_service.forecast_validation_ingestion import IngestionStamp, ingestion_key
from coaching_service.forecast_validation_metrics import calculate_metrics, envelope_metrics
from coaching_service.forecast_validation_month import freeze_month, require_current_month, settle_month
from coaching_service.forecast_validation_month_policy import require_month_policy
from coaching_service.forecast_validation_observations import (
    SEOUL,
    has_future_records,
    observed_total,
    raw_rows,
    source_digest,
)
from coaching_service.forecast_validation_receipts import ForecastSource, freeze_receipt
from coaching_service.repository import Mutation, document, write
from coaching_service.schemas import Coaching, JsonDocument, TwinIdentity
from coaching_service.store import Operation


class ForecastValidation:
    def __init__(self, core: CoachingCore, clock: Callable[[], float] = time.time) -> None:
        self.core: CoachingCore = core
        self.clock: Callable[[], float] = clock

    async def register(self, op: Operation, request: RegistrationRequest) -> JsonDocument:
        async def action() -> Mutation:
            repository = self.core.repository
            key = "forecast-registration/" + request.coaching_id
            if await anyio.to_thread.run_sync(repository.store.load, op.owner, key) is not None:
                raise ServiceError("forecast_already_registered", 409)
            coaching = Coaching.model_validate_json(
                await repository.load(op.owner, "coaching/" + request.coaching_id)
            )
            twin = await self.core.twin(op.owner)
            identity = await anyio.to_thread.run_sync(self.core.engine.identity, twin)
            stamp_json = await anyio.to_thread.run_sync(
                repository.store.load, op.owner, ingestion_key(identity.revision)
            )
            stamp = None if stamp_json is None else IngestionStamp.model_validate_json(stamp_json)
            try:
                source = ForecastSource(coaching=coaching, twin=twin, identity=identity, stamp=stamp)
                frozen = freeze_receipt(
                    source,
                    request,
                    self.clock(),
                )
                if request.monthly is not None:
                    plan = None if request.monthly.budget_plan_id is None else await MonthlyBudgets(
                        repository, self.clock
                    ).get(op.owner, request.monthly.budget_plan_id)
                    month = freeze_month(source, frozen, request.monthly, plan, raw_rows(twin, op.owner))
                    frozen = frozen.model_copy(update={"monthly": month})
            except ValidationError:
                raise ServiceError("validation_source_contract_invalid") from None
            return Mutation(result=document(frozen), writes=(write(key, frozen),))

        return await self.core.repository.mutate(op, action)

    async def registration(self, owner: str, registration_id: str) -> Registration:
        try:
            return Registration.model_validate_json(
                await self.core.repository.load(owner, "forecast-registration/" + registration_id)
            )
        except ValidationError:
            raise ServiceError("validation_saved_registration_invalid", 409) from None

    async def settlement(self, owner: str, registration_id: str) -> Settlement:
        try:
            return Settlement.model_validate_json(
                await self.core.repository.load(owner, "forecast-settlement/" + registration_id)
            )
        except ValidationError:
            raise ServiceError("validation_saved_settlement_invalid", 409) from None

    async def settle(self, op: Operation, registration_id: str, request: ObservationRequest) -> JsonDocument:
        async def action() -> Mutation:
            key = "forecast-settlement/" + registration_id
            if await anyio.to_thread.run_sync(self.core.repository.store.load, op.owner, key) is not None:
                raise ServiceError("forecast_already_settled", 409)
            frozen = await self.registration(op.owner, registration_id)
            now = self.clock()
            deadline = datetime.combine(frozen.forecast_end + timedelta(days=1), day_time.min, SEOUL)
            if now < deadline.timestamp():
                raise ServiceError("validation_outcome_not_mature", 409)
            coverage_start = frozen.forecast_start if frozen.monthly is None else frozen.monthly.month_start
            if request.coverage_start != coverage_start or request.coverage_end != frozen.forecast_end:
                raise ServiceError("validation_coverage_period_mismatch")
            twin = await self.core.twin(op.owner)
            identity = await anyio.to_thread.run_sync(self.core.engine.identity, twin)
            if (
                identity.as_of < frozen.forecast_end.isoformat()
                or identity.revision <= frozen.identity.revision
            ):
                raise ServiceError("validation_observation_not_updated", 409)
            stamp = IngestionStamp.model_validate_json(
                await self.core.repository.load(op.owner, ingestion_key(identity.revision))
            )
            if stamp.identity != identity or not frozen.registered_at <= stamp.received_at <= now:
                raise ServiceError("validation_observation_stamp_mismatch", 409)
            try:
                rows = raw_rows(twin, op.owner)
                if (
                    has_future_records(rows, now)
                    or identity.as_of > datetime.fromtimestamp(now, SEOUL).date().isoformat()
                ):
                    raise ServiceError("validation_future_observation")
                actual = observed_total(rows, frozen.forecast_start, frozen.forecast_end)
                monthly = settle_month(frozen, rows)
            except ValidationError:
                raise ServiceError("validation_observation_contract_invalid") from None
            settled = Settlement(
                registration=frozen,
                settled_at=now,
                actual_krw=actual.total_krw,
                actual_transaction_count=actual.transaction_count,
                observed_identity=identity,
                observed_digest=source_digest(twin),
                source_reference=request.source_reference,
                monthly=monthly,
            )
            return Mutation(result=document(settled), writes=(write(key, settled),))

        return await self.core.repository.mutate(op, action)

    async def require_current_outcomes(
        self, owner: str, settlements: tuple[Settlement, ...],
    ) -> tuple[str, TwinIdentity]:
        """Reject revised window totals without invalidating unrelated later transactions.

        The original settlement remains an immutable historical record. A fresh
        report must match today's raw purchase sum AND count for each same window;
        changed global Twin digests alone are not evidence of a revised outcome.
        """
        twin = await self.core.twin(owner)
        identity = await anyio.to_thread.run_sync(self.core.engine.identity, twin)
        try:
            rows = raw_rows(twin, owner)
            for settlement in settlements:
                frozen = settlement.registration
                require_current_month(settlement, rows)
                if identity.as_of < frozen.forecast_end.isoformat():
                    raise ServiceError("validation_observation_revised", 409)
                current = observed_total(rows, frozen.forecast_start, frozen.forecast_end)
                if (current.total_krw, current.transaction_count) != (
                    settlement.actual_krw,
                    settlement.actual_transaction_count,
                ):
                    raise ServiceError("validation_observation_revised", 409)
        except ValidationError:
            raise ServiceError("validation_observation_contract_invalid") from None
        return source_digest(twin), identity

    async def metrics(self, owner: str, request: MetricRequest) -> MetricReport:
        """Only explicit settled IDs from one comparable cohort enter a report.

        Single-owner rolling windows are dependent. Counts/overlap are disclosed;
        there is no iid confidence interval or automatic production promotion.
        """
        if len(set(request.registration_ids)) != len(request.registration_ids):
            raise ServiceError("validation_duplicate_registration")
        settlements = tuple([await self.settlement(owner, key) for key in request.registration_ids])
        forecasts = tuple(row.registration for row in settlements)
        first = forecasts[0]
        if any(
            (
                row.target_version,
                row.horizon_days,
                row.model_digest,
                row.engine_commit,
                row.evidence_tier,
                row.data_origin,
                row.baseline.method,
            )
            != (
                first.target_version,
                first.horizon_days,
                first.model_digest,
                first.engine_commit,
                first.evidence_tier,
                first.data_origin,
                first.baseline.method,
            )
            for row in forecasts
        ):
            raise ServiceError("validation_incomparable_cohort")
        checked_digest, checked_identity = await self.require_current_outcomes(owner, settlements)
        ordered = sorted(forecasts, key=lambda row: (row.forecast_end, row.forecast_start))
        independent = 0
        last_end = None
        for row in ordered:
            if last_end is None or row.forecast_start > last_end:
                independent += 1
                last_end = row.forecast_end
        report = MetricReport(
            registration_ids=request.registration_ids,
            source_references=tuple(row.source_reference for row in forecasts),
            horizon_days=first.horizon_days,
            model_digest=first.model_digest,
            engine_commit=first.engine_commit,
            evidence_tier=first.evidence_tier,
            data_origin=first.data_origin,
            values=calculate_metrics(
                tuple(row.prediction for row in forecasts),
                tuple(row.actual_krw for row in settlements),
                tuple(row.baseline.prediction_krw for row in forecasts),
            ),
            envelopes=envelope_metrics(settlements),
            overlapping_windows=independent < len(forecasts),
            non_overlapping_window_count=independent,
        )
        # 최초 조회와 thread 경계 사이에 이벤트가 확정될 수 있으므로 계산 뒤 다시 확인한다.
        # 마지막 read 시점의 일관성만 보장한다. 이 응답 이후의 거래는 다음 조회 대상이다.
        if source_digest(await self.core.twin(owner)) != checked_digest:
            raise ServiceError("validation_observation_changed_during_metrics", 409)
        for frozen in forecasts:
            if frozen.monthly is not None:
                require_month_policy(frozen.monthly)
        return report.model_copy(update={
            "observed_identity": checked_identity, "observed_checked_at": self.clock(),
        })
