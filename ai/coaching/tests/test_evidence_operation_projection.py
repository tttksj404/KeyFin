# ruff: noqa: INP001
from __future__ import annotations

import copy
import hashlib
import json
from typing import TYPE_CHECKING

import pytest
from test_evidence_projection import receipt_with_numeric_result

import coaching_service.evidence as evidence_module
from coaching_service.evidence import bounded_evidence, context_limited, token_retry_evidence
from coaching_service.llm_contract import ChatMessage, EvidenceInput
from coaching_service.schemas import Receipt

if TYPE_CHECKING:
    from coaching_service.llm_contract import Operation


def nested_receipt() -> Receipt:
    """Known engine payloads duplicate current and prior analysis, without personal data."""
    original = receipt_with_numeric_result().model_dump(mode="json")
    original["result"]["datasets"] = {"projection": [{"date": "2026-09-16", "cash_krw": 123}] * 2500}
    original["result"]["visualizations"] = [{"dataset": "projection", "type": "line"}]
    original["result"]["projection"] = {
        "cash": {"terminal_balance": {"p50_krw": 123}},
        "warnings": [{"code": "PROJECTION_WARNING", "detail": "가정에 따른 결과입니다."}],
    }
    original["historical"]["engine_result"] = copy.deepcopy(original["result"])
    original["numeric_result"]["dialogue_context"] = {"engine_result": copy.deepcopy(original["result"])}
    original["numeric_result"]["datasets"] = {
        "projection": [{"date": "2026-09-16", "cash_krw": 123}] * 2500,
        "calendar": [{"date": "2026-09-16", "expected_amount_krw": 50000}],
        "account_risk": [{"account_id": "synthetic", "p_shortfall": 0.25}],
        "unknown_summary": {"uncertain_amount_krw": 789},
    }
    return Receipt.model_validate(original)


def test_nested_known_payloads_project_before_receipt_character_limit() -> None:
    # Given: the raw financial receipt exceeds the character guard solely due to repeated payloads.
    receipt = nested_receipt()
    before = receipt.model_dump_json()
    assert len(before) > 64000

    # When: the model-only copy is bounded.
    evidence = bounded_evidence(receipt, "현재 위험을 점검해 주세요.")

    # Then: structural projection retains the useful result and never changes the original.
    assert not context_limited(evidence)
    projected = json.loads(evidence.facts_json)
    assert receipt.model_dump_json() == before
    assert "visualizations" not in projected["result"]
    assert "projection" not in projected["result"]["datasets"]
    assert projected["result"]["projection"]["cash"]["terminal_balance"]["p50_krw"] == 123
    assert projected["numeric_result"]["datasets"]["unknown_summary"]["uncertain_amount_krw"] == 789
    assert projected["numeric_result"]["datasets"]["calendar"][0]["expected_amount_krw"] == 50000
    assert projected["numeric_result"]["datasets"]["account_risk"][0]["p_shortfall"] == 0.25
    assert projected["historical"]["engine_result"]["$ref"] == "$.result"
    assert projected["numeric_result"]["dialogue_context"]["engine_result"]["$ref"] == "$.result"


def test_duplicate_analysis_is_exactly_fingerprinted_and_original_is_retained() -> None:
    # Given: current and historical engine documents are byte-for-byte canonically equivalent.
    receipt = nested_receipt()
    canonical = evidence_module.canonical_json(receipt.result.root).encode("utf-8")

    # When: duplicate analyses are replaced by references in the model copy.
    projected = json.loads(bounded_evidence(receipt).facts_json)

    # Then: the source location, original presence, and exact content hash remain available.
    metadata = projected["llm_projection"]
    duplicate = next(
        item
        for item in metadata["deduplicated_fields"]
        if item["receipt_path"] == "$.historical.engine_result"
    )
    assert metadata["original_retained"] is True
    assert duplicate["source_path"] == "$.result"
    assert duplicate["canonical_json_sha256"] == hashlib.sha256(canonical).hexdigest()


