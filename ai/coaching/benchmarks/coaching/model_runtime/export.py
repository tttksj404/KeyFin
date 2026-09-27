"""Export the exact public service prompts for an isolated candidate runtime."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Final

from benchmarks.coaching.model_runtime.cases import FINANCE_CASES, ROUTE_CASES
from coaching_service.finance_knowledge import finance_evidence
from coaching_service.llm_contract import EvidenceInput
from coaching_service.llm_prompt import system_prompt, user_payload

_ROUTE_FACTS: Final = '{"operation":"dialogue"}'


def safe_output(path: Path) -> Path:
    """Keep runnable manifests in ignored artifacts rather than source control."""
    resolved = path.resolve()
    artifact_root = (Path(__file__).parents[3] / "artifacts").resolve()
    if artifact_root not in resolved.parents:
        raise ValueError("model_runtime_output_must_be_below_artifacts")
    resolved.parent.mkdir(parents=True, exist_ok=True)
    return resolved


def route_row(case_id: str, question: str, mode: str) -> dict[str, object]:
    """Build the same bounded route prompt that the dialogue adapter submits."""
    evidence = EvidenceInput(question=question, facts_json=_ROUTE_FACTS)
    return {
        "id": case_id,
        "kind": "route",
        "messages": [
            {"role": "system", "content": system_prompt("route")},
            {"role": "user", "content": user_payload(evidence)},
        ],
        "expected": {"mode": mode},
        "max_tokens": 64,
    }


def finance_row(
    case_id: str,
    question: str,
    status: str,
    required_fact_ids: tuple[str, ...],
    required_missing: tuple[str, ...],
) -> dict[str, object]:
    """Build the actual FinanceSelection prompt and keep evidence IDs for validation."""
    evidence = finance_evidence(question)
    facts = json.loads(evidence.facts_json)["knowledge_facts"]
    allowed = tuple(row["id"] for row in facts)
    return {
        "id": case_id,
        "kind": "finance_selection",
        "messages": [
            {"role": "system", "content": system_prompt("write", finance=True)},
            {"role": "user", "content": user_payload(evidence)},
        ],
        "expected": {
            "status": status,
            "required_fact_ids": required_fact_ids,
            "required_missing": required_missing,
            "allowed_fact_ids": allowed,
        },
        "max_tokens": 96,
    }


def manifest() -> dict[str, object]:
    """Return a public synthetic contract, not a customer prompt or financial target."""
    cases = [route_row(case.id, case.question, case.mode) for case in ROUTE_CASES]
    cases.extend(
        finance_row(case.id, case.question, case.status, case.required_fact_ids, case.required_missing)
        for case in FINANCE_CASES
    )
    return {
        "schema": "keyfin-model-runtime-manifest/1",
        "cases": cases,
        "scope": {
            "source": "public_fixed_prompts_and_pinned_catalog",
            "customer_data_included": False,
            "fdt_prediction_accuracy_measured": False,
        },
    }


def write_manifest(path: Path) -> dict[str, object]:
    """Serialize a stable byte representation so the remote report can cite its input."""
    payload = manifest()
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
    print(json.dumps(write_manifest(parser.parse_args().output), ensure_ascii=False))  # noqa: T201


if __name__ == "__main__":
    main()
