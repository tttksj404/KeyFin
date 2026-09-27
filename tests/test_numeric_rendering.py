# ruff: noqa: INP001
"""Regression checks for deterministic numeric-result wording."""

from __future__ import annotations

from datetime import date
from typing import Literal, TypeAlias

import pytest
from fdt.util import digest
from test_engine import fixture

from coaching_service.engine import EngineAdapter
from coaching_service.numeric_rendering import numeric_rows_for, numeric_text
from coaching_service.periods import RollingDays, resolve_period
from coaching_service.rendering import authoritative_text, envelope_balance_table
from coaching_service.schemas import JsonDocument, Receipt

JsonObject: TypeAlias = dict[str, object]
InvalidMutation: TypeAlias = Literal["unit", "missing", "nan", "inf", "horizon", "mode"]
# Users read these facts; statistics jargon and the old stock disclaimer must not reach them.
_JARGON = ("P10", "P50", "P90", "조건부", "경로", "보장")


def metric(value: float | None, unit: str) -> JsonObject:
    return {
        "value": value,
        "unit": unit,
        "basis": "simulation",
        "method": "empirical_paths",
        "evidence": ["input_digest", "model"],
    }


def numeric_result(
    mode: str,
    metrics: JsonObject,
    *,
    status: str = "ok",
    required_inputs: list[str] | None = None,
    decision: JsonObject | None = None,
) -> JsonObject:
    result: JsonObject = {
        "schema_version": "1.0",
        "mode": mode,
        "status": status,
        "twin_id": "twin",
        "revision": 3,
        "as_of": "2026-09-09",
        "horizon_days": 7,
        "model": {
            "version": "pinned",
            "request_digest": digest({"mode": mode, "horizon_days": 7, "paths": 20, "seed": 42}),
        },
        "input_digest": "digest",
        "assumptions": [],
        "warnings": [],
        "limitations": ["조건부 모델 경로이며 실제 미래를 보장하지 않습니다."],
        "metrics": metrics,
        "datasets": {},
        "visualizations": [],
    }
    if required_inputs is not None:
        result["required_inputs"] = required_inputs
    if decision is not None:
        result["decision"] = decision
    return result


def receipt_for(
    mode: str,
    metrics: JsonObject,
    *,
    status: str = "ok",
    required_inputs: list[str] | None = None,
    decision: JsonObject | None = None,
) -> Receipt:
    return Receipt.model_validate(
        {
            "engine_commit": "pinned-engine",
            "identity": {
                "user_id": "user",
                "twin_id": "twin",
                "revision": 3,
                "input_digest": "digest",
                "as_of": "2026-09-09",
            },
            "request": {"on_date": "2026-09-09", "through_date": "2026-09-16"},
            "result": {"status": "ready"},
            "trigger": "dialogue",
            "numeric_request": {"mode": mode, "horizon_days": 7, "paths": 20, "seed": 42},
            "numeric_result": numeric_result(
                mode,
                metrics,
                status=status,
                required_inputs=required_inputs,
                decision=decision,
            ),
            "period": resolve_period(date(2026, 9, 9), RollingDays(days=7), "analysis"),
        }
    )


