"""Score the serving cascade without persisting synthetic question text or answers.

The product first renders a strict, stable catalog answer or an explicit source
boundary.  Only the remaining questions are eligible for model fact selection.
This evaluator measures the deterministic half independently; a remote model
report can then be joined by manifest digest and residual count without copying
the test prompts into an artifact.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import TYPE_CHECKING, Final

from coaching_service.finance_knowledge import (
    _MISSING_TEXT,
    deterministic_finance_status,
    deterministic_finance_wording,
    finance_evidence,
)

if TYPE_CHECKING:
    from pydantic import JsonValue

    from coaching_service.llm_contract import FinanceWording

_SCHEMA: Final = "keyfin-finance-cascade-report/1"


def _string_values(value: JsonValue | None, field: str) -> tuple[str, ...]:
    """Parse one fixed manifest string array before using it in a score."""
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise TypeError("finance_cascade_manifest_" + field)
    return tuple(value)


def _case_fields(case: JsonValue) -> tuple[str, str, dict[str, JsonValue]]:
    """Read only one test label, its untrusted question, and its expected contract."""
    if not isinstance(case, dict):
        raise TypeError("finance_cascade_manifest_case")
    case_id, messages, expected = case.get("id"), case.get("messages"), case.get("expected")
    if not isinstance(case_id, str) or not isinstance(messages, list) or len(messages) < 2:
        raise TypeError("finance_cascade_manifest_case")
    user = messages[1]
    if (
        not isinstance(user, dict)
        or not isinstance(user.get("content"), str)
        or not isinstance(expected, dict)
    ):
        raise TypeError("finance_cascade_manifest_case")
    try:
        payload = json.loads(user["content"])
    except json.JSONDecodeError as error:
        raise ValueError("finance_cascade_manifest_user_json") from error
    question = payload.get("untrusted_question") if isinstance(payload, dict) else None
    if not isinstance(question, str):
        raise TypeError("finance_cascade_manifest_question")
    return case_id, question, expected


def _direct_answer(question: str) -> FinanceWording | None:
    """Apply exactly the model-free serving order used by the dialogue layer."""
    evidence = finance_evidence(question)
    return deterministic_finance_wording(evidence) or deterministic_finance_status(evidence)


def _direct_case_ok(answer: FinanceWording, expected: dict[str, JsonValue]) -> bool:
    """Verify status, citations, and visible required-boundary text against frozen labels."""
    status = expected.get("status")
    if not isinstance(status, str) or answer.answer_status != status:
        return False
    required = _string_values(expected.get("required_fact_ids"), "required_fact_ids")
    permitted = _string_values(expected.get("permitted_fact_ids"), "permitted_fact_ids")
    if not set(required).issubset(answer.reference_ids) or not set(answer.reference_ids).issubset(permitted):
        return False
    missing = _string_values(expected.get("required_missing"), "required_missing")
    return all(
        key in _MISSING_TEXT and _MISSING_TEXT[key] in answer.text
        for key in missing
    )


def evaluate_manifest(path: Path) -> dict[str, object]:
    """Return aggregate deterministic coverage for a fixed finance-selection manifest."""
    raw = path.read_bytes()
    try:
        manifest = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ValueError("finance_cascade_manifest_json") from error
    cases = manifest.get("cases") if isinstance(manifest, dict) else None
    if not isinstance(cases, list) or not cases:
        raise ValueError("finance_cascade_manifest_cases")
    direct_case_ids: list[str] = []
    residual_case_ids: list[str] = []
    direct_ok = 0
    for case in cases:
        case_id, question, expected = _case_fields(case)
        answer = _direct_answer(question)
        if answer is None:
            residual_case_ids.append(case_id)
            continue
        direct_case_ids.append(case_id)
        direct_ok += int(_direct_case_ok(answer, expected))
    return {
        "schema": _SCHEMA,
        "manifest_sha256": hashlib.sha256(raw).hexdigest(),
        "cases": len(cases),
        "direct": {"cases": len(direct_case_ids), "semantic_ok": direct_ok},
        "model_residual": {"cases": len(residual_case_ids)},
        "direct_case_ids_sha256": hashlib.sha256(
            json.dumps(direct_case_ids, separators=(",", ":")).encode()
        ).hexdigest(),
        "model_residual_case_ids_sha256": hashlib.sha256(
            json.dumps(residual_case_ids, separators=(",", ":")).encode()
        ).hexdigest(),
        "scope": {
            "deterministic_serving_path_only": True,
            "customer_data_included": False,
            "fdt_prediction_accuracy_measured": False,
            "test_questions_or_answers_retained": False,
        },
    }


def write_model_residual_manifest(manifest_path: Path, output_path: Path) -> dict[str, object]:
    """Freeze only cases the actual deterministic serving path did not answer.

    The residual manifest preserves the original validated prompt and expected
    selection contract for remote inference. It is an ignored experiment input;
    the returned receipt intentionally retains only counts and parent hashes.
    """
    raw = manifest_path.read_bytes()
    try:
        manifest = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ValueError("finance_cascade_manifest_json") from error
    cases = manifest.get("cases") if isinstance(manifest, dict) else None
    if not isinstance(cases, list) or not cases:
        raise ValueError("finance_cascade_manifest_cases")
    if output_path.exists():
        raise FileExistsError("finance_cascade_residual_output_exists")
    residual = []
    direct_cases = 0
    for case in cases:
        _, question, _ = _case_fields(case)
        if _direct_answer(question) is None:
            residual.append(case)
        else:
            direct_cases += 1
    payload = {
        "schema": "keyfin-finance-selection-manifest/1",
        "cases": residual,
        "scope": {
            "source": "deterministic_serving_residual_static_synthetic_finance_selection",
            "parent_manifest_sha256": hashlib.sha256(raw).hexdigest(),
            "deterministic_direct_cases_excluded": True,
            "customer_data_included": False,
            "fdt_prediction_accuracy_measured": False,
            "used_for_candidate_training": False,
            "used_for_candidate_selection": False,
            "independent_human_oracle": False,
        },
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "parent_manifest_sha256": payload["scope"]["parent_manifest_sha256"],
        "cases": len(cases),
        "direct_cases": direct_cases,
        "model_residual_cases": len(residual),
        "customer_data_included": False,
        "fdt_prediction_accuracy_measured": False,
        "test_questions_or_answers_retained": False,
    }


def write_report(manifest_path: Path, output_path: Path) -> dict[str, object]:
    """Persist a new aggregate-only cascade result after rejecting accidental overwrite."""
    if output_path.exists():
        raise FileExistsError("finance_cascade_output_exists")
    report = evaluate_manifest(manifest_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> None:
    """Write a local aggregate report for a separately supplied static manifest."""
    parser = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument("--manifest", type=Path, required=True)
    _ = parser.add_argument("--output", type=Path, required=True)
    options = parser.parse_args()
    report = write_report(options.manifest, options.output)
    print(json.dumps({"cases": report["cases"], "direct": report["direct"]}))  # noqa: T201


if __name__ == "__main__":
    main()
