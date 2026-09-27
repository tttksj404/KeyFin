"""Freeze the actual stored FDT receipt, never a caller-supplied prediction."""

from datetime import datetime, time, timedelta
from math import isfinite
from typing import assert_never

from pydantic import ValidationError

from coaching_service.errors import ServiceError
from coaching_service.forecast_validation_contracts import Quantiles, Registration, RegistrationRequest, Tier
from coaching_service.forecast_validation_ingestion import IngestionStamp
from coaching_service.forecast_validation_observations import (
    SEOUL,
    baseline_for,
    has_future_records,
    raw_rows,
    source_digest,
)
from coaching_service.numeric_rendering import ForecastResult
from coaching_service.periods import ResolvedPeriod
from coaching_service.provenance import ENGINE_COMMIT
from coaching_service.repository import document
from coaching_service.schemas import Coaching, Frozen, JsonDocument, TwinIdentity


class ForecastSource(Frozen):
    coaching: Coaching
    twin: JsonDocument
    identity: TwinIdentity
    stamp: IngestionStamp | None


def checked_forecast(source: ForecastSource) -> tuple[ForecastResult, ResolvedPeriod]:
    """Verify the same source, target and inclusive date window as the displayed result."""
    receipt, identity = source.coaching.receipt, source.identity
    if receipt.numeric_result is None or receipt.numeric_request is None or receipt.period is None:
        raise ServiceError("validation_requires_forecast_receipt")
    try:
        result = ForecastResult.model_validate_json(receipt.numeric_result.model_dump_json())
    except ValidationError:
        raise ServiceError("validation_invalid_forecast_receipt") from None
    period = receipt.period
    if (
        receipt.identity != identity
        or result.twin_id != identity.twin_id
        or result.revision != identity.revision
        or result.input_digest != identity.input_digest
        or result.as_of.isoformat() != identity.as_of
        or period.reference_date != result.as_of
        or period.forecast_days != result.horizon_days
        or period.forecast_start != result.as_of + timedelta(days=1)
        or period.forecast_end != result.as_of + timedelta(days=result.horizon_days)
        or receipt.engine_commit != ENGINE_COMMIT
        or receipt.numeric_request.root.get("mode") != "forecast"
        or receipt.numeric_request.root.get("horizon_days", 90) != result.horizon_days
        or receipt.numeric_request.root.get("scenario") not in (None, {})
    ):
        raise ServiceError("validation_receipt_identity_or_period_mismatch", 409)
    if result.status == "insufficient_data":
        raise ServiceError("validation_forecast_unavailable")
    return result, period


def evidence_tier(request: RegistrationRequest, source: ForecastSource, deadline: float, now: float) -> Tier:
    match request.data_origin:
        case "synthetic":
            return "synthetic"
        case "historical_real":
            return "replay"
        case "backend_attested_real":
            if source.stamp is None or now >= deadline:
                raise ServiceError("validation_prospective_registration_too_late_or_unstamped", 409)
            return "prospective_attested"
        case unreachable:
            assert_never(unreachable)


def freeze_receipt(
    source: ForecastSource, request: RegistrationRequest, registered_at: float
) -> Registration:
    """Freeze a stored result; replay labels never provide independent real evidence."""
    coaching, twin, identity, stamp = source.coaching, source.twin, source.identity, source.stamp
    result, period = checked_forecast(source)
    metrics = tuple(result.metrics.get(f"total_expense_p{q}_krw") for q in (10, 50, 90))
    if any(
        metric is None or metric.unit != "KRW" or metric.basis != "simulation_consumption_only"
        for metric in metrics
    ):
        raise ServiceError("validation_target_metric_mismatch")
    prediction = Quantiles.model_validate(
        {f"p{q}": metric.value for q, metric in zip((10, 50, 90), metrics, strict=True) if metric is not None}
    )
    if not isfinite(coaching.created_at) or not 0 < coaching.created_at <= registered_at:
        raise ServiceError("validation_invalid_issue_time")
    rows = raw_rows(twin, identity.user_id)
    if (
        has_future_records(rows, registered_at)
        or result.as_of > datetime.fromtimestamp(registered_at, SEOUL).date()
    ):
        raise ServiceError("validation_future_input")
    if stamp is not None and (stamp.identity != identity or stamp.received_at > coaching.created_at):
        raise ServiceError("validation_ingestion_identity_or_time_mismatch", 409)
    start_timestamp = datetime.combine(period.forecast_start, time.min, SEOUL).timestamp()
    tier = evidence_tier(request, source, start_timestamp, registered_at)
    model = JsonDocument(result.model)
    return Registration(
        id=coaching.id,
        coaching_id=coaching.id,
        issued_at=coaching.created_at,
        registered_at=registered_at,
        cutoff=result.as_of,
        forecast_start=period.forecast_start,
        forecast_end=period.forecast_end,
        horizon_days=result.horizon_days,
        identity=identity,
        engine_commit=coaching.receipt.engine_commit,
        model=model,
        model_digest=source_digest(model),
        receipt_digest=source_digest(document(coaching.receipt)),
        ingestion_received_at=None if stamp is None else stamp.received_at,
        data_origin=request.data_origin,
        evidence_tier=tier,
        source_reference=request.source_reference,
        prediction=prediction,
        baseline=baseline_for(rows, result.as_of, result.horizon_days),
    )
