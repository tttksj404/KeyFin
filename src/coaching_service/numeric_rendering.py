"""Render only typed, receipt-bound numeric engine facts."""

from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from math import isfinite
from typing import TYPE_CHECKING, Annotated, ClassVar, Final, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, JsonValue, TypeAdapter, ValidationError, model_validator

from coaching_service.periods import DateOnly  # noqa: TC001 - Pydantic resolves this at runtime
from coaching_service.schemas import BudgetRiskRow, EnvelopeSpendRow, NumericRows

if TYPE_CHECKING:
    from coaching_service.schemas import Receipt

Mode: TypeAlias = Literal["forecast", "what_if", "goal", "risk", "optimize"]
Status: TypeAlias = Literal["ok", "partial", "insufficient_data"]
Unit: TypeAlias = Literal["KRW", "probability", "count", "ratio", "days", "months"]
Number: TypeAlias = int | float
Text = Annotated[str, Field(min_length=1, max_length=2000)]

_INVALID_RESULT = "수치 분석 결과의 계약을 확인할 수 없어 금액·비율을 표시하지 않습니다."


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


def _short_accounts(result: NumericResult, dataset: str) -> list[tuple[str, float]]:
    """Label each account the engine says can run short, as ``(label, share)``, worst first.

    The engine's ``account_shortfall`` rows carry only its own account id, the
    reported opening balance and the income flag (no bank name), so the label is
    "주거래 계좌" or the account's reported balance. Malformed rows are skipped.
    """
    raw = result.datasets.get(dataset)
    if not isinstance(raw, list):
        return []
    found: list[tuple[str, float]] = []
    for row in raw:
        if not isinstance(row, dict):
            continue
        share = row.get("p_shortfall")
        if isinstance(share, bool) or not isinstance(share, (int, float)) or not 0 < share <= 1:
            continue
        balance = row.get("balance_krw")
        if row.get("is_income") is True:
            label = "주거래 계좌"
        elif isinstance(balance, int) and not isinstance(balance, bool):
            label = f"{_money_text(balance)}이 든 계좌"
        else:
            label = "일부 계좌"
        found.append((label, float(share)))
    return sorted(found, key=lambda item: item[1], reverse=True)


def _short_account_sentence(result: NumericResult, dataset: str, *, total_cash_ok: bool) -> list[str]:
    """Say which account runs short, and that combined cash is fine when the engine says so."""
    short = _short_accounts(result, dataset)
    if not short:
        return []
    label, share = short[0]
    # Every label ends in "계좌", so the topic particle is always "는".
    target = label if len(short) == 1 else f"{label} 등 {len(short)}개 계좌"
    sentence = f"{target}는 예정된 결제 때 잔액이 모자랄 수 있어요(예측한 경우 중 {_percent_text(share)})."
    if total_cash_ok:
        return [
            "모든 계좌를 합친 현금은 부족해지지 않아요. 다만 " + sentence
            + " **결제 전에 다른 계좌에서 옮겨 두면 막을 수 있어요.**"
        ]
    return [sentence]


def _common(result: NumericResult) -> list[str]:
    pieces: list[str] = []
    if result.status == "partial":
        pieces.append("일부 자료가 빠져 있어 수치가 달라질 수 있어요.")
    elif result.status == "insufficient_data":
        pieces.append("꼭 필요한 자료가 부족해 일부 수치는 계산하지 못했어요.")
    if result.required_inputs:
        pieces.append("필요 자료: " + ", ".join(result.required_inputs) + ".")
    return pieces


def _forecast(result: ForecastResult) -> list[str]:
    # The mean stays a required contract field even though the sentence below leads with the typical value.
    _ = _required_money(result, "expected_expense_krw")
    low, typical, high = _required_money_triplet(result, "total_expense")
    pieces = [
        (
            f"이 예측 구간 변동소비는 보통 {_money_text(typical)} 정도로 예상돼요. "
            f"적게 쓰면 {_money_text(low)}, 많이 쓰면 {_money_text(high)}까지 볼 수 있어요."
        )
    ]
    cash = _money_triplet(result, "terminal_cash")
    if all(value is not None for value in cash):
        cash_low, cash_typical, cash_high = _required_money_triplet(result, "terminal_cash")
        pieces.append(
            f"기간 말 현금은 보통 {_money_text(cash_typical)}, 적게 남으면 {_money_text(cash_low)}, "
            f"많이 남으면 {_money_text(cash_high)}으로 예상돼요."
        )
    else:
        resource_p50 = _required_money(result, "terminal_resource_change_p50_krw")
        pieces.append(
            f"이 기간에 들어오고 나가는 돈을 합치면 보통 {_money_text(resource_p50)}으로 예상돼요. "
            "현재 잔액 자료가 없어 이 값은 통장 잔액이나 순자산이 아니에요."
        )
    return pieces


