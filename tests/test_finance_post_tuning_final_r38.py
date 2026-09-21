"""Scope and disjointness checks for the post-fix synthetic holdout."""

# ruff: noqa: INP001

from __future__ import annotations

import json

from benchmarks.coaching.model_runtime.finance_post_tuning_final import cases as r37_cases
from benchmarks.coaching.model_runtime.finance_post_tuning_final_r38 import manifest
from benchmarks.coaching.model_runtime.finance_selection_export import (
    DEVELOPMENT_CASES,
    FINAL_CASES,
)
from benchmarks.coaching.model_runtime.finance_sft_dataset import build_examples
from coaching_service.knowledge_retrieval import compact


def test_post_fix_final_is_new_and_never_a_training_or_candidate_selection_input() -> None:
    """The r38 score cannot recycle the defect-discovery screen it follows."""
    payload = manifest()
    cases = payload["cases"]
    excluded = {
        compact(case.question)
        for case in (*DEVELOPMENT_CASES, *FINAL_CASES, *r37_cases())
    }
    excluded.update(
        compact(json.loads(example.messages[1]["content"])["untrusted_question"])
        for example in build_examples()
    )

    assert payload["scope"] == {
        "source": "post_fix_static_synthetic_finance_selection",
        "partition": "final_post_fix_r38",
        "customer_data_included": False,
        "fdt_prediction_accuracy_measured": False,
        "used_for_candidate_training": False,
        "used_for_candidate_selection": False,
        "independent_human_oracle": False,
    }
    assert len(cases) >= 45
    assert len({row["id"] for row in cases}) == len(cases)
    assert all(row["kind"] == "finance_selection" for row in cases)
    assert all(
        compact(json.loads(row["messages"][1]["content"])["untrusted_question"]) not in excluded
        for row in cases
    )
