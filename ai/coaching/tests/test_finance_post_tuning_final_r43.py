"""Scope contracts for the r43 serving-cascade holdout."""

# ruff: noqa: INP001

from __future__ import annotations

import json

from benchmarks.coaching.model_runtime.finance_post_tuning_final import cases as r37_cases
from benchmarks.coaching.model_runtime.finance_post_tuning_final_r38 import cases as r38_cases
from benchmarks.coaching.model_runtime.finance_post_tuning_final_r39 import cases as r39_cases
from benchmarks.coaching.model_runtime.finance_post_tuning_final_r40 import cases as r40_cases
from benchmarks.coaching.model_runtime.finance_post_tuning_final_r41 import cases as r41_cases
from benchmarks.coaching.model_runtime.finance_post_tuning_final_r43 import manifest
from benchmarks.coaching.model_runtime.finance_selection_export import (
    DEVELOPMENT_CASES,
    FINAL_CASES,
)
from benchmarks.coaching.model_runtime.finance_sft_r42_dataset import build_examples as r42_examples
from coaching_service.knowledge_retrieval import compact


def test_r43_holdout_excludes_all_earlier_static_and_r42_training_prompts() -> None:
    """The frozen r43 score cannot be memorized by the r42 candidate."""
    payload = manifest()
    cases = payload["cases"]
    excluded = {
        compact(case.question)
        for case in (
            *DEVELOPMENT_CASES,
            *FINAL_CASES,
            *r37_cases(),
            *r38_cases(),
            *r39_cases(),
            *r40_cases(),
            *r41_cases(),
        )
    }
    excluded.update(
        compact(json.loads(example.messages[1]["content"])["untrusted_question"])
        for example in r42_examples()
    )

    assert payload["scope"] == {
        "source": "post_fix_static_synthetic_finance_selection",
        "partition": "final_post_fix_r43",
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