CASES = (
    (
        "forecast",
        {
            "expected_expense_krw": metric(21_000, "KRW"),
            "total_expense_p10_krw": metric(10_000, "KRW"),
            "total_expense_p50_krw": metric(20_000, "KRW"),
            "total_expense_p90_krw": metric(30_000, "KRW"),
            "terminal_cash_p10_krw": metric(350_000, "KRW"),
            "terminal_cash_p50_krw": metric(400_000, "KRW"),
            "terminal_cash_p90_krw": metric(450_000, "KRW"),
            "terminal_resource_change_p10_krw": metric(5_000, "KRW"),
            "terminal_resource_change_p50_krw": metric(15_000, "KRW"),
            "terminal_resource_change_p90_krw": metric(25_000, "KRW"),
        },
        None,
        (
            "변동소비는 보통 20,000원 정도로 예상돼요. 적게 쓰면 10,000원, 많이 쓰면 30,000원까지",
            "기간 말 현금은 보통 400,000원, 적게 남으면 350,000원, 많이 남으면 450,000원",
        ),
    ),
    (
        "risk",
        {
            "p_any_account_shortfall": metric(0.25, "probability"),
            "p_total_cash_shortfall": metric(0.1, "probability"),
            "p_liquid_below_reserve": metric(0.3, "probability"),
            "maximum_total_cash_shortage_p50_krw": metric(50_000, "KRW"),
        },
        None,
        ("계좌 하나라도 잔액이 부족해지는 경우는 25%", "가장 많이 부족할 때 모자라는 돈은 보통 50,000원"),
    ),
    (
        "goal",
        {
            "goal_target_krw": metric(1_000_000, "KRW"),
            "p_goal_reached": metric(0.7, "probability"),
            "p_goal_and_no_shortfall": metric(0.6, "probability"),
            "goal_gap_p50_krw": metric(80_000, "KRW"),
            "additional_external_income_each_30d_krw": metric(50_000, "KRW"),
        },
        {
            "goal_basis": "cash_minus_card_payable_minus_reserve",
            "deadline": "2026-09-16",
            "required_success_probability": 0.8,
            "feasibility": "below_threshold",
            "fixed_monthly_p50_krw": 100_000,
            "external_income_installment_days": [1],
            "external_income_note": "가정한 외부 자금이며 자동으로 생기지 않습니다.",
        },
        (
            "목표 1,000,000원에 닿은 경우는 70%",
            "잔액이 부족해지지 않고 닿은 경우는 60%",
            "목표까지 모자라는 돈은 보통 80,000원",
        ),
    ),
    (
        "what_if",
        {
            "paired_expense_saving_p50_krw": metric(30_000, "KRW"),
            "paired_terminal_cash_delta_p50_krw": metric(20_000, "KRW"),
            "paired_terminal_resource_delta_p50_krw": metric(10_000, "KRW"),
            "branch_p_any_account_shortfall": metric(0.15, "probability"),
        },
        {
            "branch_mutates_twin": False,
            "comparison_method": "paired_common_random_numbers",
            "intervention": {"expense_multiplier": 0.9},
            "causal_effect_claim": False,
        },
        ("소비는 보통 30,000원 줄어들", "기간 말 현금 차이는 보통 20,000원"),
    ),
    (
        "optimize",
        {
            "candidate_count": metric(9, "count"),
            "feasible_candidate_count": metric(2, "count"),
            "selected_expected_saving_krw": metric(40_000, "KRW"),
        },
        {
            "feasibility": "feasible",
            "selected_candidate_id": "candidate-002",
            "selected_reductions": {"외식": 0.2, "쇼핑": 0.1},
            "target_krw": 1_000_000,
            "reserve_krw": 100_000,
            "required_joint_success": 0.8,
            "maximum_any_account_shortfall": 0.1,
            "fixed_monthly_p50_krw": 100_000,
            "optimality_scope": "EXHAUSTIVE_FINITE_GRID_ONLY",
            "objective": "MIN_EXPECTED_CONSUMPTION_REDUCTION",
            "protected_fixed_and_recurring": True,
            "executed": False,
        },
        ("유한 후보 9개 중 입력 제약을 충족한 후보는 2개", "모형상 기대 소비 감소는 40,000원"),
    ),
)


@pytest.mark.parametrize(("mode", "metrics", "decision", "expected"), CASES)
def test_supported_mode_renders_period_values_units_in_plain_words(
    mode: str,
    metrics: JsonObject,
    decision: JsonObject | None,
    expected: tuple[str, ...],
) -> None:
    text = authoritative_text(receipt_for(mode, metrics, decision=decision))

    assert "예측 구간은 2026-09-10부터 2026-09-16 마감까지 7일" in text
    assert all(phrase in text for phrase in expected)
    assert not any(term in text for term in _JARGON)


def test_partial_forecast_names_missing_input_and_does_not_call_resource_proxy_cash() -> None:
    receipt = receipt_for(
        "forecast",
        {
            "expected_expense_krw": metric(21_000, "KRW"),
            "total_expense_p10_krw": metric(10_000, "KRW"),
            "total_expense_p50_krw": metric(20_000, "KRW"),
            "total_expense_p90_krw": metric(30_000, "KRW"),
            "terminal_cash_p10_krw": metric(None, "KRW"),
            "terminal_cash_p50_krw": metric(None, "KRW"),
            "terminal_cash_p90_krw": metric(None, "KRW"),
            "terminal_resource_change_p10_krw": metric(-25_000, "KRW"),
            "terminal_resource_change_p50_krw": metric(-15_000, "KRW"),
            "terminal_resource_change_p90_krw": metric(-5_000, "KRW"),
        },
        status="partial",
        required_inputs=["snapshot.accounts.balance_krw"],
    )

    text = authoritative_text(receipt)

    assert "필요 자료: snapshot.accounts.balance_krw" in text
    assert "들어오고 나가는 돈을 합치면 보통 -15,000원으로 예상돼요" in text
    assert "기간 말 현금은 보통 -15,000원" not in text


