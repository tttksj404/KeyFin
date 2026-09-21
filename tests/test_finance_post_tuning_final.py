"""Scope contracts for the post-tuning synthetic FinanceSelection screen."""

# ruff: noqa: INP001

from __future__ import annotations

import json

from benchmarks.coaching.model_runtime.finance_post_tuning_final import manifest
from benchmarks.coaching.model_runtime.finance_selection_export import (
    DEVELOPMENT_CASES,
    FINAL_CASES,
)
from benchmarks.coaching.model_runtime.finance_sft_dataset import build_examples
from coaching_service.knowledge_retrieval import compact


def test_post_tuning_final_is_distinct_from_training_and_candidate_selection() -> None:
    """A frozen screen may be evaluated once, but must never silently become training data."""
    payload = manifest()
    cases = payload["cases"]
    scope = payload["scope"]
    excluded = {
        compact(case.question)
        for case in (*DEVELOPMENT_CASES, *FINAL_CASES)
    }
    excluded.update(
        compact(json.loads(example.messages[1]["content"])["untrusted_question"])
        for example in build_examples()
    )

    assert scope == {
        "source": "post_tuning_static_synthetic_finance_selection",
        "partition": "final_post_tuning",
        "customer_data_included": False,
        "fdt_prediction_accuracy_measured": False,
        "used_for_candidate_training": False,
        "used_for_candidate_selection": False,
        "independent_human_oracle": False,
    }
    assert len(cases) >= 40
    assert len({row["id"] for row in cases}) == len(cases)
    assert all(row["kind"] == "finance_selection" for row in cases)
    assert all(
        compact(json.loads(row["messages"][1]["content"])["untrusted_question"]) not in excluded
        for row in cases
    )
