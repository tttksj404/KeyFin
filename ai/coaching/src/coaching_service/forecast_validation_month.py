"""당월 잔여기간 예측과 월 전체의 예산 사용을 연결하되 목표별로 평가한다."""

from pydantic import Field, TypeAdapter

from coaching_service.errors import ServiceError
from coaching_service.forecast_validation_contracts import Registration, Settlement
from coaching_service.forecast_validation_month_contracts import (
    BudgetComparison,
    EnvelopeComparison,
    FrozenEnvelopeForecast,
    MonthlyBudgetPlan,
    MonthlyEvaluationRequest,
    MonthlyRegistration,
    MonthlySettlement,
    month_end,
)
from coaching_service.forecast_validation_month_observations import observed_envelopes, window_digest
from coaching_service.forecast_validation_month_policy import observation_policy_sha256, require_month_policy
from coaching_service.forecast_validation_observations import RawTransaction
from coaching_service.forecast_validation_receipts import ForecastSource, checked_forecast
from coaching_service.forecast_validation_values import ENVELOPES, Amount, EnvelopeName, Quantiles
from coaching_service.schemas import Frozen


class ForecastEnvelope(Frozen):
    envelope: EnvelopeName
    p10: Amount = Field(alias="p10_krw")
    p50: Amount = Field(alias="p50_krw")
    p90: Amount = Field(alias="p90_krw")


def freeze_month(
    source: ForecastSource, frozen: Registration, spec: MonthlyEvaluationRequest,
    plan: MonthlyBudgetPlan | None, rows: tuple[RawTransaction, ...],
) -> MonthlyRegistration:
    policy = observation_policy_sha256()
    result, period = checked_forecast(source)
    start, end = frozen.cutoff.replace(day=1), month_end(frozen.cutoff)
    if period.forecast_end != end or period.forecast_start.month != frozen.cutoff.month:
        raise ServiceError("validation_requires_same_month_end_forecast")
    if spec.history_coverage_start != start or spec.history_coverage_end != frozen.cutoff:
        raise ServiceError("validation_month_history_coverage_mismatch")
    if min(row.transaction_date for row in rows) > start:
        raise ServiceError("validation_month_history_missing")
    if plan is not None:
        if plan.month_start != start or plan.month_end != end or plan.data_origin != frozen.data_origin:
            raise ServiceError("validation_budget_month_or_origin_mismatch")
        if plan.received_at > frozen.issued_at:
            raise ServiceError("validation_budget_received_after_forecast", 409)
        if frozen.evidence_tier == "prospective_attested" and not plan.received_before_month_start:
            raise ServiceError("validation_prospective_budget_received_too_late", 409)
    predictions = TypeAdapter(tuple[ForecastEnvelope, ...]).validate_python(result.datasets.get("envelopes"))
    if len(predictions) != 7 or {row.envelope for row in predictions} != set(ENVELOPES):
        raise ServiceError("validation_requires_seven_envelope_predictions")
    lookup = {row.envelope: row for row in predictions}
    before = observed_envelopes(rows, start, frozen.cutoff)
    history_start = min(row.transaction_date for row in rows)
    history = {row.envelope: row for row in observed_envelopes(rows, history_start, frozen.cutoff)}
    days = (frozen.cutoff - history_start).days + 1
    forecasts = tuple(
        FrozenEnvelopeForecast(
            envelope=row.envelope,
            future_prediction=Quantiles(
                p10=lookup[row.envelope].p10, p50=lookup[row.envelope].p50, p90=lookup[row.envelope].p90,
            ),
            month_prediction=Quantiles(
                p10=row.consumption_krw + lookup[row.envelope].p10,
                p50=row.consumption_krw + lookup[row.envelope].p50,
                p90=row.consumption_krw + lookup[row.envelope].p90,
            ),
            baseline_future_krw=history[row.envelope].consumption_krw / days * frozen.horizon_days,
            observed_before_forecast=row,
        )
        for row in before
    )
    month = MonthlyRegistration(
        month_start=start, month_end=end, history_source_reference=spec.source_reference,
        history_digest=window_digest(rows, start, frozen.cutoff), budget_plan=plan, forecasts=forecasts,
        policy_sha256=policy,
    )
    require_month_policy(month)
    return month


def settle_month(frozen: Registration, rows: tuple[RawTransaction, ...]) -> MonthlySettlement | None:
    month = frozen.monthly
    if month is None:
        return None
    require_month_policy(month)
    if window_digest(rows, month.month_start, frozen.cutoff) != month.history_digest:
        raise ServiceError("validation_month_history_revised", 409)
    future = {
        row.envelope: row for row in observed_envelopes(rows, frozen.forecast_start, frozen.forecast_end)
    }
    whole = {row.envelope: row for row in observed_envelopes(rows, month.month_start, month.month_end)}
    forecasts = {row.envelope: row for row in month.forecasts}
    if len(month.forecasts) != 7 or set(forecasts) != set(ENVELOPES):
        raise ServiceError("validation_saved_registration_invalid", 409)
    budgets = {} if month.budget_plan is None else {
        row.envelope: row for row in month.budget_plan.allocations
    }
    comparisons: list[EnvelopeComparison] = []
    # 봉투 이름이 조인 키다. 저장 배열의 순서·향후 표시 순서가 계산에 영향을 주지 않는다.
    for name in ENVELOPES:
        prediction, actual, monthly = forecasts[name], future[name], whole[name]
        budget = budgets.get(actual.envelope)
        limit = None if budget is None else budget.original_budget_krw
        error = prediction.future_prediction.p50 - actual.consumption_krw
        comparisons.append(EnvelopeComparison(
            envelope=actual.envelope, future_actual=actual, month_actual=monthly,
            future_error_krw=error, future_absolute_error_krw=abs(error),
            baseline_future_absolute_error_krw=abs(prediction.baseline_future_krw - actual.consumption_krw),
            original_budget_krw=limit,
            budget_usage_ratio=None if limit in (None, 0) else monthly.budget_used_krw / limit,
            budget_remaining_krw=None if limit is None else limit - monthly.budget_used_krw,
            budget_state=(
                "not_registered" if limit is None else
                "zero_budget_unused" if limit == 0 and monthly.budget_used_krw == 0 else
                "zero_budget_exceeded" if limit == 0 else
                "over" if monthly.budget_used_krw > limit else "within"
            ),
            planned_saving_krw=None if budget is None else budget.planned_saving_krw,
            budget_comparison=BudgetComparison(
                observed_spending_basis=(
                    "different" if monthly.consumption_krw > monthly.budget_used_krw else "aligned"
                ),
                diagnosis=(
                    "indeterminate_missing_budget" if limit is None else
                    "indeterminate_target_mismatch" if monthly.consumption_krw > monthly.budget_used_krw
                    else "indeterminate_causal_evidence"
                ),
            ),
        ))
    require_month_policy(month)
    return MonthlySettlement(
        month_start=month.month_start, month_end=month.month_end,
        observations_digest=window_digest(rows, month.month_start, month.month_end),
        comparisons=tuple(comparisons),
    )


def require_current_month(settlement: Settlement, rows: tuple[RawTransaction, ...]) -> None:
    if settlement.registration.monthly is not None:
        require_month_policy(settlement.registration.monthly)
    month = settlement.monthly
    if (
        month is not None
        and window_digest(rows, month.month_start, month.month_end) != month.observations_digest
    ):
        raise ServiceError("validation_observation_revised", 409)