def test_insufficient_goal_does_not_turn_unknown_value_into_probability() -> None:
    receipt = receipt_for(
        "goal",
        {
            "goal_target_krw": metric(1_000_000, "KRW"),
            "p_goal_reached": metric(None, "probability"),
            "p_goal_and_no_shortfall": metric(None, "probability"),
            "goal_gap_p50_krw": metric(None, "KRW"),
            "additional_external_income_each_30d_krw": metric(None, "KRW"),
        },
        status="insufficient_data",
        required_inputs=["snapshot.accounts"],
        decision={
            "goal_basis": "cash_minus_card_payable_minus_reserve",
            "feasibility": "unknown",
            "fixed_monthly_p50_krw": 100_000,
        },
    )

    text = authoritative_text(receipt)

    assert "목표 1,000,000원" in text
    assert "목표에 닿을 가능성을 계산하지 못했어요" in text
    assert "필요 자료: snapshot.accounts" in text
    assert "%" not in text


@pytest.mark.parametrize(
    "mutation",
    ["unit", "missing", "nan", "inf", "horizon", "mode"],
)
def test_invalid_numeric_contract_fails_closed_without_rendering_value(
    mutation: InvalidMutation,
) -> None:
    metrics: JsonObject = {
        "expected_expense_krw": metric(21_000, "KRW"),
        "total_expense_p10_krw": metric(10_000, "KRW"),
        "total_expense_p50_krw": metric(20_000, "KRW"),
        "total_expense_p90_krw": metric(30_000, "KRW"),
        "terminal_cash_p10_krw": metric(350_000, "KRW"),
        "terminal_cash_p50_krw": metric(400_000, "KRW"),
        "terminal_cash_p90_krw": metric(450_000, "KRW"),
        "terminal_resource_change_p10_krw": metric(5_000, "KRW"),
        "terminal_resource_change_p50_krw": metric(15_000, "KRW"),
        "terminal_resource_change_p90_krw": metric(25_000, "KRW"),
    }
    if mutation == "unit":
        metrics["total_expense_p50_krw"] = metric(20_000, "count")
    elif mutation == "missing":
        metrics.pop("total_expense_p90_krw")
    elif mutation == "nan":
        metrics["total_expense_p50_krw"] = metric(float("nan"), "KRW")
    elif mutation == "inf":
        metrics["total_expense_p50_krw"] = metric(float("inf"), "KRW")
    invalid = receipt_for("forecast", metrics)
    if mutation in {"horizon", "mode"}:
        document = invalid.numeric_result
        assert document is not None
        raw: JsonObject = dict(document.root)
        if mutation == "horizon":
            raw["horizon_days"] = 8
        else:
            raw["mode"] = "risk"
        invalid = invalid.model_copy(update={"numeric_result": JsonDocument.model_validate(raw)})

    text = authoritative_text(invalid)

    assert "수치 분석 결과의 계약을 확인할 수 없어 금액·비율을 표시하지 않습니다." in text
    assert "20,000원" not in text


@pytest.mark.parametrize(
    ("mode", "extra"),
    [
        ("forecast", {}),
        ("risk", {}),
        ("what_if", {"scenario": {"expense_multiplier": 0.9}}),
        ("goal", {"goal": {"target_krw": 1_000_000}}),
        (
            "optimize",
            {
                "goal": {"target_krw": 1_000_000},
                "optimization": {"envelopes": ["외식"], "reduction_grid": [0, 0.1]},
            },
        ),
    ],
)
@pytest.mark.parametrize("omit_defaults", [False, True])
def test_real_engine_supported_mode_matches_renderer_contract(
    mode: str,
    extra: JsonObject,
    omit_defaults: bool,
) -> None:
    engine = EngineAdapter()
    twin = engine.create(fixture("user"), "user")
    identity = engine.identity(twin)
    optional = {} if omit_defaults else {"paths": 20, "seed": 42}
    request = JsonDocument({"mode": mode, "horizon_days": 7, **optional, **extra})
    result = engine.numeric(twin, request)
    period = resolve_period(date.fromisoformat(identity.as_of), RollingDays(days=7), "analysis")
    receipt = Receipt(
        engine_commit="pinned-engine",
        identity=identity,
        request=JsonDocument({"on_date": identity.as_of, "through_date": period.forecast_end.isoformat()}),
        result=JsonDocument({"status": "ready"}),
        trigger="dialogue",
        numeric_request=request,
        numeric_result=result,
        period=period,
    )

    text = authoritative_text(receipt)

    assert "수치 분석 결과의 계약을 확인할 수 없어" not in text
    assert not any(term in text for term in _JARGON)


