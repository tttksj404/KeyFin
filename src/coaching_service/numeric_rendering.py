"""Render only typed, receipt-bound numeric engine facts."""

from __future__ import annotations

import json
from hashlib import sha256
from math import isfinite
from typing import TYPE_CHECKING, Annotated, ClassVar, Final, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, JsonValue, TypeAdapter, ValidationError, model_validator

from coaching_service.periods import DateOnly  # noqa: TC001 - Pydantic resolves this at runtime

if TYPE_CHECKING:
    from coaching_service.schemas import Receipt

Mode: TypeAlias = Literal["forecast", "what_if", "goal", "risk", "optimize"]
Status: TypeAlias = Literal["ok", "partial", "insufficient_data"]
Unit: TypeAlias = Literal["KRW", "probability", "count", "ratio", "days", "months"]
Number: TypeAlias = int | float
Text = Annotated[str, Field(min_length=1, max_length=2000)]

_INVALID_RESULT = "수치 분석 결과의 계약을 확인할 수 없어 금액·비율을 표시하지 않습니다."
_LIMIT = (
    "이 수치는 입력 자료와 조건부 모델 경로에 따른 추정이며, "
    "실제 미래를 보장하거나 외부 검증된 확률을 뜻하지 않습니다."
)


class StrictContract(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
        allow_inf_nan=False,
    )


class Metric(StrictContract):
    value: Number | None
    unit: Unit
    basis: Annotated[str, Field(min_length=1, max_length=200)]
    method: Annotated[str, Field(min_length=1, max_length=200)]
    evidence: tuple[Annotated[str, Field(min_length=1, max_length=200)], ...] = Field(max_length=100)


class EngineWarning(StrictContract):
    code: Annotated[str, Field(min_length=1, max_length=200)]
    message: str
    details: dict[str, JsonValue]


class WhatIfDecision(StrictContract):
    branch_mutates_twin: Literal[False]
    comparison_method: Literal["paired_common_random_numbers"]
    intervention: dict[str, JsonValue]
    causal_effect_claim: Literal[False]


class GoalDecision(StrictContract):
    goal_basis: Literal["cash_minus_card_payable_minus_reserve"]
    feasibility: Literal["unknown", "meets_threshold", "below_threshold"]
    fixed_monthly_p50_krw: int | None
    deadline: DateOnly | None = None
    required_success_probability: Number | None = None
    external_income_installment_days: tuple[Annotated[int, Field(ge=1)], ...] = ()
    external_income_note: str | None = None


class OptimizeDecision(StrictContract):
    feasibility: Literal["unknown", "feasible", "infeasible"]
    selected_candidate_id: str | None
    fixed_monthly_p50_krw: int | None
    selected_reductions: dict[str, Number] | None = None
    target_krw: int | None = None
    reserve_krw: int | None = None
    required_joint_success: Number | None = None
    maximum_any_account_shortfall: Number | None = None
    optimality_scope: Literal["EXHAUSTIVE_FINITE_GRID_ONLY"] | None = None
    objective: Literal["MIN_EXPECTED_CONSUMPTION_REDUCTION"] | None = None
    protected_fixed_and_recurring: Literal[True] | None = None
    executed: Literal[False] | None = None


class NumericResult(StrictContract):
    """The complete top-level FDT result, with mode-specific facts checked below.

    The engine remains the source of every amount. This adapter rejects drift or
    mismatched receipt identity instead of filling a missing metric with zero.
    """

    schema_version: Literal["1.0"]
    status: Status
    twin_id: Annotated[str, Field(min_length=1)]
    revision: Annotated[int, Field(ge=0)]
    as_of: DateOnly
    horizon_days: Annotated[int, Field(ge=1, le=90)]
    model: dict[str, JsonValue]
    input_digest: Annotated[str, Field(min_length=1)]
    assumptions: tuple[dict[str, JsonValue], ...] = Field(max_length=200)
    warnings: tuple[EngineWarning, ...] = Field(max_length=200)
    limitations: tuple[Text, ...] = Field(min_length=1, max_length=50)
    metrics: dict[str, Metric]
    datasets: dict[str, JsonValue]
    visualizations: tuple[dict[str, JsonValue], ...]
    required_inputs: tuple[Annotated[str, Field(min_length=1, max_length=200)], ...] = Field(
        default=(), max_length=100
    )


