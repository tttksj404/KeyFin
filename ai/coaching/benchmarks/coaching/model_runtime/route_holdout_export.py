"""Export a pre-existing synthetic route holdout without engine receipts or customer data."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Final, Literal

from benchmarks.coaching.cases import Attack, Family, load_catalog, text_context
from benchmarks.coaching.model_runtime.export import safe_output
from coaching_service.llm_contract import EvidenceInput
from coaching_service.llm_prompt import RoutePromptVersion, system_prompt, user_payload

_ROUTE_FACTS: Final = '{"operation":"dialogue"}'
_STRATA: Final = ("complete", "adversarial")
RoutePartition = Literal["development", "holdout"]


def row(
    family: Family,
    attack: Attack | None,
    stratum: str,
    route_prompt_version: RoutePromptVersion,
) -> dict[str, object]:
    """Construct exactly the route prompt, without FDT amounts or engine output."""
    question, history = text_context(family, attack)
    evidence = EvidenceInput(question=question, history=history, facts_json=_ROUTE_FACTS)
    return {
        "id": "route-" + family.family_id + "-" + stratum,
        "kind": "route",
        "stratum": stratum,
        "messages": [
            {"role": "system", "content": system_prompt("route", route_prompt_version=route_prompt_version)},
            {"role": "user", "content": user_payload(evidence)},
        ],
        "expected": {"mode": family.expected_route},
        "max_tokens": 64,
    }


def manifest(
    *,
    partition: RoutePartition = "holdout",
    route_prompt_version: RoutePromptVersion = "production",
) -> dict[str, object]:
    """Export one frozen synthetic partition without customer or FDT evidence."""
    catalog = load_catalog()
    attacks = {attack.template_id: attack for attack in catalog.attacks}
    cases: list[dict[str, object]] = []
    for family in catalog.families:
        if family.split != partition:
            continue
        attack = attacks[family.attack_template_id]
        if attack.split != partition:
            raise ValueError("route_evaluation_attack_split_mismatch")
        cases.append(row(family, None, "complete", route_prompt_version))
        cases.append(row(family, attack, "adversarial", route_prompt_version))
    if len(cases) != len({str(case["id"]) for case in cases}):
        raise ValueError("route_evaluation_case_id_duplicate")
    return {
        "schema": "keyfin-route-evaluation-manifest/2",
        "cases": cases,
        "scope": {
            "source": "preexisting_static_synthetic_route_dataset",
            "partition": partition,
            "route_prompt_version": route_prompt_version,
            "customer_data_included": False,
            "fdt_prediction_accuracy_measured": False,
            "used_for_candidate_training": False,
        },
    }


def write_manifest(
    path: Path,
    *,
    partition: RoutePartition = "holdout",
    route_prompt_version: RoutePromptVersion = "production",
) -> dict[str, object]:
    """Write a canonical ignored artifact and return only a reproducibility digest."""
    payload = manifest(partition=partition, route_prompt_version=route_prompt_version)
    serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    destination = safe_output(path)
    destination.write_text(serialized, encoding="utf-8")
    return {
        "path": str(destination),
        "sha256": hashlib.sha256(serialized.encode()).hexdigest(),
        "cases": len(payload["cases"]),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument("--output", required=True, type=Path)
    _ = parser.add_argument("--partition", choices=("development", "holdout"), default="holdout")
    _ = parser.add_argument(
        "--route-prompt-version",
        choices=("production", "candidate_v2", "candidate_v3"),
        default="production",
    )
    args = parser.parse_args()
    print(  # noqa: T201
        json.dumps(
            write_manifest(
                args.output,
                partition=args.partition,
                route_prompt_version=args.route_prompt_version,
            ),
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