def test_numeric_forecast_is_labeled_separately_from_history_and_current_balance() -> None:
    base = receipt_for(
        "forecast",
        {
            "expected_expense_krw": metric(21_000, "KRW"),
            "total_expense_p10_krw": metric(10_000, "KRW"),
            "total_expense_p50_krw": metric(20_000, "KRW"),
            "total_expense_p90_krw": metric(30_000, "KRW"),
            "terminal_cash_p10_krw": metric(350_000, "KRW"),
            "terminal_cash_p50_krw": metric(400_000, "KRW"),
            "terminal_cash_p90_krw": metric(450_000, "KRW"),
            "terminal_resource_change_p10_krw": metric(5_000, "KRW"),
            "terminal_resource_change_p50_krw": metric(15_000, "KRW"),
            "terminal_resource_change_p90_krw": metric(25_000, "KRW"),
        },
    )
    raw = base.model_dump(mode="json")
    raw["historical"] = {
        "coaching_id": "past",
        "created_at": 1.0,
        "payment": {
            "transaction_id": "past-payment",
            "envelope": "기타",
            "amount_krw": 888_888,
            "balance_before_krw": 999_999,
            "balance_after_krw": 111_111,
            "remaining_percent": "11.1",
            "weekly_count": 1,
        },
        "trigger": "p0_half_balance",
        "engine_result": {"status": "ready"},
        "transaction_status": "active",
    }
    raw["current_envelopes"] = [{"envelope": "기타", "balance_krw": 777_777}]

    text = authoritative_text(Receipt.model_validate(raw))

    assert "이전 코칭 생성 당시의 기록: 결제액 888,888원" in text
    assert "현재 수신 이벤트까지 반영한 기타 봉투 장부 잔액은 777,777원" in text
    assert "기간 말 현금은 보통 400,000원, 적게 남으면 350,000원, 많이 남으면 450,000원" in text


def test_dialogue_review_sends_envelope_balances_as_a_table_not_seven_sentences() -> None:
    # Live 2026-09-23 ("내 소비습관 어때"): seven "…봉투 장부 잔액은 N원입니다." lines
    # repeated. A dialogue turn with several envelopes ships them as table rows and
    # the text keeps one sentence describing that table.
    raw = receipt_for("forecast", {}).model_dump(mode="json")
    raw["numeric_result"] = None
    raw["numeric_request"] = None
    raw["current_envelopes"] = [
        {"envelope": "외식", "balance_krw": 343_700},
        {"envelope": "교통비", "balance_krw": 150_000},
    ]
    receipt = Receipt.model_validate(raw)

    text = authoritative_text(receipt)

    assert "장부 잔액은" not in text
    assert "봉투별 남은 잔액은 아래 표에 정리했어요." in text
    assert envelope_balance_table(receipt) == receipt.current_envelopes


def test_payment_and_single_envelope_turns_keep_balance_sentences() -> None:
    raw = receipt_for("forecast", {}).model_dump(mode="json")
    raw["numeric_result"] = None
    raw["numeric_request"] = None
    raw["current_envelopes"] = [{"envelope": "외식", "balance_krw": 343_700}]
    single = Receipt.model_validate(raw)
    # One envelope is simply stated; no table is attached.
    assert "외식 봉투 장부 잔액은 343,700원입니다." in authoritative_text(single)
    assert envelope_balance_table(single) == ()