class ForecastResult(NumericResult):
    mode: Literal["forecast"]

    @model_validator(mode="after")
    def validate_forecast(self) -> ForecastResult:
        values = (
            _money(self, "expected_expense_krw"),
            _money(self, "total_expense_p10_krw"),
            _money(self, "total_expense_p50_krw"),
            _money(self, "total_expense_p90_krw"),
        )
        if any(value is None or value < 0 for value in values):
            raise ValueError("forecast expense metrics must be non-negative amounts")
        _ordered(values[1:])
        cash = _money_triplet(self, "terminal_cash")
        resource = _money_triplet(self, "terminal_resource_change")
        if any(value is None for value in resource):
            raise ValueError("forecast resource metrics must be available")
        if any(value is None for value in cash) and any(value is not None for value in cash):
            raise ValueError("forecast cash quantiles must be all present or all unavailable")
        if all(value is not None for value in cash):
            _ordered(cash)
        _ordered(resource)
        return self


class RiskResult(NumericResult):
    mode: Literal["risk"]

    @model_validator(mode="after")
    def validate_risk(self) -> RiskResult:
        probabilities = (
            _probability(self, "p_any_account_shortfall"),
            _probability(self, "p_total_cash_shortfall"),
            _probability(self, "p_liquid_below_reserve"),
        )
        shortage = _optional_money(self, "maximum_total_cash_shortage_p50_krw")
        if probabilities[0] is not None and shortage is None:
            raise ValueError("risk shortage amount must accompany an available cash risk")
        return self


class GoalResult(NumericResult):
    mode: Literal["goal"]
    decision: GoalDecision

    @model_validator(mode="after")
    def validate_goal(self) -> GoalResult:
        target = _money(self, "goal_target_krw")
        if target is None or target < 0:
            raise ValueError("goal target must be available")
        reached = _probability(self, "p_goal_reached")
        joint = _probability(self, "p_goal_and_no_shortfall")
        if self.status == "insufficient_data":
            if reached is not None or joint is not None or self.decision.feasibility != "unknown":
                raise ValueError("insufficient goal results cannot report feasibility")
            return self
        if reached is None or joint is None or joint > reached:
            raise ValueError("goal probabilities are missing or inconsistent")
        gap = _money(self, "goal_gap_p50_krw")
        external = _money(self, "additional_external_income_each_30d_krw")
        if gap is None or gap < 0 or external is None or external < 0:
            raise ValueError("goal gap metrics must be available")
        return self


class WhatIfResult(NumericResult):
    mode: Literal["what_if"]
    decision: WhatIfDecision

    @model_validator(mode="after")
    def validate_what_if(self) -> WhatIfResult:
        saving = _money(self, "paired_expense_saving_p50_krw")
        cash = _money(self, "paired_terminal_cash_delta_p50_krw")
        resource = _money(self, "paired_terminal_resource_delta_p50_krw")
        _ = _probability(self, "branch_p_any_account_shortfall")
        if saving is None or resource is None:
            raise ValueError("what-if paired metrics must be available")
        if cash is None and not self.required_inputs:
            raise ValueError("unavailable what-if cash delta must name required inputs")
        return self


