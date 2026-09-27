# ruff: noqa: INP001
"""Writer context contains displayed facts once; original engine evidence stays intact."""

import json

from coaching_service.coaching import supplementary_evidence
from coaching_service.llm_contract import EvidenceInput


def test_duplicate_analysis_is_not_forwarded_to_followup_writer() -> None:
    original = EvidenceInput(
        question="이번 달 말까지 예측해줘",
        facts_json=json.dumps(
            {
                "result": {"projection": [123456] * 2500},
                "numeric_result": {"projection": [123456] * 2500},
            }
        ),
    )
    displayed = "예측 기간 2026-09-04~2026-09-30, 예상 소비액 100,000원. 조건부 예측입니다."
    actual = supplementary_evidence(original, displayed)
    assert json.loads(actual.facts_json)["authoritative_answer"] == displayed
    assert actual.question == original.question
    assert len(actual.facts_json) < 300
    assert len(original.facts_json) > 20000
    assert "numeric_result" in original.facts_json