def _risk(result: RiskResult) -> list[str]:
    any_account = _probability(result, "p_any_account_shortfall")
    total_cash = _probability(result, "p_total_cash_shortfall")
    below_reserve = _probability(result, "p_liquid_below_reserve")
    if any_account is None or total_cash is None or below_reserve is None:
        return ["현재 잔액 자료가 없어 잔액이 부족해질 가능성과 모자라는 돈을 계산하지 못했어요."]
    pieces = [
        # Plain-language first: which account runs short, and whether combined cash is fine.
        *_short_account_sentence(result, "account_shortfall", total_cash_ok=total_cash == 0),
        (
            f"예측한 여러 경우 중 계좌 하나라도 잔액이 부족해지는 경우는 {_percent_text(any_account)}, "
            f"모든 계좌를 합쳐도 부족해지는 경우는 {_percent_text(total_cash)}예요."
        ),
        f"비상금(보관액) 아래로 내려간 경우는 {_percent_text(below_reserve)}예요.",
    ]
    shortage = _optional_money(result, "maximum_total_cash_shortage_p50_krw")
    if shortage is not None:
        pieces.append(
            f"모든 계좌를 합친 현금이 가장 많이 부족할 때 모자라는 돈은 보통 {_money_text(shortage)}이에요."
        )
    return pieces


