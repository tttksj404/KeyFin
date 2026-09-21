"""Contracts for the deterministic-first general-finance cascade evaluation."""

# ruff: noqa: INP001

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from benchmarks.coaching.model_runtime.finance_cascade import (
    evaluate_manifest,
    write_model_residual_manifest,
)
from benchmarks.coaching.model_runtime.finance_selection_export import manifest

if TYPE_CHECKING:
    from pathlib import Path


def test_cascade_evaluation_keeps_questions_out_of_its_aggregate_result(tmp_path: Path) -> None:
    """The local direct-path score reports only counts and hashes, never test prompts."""
    source = tmp_path / "development.json"
    source.write_text(json.dumps(manifest("development"), ensure_ascii=False), encoding="utf-8")

    report = evaluate_manifest(source)
    serialized = json.dumps(report, ensure_ascii=False)

    assert report["cases"] == 24
    assert report["direct"] == {"cases": 24, "semantic_ok": 24}
    assert report["model_residual"] == {"cases": 0}
    assert "복리" not in serialized
    assert "DSR" not in serialized


def test_residual_export_keeps_only_cases_the_direct_serving_path_did_not_answer(tmp_path: Path) -> None:
    """A remote selector never re-evaluates a model-free answered case."""
    source = tmp_path / "development.json"
    output = tmp_path / "residual.json"
    source.write_text(json.dumps(manifest("development"), ensure_ascii=False), encoding="utf-8")

    receipt = write_model_residual_manifest(source, output)
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert receipt["cases"] == 24
    assert receipt["direct_cases"] == 24
    assert receipt["model_residual_cases"] == 0
    assert receipt["test_questions_or_answers_retained"] is False
    assert payload["cases"] == []
    assert payload["scope"]["deterministic_direct_cases_excluded"] is True