@pytest.mark.parametrize("operation", ["route", "judge", "write"])
def test_operation_projection_preserves_question_history_payment_and_data_guards(
    operation: Operation,
) -> None:
    # Given: missing data, canceled prior payment, independent warnings and numeric assumptions.
    receipt = receipt_with_numeric_result()
    history = (ChatMessage(role="user", content="이전 결제 상태를 확인하고 싶어요."),)
    evidence = bounded_evidence(receipt, "현재 자료가 충분한가요?", history)

    # When: a model operation requests its explicit evidence scope.
    projected_evidence = evidence_module.operation_evidence(evidence, operation)
    projected = json.loads(projected_evidence.facts_json)

    # Then: factual guardrails and payment context survive every operation.
    assert projected_evidence.question == evidence.question
    assert projected_evidence.history == history
    assert projected["result"]["status"] == "needs_data"
    assert projected["result"]["next_action"] == receipt.result.root["next_action"]
    assert projected["result"]["warnings"] == receipt.result.root["warnings"]
    assert projected["historical"]["transaction_status"] == "canceled"
    assert projected["historical"]["payment"]["amount_krw"] == 50000
    assert projected["numeric_result"]["assumptions"] == receipt.numeric_result.root["assumptions"]
    assert projected["numeric_result"]["limitations"] == receipt.numeric_result.root["limitations"]
    assert projected["llm_projection"]["operation"] == operation
    assert receipt == receipt_with_numeric_result()


def test_route_excludes_numeric_aggregates_while_write_and_judge_keep_them() -> None:
    # Given: routing uses intent and state; judge/write can use the full structured evidence.
    evidence = bounded_evidence(receipt_with_numeric_result(), "현재 위험을 확인해 주세요.")

    # When: operation-specific copies are produced.
    route = json.loads(evidence_module.operation_evidence(evidence, "route").facts_json)
    write = json.loads(evidence_module.operation_evidence(evidence, "write").facts_json)
    judge = json.loads(evidence_module.operation_evidence(evidence, "judge").facts_json)

    # Then: only the routing scope omits the known aggregate and records its source.
    assert "metrics" not in route["numeric_result"]
    assert write["numeric_result"]["metrics"] == judge["numeric_result"]["metrics"]
    assert write["numeric_result"]["metrics"][0]["value"] == 12500
    assert any(
        item["receipt_path"] == "$.numeric_result.metrics"
        for item in route["llm_projection"]["omitted_fields"]
    )


def test_unknown_oversized_financial_field_is_never_silently_cut() -> None:
    # Given: an unknown field could carry unique important evidence.
    original = receipt_with_numeric_result().model_dump(mode="json")
    original["numeric_result"]["unfamiliar_required_evidence"] = "가" * 65000
    receipt = Receipt.model_validate(original)
    before = receipt.model_dump_json()

    # When: the receipt is projected and bounded.
    evidence = bounded_evidence(receipt)

    # Then: the unknown content causes an explicit limit; it is not dropped or string-sliced.
    assert context_limited(evidence)
    assert receipt.model_dump_json() == before


def test_explicit_daily_series_request_retains_series_and_reports_limit() -> None:
    # Given: the requested source is the otherwise omitted large daily projection.
    receipt = nested_receipt()

    # When: the question explicitly asks for daily rows.
    evidence = bounded_evidence(receipt, "일별 시계열 자료를 확인하고 싶어요.")

    # Then: required rows cannot be dropped just to pass a character limit.
    assert context_limited(evidence)


def test_token_limit_retry_keeps_only_provenance_for_supplementary_wording() -> None:
    """A retry may shrink non-authoritative writer context without changing the receipt."""
    original = EvidenceInput(
        purpose="coaching",
        question="추가로 확인할 사항을 알려줘.",
        history=(
            ChatMessage(role="user", content="이전 질문 " + "가" * 400),
            ChatMessage(role="assistant", content="이전 답변 " + "나" * 400),
            ChatMessage(role="user", content="최근 질문 " + "다" * 400),
        ),
        facts_json=json.dumps({"opaque_engine_payload": "라" * 5000}, ensure_ascii=False),
    )

    retry = token_retry_evidence(original)

    assert retry is not None
    assert retry.question == original.question
    assert len(retry.history) == 2
    assert all(len(row.content) <= 252 for row in retry.history)
    facts = json.loads(retry.facts_json)
    assert facts["model_context_status"] == "reduced_after_token_limit"
    assert facts["source_canonical_sha256"] == hashlib.sha256(
        original.facts_json.encode("utf-8")
    ).hexdigest()
    assert "opaque_engine_payload" not in retry.facts_json
    assert original.facts_json.endswith("}"), "the original evidence remains unchanged"


def test_token_limit_retry_never_removes_finance_selection_sources() -> None:
    """Source-backed fact selection must fail closed rather than retry without facts."""
    evidence = EvidenceInput(
        purpose="finance", question="일반 금융 개념을 알려줘.", facts_json=json.dumps({"x": "가" * 5000})
    )

    assert token_retry_evidence(evidence) is None
