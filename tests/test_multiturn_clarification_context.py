# ruff: noqa: INP001
"""Multi-turn clarification context (live-issue class #3 + the sweep's multi-turn note).

Each turn used to re-parse only the current question, so a bare follow-up after a
``needs_clarification`` ("30만원" after "얼마?", "이번달" after "언제?") parsed to
nothing and the pending purchase/spending was lost. These flows verify that a bare
fragment merges into the stored clarification and re-resolves, that a complete
different question discards the stale context instead of force-merging, and that a
retried merge turn stays idempotent.
"""

from pathlib import Path

import httpx2
import pytest
from test_api import TOKEN, TestModel, setup
from test_engine import fixture
from test_purchase_what_if import card_fixture

from coaching_service.dialogue import merged_clarification_question
from coaching_service.fast_routes import (
    _MERGED_QUESTION_MAX_CHARS,
    NaturalPurchase,
    is_bare_purchase_fragment,
    merged_purchase_question,
    natural_purchase,
    spending_period_fragment,
)
from coaching_service.llm_contract import EvidenceInput, Routing
from coaching_service.schemas import Bootstrap, JsonDocument, PendingClarification, Session


class RouteMustNotRun(TestModel):
    async def route(self, evidence: EvidenceInput) -> Routing:
        raise AssertionError("a merged purchase turn must resolve without model routing")


class RouteTo(TestModel):
    """Force one model route so a fresh (non-merged) follow-up lands deterministically."""

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


def september_spending_fixture() -> Bootstrap:
    """One September 교통비 expense so an in-month spending query is answerable."""
    base = fixture()
    row = {
        **base.transactions[0].root,
        "transaction_id": "sep",
        "category": "교통",
        "subcategory": "택시",
        "amount_krw": 5000,
        "transaction_date": "2026-09-05",
    }
    return base.model_copy(update={"transactions": (JsonDocument(row),)})


# --- unit: the merge decision (bare fragment merges, complete turn discards) ---


def test_purchase_amount_fragment_merges_but_concept_and_offtopic_do_not() -> None:
    pending = PendingClarification(
        kind="purchase", question="닌텐도 스위치 사고싶어", code="purchase_amount_required"
    )
    assert merged_clarification_question(pending, "30만원") == "닌텐도 스위치 사고싶어 30만원"
    assert merged_clarification_question(pending, "내일") == "닌텐도 스위치 사고싶어 내일"
    assert merged_clarification_question(pending, "현금으로") == "닌텐도 스위치 사고싶어 현금으로"
    # A complete different question is never force-merged.
    assert merged_clarification_question(pending, "복리가 뭐야") is None
    assert merged_clarification_question(pending, "저녁 뭐 먹을까") is None
    assert merged_clarification_question(pending, "노트북 100만원 오늘 살까") is None
    assert merged_clarification_question(pending, "이번달 소비 얼마야") is None


def test_payment_method_answer_overrides_stale_conflicting_token() -> None:
    # A pending clarification that stored BOTH a cash and a card token ("현금결제
    # 신용카드로") must be resolvable: the user's single-method answer overrides the
    # conflicting stale token instead of appending forever (the reported loop where
    # "현금·계좌 결제인지 카드 결제인지" repeats no matter what the user answers).
    stale = "노트북 30만원 현금결제 신용카드로 이번주에 사도될까"
    assert natural_purchase(stale) == "purchase_payment_method_required"
    # Answering "현금" drops the stale card token and resolves to a cash purchase.
    cash_merge = merged_purchase_question(stale, "현금으로")
    assert cash_merge is not None
    cash_result = natural_purchase(cash_merge)
    assert isinstance(cash_result, NaturalPurchase)
    assert cash_result.payment_hint == "cash"
    # Answering "신용카드" drops the stale cash token; it no longer re-asks the method,
    # it advances to the distinct card settlement-date question.
    assert natural_purchase(merged_purchase_question(stale, "신용카드")) == (
        "purchase_card_payment_date_required"
    )
    # A contradictory answer (both methods) is not a choice, so it still asks.
    assert natural_purchase(merged_purchase_question(stale, "현금 신용카드")) == (
        "purchase_payment_method_required"
    )


def test_distinct_past_tense_purchase_is_not_merged() -> None:
    # A complete, independent purchase statement ("커피 3만원 샀어") must discard the
    # pending 닌텐도 clarification and be handled fresh, not merged as a bare amount.
    pending = PendingClarification(
        kind="purchase", question="닌텐도 스위치 사고싶어", code="purchase_amount_required"
    )
    assert is_bare_purchase_fragment("커피 3만원 샀어") is False
    assert merged_clarification_question(pending, "커피 3만원 샀어") is None


