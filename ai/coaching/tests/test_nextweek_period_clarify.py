# ruff: noqa: INP001
"""Live-session fixes: 다음주 purchase date, date-fragment merge, chat-turn period clarify.

Three related live-testing issues:
  #1 the purchase parser now recognizes "다음주" (next week) as a purchase date;
  #2 a bare date fragment ("다음주에") answers a pending purchase_date_required and
     re-resolves through the purchase route instead of being hijacked to the period path;
  #3 the chat-turn period-family codes return a 200 needs_clarification turn (like the
     purchase clarifications) instead of a 4xx that the backend turns into a 503, while
     forecast-validation and chart period errors keep their 4xx contract (scope guard).
"""

from datetime import date
from pathlib import Path

import httpx2
import pytest
from test_api import TOKEN, TestModel, setup
from test_engine import fixture
from test_purchase_what_if import card_fixture

from coaching_service.chat_answers import period_clarification_answer
from coaching_service.dialogue import merged_clarification_question, resolve_purchase_change
from coaching_service.fast_routes import (
    NaturalPurchase,
    _purchase_date_token,
    is_bare_purchase_fragment,
    natural_purchase,
)
from coaching_service.llm_contract import EvidenceInput, Routing
from coaching_service.schemas import Bootstrap, JsonDocument, PendingClarification, Session


class RouteMustNotRun(TestModel):
    async def route(self, evidence: EvidenceInput) -> Routing:
        raise AssertionError("a deterministic purchase turn must not wait for model routing")


class RouteTo(TestModel):
    def __init__(self, mode: str) -> None:
        super().__init__()
        self._mode = mode

    async def route(self, evidence: EvidenceInput) -> Routing:
        self.routes += 1
        self.seen.append(evidence)
        return Routing(mode=self._mode, source="llm")  # type: ignore[arg-type]


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


async def _bootstrap(client: httpx2.AsyncClient, twin: Bootstrap) -> str:
    assert (
        await client.post(
            "/v1/twin", json=twin.model_dump(mode="json"), headers={"Idempotency-Key": "init"},
        )
    ).status_code == 200
    session = await client.post("/v1/sessions", json={}, headers={"Idempotency-Key": "session"})
    return session.json()["id"]


# --- FIX 1: "다음주" is a recognized purchase date, alongside the existing tokens ---


def test_next_week_parses_to_natural_purchase() -> None:
    parsed = natural_purchase("다음주에 닌텐도 스위치 30만원 현금으로 사고싶어")
    assert isinstance(parsed, NaturalPurchase)
    assert parsed.amount_krw == 300_000
    assert parsed.envelope == "기타"
    assert parsed.date_token == "next_week"
    assert parsed.payment_hint == "cash"


def test_existing_purchase_date_tokens_still_work() -> None:
    assert _purchase_date_token("내일산다", exclude=None) == "tomorrow"
    assert _purchase_date_token("다음주에산다", exclude=None) == "next_week"
    assert _purchase_date_token("이번주에산다", exclude=None) == "this_week"
    assert _purchase_date_token("오늘산다", exclude=None) == "today"
    assert _purchase_date_token("2026-10-01에산다", exclude=None) == "2026-10-01"


def test_next_week_resolves_to_reference_plus_seven_days() -> None:
    purchase = NaturalPurchase(
        amount_krw=300_000, envelope="기타",
        date_token="next_week",  # noqa: S106 - a calendar token, not a credential.
        payment_hint="cash", card_payment_date=None,
    )
    twin = JsonDocument({"snapshot": {"accounts": [{"account_id": "a"}], "cards": []}})
    change = resolve_purchase_change(purchase, twin, date(2026, 9, 9))
    assert change.root["date"] == "2026-09-16"
    assert change.root["account_id"] == "a"


# --- FIX 2: a bare "다음주에" fragment merges into a pending purchase awaiting a date ---


def test_next_week_fragment_is_a_bare_purchase_fragment() -> None:
    assert is_bare_purchase_fragment("다음주에") is True
    pending = PendingClarification(
        kind="purchase", question="닌텐도 스위치 748000원 사고싶어", code="purchase_date_required"
    )
    assert merged_clarification_question(pending, "다음주에") == (
        "닌텐도 스위치 748000원 사고싶어 다음주에"
    )


