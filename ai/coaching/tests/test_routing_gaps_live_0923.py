# ruff: noqa: INP001
"""Routing gaps found by the 2026-09-23 live end-to-end run.

- "예산 위험해?" had "위험" but no admitted risk signal, so the model sent it to a
  generic review instead of the risk analysis.
- "교통비 이번달 얼마 썼어" put the envelope before the period, which the exact
  spending grammar rejected, so the model answered a review without the amount.
- "오늘 날씨 어때" was routed to a finance mode and then asked for a period only
  because the period parser trips on "오늘"; it is simply off-topic.
"""

from pathlib import Path

import httpx2
import pytest
from test_api import TOKEN, setup
from test_engine import fixture
from test_multiturn_clarification_context import RouteTo

from coaching_service.fast_routes import deterministic_analysis_route
from coaching_service.spending_history import supports_spending_question


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def test_budget_risk_question_routes_to_risk_without_the_model() -> None:
    assert deterministic_analysis_route("예산 위험해?") == "risk"
    assert deterministic_analysis_route("이번달 예산 위험한가") == "risk"
    # A definition question keeps the knowledge route.
    assert deterministic_analysis_route("예산 위험이 무슨 뜻이야") is None


@pytest.mark.parametrize(
    "question",
    [
        "교통비 이번달 얼마 썼어",
        "외식비 지난달 얼마",
        "쇼핑 봉투 이번달 소비 알려줘",
        "이번달 교통비 얼마 썼어",
    ],
)
def test_envelope_first_spending_questions_use_the_same_grammar(question: str) -> None:
    assert supports_spending_question(question)


def test_envelope_first_rewrite_does_not_admit_unsupported_filters() -> None:
    # The rewrite only reorders; filters the grammar never supported stay unsupported.
    assert not supports_spending_question("교통비 이번달 1만원 이상 얼마 썼어")


async def _ask(tmp_path: Path, question: str) -> dict[str, object]:
    model = RouteTo("review")
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=setup(tmp_path / "gaps.sqlite3", model)),
        base_url="http://test", headers={"Authorization": "Bearer " + TOKEN},
    ) as client:
        assert (
            await client.post(
                "/v1/twin", json=fixture().model_dump(mode="json"), headers={"Idempotency-Key": "t"}
            )
        ).status_code == 200
        session = await client.post("/v1/sessions", json={}, headers={"Idempotency-Key": "s"})
        reply = await client.post(
            f"/v1/sessions/{session.json()['id']}/messages",
            json={"question": question},
            headers={"Idempotency-Key": "q"},
        )
        assert reply.status_code == 200, reply.text
        return reply.json()


@pytest.mark.anyio
async def test_off_topic_question_misrouted_to_finance_is_answered_as_out_of_scope(tmp_path: Path) -> None:
    answer = await _ask(tmp_path, "오늘 날씨 어때")
    assert (answer["status"], answer["fallback_reason"]) == ("out_of_scope", "non_financial_question")


@pytest.mark.anyio
async def test_finance_question_with_ambiguous_period_still_asks_for_the_period(tmp_path: Path) -> None:
    answer = await _ask(tmp_path, "오늘 기준 예산 어때")
    assert (answer["status"], answer["fallback_reason"]) == (
        "needs_clarification",
        "period_clarification_required",
    )


@pytest.mark.parametrize(
    "question",
    [
        # Review D1: a purchase must keep the purchase review, never a purchase-less risk run.
        "내일 노트북 200만원 사면 예산 위험해?",
        # Review D2: general, how-to, plan and other-subject budget questions stay model-routed.
        "예산 초과하면 위험한가요?",
        "예산을 위험하지 않게 짜려면 어떻게 해?",
        "국가 예산 적자 위험해?",
        "예산 없이 사는 거 위험할까?",
        "예산 관리 앱 쓰는 거 위험해?",
        "예산 위험 알림 끄는 법",
        "여행 예산 100만원인데 위험해?",
        "예산을 늘리면 위험이 줄어?",
    ],
)
def test_budget_risk_shortcut_admits_only_the_bare_question(question: str) -> None:
    assert deterministic_analysis_route(question) is None


@pytest.mark.anyio
@pytest.mark.parametrize(
    "question",
    ["내일 외식해도 될까?", "주말에 쇼핑 가도 괜찮을까?", "다음주 교통비 괜찮아?", "올해 생활비 괜찮을까?"],
)
async def test_everyday_spending_words_count_as_finance(tmp_path: Path, question: str) -> None:
    # Review D3: these are finance questions with an unresolved period, not off-topic.
    answer = await _ask(tmp_path, question)
    assert answer["status"] != "out_of_scope", answer
