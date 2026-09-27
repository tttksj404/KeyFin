# ruff: noqa: INP001
"""A flow suite must reject failed checks and use an input-only accounting oracle."""

from datetime import date
from pathlib import Path

import httpx2

from benchmarks.coaching.flow.client import Flow
from benchmarks.coaching.flow.fixtures import expected_month_spend, scenario
from benchmarks.coaching.flow.references import exact_references
from benchmarks.coaching.flow.run import run
from coaching_service.chat_answers import ChatAnswer
from coaching_service.schemas import JsonDocument


def test_month_spend_oracle_excludes_prior_month_and_reverses_canceled_payment() -> None:
    # Given: two observed September days, then a payment and a smaller purchase.
    fixture = scenario("synthetic-owner", date(2026, 9, 3))
    # When: the first payment is canceled after both purchases.
    total = expected_month_spend(fixture, canceled=True)
    # Then: only September's observed days and the uncanceled purchase remain.
    assert total == 14000


def test_month_start_oracle_does_not_invent_current_month_history() -> None:
    # Given: all observed history precedes the first day of the current month.
    fixture = scenario("synthetic-owner", date(2028, 3, 1))
    # When: both same-day purchases have occurred and neither is canceled.
    total = expected_month_spend(fixture, canceled=False)
    # Then: leap-day history is excluded from the March total.
    assert total == 62000


def test_payment_chat_flow_persists_after_real_api_process_restart(tmp_path: Path) -> None:
    # Given: a fresh synthetic owner and an isolated SQLite database.
    output = tmp_path / "artifacts" / "flow"
    # When: the complete TCP lifecycle terminates and recreates the API process.
    report = run(output, "fake", date(2026, 9, 3))
    # Then: every financial and persistence gate passes with separate process IDs.
    assert report.completed, [check.name for check in report.checks if not check.passed]
    assert report.process_ids[0] != report.process_ids[1]
    assert report.final_process_stopped
    assert report.backend == "fake"


def test_required_router_template_fallback_fails_admission() -> None:
    # Given: an HTTP answer could still exist after an intent model deadline.
    route = JsonDocument({"mode": "review", "source": "template", "fallback_reason": "deadline"})
    with httpx2.Client() as client:
        flow = Flow(client)
        # When: the benchmark observes the stored routing metadata.
        flow.observe_route("forecast", route, required=True)
    # Then: a fallback is explicit and is never counted as accepted GPU routing.
    assert flow.checks[0].passed is False
    assert flow.routes[0].fallback_reason == "deadline"


def test_clear_numeric_template_route_passes_without_model_route_adoption() -> None:
    # Given: a narrow deterministic FDT mode has no fallback reason and still has a numeric contract.
    route = JsonDocument({"mode": "forecast", "source": "template"})
    with httpx2.Client() as client:
        flow = Flow(client)
        # When: the flow observes the intentionally router-free request.
        flow.observe_route("forecast", route, required=True, allows_deterministic=True)
    # Then: deterministic selection passes, while fallback templates remain covered above.
    assert flow.checks[0].passed is True


def test_exact_personal_engine_route_passes_without_model_route_adoption() -> None:
    # Given: the personal grammar is independently parsed and the engine returns
    # the ledger-backed response without falling back from a model decision.
    answer = ChatAnswer(
        id="personal-1",
        answer_type="personal_context",
        status="answered",
        text="계좌 잔액 합계입니다.",
        wording_source="engine",
        model="not_called",
        evidence=JsonDocument({"routing": {"mode": "personal", "source": "template"}}),
        created_at=0,
    )
    with httpx2.Client() as client:
        flow = Flow(client)
        # When: the benchmark observes the complete engine provenance.
        flow.observe("personal", answer)
    # Then: the deterministic grammar is accepted, without treating it as LLM adoption.
    assert flow.checks[0].passed is True


def test_missing_optional_router_metadata_is_not_claimed_as_model_adoption() -> None:
    # Given: a general concept response does not expose an intent route receipt.
    with httpx2.Client() as client:
        flow = Flow(client)
        # When: the available evidence is recorded.
        flow.observe_route("concept", None, required=False)
    # Then: absent metadata remains absent instead of being synthesized as an LLM call.
    assert flow.routes[0].metadata_available is False
    assert flow.routes[0].source is None
    assert flow.checks == []


def test_answer_reference_rejects_wrong_kind_despite_same_text_and_id() -> None:
    # Given: the stored reply text matches, but a chat result points at a coaching endpoint.
    answer = JsonDocument({"id": "answer-1", "text": "동일한 설명"})
    session = JsonDocument(
        {
            "messages": [
                {"role": "user", "content": "질문", "response": None},
                {
                    "role": "assistant",
                    "content": "동일한 설명",
                    "response": {"kind": "coaching", "id": "answer-1"},
                },
            ]
        }
    )
    # When / Then: text-only persistence cannot pass the source-link contract.
    assert not exact_references(session, (answer,))


def test_answer_reference_rejects_a_different_answer_with_the_same_text() -> None:
    # Given: repeated text does not identify the same saved answer.
    answer = JsonDocument({"id": "answer-1", "text": "동일한 설명"})
    session = JsonDocument(
        {
            "messages": [
                {"role": "user", "content": "질문", "response": None},
                {
                    "role": "assistant",
                    "content": "동일한 설명",
                    "response": {"kind": "chat", "id": "answer-2"},
                },
            ]
        }
    )
    # When / Then: reconnect hydration cannot silently load an unrelated source.
    assert not exact_references(session, (answer,))


def test_answer_reference_accepts_both_original_response_kinds_in_order() -> None:
    # Given: a concept answer and an engine-backed coaching answer share one session.
    answers = (
        JsonDocument({"id": "chat-1", "text": "개념 설명"}),
        JsonDocument({"id": "coach-1", "text": "기간 예측", "receipt": {}}),
    )
    session = JsonDocument(
        {
            "messages": [
                {"role": "user", "content": "개념", "response": None},
                {"role": "assistant", "content": "개념 설명", "response": {"kind": "chat", "id": "chat-1"}},
                {"role": "user", "content": "예측", "response": None},
                {
                    "role": "assistant",
                    "content": "기간 예측",
                    "response": {"kind": "coaching", "id": "coach-1"},
                },
            ]
        }
    )
    # When / Then: each reference resolves to its own source payload, in conversation order.
    assert exact_references(session, answers)
