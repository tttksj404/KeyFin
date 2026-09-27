"""The remote model-runtime suite must stay public, bounded, and schema-specific."""

# ruff: noqa: INP001
from __future__ import annotations

import json

from benchmarks.coaching.model_runtime.export import manifest
from benchmarks.coaching.model_runtime.finance_development_export import (
    manifest as finance_development_manifest,
)
from benchmarks.coaching.model_runtime.finance_final_export import manifest as finance_final_manifest
from benchmarks.coaching.model_runtime.route_final_export import manifest as route_final_manifest
from benchmarks.coaching.model_runtime.route_holdout_export import manifest as route_holdout_manifest
from benchmarks.coaching.model_runtime.runner import object_from_text, semantic_ok


def test_manifest_has_unique_public_cases_and_no_customer_prediction_claim() -> None:
    payload = manifest()
    cases = payload["cases"]

    assert payload["scope"] == {
        "source": "public_fixed_prompts_and_pinned_catalog",
        "customer_data_included": False,
        "fdt_prediction_accuracy_measured": False,
    }
    assert isinstance(cases, list)
    assert len(cases) == 14
    assert len({row["id"] for row in cases}) == len(cases)
    assert all(len(row["messages"]) == 2 for row in cases)
    assert all(row["max_tokens"] in {64, 96} for row in cases)


def test_runner_scores_only_the_constrained_schema_fields() -> None:
    route = next(row for row in manifest()["cases"] if row["kind"] == "route")
    finance = next(row for row in manifest()["cases"] if row["kind"] == "finance_selection")

    assert object_from_text('<think>ignore</think>{"mode":"finance"}') is None
    assert object_from_text('{"mode":"finance"} trailing') is None
    assert object_from_text('```json\n{"mode":"finance"}\n```') == {"mode": "finance"}
    assert semantic_ok(route, '{"mode":"finance"}') == (True, True)
    assert semantic_ok(route, '{"mode":"finance","extra":true}') == (False, True)
    finance_output = {
        "status": finance["expected"]["status"],
        "fact_ids": list(finance["expected"]["required_fact_ids"]),
        "missing": list(finance["expected"]["required_missing"]),
    }
    assert semantic_ok(finance, json.dumps(finance_output)) == (True, True)


def test_runner_rejects_finance_fields_that_the_service_contract_would_reject() -> None:
    """The offline score must not count a completion that production falls back from."""
    finance = next(row for row in manifest()["cases"] if row["kind"] == "finance_selection")
    expected = finance["expected"]
    valid = {
        "status": expected["status"],
        "fact_ids": list(expected["required_fact_ids"]),
        "missing": list(expected["required_missing"]),
    }

    assert semantic_ok(finance, json.dumps({**valid, "unsupported": True})) == (False, True)
    assert semantic_ok(finance, '{"status":"answered","status":"needs_source","fact_ids":[]}') == (
        False,
        False,
    )


def test_route_evaluation_uses_only_preexisting_synthetic_prompt_labels() -> None:
    payload = route_holdout_manifest()
    cases = payload["cases"]

    assert payload["scope"] == {
        "source": "preexisting_static_synthetic_route_dataset",
        "partition": "holdout",
        "route_prompt_version": "production",
        "customer_data_included": False,
        "fdt_prediction_accuracy_measured": False,
        "used_for_candidate_training": False,
    }
    assert isinstance(cases, list)
    assert len(cases) == 120
    assert {row["stratum"] for row in cases} == {"complete", "adversarial"}
    assert all(row["kind"] == "route" and row["max_tokens"] == 64 for row in cases)


def test_route_development_partition_can_compare_an_isolated_prompt_candidate() -> None:
    payload = route_holdout_manifest(partition="development", route_prompt_version="candidate_v3")

    assert payload["scope"]["partition"] == "development"
    assert payload["scope"]["route_prompt_version"] == "candidate_v3"
    assert len(payload["cases"]) == 36
    assert all(row["kind"] == "route" and row["max_tokens"] == 64 for row in payload["cases"])


def test_route_final_set_is_separate_from_selection_and_customer_data() -> None:
    payload = route_final_manifest()
    cases = payload["cases"]

    assert payload["scope"] == {
        "source": "post_selection_policy_labeled_static_synthetic_final_set",
        "route_prompt_version": "candidate_v3",
        "customer_data_included": False,
        "fdt_prediction_accuracy_measured": False,
        "used_for_candidate_training": False,
        "used_for_candidate_selection": False,
    }
    assert len(cases) == 48
    assert {row["stratum"] for row in cases} == {"complete", "adversarial"}
    assert len({row["id"] for row in cases}) == len(cases)


def test_finance_development_and_final_sets_are_disjoint_and_scope_bounded() -> None:
    """A candidate may be tuned on development cases but never on frozen final prompts."""
    development = finance_development_manifest()
    final = finance_final_manifest()

    assert development["scope"]["partition"] == "development"
    assert development["scope"]["used_for_candidate_selection"] is True
    assert final["scope"]["partition"] == "final"
    assert final["scope"]["used_for_candidate_selection"] is False
    assert development["scope"]["customer_data_included"] is False
    assert final["scope"]["fdt_prediction_accuracy_measured"] is False
    development_ids = {row["id"] for row in development["cases"]}
    final_ids = {row["id"] for row in final["cases"]}
    assert len(development_ids) == 24
    assert len(final_ids) == 24
    assert development_ids.isdisjoint(final_ids)
    assert all(row["kind"] == "finance_selection" for row in (*development["cases"], *final["cases"]))


def test_finance_development_manifest_can_isolate_a_prompt_candidate() -> None:
    """Prompt tuning is permitted only on the development partition."""
    candidate = finance_development_manifest(finance_prompt_version="candidate_v2")

    assert candidate["scope"]["finance_prompt_version"] == "candidate_v2"
    assert candidate["scope"]["used_for_candidate_selection"] is True
    assert len(candidate["cases"]) == 24