class OptimizeResult(NumericResult):
    mode: Literal["optimize"]
    decision: OptimizeDecision

    @model_validator(mode="after")
    def validate_optimize(self) -> OptimizeResult:
        if self.status == "insufficient_data":
            if self.decision.feasibility != "unknown" or self.decision.selected_candidate_id is not None:
                raise ValueError("insufficient optimization results cannot select a candidate")
            return self
        candidates = _count(self, "candidate_count")
        feasible = _count(self, "feasible_candidate_count")
        saving = _money(self, "selected_expected_saving_krw")
        if candidates is None or feasible is None or feasible > candidates:
            raise ValueError("optimization candidate counts are missing or inconsistent")
        selected = self.decision.selected_candidate_id is not None
        if selected != (saving is not None) or selected != (self.decision.selected_reductions is not None):
            raise ValueError("optimization selection facts are inconsistent")
        if self.decision.selected_reductions is not None:
            for reduction in self.decision.selected_reductions.values():
                if not 0 <= reduction <= 1:
                    raise ValueError("optimization reductions must be ratios")
        return self


ResultUnion: TypeAlias = ForecastResult | RiskResult | GoalResult | WhatIfResult | OptimizeResult
ParsedResult: TypeAlias = Annotated[ResultUnion, Field(discriminator="mode")]
_RESULT: TypeAdapter[ParsedResult] = TypeAdapter(ParsedResult)


def _metric(result: NumericResult, name: str, unit: Unit) -> Metric:
    value = result.metrics.get(name)
    if value is None or value.unit != unit:
        message = f"missing or invalid metric: {name}"
        raise ValueError(message)
    return value


def _number(metric: Metric) -> Number | None:
    value = metric.value
    if value is not None and (isinstance(value, bool) or not isfinite(value)):
        raise ValueError("metric value must be a finite number or null")
    return value


def _money(result: NumericResult, name: str) -> int | None:
    value = _number(_metric(result, name, "KRW"))
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool) or not -(10**12) <= value <= 10**12:
        message = f"money metric must be a bounded integer: {name}"
        raise ValueError(message)
    return value


def _required_money(result: NumericResult, name: str) -> int:
    value = _money(result, name)
    if value is None:
        message = f"required money metric is unavailable: {name}"
        raise ValueError(message)
    return value


def _optional_money(result: NumericResult, name: str) -> int | None:
    return None if name not in result.metrics else _money(result, name)


def _probability(result: NumericResult, name: str) -> float | None:
    value = _number(_metric(result, name, "probability"))
    if value is None:
        return None
    converted = float(value)
    if not 0 <= converted <= 1:
        message = f"probability metric is outside zero to one: {name}"
        raise ValueError(message)
    return converted


def _count(result: NumericResult, name: str) -> int | None:
    value = _number(_metric(result, name, "count"))
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        message = f"count metric must be a non-negative integer: {name}"
        raise ValueError(message)
    return value


def _required_count(result: NumericResult, name: str) -> int:
    value = _count(result, name)
    if value is None:
        message = f"required count metric is unavailable: {name}"
        raise ValueError(message)
    return value


def _money_triplet(result: NumericResult, prefix: str) -> tuple[int | None, int | None, int | None]:
    return (
        _money(result, f"{prefix}_p10_krw"),
        _money(result, f"{prefix}_p50_krw"),
        _money(result, f"{prefix}_p90_krw"),
    )


def _required_money_triplet(result: NumericResult, prefix: str) -> tuple[int, int, int]:
    return (
        _required_money(result, f"{prefix}_p10_krw"),
        _required_money(result, f"{prefix}_p50_krw"),
        _required_money(result, f"{prefix}_p90_krw"),
    )


def _ordered(values: tuple[int | None, ...]) -> None:
    if any(value is None for value in values):
        return
    definite = tuple(value for value in values if value is not None)
    if tuple(sorted(definite)) != definite:
        raise ValueError("numeric quantiles are not ordered")


def _money_text(value: int) -> str:
    return f"{value:,}원"


def _percent_text(value: float) -> str:
    return f"{value * 100:.1f}".rstrip("0").rstrip(".") + "%"