def test_merged_purchase_context_is_bounded() -> None:
    # A pathological chain of fragment turns must not grow the stored pending text
    # without bound (it would eventually exceed PendingClarification.question=4000).
    question = "닌텐도 스위치 사고싶어"
    for _ in range(2000):
        merged = merged_clarification_question(
            PendingClarification(kind="purchase", question=question, code="purchase_amount_required"),
            "현금으로",
        )
        assert merged is not None
        question = merged
        assert len(question) <= _MERGED_QUESTION_MAX_CHARS


def test_spending_period_fragment_merges_to_valid_query() -> None:
    pending = PendingClarification(
        kind="spending", question="소비 조회", code="spending_clarification"
    )
    # "소비 조회" alone cannot re-form a supported query, so the period + all-envelope
    # aggregate is synthesized; a period that keeps a stated envelope is preserved.
    assert merged_clarification_question(pending, "이번달") == "이번달 소비 얼마야"
    with_envelope = PendingClarification(
        kind="spending", question="외식비 얼마 썼어", code="spending_clarification"
    )
    assert merged_clarification_question(with_envelope, "이번달") == "이번달 외식비 얼마 썼어"
    assert merged_clarification_question(pending, "복리가 뭐야") is None


def test_fragment_helpers_reject_complete_routes() -> None:
    assert is_bare_purchase_fragment("30만원") is True
    assert is_bare_purchase_fragment("현금으로") is True
    assert is_bare_purchase_fragment("복리가 뭐야") is False
    assert is_bare_purchase_fragment("노트북 100만원 오늘 살까") is False
    assert spending_period_fragment("이번달") == "이번달"
    assert spending_period_fragment("이번달 소비 얼마야") is None
    assert spending_period_fragment("복리가 뭐야") is None


# --- PURCHASE: multi-step merge to a verdict (amount → date → payment → verdict) ---


@pytest.mark.anyio
async def test_purchase_multi_turn_merges_to_verdict(tmp_path: Path) -> None:
    model = RouteMustNotRun()
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=setup(tmp_path / "mt-purchase.sqlite3", model)),
        base_url="http://test", headers={"Authorization": "Bearer " + TOKEN},
    ) as client:
        # A single account plus a single card makes the payment method genuinely
        # ambiguous until the user names cash, so every clarify step is exercised.
        path = "/v1/sessions/" + await _bootstrap(client, card_fixture())

        async def turn(question: str, key: str) -> dict:
            response = await client.post(
                path + "/messages", json={"question": question}, headers={"Idempotency-Key": key}
            )
            assert response.status_code == 200, response.text
            return response.json()

        first = await turn("닌텐도 스위치 사고싶어", "t1")
        assert first["answer_type"] == "purchase_review"
        assert first["fallback_reason"] == "purchase_amount_required"

        after_amount = await turn("30만원", "t2")
        assert after_amount["answer_type"] == "purchase_review"
        assert after_amount["fallback_reason"] == "purchase_date_required"

        # "이번주" supplies the purchase timing (and the default review horizon);
        # a card+account snapshot still leaves the payment method ambiguous.
        after_date = await turn("이번주", "t3")
        assert after_date["answer_type"] == "purchase_review"
        assert after_date["fallback_reason"] == "purchase_payment_method_required"

        verdict = await turn("현금으로", "t4")
        # The follow-ups accumulated into one resolved purchase and produced a
        # coaching verdict (a Coaching carries a receipt; a ChatAnswer does not).
        assert "receipt" in verdict
        assert verdict["receipt"]["request"]["changes"] == [
            {
                "kind": "expense",
                "date": "2026-09-09",
                "amount_krw": 300_000,
                "envelope": "기타",
                "account_id": "a",
            }
        ]
        # Pending context is cleared once resolved.
        session = Session.model_validate_json((await client.get(path)).content)
        assert session.pending_clarification is None
        assert model.writes == 0
        assert model.routes == 0


# --- SPENDING: a period follow-up answers the earlier ambiguous spending turn ---