def test_review_text_drops_engine_boilerplate_but_keeps_actionable_steps() -> None:
    # Live 2026-09-23: every review repeated "새로운 감축을 권하지 않습니다… 안전 보장은
    # 아닙니다", "경로 수와 분위수는…", "기존 소비의 미래 카드 청구는…" regardless of data.
    raw = receipt_for("forecast", {}).model_dump(mode="json")
    raw["numeric_result"] = None
    raw["numeric_request"] = None
    raw["result"] = {
        "status": "ready",
        "next_action": {
            "kind": "keep_and_review",
            "title": "이번 점검에서는 새로운 감축을 권하지 않습니다",
            "detail": "안전 보장은 아닙니다.",
        },
        "warnings": [
            {"code": "CONDITIONAL_MODEL", "severity": "user", "detail": "경로 수와 분위수는 계산입니다."},
            {
                "code": "EXISTING_CARD_SCHEDULE_APPROXIMATION",
                "severity": "user",
                "detail": "카드 청구 단순화.",
            },
            {"code": "ASSUMED_SNAPSHOT", "severity": "user", "detail": "데모 가정이 포함되어 있습니다."},
        ],
    }
    text = authoritative_text(Receipt.model_validate(raw))
    assert "새로운 감축" not in text
    assert "경로 수와 분위수" not in text
    assert "카드 청구 단순화" not in text
    # A data-specific caveat still reaches the user.
    assert "데모 가정이 포함되어 있습니다." in text

    raw["result"]["next_action"] = {
        "kind": "prepare_payment_account",
        "title": "결제 계좌를 준비하세요",
        "detail": "예정 결제 전에 잔액을 옮겨 두세요.",
    }
    actionable = authoritative_text(Receipt.model_validate(raw))
    assert "결제 계좌를 준비하세요. 예정 결제 전에 잔액을 옮겨 두세요." in actionable
    # The user asked for this caveat to go everywhere (2026-09-23), even next to a step.
    assert "경로 수와 분위수" not in actionable
    assert "카드 청구 단순화" not in actionable


def test_numeric_turn_carries_no_balance_table() -> None:
    raw = receipt_for("forecast", {}).model_dump(mode="json")
    raw["current_envelopes"] = [
        {"envelope": "외식", "balance_krw": 1},
        {"envelope": "기타", "balance_krw": 2},
    ]
    assert envelope_balance_table(Receipt.model_validate(raw)) == ()


def _risk_with_accounts(total_cash: float, rows: list[JsonObject]) -> Receipt:
    base = receipt_for(
        "risk",
        {
            "p_any_account_shortfall": metric(1.0, "probability"),
            "p_total_cash_shortfall": metric(total_cash, "probability"),
            "p_liquid_below_reserve": metric(0.0, "probability"),
            "maximum_total_cash_shortage_p50_krw": metric(0, "KRW"),
        },
    )
    raw = base.model_dump(mode="json")
    raw["numeric_result"]["datasets"]["account_shortfall"] = rows
    return Receipt.model_validate(raw)


def test_risk_names_the_short_account_and_says_combined_cash_is_fine() -> None:
    # Live 2026-09-23: 100% "account shortfall" with 0% combined shortfall scared a
    # user holding 5.6M because a 45,400원 side account was never named.
    receipt = _risk_with_accounts(
        0.0,
        [
            {"account_id": "1", "balance_krw": 5_624_570, "is_income": True, "p_shortfall": 0.0},
            {"account_id": "2", "balance_krw": 45_400, "is_income": False, "p_shortfall": 1.0},
        ],
    )
    text = "\n".join(numeric_text(receipt))
    assert text.startswith("모든 계좌를 합친 현금은 부족해지지 않아요.")
    assert "다만 45,400원이 든 계좌는 예정된 결제 때 잔액이 모자랄 수 있어요(예측한 경우 중 100%)" in text
    assert "주거래 계좌" not in text  # the income account is not short, so not named
    # The engine's own figures still follow for transparency.
    assert "계좌 하나라도 잔액이 부족해지는 경우는 100%" in text


def test_risk_names_account_without_reassurance_when_combined_cash_is_short() -> None:
    receipt = _risk_with_accounts(
        0.4,
        [{"account_id": "1", "balance_krw": 10_000, "is_income": True, "p_shortfall": 0.4}],
    )
    text = "\n".join(numeric_text(receipt))
    assert "모든 계좌를 합친 현금은 부족해지지 않아요" not in text
    assert "주거래 계좌는 예정된 결제 때 잔액이 모자랄 수 있어요(예측한 경우 중 40%)" in text


