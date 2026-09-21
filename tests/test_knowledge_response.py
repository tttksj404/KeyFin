# ruff: noqa: INP001
"""The new coverage report must reject wrong evidence and wrong personal arithmetic."""

from pathlib import Path

import pytest

from benchmarks.coaching.knowledge_response.cases import CONCEPTS, PERSONAL, Case
from benchmarks.coaching.knowledge_response.run import run
from benchmarks.coaching.knowledge_response.score import evaluate
from coaching_service.chat_answers import ChatAnswer, knowledge_answer
from coaching_service.finance_knowledge import selected_finance_wording
from coaching_service.schemas import JsonDocument


def test_wrong_approved_reference_is_not_counted_as_correct_coverage() -> None:
    # Given: a valid answer selects an approved but unrelated concept.
    answer = ChatAnswer(
        id="answer",
        answer_type="finance_education",
        status="answered",
        text="자료 설명",
        wording_source="llm",
        model="synthetic",
        created_at=0,
        evidence=JsonDocument({"references": [{"id": "deposits"}]}),
    )
    # When: the question asks about compound interest.
    passed = evaluate(CONCEPTS[0], JsonDocument.model_validate_json(answer.model_dump_json()))
    # Then: HTTP/schema validity cannot stand in for the expected reference.
    assert passed is False


@pytest.mark.parametrize("text", ["", "복리는 원금에만 이자가 붙고 이자에는 이자가 붙지 않습니다."])
def test_correct_reference_cannot_hide_missing_or_contradictory_body(text: str) -> None:
    answer = ChatAnswer(
        id="answer", answer_type="finance_education", status="answered", text=text,
        wording_source="llm", model="synthetic", created_at=0,
        evidence=JsonDocument({"references": [{"id": "compound_interest"}]}),
    )
    assert not evaluate(CONCEPTS[0], JsonDocument.model_validate_json(answer.model_dump_json()))


def test_approved_body_passes_but_appended_unsupported_claim_fails() -> None:
    wording = selected_finance_wording('{"status":"answered","fact_ids":["compound_interest"]}', "test")
    answer = ChatAnswer(
        id="answer", answer_type="finance_education", status="answered", text=wording.text,
        wording_source="llm", model="synthetic", created_at=0,
        evidence=JsonDocument({"references": [{"id": "compound_interest"}]}),
    )
    assert evaluate(CONCEPTS[0], JsonDocument.model_validate_json(answer.model_dump_json()))
    changed = answer.model_copy(update={"text": answer.text + "\n이 상품은 손실이 절대 없습니다."})
    assert not evaluate(CONCEPTS[0], JsonDocument.model_validate_json(changed.model_dump_json()))


def test_catalog_template_with_the_same_pinned_body_counts_as_a_correct_answer() -> None:
    """The quality score must not punish a model-free response for avoiding latency."""
    wording = selected_finance_wording(
        '{"status":"answered","fact_ids":["compound_interest"]}', "not_called",
    ).model_copy(update={"source": "template"})
    answer = knowledge_answer(wording)

    assert evaluate(CONCEPTS[0], JsonDocument.model_validate_json(answer.model_dump_json()))


def test_wrong_personal_total_is_not_counted_as_an_answer() -> None:
    # Given: an otherwise valid account response silently omits the overdraft.
    answer = ChatAnswer(
        id="answer",
        answer_type="personal_context",
        status="answered",
        text="계좌 현황",
        wording_source="engine",
        model="not_called",
        created_at=0,
        evidence=JsonDocument({"topic": "accounts", "total_krw": 1320000}),
    )
    # When: the independent fixture requires the negative account to be included.
    passed = evaluate(PERSONAL[0], JsonDocument.model_validate_json(answer.model_dump_json()))
    # Then: the benchmark rejects the wrong arithmetic.
    assert passed is False


def test_partial_source_answer_requires_exact_paragraph_and_visible_limit() -> None:
    wording = selected_finance_wording(
        '{"status":"needs_source","fact_ids":["interest_types"],"missing":["latest_source"]}', "test",
    )
    answer = knowledge_answer(wording)
    case = Case(
        id="mixed-current-rate", question="고정금리 설명과 오늘 금리",
        expected_status="needs_source", reference_id="interest_types",
    )
    assert evaluate(case, JsonDocument.model_validate_json(answer.model_dump_json()))
    changed = answer.model_copy(update={"text": answer.text + " 오늘 금리는 0%입니다."})
    assert not evaluate(case, JsonDocument.model_validate_json(changed.model_dump_json()))


def test_coverage_catalog_contains_twenty_seven_distinct_declared_topics() -> None:
    # Given: questions are manually fixed, not generated from production aliases.
    references = tuple(case.reference_id for case in CONCEPTS)
    # When: coverage is counted by distinct concepts.
    count = len(set(references))
    # Then: one repeated topic cannot inflate the declared breadth.
    assert count == len(CONCEPTS) == 27


def test_new_knowledge_and_personal_suite_runs_over_real_tcp(tmp_path: Path) -> None:
    # Given: a fresh owner, own API subprocess and synthetic model decisions.
    target = tmp_path / "artifacts" / "knowledge"
    # When: all independent and same-session questions run through the public API.
    report = run(target, "fake")
    # Then: every coverage/persistence gate passes, without claiming GPU quality.
    assert report.completed, [check.name for check in report.checks if not check.passed]
    assert len(report.cases) == 41
    assert report.backend == "fake"
    assert report.api_process_stopped