@pytest.mark.anyio
async def test_next_week_full_sentence_purchase_reaches_verdict(tmp_path: Path) -> None:
    # The direct full sentence: the date now parses, so a single-account snapshot
    # resolves straight to a verdict (a Coaching carries a receipt; a ChatAnswer does not).
    model = RouteMustNotRun()
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=setup(tmp_path / "nw-full.sqlite3", model)),
        base_url="http://test", headers={"Authorization": "Bearer " + TOKEN},
    ) as client:
        path = "/v1/sessions/" + await _bootstrap(client, fixture())
        verdict = await client.post(
            path + "/messages",
            json={"question": "다음주에 닌텐도 스위치2를 748000원에 사고싶어"},
            headers={"Idempotency-Key": "t1"},
        )
        assert verdict.status_code == 200, verdict.text
        body = verdict.json()
        assert "receipt" in body
        assert body["receipt"]["request"]["changes"] == [
            {
                "kind": "expense",
                "date": "2026-09-16",
                "amount_krw": 748_000,
                "envelope": "기타",
                "account_id": "a",
            }
        ]
        assert model.routes == 0


@pytest.mark.anyio
async def test_next_week_date_clarify_then_fragment_merges_to_verdict(tmp_path: Path) -> None:
    # The clarify flow: amount+item without a date clarifies, then a bare "다음주에"
    # merges and re-resolves. A card+account snapshot still leaves the payment method
    # ambiguous (a "next clarify"), then 현금으로 resolves to the verdict.
    model = RouteMustNotRun()
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=setup(tmp_path / "nw-merge.sqlite3", model)),
        base_url="http://test", headers={"Authorization": "Bearer " + TOKEN},
    ) as client:
        path = "/v1/sessions/" + await _bootstrap(client, card_fixture())

        async def turn(question: str, key: str) -> dict:
            response = await client.post(
                path + "/messages", json={"question": question}, headers={"Idempotency-Key": key}
            )
            assert response.status_code == 200, response.text
            return response.json()

        first = await turn("닌텐도 스위치 748000원 사고싶어", "t1")
        assert first["answer_type"] == "purchase_review"
        assert first["fallback_reason"] == "purchase_date_required"

        after_date = await turn("다음주에", "t2")
        # The fragment merged into the pending purchase (not hijacked to the period
        # route); the date resolved, leaving only the payment method ambiguous.
        assert after_date["answer_type"] == "purchase_review"
        assert after_date["fallback_reason"] == "purchase_payment_method_required"

        verdict = await turn("현금으로", "t3")
        assert "receipt" in verdict
        assert verdict["receipt"]["request"]["changes"] == [
            {
                "kind": "expense",
                "date": "2026-09-16",
                "amount_krw": 748_000,
                "envelope": "기타",
                "account_id": "a",
            }
        ]
        session = Session.model_validate_json((await client.get(path)).content)
        assert session.pending_clarification is None
        assert model.routes == 0


# --- FIX 3 unit: each chat-turn period code maps to a digit-free 200 clarification ---


@pytest.mark.parametrize(
    "code",
    [
        "period_clarification_required",
        "period_conflict",
        "period_unsupported_calendar",
        "invalid_question_period",
        "period_not_supported_for_intent",
    ],
)
def test_chat_period_code_maps_to_needs_clarification(code: str) -> None:
    answer = period_clarification_answer(code)
    assert answer is not None
    assert answer.answer_type == "period_review"
    assert answer.status == "needs_clarification"
    assert answer.fallback_reason == code
    assert answer.model == "not_called"
    assert answer.wording_source == "engine"
    assert answer.text
    assert not any(ch.isdigit() for ch in answer.text)
    assert answer.evidence.root == {"period": {"clarification": code}}


