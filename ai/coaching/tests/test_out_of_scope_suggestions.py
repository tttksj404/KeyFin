# ruff: noqa: INP001
"""out_of_scope wording gains nearest-concept suggestions without changing when it fires."""

from __future__ import annotations

from coaching_service.finance_knowledge import (
    FinanceSelection,
    finance_evidence,
    selected_finance_wording,
)

_OUT_OF_SCOPE = FinanceSelection(status="out_of_scope", fact_ids=()).model_dump_json()


def test_out_of_scope_still_reports_empty_fact_ids_and_status() -> None:
    evidence = finance_evidence("복리가 뭔지 알려줘")
    wording = selected_finance_wording(_OUT_OF_SCOPE, "not_called", evidence=evidence)
    assert wording.answer_status == "out_of_scope"
    assert wording.reference_ids == ()


def test_out_of_scope_suggests_a_nearby_registered_concept_when_one_exists() -> None:
    evidence = finance_evidence("복리가 뭔지 알려줘")
    wording = selected_finance_wording(_OUT_OF_SCOPE, "not_called", evidence=evidence)
    assert "복리" in wording.text
    assert "아직 없습니다" in wording.text


def test_out_of_scope_falls_back_to_flat_text_when_nothing_is_nearby() -> None:
    evidence = finance_evidence("오늘 점심 뭐 먹을지 추천해줘")
    wording = selected_finance_wording(_OUT_OF_SCOPE, "not_called", evidence=evidence)
    assert wording.answer_status == "out_of_scope"
    assert wording.reference_ids == ()
    assert "예를 들어" not in wording.text


def test_out_of_scope_without_evidence_still_returns_the_base_text() -> None:
    wording = selected_finance_wording(_OUT_OF_SCOPE, "not_called")
    assert wording.answer_status == "out_of_scope"
    assert "아직 없습니다" in wording.text
    assert "예를 들어" not in wording.text