def test_risk_without_account_rows_keeps_the_existing_wording() -> None:
    # Older engine results carry no account_shortfall dataset: nothing new is claimed.
    text = "\n".join(numeric_text(_risk_with_accounts(0.0, [])))
    assert "모자랄 수 있어요" not in text
    assert "계좌 하나라도 잔액이 부족해지는 경우는 100%" in text


def test_fresh_numeric_turn_leads_with_its_answer_not_every_envelope_balance() -> None:
    # A fresh forecast/what-if/risk question must answer itself first. Dumping all
    # seven envelope ledger balances ahead of the result buried the answer so the
    # chat looked like it ignored the asked period/scenario (live 2026-09-23).
    base = receipt_for(
        "forecast",
        {
            "expected_expense_krw": metric(21_000, "KRW"),
            "total_expense_p10_krw": metric(10_000, "KRW"),
            "total_expense_p50_krw": metric(20_000, "KRW"),
            "total_expense_p90_krw": metric(30_000, "KRW"),
            "terminal_cash_p10_krw": metric(350_000, "KRW"),
            "terminal_cash_p50_krw": metric(400_000, "KRW"),
            "terminal_cash_p90_krw": metric(450_000, "KRW"),
            "terminal_resource_change_p10_krw": metric(5_000, "KRW"),
            "terminal_resource_change_p50_krw": metric(15_000, "KRW"),
            "terminal_resource_change_p90_krw": metric(25_000, "KRW"),
        },
    )
    raw = base.model_dump(mode="json")
    raw["current_envelopes"] = [
        {"envelope": "외식", "balance_krw": 343_700},
        {"envelope": "기타", "balance_krw": 50_000},
    ]

    text = authoritative_text(Receipt.model_validate(raw))

    assert "장부 잔액" not in text
    assert "기간 말 현금은 보통 400,000원, 적게 남으면 350,000원, 많이 남으면 450,000원" in text


@pytest.mark.parametrize(
    ("original", "changed"),
    [
        (
            {"mode": "goal", "goal": {"target_krw": 1_000_000}},
            {"mode": "goal", "goal": {"target_krw": 10_000_000}},
        ),
        (
            {"mode": "forecast", "scenario": {"expense_multiplier": 1.0}},
            {"mode": "forecast", "scenario": {"expense_multiplier": 0.5}},
        ),
        ({"mode": "forecast", "seed": 42}, {"mode": "forecast", "seed": 123}),
    ],
)
def test_numeric_result_when_request_parameters_change_is_rejected(
    original: JsonObject,
    changed: JsonObject,
) -> None:
    # Given: an actual engine result and another request sharing its twin, mode and horizon.
    engine = EngineAdapter()
    twin = engine.create(fixture("user"), "user")
    identity = engine.identity(twin)
    actual_request = JsonDocument.model_validate({"horizon_days": 7, "paths": 20, **original})
    changed_request = JsonDocument.model_validate({"horizon_days": 7, "paths": 20, **changed})
    result = engine.numeric(twin, actual_request)
    period = resolve_period(date.fromisoformat(identity.as_of), RollingDays(days=7), "analysis")
    receipt = Receipt(
        engine_commit="pinned-engine",
        identity=identity,
        request=JsonDocument({"on_date": identity.as_of, "through_date": period.forecast_end.isoformat()}),
        result=JsonDocument({"status": "ready"}),
        trigger="dialogue",
        numeric_request=changed_request,
        numeric_result=result,
        period=period,
    )
    # When: the renderer checks the result against the changed request.
    text = authoritative_text(receipt)
    # Then: no forecast or goal amounts from the other request are admitted.
    assert "수치 분석 결과의 계약을 확인할 수 없어 금액·비율을 표시하지 않습니다." in text
    assert "현재 현금 400,000원" not in text


def _numeric_receipt(engine: EngineAdapter, twin: JsonDocument, mode: str, **extra: object) -> Receipt:
    request = JsonDocument({"mode": mode, "horizon_days": 7, "paths": 20, "seed": 42, **extra})
    identity = engine.identity(twin)
    period = resolve_period(date.fromisoformat(identity.as_of), RollingDays(days=7), "analysis")
    return Receipt(
        engine_commit="pinned-engine",
        identity=identity,
        request=JsonDocument({"on_date": identity.as_of, "through_date": period.forecast_end.isoformat()}),
        result=JsonDocument({"status": "ready"}),
        trigger="dialogue",
        numeric_request=request,
        numeric_result=engine.numeric(twin, request),
        period=period,
    )