@pytest.mark.anyio
async def test_spending_period_followup_answers_this_month(tmp_path: Path) -> None:
    model = RouteTo("history")
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=setup(tmp_path / "mt-spending.sqlite3", model)),
        base_url="http://test", headers={"Authorization": "Bearer " + TOKEN},
    ) as client:
        path = "/v1/sessions/" + await _bootstrap(client, september_spending_fixture())
        ambiguous = await client.post(
            path + "/messages", json={"question": "소비 조회"}, headers={"Idempotency-Key": "s1"}
        )
        assert ambiguous.status_code == 200, ambiguous.text
        assert ambiguous.json()["answer_type"] == "spending_history"
        assert ambiguous.json()["status"] == "needs_clarification"
        pending = Session.model_validate_json((await client.get(path)).content).pending_clarification
        assert pending is not None
        assert pending.kind == "spending"

        answered = await client.post(
            path + "/messages", json={"question": "이번달"}, headers={"Idempotency-Key": "s2"}
        )
        assert answered.status_code == 200, answered.text
        body = answered.json()
        assert body["answer_type"] == "spending_history"
        assert body["status"] == "answered"
        assert body["total_krw"] == 5000
        assert {row["envelope"]: row["total_krw"] for row in body["rows"]} == {"교통비": 5000}
        # The period question was resolved deterministically (no second model route).
        assert model.routes == 1
        session = Session.model_validate_json((await client.get(path)).content)
        assert session.pending_clarification is None


# --- GUARD: a complete different question discards the pending purchase context ---


@pytest.mark.anyio
async def test_concept_followup_is_not_merged_and_discards_pending(tmp_path: Path) -> None:
    model = RouteTo("finance")
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=setup(tmp_path / "mt-guard-concept.sqlite3", model)),
        base_url="http://test", headers={"Authorization": "Bearer " + TOKEN},
    ) as client:
        path = "/v1/sessions/" + await _bootstrap(client, fixture())
        first = await client.post(
            path + "/messages",
            json={"question": "닌텐도 스위치 사고싶어"},
            headers={"Idempotency-Key": "g1"},
        )
        assert first.json()["fallback_reason"] == "purchase_amount_required"

        concept = await client.post(
            path + "/messages", json={"question": "복리가 뭐야"}, headers={"Idempotency-Key": "g2"}
        )
        assert concept.status_code == 200, concept.text
        # Answered on the concept route, never merged into the pending purchase.
        assert concept.json()["answer_type"] == "finance_education"
        session = Session.model_validate_json((await client.get(path)).content)
        assert session.pending_clarification is None


@pytest.mark.anyio
async def test_offtopic_followup_is_not_merged_and_discards_pending(tmp_path: Path) -> None:
    model = RouteTo("other")
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=setup(tmp_path / "mt-guard-offtopic.sqlite3", model)),
        base_url="http://test", headers={"Authorization": "Bearer " + TOKEN},
    ) as client:
        path = "/v1/sessions/" + await _bootstrap(client, fixture())
        first = await client.post(
            path + "/messages",
            json={"question": "닌텐도 스위치 사고싶어"},
            headers={"Idempotency-Key": "o1"},
        )
        assert first.json()["fallback_reason"] == "purchase_amount_required"

        offtopic = await client.post(
            path + "/messages",
            json={"question": "저녁 뭐 먹을까"},
            headers={"Idempotency-Key": "o2"},
        )
        assert offtopic.status_code == 200, offtopic.text
        assert offtopic.json()["answer_type"] == "scope_response"
        assert offtopic.json()["status"] == "out_of_scope"
        session = Session.model_validate_json((await client.get(path)).content)
        assert session.pending_clarification is None


# --- IDEMPOTENCY: a retried merge turn returns the same result ---


@pytest.mark.anyio
async def test_retried_merge_turn_is_idempotent(tmp_path: Path) -> None:
    model = RouteMustNotRun()
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=setup(tmp_path / "mt-idem.sqlite3", model)),
        base_url="http://test", headers={"Authorization": "Bearer " + TOKEN},
    ) as client:
        path = "/v1/sessions/" + await _bootstrap(client, fixture())
        first = await client.post(
            path + "/messages",
            json={"question": "닌텐도 스위치 사고싶어"},
            headers={"Idempotency-Key": "i1"},
        )
        assert first.json()["fallback_reason"] == "purchase_amount_required"
        body = {"question": "30만원"}
        merged = await client.post(path + "/messages", json=body, headers={"Idempotency-Key": "merge"})
        retry = await client.post(path + "/messages", json=body, headers={"Idempotency-Key": "merge"})
        assert merged.status_code == retry.status_code == 200
        assert merged.json() == retry.json()
        assert merged.json()["fallback_reason"] == "purchase_date_required"