def _common(result: NumericResult) -> list[str]:
    pieces: list[str] = []
    if result.status == "partial":
        pieces.append("일부 자료 제약이 있어 수치는 조건부로 확인해야 합니다.")
    elif result.status == "insufficient_data":
        pieces.append("필수 자료가 부족해 지원되는 일부 수치를 계산하지 못했습니다.")
    if result.required_inputs:
        pieces.append("필요 자료: " + ", ".join(result.required_inputs) + ".")
    pieces.append(_LIMIT)
    return pieces


def _forecast(result: ForecastResult) -> list[str]:
    average = _required_money(result, "expected_expense_krw")
    expense = _required_money_triplet(result, "total_expense")
    pieces = [
        "조건부 모형에서 이 예측 구간의 변동소비 평균은 "
        f"{_money_text(average)}이고 P10·P50·P90은 "
        + "·".join(_money_text(value) for value in expense)
        + "입니다."
    ]
    cash = _money_triplet(result, "terminal_cash")
    if all(value is not None for value in cash):
        definite_cash = _required_money_triplet(result, "terminal_cash")
        pieces.append(
            "기간말 현금 P10·P50·P90은 " + "·".join(_money_text(value) for value in definite_cash) + "입니다."
        )
    else:
        resource_p50 = _required_money(result, "terminal_resource_change_p50_krw")
        pieces.append(
            f"구매시점 자금 여력 변화 P50은 {_money_text(resource_p50)}입니다. "
            "현재 잔액 자료가 없어 이 값은 현금 잔액이나 순자산이 아닙니다."
        )
    return pieces


def _risk(result: RiskResult) -> list[str]:
    any_account = _probability(result, "p_any_account_shortfall")
    total_cash = _probability(result, "p_total_cash_shortfall")
    below_reserve = _probability(result, "p_liquid_below_reserve")
    if any_account is None or total_cash is None or below_reserve is None:
        return ["현재 잔액 자료가 없어 계좌 부족 경로 비율과 부족액을 계산하지 못했습니다."]
    pieces = [
        (
            f"조건부 모형 경로에서 계좌 하나라도 잔액 부족이 생긴 경로는 {_percent_text(any_account)}이고, "
            f"합산 현금 부족 경로는 {_percent_text(total_cash)}입니다."
        ),
        f"보관액 아래로 내려간 경로는 {_percent_text(below_reserve)}입니다.",
    ]
    shortage = _optional_money(result, "maximum_total_cash_shortage_p50_krw")
    if shortage is not None:
        pieces.append(f"최대 합산 현금 부족액 P50은 {_money_text(shortage)}입니다.")
    return pieces


def _goal(result: GoalResult) -> list[str]:
    target = _required_money(result, "goal_target_krw")
    reached = _probability(result, "p_goal_reached")
    joint = _probability(result, "p_goal_and_no_shortfall")
    if reached is None or joint is None:
        message = (
            f"목표 {_money_text(target)}은 확인했지만 현재 자료로 목표 도달 경로 비율은 계산하지 못했습니다."
        )
        return [message]
    pieces = [
        (
            f"조건부 모형에서 목표 {_money_text(target)}에 도달한 경로는 {_percent_text(reached)}이고, "
            f"계좌 부족 없이 도달한 경로는 {_percent_text(joint)}입니다."
        )
    ]
    gap = _required_money(result, "goal_gap_p50_krw")
    external = _required_money(result, "additional_external_income_each_30d_krw")
    pieces.append(f"목표 부족액 P50은 {_money_text(gap)}입니다.")
    pieces.append(
        f"목표 조건에서 계산된 30일마다의 가상 외부자금은 {_money_text(external)}입니다. "
        "절약으로 자동 생성되는 금액이 아닙니다."
    )
    return pieces


