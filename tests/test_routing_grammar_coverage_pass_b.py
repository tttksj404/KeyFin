# ruff: noqa: INP001
"""Pass B: reasonable natural phrasings hit the correct deterministic route.

Every expansion here pairs an intended-phrasing assertion with a set of
should-NOT-match sentences.  The false-positive guards are the primary risk:
concept/definition/goal questions must never be swallowed into a lookup, a
spending total, or a purchase clarify.  See scratchpad/impl_passB.md.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

import httpx2
import pytest
from test_api import TOKEN, TestModel, setup
from test_engine import fixture

from coaching_service.chat_answers import purchase_clarification_answer
from coaching_service.dialogue import resolve_purchase_change
from coaching_service.errors import ServiceError
from coaching_service.fast_routes import (
    NaturalPurchase,
    deterministic_analysis_route,
    deterministic_lookup_route,
    natural_goal,
    natural_purchase,
)
from coaching_service.personal_query import select_personal_topic
from coaching_service.schemas import JsonDocument
from coaching_service.spending_history import supports_spending_question

if TYPE_CHECKING:
    from pathlib import Path

    from coaching_service.llm_contract import EvidenceInput, Routing


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


# --- 1. debts: 빚 / 대출 aliases ------------------------------------------------


@pytest.mark.parametrize("question", ["빚 얼마야", "대출 얼마 남았어", "내 빚 알려줘", "남은 대출 얼마"])
def test_debt_aliases_route_to_debts_lookup(question: str) -> None:
    assert select_personal_topic(question) == "debts"
    assert deterministic_lookup_route(question) == "personal"


@pytest.mark.parametrize("question", [
    "대출 이자율이 뭐야",  # concept, not a balance lookup
    "빚 갚는 순서",  # advice, not a balance lookup
    "대출 이자를 어떻게 계산해",  # calculation concept
    "빚투자 괜찮을까",  # not a debts-balance grammar
])
def test_debt_alias_does_not_swallow_concept_or_advice(question: str) -> None:
    assert select_personal_topic(question) is None
    assert deterministic_lookup_route(question) is None


# --- definition guard on the lookup route (finding 1) --------------------------


@pytest.mark.parametrize("question", [
    "대출이 뭐야",
    "빚이 뭐야",
    "예산이 뭐야",
    "자산이 뭐야",
    "순자산 개념",
])
def test_definition_shaped_lookup_falls_through_to_concept(question: str) -> None:
    # A definition-shaped question must reach the finance-concept path, never be
    # captured as a personal-data lookup even though the alias is registered.
    assert deterministic_lookup_route(question) is None


@pytest.mark.parametrize("question", [
    "빚 얼마야",
    "대출 얼마 남았어",
    "내 자산 얼마야",
    "계좌 상태",
    "남은 예산 얼마야",
])
def test_genuine_lookups_still_route_despite_definition_guard(question: str) -> None:
    assert deterministic_lookup_route(question) == "personal"


# --- 3. assets: 순자산 ----------------------------------------------------------


def test_net_worth_alias_is_recognized() -> None:
    assert select_personal_topic("순자산 얼마야") == "assets"
    assert deterministic_lookup_route("순자산 얼마야") == "personal"


@pytest.mark.parametrize("question", ["순자산 개념", "순자산이 늘어나는 이유는 뭐야"])
def test_net_worth_alias_does_not_swallow_concept(question: str) -> None:
    assert select_personal_topic(question) is None


# --- 4/9. lookup grammar: 상태 / 있어 / 에 조사, 자산 상태·현황 ------------------


@pytest.mark.parametrize(("question", "topic"), [
    ("계좌 상태", "accounts"),
    ("계좌 얼마 있어", "accounts"),
    ("계좌에 얼마 있어", "accounts"),
    ("자산 상태 보여줘", "assets"),
    ("자산 현황", "assets"),
    ("자산 상태 알려줘", "assets"),
])
def test_state_and_have_forms_route_to_lookup(question: str, topic: str) -> None:
    assert select_personal_topic(question) == topic
    assert deterministic_lookup_route(question) == "personal"


@pytest.mark.parametrize("question", [
    "계좌 상태가 나빠지면 어떻게 돼",  # explanatory, not a state lookup
    "자산 상태를 개선하는 방법",  # advice
    "돈 관리 상태 점검하는 법",  # advice, no registered topic
])
def test_state_forms_do_not_swallow_advice(question: str) -> None:
    assert select_personal_topic(question) is None


# --- 8. budget in the fast lookup route ----------------------------------------


@pytest.mark.parametrize("question", ["남은 예산 얼마야", "예산 현황 보여줘", "봉투 잔액 알려줘"])
def test_budget_uses_the_deterministic_lookup_route(question: str) -> None:
    # budget's summary is rendered directly from the ledger, so it is as
    # grounded as the snapshot topics and no longer always detours via the model.
    assert select_personal_topic(question) == "budget"
    assert deterministic_lookup_route(question) == "personal"


@pytest.mark.parametrize("question", ["예산 세우는 방법 알려줘", "예산을 어떻게 짜"])
def test_budget_advice_stays_off_the_lookup_route(question: str) -> None:
    assert select_personal_topic(question) is None


# --- 5. risk stem: 모자랄 -------------------------------------------------------


@pytest.mark.parametrize("question", [
    "월말에 돈 모자랄까",
    "이번달 생활비 모자란 거 아니야",
    "다음달 잔액 모자랐어",
])
def test_shortfall_conjugations_route_to_risk(question: str) -> None:
    assert deterministic_analysis_route(question) == "risk"


@pytest.mark.parametrize("question", [
    "모자가 얼마야",  # 모자 = hat; must not become a shortfall risk
    "새 모자 사고싶어",  # hat purchase, not a risk
    "모자란 지식을 어떻게 채워",  # generic, no future/financial risk frame
])
def test_shortfall_stem_does_not_match_hat_or_generic(question: str) -> None:
    assert deterministic_analysis_route(question) != "risk"


# --- 7. spend-forecast: 쓸까 계열 ----------------------------------------------


@pytest.mark.parametrize("question", [
    "이번달 얼마 쓸까",
    "이번달 돈 얼마나 쓸까",
    "다음달 얼마 지출할까",
])
def test_future_spend_questions_route_to_forecast(question: str) -> None:
    assert deterministic_analysis_route(question) == "forecast"


@pytest.mark.parametrize("question", [
    "이번달 편지 쓸까",  # 쓰다=write, no money/quantity signal
    "일기 쓸까 말까",  # no future marker, no money signal
    "쓸데없는 지출이 뭐야",  # definition-language guard
])
def test_spend_forecast_does_not_match_non_financial_write(question: str) -> None:
    assert deterministic_analysis_route(question) != "forecast"


# --- 6. spending verbs: 나갔 / 지출했 ------------------------------------------


@pytest.mark.parametrize("question", [
    "이번달 교통비 얼마 나갔어",
    "이번달 교통비 얼마 지출했어",
    "지난달 얼마 나갔어",
])
def test_spending_verbs_are_recognized(question: str) -> None:
    assert supports_spending_question(question) is True


@pytest.mark.parametrize("question", [
    "교통비 아꼈어",  # saving, not a spending total
    "이번달 교통비 왜 나갔어",  # explanatory, not a supported aggregate
    "교통비 지출했는데 괜찮을까",  # advisory, not a bare aggregate
])
def test_spending_verbs_do_not_swallow_non_spending(question: str) -> None:
    assert supports_spending_question(question) is False


# --- 2. goal: amount with no particle before the verb --------------------------


@pytest.mark.parametrize(("question", "target"), [
    ("이번달 100만원 모을 수 있어", 1_000_000),
    ("다음달 50만원 모을 수 있을까", 500_000),
])
def test_goal_amount_without_trailing_particle_parses(question: str, target: int) -> None:
    parsed = natural_goal(question)
    assert parsed is not None
    assert parsed.target_krw == target


@pytest.mark.parametrize("question", [
    "100만원 모을 수 있어",  # no period
    "이번달 백만원 모을 수 있어",  # non-arabic amount
    "이번달 100만원 어디에 투자할까",  # advisory/product
    "이번달 100만원 목표를 세워줘",  # planning verb (disallowed)
])
def test_goal_relaxation_still_rejects_ambiguous_or_advisory(question: str) -> None:
    assert natural_goal(question) is None


# --- 10. card purchase without an ISO settlement date: one clear next-step ------


def test_clean_single_card_purchase_asks_for_settlement_date_not_a_loop() -> None:
    # A clean single-method card phrasing must not re-ask cash-vs-card forever;
    # it returns a distinct code asking precisely for the settlement date.
    outcome = natural_purchase("노트북 30만원 신용카드로 이번주에 사도 될까")
    assert outcome == "purchase_card_payment_date_required"


def test_clean_single_cash_purchase_still_resolves() -> None:
    parsed = natural_purchase("노트북 30만원 현금으로 이번주에 사도 될까")
    assert isinstance(parsed, NaturalPurchase)
    assert parsed.payment_hint == "cash"


def test_card_with_explicit_settlement_date_still_parses() -> None:
    parsed = natural_purchase("노트북 30만원 카드로 이번주에 사서 2026-10-25에 결제")
    assert isinstance(parsed, NaturalPurchase)
    assert parsed.payment_hint == "card"
    assert parsed.card_payment_date == "2026-10-25"


def test_new_card_date_code_has_a_digit_free_clarification() -> None:
    answer = purchase_clarification_answer("purchase_card_payment_date_required")
    assert answer is not None
    assert answer.status == "needs_clarification"
    assert answer.fallback_reason == "purchase_card_payment_date_required"
    assert answer.model == "not_called"
    # The safety contract keeps every clarification digit-free.
    assert not any(character.isdigit() for character in answer.text)


def test_single_card_snapshot_without_date_asks_for_settlement_date() -> None:
    # payment_hint None inferred to a single-card snapshot still needs the date;
    # the resolver raises the same precise code rather than re-asking the method.
    purchase = NaturalPurchase(
        amount_krw=300_000,
        envelope="기타",
        date_token="this_week",  # noqa: S106 - a calendar token, not a credential.
        payment_hint=None,
        card_payment_date=None,
    )
    twin = JsonDocument({"snapshot": {"accounts": [], "cards": [{"card_id": "c1"}]}})
    with pytest.raises(ServiceError) as raised:
        resolve_purchase_change(purchase, twin, date(2026, 9, 9))
    assert raised.value.code == "purchase_card_payment_date_required"


class _RouteMustNotRun(TestModel):
    async def route(self, evidence: EvidenceInput) -> Routing:
        raise AssertionError("a text-only purchase clarify must not wait for model routing")


@pytest.mark.anyio
async def test_clean_card_purchase_clarifies_at_200_without_model(tmp_path: Path) -> None:
    model = _RouteMustNotRun()
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=setup(tmp_path / "passb-card.sqlite3", model)),
        base_url="http://test", headers={"Authorization": "Bearer " + TOKEN},
    ) as client:
        assert (
            await client.post(
                "/v1/twin", json=fixture().model_dump(mode="json"),
                headers={"Idempotency-Key": "init"},
            )
        ).status_code == 200
        session = await client.post("/v1/sessions", json={}, headers={"Idempotency-Key": "s"})
        response = await client.post(
            "/v1/sessions/" + session.json()["id"] + "/messages",
            json={"question": "노트북 30만원 신용카드로 이번주에 사도 될까"},
            headers={"Idempotency-Key": "turn"},
        )
    assert response.status_code == 200, response.text
    answer = response.json()
    assert answer["answer_type"] == "purchase_review"
    assert answer["status"] == "needs_clarification"
    assert answer["fallback_reason"] == "purchase_card_payment_date_required"
    assert answer["model"] == "not_called"
    assert model.routes == 0
    assert model.writes == 0
