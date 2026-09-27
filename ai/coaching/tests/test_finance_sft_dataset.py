# ruff: noqa: INP001
"""Contracts for the synthetic-only FinanceSelection fine-tuning input."""

from __future__ import annotations

import json
from collections import Counter
from typing import TYPE_CHECKING

from benchmarks.coaching.model_runtime.finance_selection_export import (
    DEVELOPMENT_CASES,
    FINAL_CASES,
)
from benchmarks.coaching.model_runtime.finance_sft_dataset import build_examples, write_jsonl
from benchmarks.coaching.model_runtime.finance_sft_r42_dataset import build_examples as build_r42_examples
from benchmarks.coaching.model_runtime.finance_sft_r42_dataset import excluded_holdout_questions
from coaching_service.finance_knowledge import FinanceSelection
from coaching_service.knowledge_retrieval import compact

if TYPE_CHECKING:
    from pathlib import Path


def test_sft_examples_are_deterministic_schema_valid_and_exclude_evaluation_questions() -> None:
    """Training rows must not reuse a public development/final question verbatim."""
    examples = build_examples()
    excluded = {compact(case.question) for case in (*DEVELOPMENT_CASES, *FINAL_CASES)}

    assert len(examples) >= 150
    assert len({row.case_id for row in examples}) == len(examples)
    for row in examples:
        user = json.loads(row.messages[1]["content"])
        assert compact(user["untrusted_question"]) not in excluded
        _ = FinanceSelection.model_validate_json(row.messages[2]["content"])


def test_sft_examples_include_enough_boundary_labels_for_a_selector_to_learn_them() -> None:
    """A mostly-answerable corpus must not teach the selector to answer every request."""
    labels = Counter(
        FinanceSelection.model_validate_json(row.messages[2]["content"]).status
        for row in build_examples()
    )

    assert labels["answered"] >= 150
    assert labels["needs_source"] >= 90
    assert labels["needs_data"] >= 90
    assert labels["out_of_scope"] >= 90


def test_base_synthetic_training_reuses_its_immutable_corpus_in_one_process() -> None:
    """Several holdouts must share a frozen default corpus rather than rebuild it."""
    first = build_examples()
    second = build_examples()

    assert first is second


def test_sft_jsonl_round_trips_without_customer_or_prediction_fields(tmp_path: Path) -> None:
    """The generator writes only synthetic prompt/selection rows for a local experiment."""
    path = tmp_path / "finance-sft.jsonl"

    count = write_jsonl(path)

    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == count
    assert all(set(row) == {"case_id", "messages"} for row in rows)
    assert all("prediction" not in json.dumps(row, ensure_ascii=False).lower() for row in rows)


def test_r42_synthetic_training_excludes_every_prior_post_tuning_final_question() -> None:
    """A later adapter fit must not memorize any earlier final-screen prompt."""
    holdouts = excluded_holdout_questions()
    questions = {
        compact(json.loads(row.messages[1]["content"])["untrusted_question"])
        for row in build_r42_examples()
    }

    assert holdouts
    assert questions.isdisjoint(holdouts)


def test_r42_synthetic_training_reuses_its_immutable_corpus_in_one_process() -> None:
    """Final-gate checks must not rebuild an identical frozen training corpus."""
    first = build_r42_examples()
    second = build_r42_examples()

    assert first is second