def _what_if(result: WhatIfResult) -> list[str]:
    saving = _required_money(result, "paired_expense_saving_p50_krw")
    pieces: list[str] = []
    intervention = result.decision.intervention
    reductions = intervention.get("expense_reductions")
    if isinstance(reductions, dict) and len(reductions) == 1:
        envelope, fraction = next(iter(reductions.items()))
        if (
            isinstance(fraction, (int, float))
            and not isinstance(fraction, bool)
            and 0 < fraction < 1
        ):
            pieces.append(f"가정은 {envelope} 소비를 {_percent_text(float(fraction))} 줄이는 조건입니다.")
    multiplier = intervention.get("expense_multiplier")
    if not pieces and isinstance(multiplier, (int, float)) and not isinstance(multiplier, bool):
        reduction = 1 - float(multiplier)
        if 0 < reduction < 1:
            pieces.append(f"가정은 변동 소비를 {_percent_text(reduction)} 줄이는 조건입니다.")
    pieces.append(
        f"동일 난수 경로에서 가정 분기와 기준 분기를 비교한 소비 감소 P50은 {_money_text(saving)}입니다."
    )
    cash = _money(result, "paired_terminal_cash_delta_p50_krw")
    if cash is not None:
        pieces.append(f"가정 분기의 기간말 현금 차이 P50은 {_money_text(cash)}입니다.")
    else:
        resource = _required_money(result, "paired_terminal_resource_delta_p50_krw")
        pieces.append(
            f"가정 분기의 구매시점 자금 여력 차이 P50은 {_money_text(resource)}입니다. "
            "현재 잔액과 순자산의 차이가 아닙니다."
        )
    branch_risk = _probability(result, "branch_p_any_account_shortfall")
    if branch_risk is not None:
        pieces.append(f"가정 분기에서 계좌 부족이 생긴 경로는 {_percent_text(branch_risk)}입니다.")
    pieces.append("요청한 가정의 경로 비교이며 인과 효과나 실제 절감을 보장하지 않습니다.")
    return pieces


def _optimize(result: OptimizeResult) -> list[str]:
    if result.status == "insufficient_data":
        return ["현재 잔액 자료가 없어 유한 후보의 제약 충족 여부를 계산하지 못했습니다."]
    candidates = _required_count(result, "candidate_count")
    feasible = _required_count(result, "feasible_candidate_count")
    pieces = [f"탐색한 유한 후보 {candidates}개 중 입력 제약을 충족한 후보는 {feasible}개입니다."]
    saving = _money(result, "selected_expected_saving_krw")
    if saving is None:
        pieces.append("입력 제약을 충족해 선택된 후보가 없어 소비 감소액을 표시하지 않습니다.")
    else:
        pieces.append(f"선택된 후보의 모형상 기대 소비 감소는 {_money_text(saving)}입니다.")
        selected_reductions = result.decision.selected_reductions
        if selected_reductions is None:
            raise ValueError("selected optimization result has no reductions")
        reductions = ", ".join(
            f"{name} {_percent_text(float(value))}" for name, value in sorted(selected_reductions.items())
        )
        if reductions:
            pieces.append("선택된 후보의 소비 감소율 입력은 " + reductions + "입니다.")
    pieces.append("유한 격자 안의 계산 결과이며 실행된 변경이나 전역 최적 금융전략이 아닙니다.")
    return pieces


