"""Frozen contracts for a receipt-based, delayed-outcome forecast audit."""

from typing import Literal

from pydantic import Field

from coaching_service.forecast_validation_month_contracts import (
    MonthlyEvaluationRequest,
    MonthlyRegistration,
    MonthlySettlement,
)
from coaching_service.forecast_validation_values import (
    Amount,
    Digest,
    EnvelopeName,
    Finite,
    Origin,
    Quantiles,
    Tier,
)
from coaching_service.periods import DateOnly
from coaching_service.schemas import Frozen, Identifier, JsonDocument, TwinIdentity

# 기존 호출자의 공용 값 타입 import 경로를 명시적으로 유지한다.
__all__ = [
    "Amount", "Baseline", "Digest", "EnvelopeMetric", "Finite", "MetricReport", "MetricRequest",
    "MetricValues", "ObservationRequest", "Origin", "Quantiles", "Registration", "RegistrationRequest",
    "Settlement", "Tier",
]


class RegistrationRequest(Frozen):
    coaching_id: Identifier
    data_origin: Origin
    source_reference: str = Field(min_length=1, max_length=200)
    monthly: MonthlyEvaluationRequest | None = None


class ObservationRequest(Frozen):
    """Backend completeness attestation; callers cannot submit an actual amount."""

    coverage_start: DateOnly
    coverage_end: DateOnly
    complete: Literal[True]
    source_reference: str = Field(min_length=1, max_length=200)


class Baseline(Frozen):
    method: Literal["observed_calendar_day_mean/v1"] = "observed_calendar_day_mean/v1"
    history_start: DateOnly
    history_end: DateOnly
    history_calendar_days: int = Field(ge=1)
    history_total_krw: Amount
    prediction_krw: Finite = Field(ge=0, le=10**14)


class Registration(Frozen):
    id: Identifier
    coaching_id: Identifier
    target: Literal["total_variable_consumption"] = "total_variable_consumption"
    target_version: Literal["purchase_time_consumption/v1"] = "purchase_time_consumption/v1"
    unit: Literal["KRW"] = "KRW"
    envelope: Literal["all"] = "all"
    issued_at: Finite
    registered_at: Finite
    cutoff: DateOnly
    forecast_start: DateOnly
    forecast_end: DateOnly
    horizon_days: int = Field(ge=1, le=90)
    identity: TwinIdentity
    engine_commit: str
    model: JsonDocument
    model_digest: Digest
    receipt_digest: Digest
    ingestion_received_at: Finite | None
    data_origin: Origin
    evidence_tier: Tier
    source_reference: str
    prediction: Quantiles
    baseline: Baseline
    monthly: MonthlyRegistration | None = None
    real_accuracy_validated: Literal[False] = False


class Settlement(Frozen):
    registration: Registration
    settled_at: Finite
    actual_krw: Amount
    actual_transaction_count: int = Field(ge=0)
    observed_identity: TwinIdentity
    observed_digest: Digest
    source_reference: str
    coverage_complete_backend_attested: Literal[True] = True
    independent_human_oracle: Literal[False] = False
    monthly: MonthlySettlement | None = None


class MetricValues(Frozen):
    sample_count: int = Field(ge=1)
    mae_krw: Finite
    wape: Finite | None
    bias_krw: Finite
    wis80_krw: Finite
    coverage80: Finite
    mean_interval_width_krw: Finite
    baseline_mae_krw: Finite
    baseline_wape: Finite | None
    baseline_bias_krw: Finite


class MetricRequest(Frozen):
    registration_ids: tuple[Identifier, ...] = Field(min_length=1, max_length=100)


class EnvelopeMetric(Frozen):
    envelope: EnvelopeName
    values: MetricValues
    target: Literal["future_variable_consumption_only"] = "future_variable_consumption_only"


class MetricReport(Frozen):
    registration_ids: tuple[str, ...]
    selection: Literal["explicit_settled_ids_not_population_sample"] = (
        "explicit_settled_ids_not_population_sample"
    )
    source_references: tuple[str, ...]
    target: Literal["total_variable_consumption"] = "total_variable_consumption"
    unit: Literal["KRW"] = "KRW"
    horizon_days: int
    model_digest: Digest
    engine_commit: str
    baseline_method: Literal["observed_calendar_day_mean/v1"] = "observed_calendar_day_mean/v1"
    evidence_tier: Tier
    data_origin: Origin
    values: MetricValues
    overlapping_windows: bool
    non_overlapping_window_count: int
    confidence_interval: Literal["not_estimated_single_owner_dependent_windows"] = (
        "not_estimated_single_owner_dependent_windows"
    )
    real_accuracy_validated: Literal[False] = False
    envelopes: tuple[EnvelopeMetric, ...] | None = None
    # 응답이 검증한 원장 snapshot이다. 반환 뒤 미래 이벤트까지 최신임을 보장하지 않는다.
    observed_identity: TwinIdentity | None = None
    observed_checked_at: Finite | None = None