def test_risk_turn_exposes_per_envelope_budget_and_spend_rows_from_engine_datasets() -> None:
    # Given: a real risk result whose snapshot carries a budget (fixture 기타=100000).
    engine = EngineAdapter()
    twin = engine.create(fixture("user"), "user")
    receipt = _numeric_receipt(engine, twin, "risk")
    # When: the row extractor reads the receipt-bound result.
    rows = numeric_rows_for(receipt)
    # Then: per-envelope spend and budget-risk rows are copied straight from the engine, not invented.
    assert rows is not None
    assert rows.mode == "risk"
    assert len(rows.envelope_spend) == 7
    result = receipt.numeric_result
    assert result is not None
    engine_budget = result.root["datasets"]["budget_risk"]
    assert [row.envelope for row in rows.budget_risk] == [item["envelope"] for item in engine_budget]
    assert all(0.0 <= row.p_over_budget <= 1.0 for row in rows.budget_risk)
    assert rows.budget_risk[0].budget_krw == engine_budget[0]["budget_krw"]


def test_what_if_turn_exposes_base_envelope_spend_but_no_fabricated_per_envelope_delta() -> None:
    # Given: a real what-if result. The paired saving is aggregate-only in the engine,
    # so there is no per-envelope what-if delta and no budget_risk dataset for this mode.
    engine = EngineAdapter()
    twin = engine.create(fixture("user"), "user")
    receipt = _numeric_receipt(engine, twin, "what_if", scenario={"expense_multiplier": 0.9})
    rows = numeric_rows_for(receipt)
    assert rows is not None
    assert rows.mode == "what_if"
    assert len(rows.envelope_spend) == 7
    assert rows.budget_risk == ()


def test_forecast_and_goal_turns_carry_no_numeric_rows() -> None:
    # The structured rows are scoped to risk and what-if turns only.
    engine = EngineAdapter()
    twin = engine.create(fixture("user"), "user")
    forecast = _numeric_receipt(engine, twin, "forecast")
    goal = _numeric_receipt(engine, twin, "goal", goal={"target_krw": 1_000_000})
    assert numeric_rows_for(forecast) is None
    assert numeric_rows_for(goal) is None


def test_numeric_rows_reject_a_result_from_another_receipt() -> None:
    # A mismatched receipt identity yields no rows, mirroring numeric_text's fail-closed gate.
    engine = EngineAdapter()
    twin = engine.create(fixture("user"), "user")
    receipt = _numeric_receipt(engine, twin, "risk")
    other = JsonDocument({"mode": "risk", "horizon_days": 7, "paths": 20, "seed": 123})
    tampered = receipt.model_copy(update={"numeric_request": other})
    assert numeric_rows_for(tampered) is None


def test_real_engine_missing_cash_state_is_rendered_as_unavailable_not_invalid() -> None:
    engine = EngineAdapter()
    twin = engine.create(fixture("user").model_copy(update={"snapshot": None}), "user")
    identity = engine.identity(twin)
    period = resolve_period(date.fromisoformat(identity.as_of), RollingDays(days=7), "analysis")
    requests = (
        {"mode": "forecast"},
        {"mode": "risk"},
        {"mode": "what_if", "scenario": {"expense_multiplier": 0.9}},
        {"mode": "goal", "goal": {"target_krw": 1_000_000}},
        {
            "mode": "optimize",
            "goal": {"target_krw": 1_000_000},
            "optimization": {"envelopes": ["외식"], "reduction_grid": [0, 0.1]},
        },
    )

    for extra in requests:
        request = JsonDocument({"horizon_days": 7, "paths": 20, "seed": 42, **extra})
        receipt = Receipt(
            engine_commit="pinned-engine",
            identity=identity,
            request=JsonDocument(
                {"on_date": identity.as_of, "through_date": period.forecast_end.isoformat()}
            ),
            result=JsonDocument({"status": "ready"}),
            trigger="dialogue",
            numeric_request=request,
            numeric_result=engine.numeric(twin, request),
            period=period,
        )

        text = authoritative_text(receipt)

        assert "수치 분석 결과의 계약을 확인할 수 없어" not in text
        assert "필요 자료:" in text
        assert not any(term in text for term in _JARGON)