def _goal(result: GoalResult) -> list[str]:
    target = _required_money(result, "goal_target_krw")
    reached = _probability(result, "p_goal_reached")
    joint = _probability(result, "p_goal_and_no_shortfall")
    if reached is None or joint is None:
        message = (
            f"목표 {_money_text(target)}은 확인했지만 현재 자료로는 목표에 닿을 가능성을 계산하지 못했어요."
        )
        return [message]
    pieces = [
        (
            f"예측한 여러 경우 중 목표 {_money_text(target)}에 닿은 경우는 {_percent_text(reached)}, "
            f"계좌 잔액이 부족해지지 않고 닿은 경우는 {_percent_text(joint)}예요."
        )
    ]
    gap = _required_money(result, "goal_gap_p50_krw")
    external = _required_money(result, "additional_external_income_each_30d_krw")
    pieces.append(f"목표까지 모자라는 돈은 보통 {_money_text(gap)}이에요.")
    pieces.append(
        f"목표를 채우려면 30일마다 {_money_text(external)}이 더 들어와야 해요. "
        "아껴서 저절로 생기는 돈이 아니라 따로 더 필요한 돈이에요."
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
            pieces.append(f"{envelope} 소비를 {_percent_text(float(fraction))} 줄인다고 가정했어요.")
    multiplier = intervention.get("expense_multiplier")
    if not pieces and isinstance(multiplier, (int, float)) and not isinstance(multiplier, bool):
        reduction = 1 - float(multiplier)
        if 0 < reduction < 1:
            pieces.append(f"변동 소비를 {_percent_text(reduction)} 줄인다고 가정했어요.")
    pieces.append(f"지금처럼 쓸 때와 비교하면 소비는 보통 {_money_text(saving)} 줄어들 것으로 예상돼요.")
    cash = _money(result, "paired_terminal_cash_delta_p50_krw")
    if cash is not None:
        pieces.append(f"지금처럼 쓸 때와 비교한 기간 말 현금 차이는 보통 {_money_text(cash)}이에요.")
    else:
        resource = _required_money(result, "paired_terminal_resource_delta_p50_krw")
        pieces.append(
            "지금처럼 쓸 때와 비교해 이 기간에 들어오고 나가는 돈의 차이는 "
            f"보통 {_money_text(resource)}이에요. 통장 잔액이나 순자산의 차이는 아니에요."
        )
    branch_risk = _probability(result, "branch_p_any_account_shortfall")
    if branch_risk is not None:
        pieces.append(f"이 가정에서 계좌 하나라도 잔액이 부족해지는 경우는 {_percent_text(branch_risk)}예요.")
        pieces.extend(_short_account_sentence(result, "branch_account_shortfall", total_cash_ok=False))
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


_PURCHASE_RISK: Final = "구매 후 예측상 계좌 잔액이 부족해질 수 있어요."
_PURCHASE_OK: Final = "{env} 봉투 예산 안이고 예측상 계좌도 부족해지지 않아 괜찮아요."
# Used only when the purchase envelope is absent from the ledger: the account check
# still holds, but nothing is claimed about an envelope we could not read.
_PURCHASE_CASH_OK: Final = "예측상 계좌 잔액은 부족해지지 않아요."
_PURCHASE_OVER: Final = (
    "계좌 잔액으로는 결제할 수 있지만 {env} 봉투에 남은 {left:,}원보다 많아 "
    "봉투 예산을 {over:,}원 초과해요."
)
_PURCHASE_OVER_ALREADY: Final = (
    "계좌 잔액으로는 결제할 수 있지만 {env} 봉투는 이미 예산을 넘어서 "
    "이번 구매 {amount:,}원이 그대로 초과 금액이 돼요."
)
_PURCHASE_OVER_EMPTY: Final = (
    "계좌 잔액으로는 결제할 수 있지만 {env} 봉투에 남은 예산이 없어 "
    "이번 구매 {amount:,}원이 그대로 초과 금액이 돼요."
)
_PURCHASE_OVER_WITH_RISK: Final = "{env} 봉투 예산도 {over:,}원 초과해요."


@dataclass(frozen=True, slots=True)
class PurchaseEnvelope:
    """The purchase change against its envelope's current ledger balance."""

    envelope: str
    amount_krw: int
    left_krw: int | None

    @property
    def over_krw(self) -> int:
        if self.left_krw is None or self.amount_krw <= self.left_krw:
            return 0
        return self.amount_krw - max(self.left_krw, 0)


def purchase_envelope(receipt: Receipt) -> PurchaseEnvelope | None:
    """Read the single purchase change and what its envelope still holds right now."""
    changes = receipt.request.root.get("changes")
    if not isinstance(changes, list) or len(changes) != 1 or not isinstance(changes[0], dict):
        return None
    change = changes[0]
    envelope, amount = change.get("envelope"), change.get("amount_krw")
    if not isinstance(envelope, str) or not isinstance(amount, int) or isinstance(amount, bool):
        return None
    left = next((row.balance_krw for row in receipt.current_envelopes if row.envelope == envelope), None)
    return PurchaseEnvelope(envelope=envelope, amount_krw=amount, left_krw=left)


def purchase_verdict_text(receipt: Receipt) -> list[str]:  # noqa: C901, PLR0911, PLR0912 - each shape guard is one explicit fail-closed boundary.
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
    # The account projection alone cannot say a 300만원 laptop fits a 50,000원 기타
    # envelope (2026-09-26 live), so the verdict also weighs the purchase against what
    # its envelope holds now. The first line always answers the question asked.
    purchase = purchase_envelope(receipt)
    over = 0 if purchase is None else purchase.over_krw
    if planned_fraction > 0:
        pieces = [_PURCHASE_RISK]
        if purchase is not None and over:
            pieces.append(_PURCHASE_OVER_WITH_RISK.format(env=purchase.envelope, over=over))
    elif purchase is None or purchase.left_krw is None:
        pieces = [_PURCHASE_CASH_OK]
    elif over and purchase.left_krw < 0:
        pieces = [_PURCHASE_OVER_ALREADY.format(env=purchase.envelope, amount=purchase.amount_krw)]
    elif over and purchase.left_krw == 0:
        pieces = [_PURCHASE_OVER_EMPTY.format(env=purchase.envelope, amount=purchase.amount_krw)]
    elif over:
        pieces = [_PURCHASE_OVER.format(env=purchase.envelope, left=purchase.left_krw, over=over)]
    else:
        pieces = [_PURCHASE_OK.format(env=purchase.envelope)]
    terminal = planned_cash.get("terminal_balance")
    if isinstance(terminal, dict):
        p50 = terminal.get("p50_krw")
        if isinstance(p50, int) and not isinstance(p50, bool):
            pieces.append(f"구매 후 기간 말 현금은 보통 {p50:,}원으로 예상돼요.")
    pieces.append("부족 예측 있음." if planned_fraction > 0 else "부족 예측 없음.")
    return pieces


def _int(value: JsonValue) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _envelope_spend_rows(result: ParsedResult) -> tuple[EnvelopeSpendRow, ...]:
    """엔진 datasets['envelopes']의 봉투별 소비 분위수를 그대로 옮긴다.

    형이 어긋난 행이 하나라도 있으면 조용히 값을 만들지 않고 전체를 비운다.
    """
    raw = result.datasets.get("envelopes")
    if not isinstance(raw, list):
        return ()
    rows: list[EnvelopeSpendRow] = []
    for item in raw:
        if not isinstance(item, dict):
            return ()
        envelope = item.get("envelope")
        p10, p50, p90 = _int(item.get("p10_krw")), _int(item.get("p50_krw")), _int(item.get("p90_krw"))
        if not (
            isinstance(envelope, str)
            and envelope
            and p10 is not None
            and p50 is not None
            and p90 is not None
        ):
            return ()
        rows.append(EnvelopeSpendRow(envelope=envelope, p10_krw=p10, p50_krw=p50, p90_krw=p90))
    return tuple(rows)


def _budget_risk_rows(result: ParsedResult) -> tuple[BudgetRiskRow, ...]:
    """엔진 datasets['budget_risk']의 봉투별 예산 대비 예측·초과 확률을 그대로 옮긴다.

    스냅샷에 예산이 없으면 이 dataset 자체가 없어 빈 튜플을 돌려준다.
    """
    raw = result.datasets.get("budget_risk")
    if not isinstance(raw, list):
        return ()
    rows: list[BudgetRiskRow] = []
    for item in raw:
        if not isinstance(item, dict):
            return ()
        envelope = item.get("envelope")
        budget, observed = _int(item.get("budget_krw")), _int(item.get("observed_used_krw"))
        projected = _int(item.get("projected_used_p50_krw"))
        over = item.get("p_over_budget")
        if not (
            isinstance(envelope, str)
            and envelope
            and budget is not None
            and observed is not None
            and projected is not None
            and isinstance(over, (int, float))
            and not isinstance(over, bool)
            and 0.0 <= over <= 1.0
        ):
            return ()
        rows.append(
            BudgetRiskRow(
                envelope=envelope,
                budget_krw=budget,
                observed_used_krw=observed,
                projected_used_p50_krw=projected,
                p_over_budget=float(over),
            )
        )
    return tuple(rows)


def numeric_rows_for(receipt: Receipt) -> NumericRows | None:
    """Return receipt-bound per-envelope rows for a risk or what-if turn, or None.

    Reuses the same validation and receipt-identity gate as ``numeric_text`` so a
    row is only surfaced from a contract-valid result that belongs to this
    receipt. It never derives amounts: every figure is copied from the engine's
    own ``datasets`` and the human ``text`` is untouched. The paired what-if
    saving remains aggregate-only in the engine, so only the engine-computed
    per-envelope projected spend (and, for risk, the budget-risk breakdown when a
    snapshot budget exists) is exposed; no per-envelope what-if delta is invented.
    """
    raw = receipt.numeric_result
    if raw is None:
        return None
    try:
        encoded = json.dumps(raw.root, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
        result = _RESULT.validate_json(encoded)
        _ensure_receipt_match(result, receipt)
    except (TypeError, ValueError, ValidationError, RecursionError):
        return None
    if isinstance(result, RiskResult):
        mode: Literal["risk", "what_if"] = "risk"
        budget_risk = _budget_risk_rows(result)
    elif isinstance(result, WhatIfResult):
        mode = "what_if"
        budget_risk = ()
    else:
        return None
    envelope_spend = _envelope_spend_rows(result)
    if not envelope_spend and not budget_risk:
        return None
    return NumericRows(mode=mode, envelope_spend=envelope_spend, budget_risk=budget_risk)


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
