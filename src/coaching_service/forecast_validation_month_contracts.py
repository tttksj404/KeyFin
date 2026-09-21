"""불변 월 편성과 당시 예측·확정소비를 서로 다른 기준으로 보존한다."""

import calendar
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from coaching_service.forecast_validation_values import (
    ENVELOPES,
    Amount,
    Digest,
    EnvelopeName,
    Finite,
    Origin,
    Quantiles,
)
from coaching_service.periods import DateOnly
from coaching_service.schemas import Frozen, Identifier

BudgetAmount = Annotated[int, Field(strict=True, ge=0, le=10**12)]


class BudgetAllocation(Frozen):
    envelope: EnvelopeName
    original_budget_krw: BudgetAmount
    # 계획한 절약은 사용자 정책 목표이며 예측값이나 실제 절약 성과가 아니다.
    planned_saving_krw: BudgetAmount | None = None


class MonthlyBudgetRequest(Frozen):
    month_start: DateOnly
    approved_at: Finite = Field(gt=0, strict=True)
    data_origin: Origin
    source_reference: str = Field(min_length=1, max_length=200)
    allocations: tuple[BudgetAllocation, ...] = Field(min_length=7, max_length=7)

    @model_validator(mode="after")
    def complete_month_plan(self) -> Self:
        if self.month_start.day != 1:
            raise ValueError("budget_requires_month_start")
        if {row.envelope for row in self.allocations} != set(ENVELOPES):
            raise ValueError("budget_requires_seven_unique_envelopes")
        return self


class MonthlyBudgetPlan(Frozen):
    id: Identifier
    month_start: DateOnly
    month_end: DateOnly
    approved_at: Finite
    received_at: Finite
    data_origin: Origin
    source_reference: str
    source_digest: Digest
    allocations: tuple[BudgetAllocation, ...] = Field(min_length=7, max_length=7)
    received_before_month_start: bool
    independent_approval_verified: Literal[False] = False

    @model_validator(mode="after")
    def seven_unique_allocations(self) -> Self:
        # 저장 문서도 요청과 같은 완전성을 지킨다. 손상된 편성은 미등록이 아니다.
        if {row.envelope for row in self.allocations} != set(ENVELOPES):
            raise ValueError("budget_requires_seven_unique_envelopes")
        return self


class MonthlyEvaluationRequest(Frozen):
    budget_plan_id: Identifier | None = None
    history_coverage_start: DateOnly
    history_coverage_end: DateOnly
    history_complete: Literal[True]
    source_reference: str = Field(min_length=1, max_length=200)


class EnvelopeObservation(Frozen):
    envelope: EnvelopeName
    consumption_krw: Amount
    consumption_count: int = Field(ge=0)
    budget_used_krw: Amount
    budget_transaction_count: int = Field(ge=0)
    # 이전 저장 문서의 부재는 0원으로 단정하지 않는다.
    budget_excluded_consumption_krw: Amount | None = None


class FrozenEnvelopeForecast(Frozen):
    envelope: EnvelopeName
    future_prediction: Quantiles
    month_prediction: Quantiles
    baseline_future_krw: Finite = Field(ge=0, le=10**14)
    observed_before_forecast: EnvelopeObservation

    @model_validator(mode="after")
    def same_envelope(self) -> Self:
        if self.observed_before_forecast.envelope != self.envelope:
            raise ValueError("forecast_observation_envelope_mismatch")
        return self


class MonthlyRegistration(Frozen):
    target_version: Literal["seven_envelope_variable_consumption/v1"] = (
        "seven_envelope_variable_consumption/v1"
    )
    month_start: DateOnly
    month_end: DateOnly
    history_source_reference: str
    history_digest: Digest
    # 과거 저장 문서에는 없을 수 있다. 조회를 유지하고 정산/재채점 시 명시적으로 막는다.
    policy_sha256: Digest | None = None
    history_complete_backend_attested: Literal[True] = True
    budget_plan: MonthlyBudgetPlan | None
    forecasts: tuple[FrozenEnvelopeForecast, ...] = Field(min_length=7, max_length=7)
    budget_basis: Literal["original_approved_allocation_not_remaining_balance"] = (
        "original_approved_allocation_not_remaining_balance"
    )
    prediction_basis: Literal["observed_month_consumption_plus_future_consumption"] = (
        "observed_month_consumption_plus_future_consumption"
    )
    usage_basis: Literal["confirmed_month_consumption_with_exclude_tag_NONE"] = (
        "confirmed_month_consumption_with_exclude_tag_NONE"
    )

    @model_validator(mode="after")
    def seven_unique_forecasts(self) -> Self:
        if {row.envelope for row in self.forecasts} != set(ENVELOPES):
            raise ValueError("registration_requires_seven_unique_envelopes")
        return self


class BudgetComparison(Frozen):
    forecast_target: Literal["future_total_variable_consumption"] = "future_total_variable_consumption"
    budget_target: Literal["full_month_consumption_with_exclude_tag_NONE"] = (
        "full_month_consumption_with_exclude_tag_NONE"
    )
    observed_spending_basis: Literal["aligned", "different"]
    diagnosis: Literal[
        "indeterminate_target_mismatch", "indeterminate_missing_budget", "indeterminate_causal_evidence",
    ]
    causal_attribution_established: Literal[False] = False


class EnvelopeComparison(Frozen):
    envelope: EnvelopeName
    future_actual: EnvelopeObservation
    month_actual: EnvelopeObservation
    future_error_krw: int
    future_absolute_error_krw: Amount
    baseline_future_absolute_error_krw: Finite
    original_budget_krw: BudgetAmount | None
    budget_usage_ratio: Finite | None
    budget_remaining_krw: int | None
    budget_state: Literal["not_registered", "zero_budget_unused", "zero_budget_exceeded", "within", "over"]
    planned_saving_krw: BudgetAmount | None
    # 새 진단을 만들지 않았던 과거 정산은 명시적으로 미평가 상태를 유지한다.
    budget_comparison: BudgetComparison | None = None

    @model_validator(mode="after")
    def same_envelope(self) -> Self:
        if self.future_actual.envelope != self.envelope or self.month_actual.envelope != self.envelope:
            raise ValueError("comparison_observation_envelope_mismatch")
        return self


class MonthlySettlement(Frozen):
    month_start: DateOnly
    month_end: DateOnly
    observations_digest: Digest
    comparisons: tuple[EnvelopeComparison, ...] = Field(min_length=7, max_length=7)
    saving_effect_estimated: Literal[False] = False

    @model_validator(mode="after")
    def seven_unique_comparisons(self) -> Self:
        if {row.envelope for row in self.comparisons} != set(ENVELOPES):
            raise ValueError("settlement_requires_seven_unique_envelopes")
        return self


def month_end(day: DateOnly) -> DateOnly:
    return day.replace(day=calendar.monthrange(day.year, day.month)[1])