@pytest.mark.parametrize(
    "code",
    [
        "validation_coverage_period_mismatch",
        "validation_receipt_identity_or_period_mismatch",
        "chart_period_out_of_range",
        "chart_reference_outside_period",
        "chart_purchase_period_closed",
        "chart_purchase_out_of_period",
        "period_has_no_future_days",
        "period_ends_before_reference",
    ],
)
def test_non_chat_period_codes_are_not_converted(code: str) -> None:
    # Scope guard: forecast-validation and chart period errors keep their 4xx contract.
    assert period_clarification_answer(code) is None


# --- FIX 3 API: chat-turn period ambiguity becomes a saved 200 needs_clarification ---


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("body", "code"),
    [
        ({"question": "한 달 뒤 예측"}, "period_clarification_required"),
        ({"question": "음력 윤달 말까지 예측"}, "period_unsupported_calendar"),
        ({"question": "2026-13-45까지 예측"}, "invalid_question_period"),
        (
            {"question": "30일 뒤 예측", "analysis": {"mode": "forecast", "horizon_days": 7}},
            "period_conflict",
        ),
    ],
)
async def test_chat_period_ambiguity_returns_needs_clarification(
    tmp_path: Path, body: dict, code: str
) -> None:
    model = RouteTo("forecast")
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=setup(tmp_path / "period-clarify.sqlite3", model)),
        base_url="http://test", headers={"Authorization": "Bearer " + TOKEN},
    ) as client:
        path = "/v1/sessions/" + await _bootstrap(client, fixture())
        response = await client.post(
            path + "/messages", json=body, headers={"Idempotency-Key": "turn"}
        )
        assert response.status_code == 200, response.text
        answer = response.json()
        assert answer["answer_type"] == "period_review"
        assert answer["status"] == "needs_clarification"
        assert answer["fallback_reason"] == code
        assert answer["model"] == "not_called"
        # A 200 clarification is a normal recorded turn (user + assistant message).
        session = Session.model_validate_json((await client.get(path)).content)
        assert len(session.messages) == 2
        # The asked period is kept so a bare answer ("이번 달") completes the question; a conflict
        # with the structured analysis is not, since the analysis itself has to change.
        pending = session.pending_clarification
        if code == "period_conflict":
            assert pending is None
        else:
            assert pending is not None
            assert pending.kind == "period"
            assert pending.question == body["question"]
        assert model.writes == 0


@pytest.mark.anyio
@pytest.mark.parametrize("question", ["한 달 뒤 예측", "음력 윤달 말까지 예측", "2026-13-45까지 예측"])
async def test_a_bare_period_answer_completes_the_asked_question(tmp_path: Path, question: str) -> None:
    model = RouteTo("forecast")
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=setup(tmp_path / "period-answer.sqlite3", model)),
        base_url="http://test", headers={"Authorization": "Bearer " + TOKEN},
    ) as client:
        path = "/v1/sessions/" + await _bootstrap(client, fixture())
        asked = await client.post(
            path + "/messages", json={"question": question}, headers={"Idempotency-Key": "q"},
        )
        assert asked.json()["status"] == "needs_clarification"
        answered = await client.post(
            path + "/messages", json={"question": "이번 달"}, headers={"Idempotency-Key": "a"},
        )
        assert answered.status_code == 200, answered.text
        assert answered.json().get("status") != "needs_clarification", answered.json().get("text")
        session = Session.model_validate_json((await client.get(path)).content)
        assert session.pending_clarification is None


@pytest.mark.anyio
async def test_non_forecast_intent_with_period_clarifies_instead_of_503(tmp_path: Path) -> None:
    model = RouteTo("history")
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=setup(tmp_path / "period-intent.sqlite3", model)),
        base_url="http://test", headers={"Authorization": "Bearer " + TOKEN},
    ) as client:
        path = "/v1/sessions/" + await _bootstrap(client, fixture())
        response = await client.post(
            path + "/messages",
            json={"question": "현재까지 소비 알려줘", "period": {"kind": "rolling_days", "days": 7}},
            headers={"Idempotency-Key": "turn"},
        )
        assert response.status_code == 200, response.text
        answer = response.json()
        assert answer["answer_type"] == "period_review"
        assert answer["status"] == "needs_clarification"
        assert answer["fallback_reason"] == "period_not_supported_for_intent"
        assert model.writes == 0