def _matches_receipt(result: ParsedResult, receipt: Receipt) -> bool:
    period = receipt.period
    request = receipt.numeric_request
    if period is None or request is None:
        return False
    request_mode = request.root.get("mode")
    request_horizon = request.root.get("horizon_days")
    # The pinned FDT Engine.run applies these defaults before recording request_digest.
    # Matching only twin/mode/period would accept another goal, scenario or random seed.
    effective_request = {"horizon_days": 90, "paths": 400, "seed": 42, **request.root}
    request_digest = sha256(
        json.dumps(
            effective_request, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
    ).hexdigest()
    return (
        request_mode == result.mode
        and result.model.get("request_digest") == request_digest
        and type(request_horizon) is int
        and request_horizon == result.horizon_days
        and result.horizon_days == period.forecast_days
        and result.as_of == period.reference_date
        and result.as_of.isoformat() == receipt.identity.as_of
        and result.twin_id == receipt.identity.twin_id
        and result.revision == receipt.identity.revision
        and result.input_digest == receipt.identity.input_digest
    )


def _ensure_receipt_match(result: ParsedResult, receipt: Receipt) -> None:
    if not _matches_receipt(result, receipt):
        raise ValueError("numeric result does not belong to this receipt")


_PURCHASE_RISK: Final = "구매 후 예측상 예산을 넘겨 이번 기간이 어려울 수 있어요."
_PURCHASE_OK: Final = "예측상 예산 안에 들어와 괜찮아요."


def purchase_verdict_text(receipt: Receipt) -> list[str]:  # noqa: PLR0911 - each shape guard is one explicit fail-closed boundary.
    """Render one binary purchase verdict, reusing the review engine's own shortfall signal.

    No new probability threshold is invented here. A ``changes:[expense]``
    review already computes a paired ``baseline`` vs ``planned`` projection
    (``vendor/fdt/coaching.py`` ``Coach.review``); this only asks whether the
    planned branch's existing ``period_account_shortfall`` fraction newly
    appears or grows versus baseline, and reads back the already-computed
    quantile facts. Returns ``[]`` whenever this receipt has no purchase
    change or the expected comparison shape is absent, so a non-purchase
    review is completely unaffected.
    """
    changes = receipt.request.root.get("changes")
    if not isinstance(changes, list) or not changes:
        return []
    comparison = receipt.result.root.get("comparison")
    if not isinstance(comparison, dict):
        return []
    baseline, planned = comparison.get("baseline"), comparison.get("planned")
    if not isinstance(baseline, dict) or not isinstance(planned, dict):
        return []
    baseline_cash, planned_cash = baseline.get("cash"), planned.get("cash")
    if not isinstance(baseline_cash, dict) or not isinstance(planned_cash, dict):
        return []
    baseline_shortfall = baseline_cash.get("period_account_shortfall")
    planned_shortfall = planned_cash.get("period_account_shortfall")
    if not isinstance(baseline_shortfall, dict) or not isinstance(planned_shortfall, dict):
        return []
    baseline_fraction = baseline_shortfall.get("fraction")
    planned_fraction = planned_shortfall.get("fraction")
    if isinstance(baseline_fraction, bool) or isinstance(planned_fraction, bool):
        return []
    if not isinstance(baseline_fraction, (int, float)) or not isinstance(planned_fraction, (int, float)):
        return []
    pieces = [_PURCHASE_RISK if planned_fraction > 0 else _PURCHASE_OK]
    terminal = planned_cash.get("terminal_balance")
    if isinstance(terminal, dict):
        p50 = terminal.get("p50_krw")
        if isinstance(p50, int) and not isinstance(p50, bool):
            pieces.append(f"구매 후 기간말 예상 현금 P50은 {p50:,}원입니다.")
    pieces.append("부족 예측 있음." if planned_fraction > 0 else "부족 예측 없음.")
    return pieces


def numeric_text(receipt: Receipt) -> list[str]:
    """Return receipt-bound mode facts, or one explicit fail-closed sentence.

    General LLM wording is intentionally forbidden from emitting financial
    numbers. This server renderer is therefore the only path from a validated
    numeric result to user-visible amounts and never derives absent values.
    """
    raw = receipt.numeric_result
    if raw is None:
        return []
    try:
        encoded = json.dumps(raw.root, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
        result = _RESULT.validate_json(encoded)
        _ensure_receipt_match(result, receipt)
    except (TypeError, ValueError, ValidationError, RecursionError):
        return [_INVALID_RESULT]

    try:
        match result:
            case ForecastResult():
                pieces = _forecast(result)
            case RiskResult():
                pieces = _risk(result)
            case GoalResult():
                pieces = _goal(result)
            case WhatIfResult():
                pieces = _what_if(result)
            case OptimizeResult():
                pieces = _optimize(result)
    except ValueError:
        return [_INVALID_RESULT]
    return [*pieces, *_common(result)]
