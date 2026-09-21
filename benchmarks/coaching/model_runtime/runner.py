"""Run one local Hugging Face candidate on the fixed service-prompt manifest.

This module intentionally has no service imports.  A remote isolated runtime
receives only this file and a public manifest, then emits aggregate quality and
latency data without retaining prompts or generated text in its report.
"""

# ruff: noqa: ANN401, PLC0415

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import statistics
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

_JSON_FENCE: Final = re.compile(r"```(?:json)?\r?\n(.*?)\r?\n```", re.DOTALL)
_FINANCE_FIELDS: Final = frozenset({"status", "fact_ids", "missing"})
_FINANCE_STATUSES: Final = frozenset({"answered", "needs_source", "needs_data", "out_of_scope"})
_FINANCE_MISSING: Final = frozenset({"latest_source", "contract_terms", "tax_terms", "calculation"})


@dataclass(frozen=True, slots=True)
class Candidate:
    """One pinned model-loading configuration for a reproducible comparison."""

    path: Path
    name: str
    revision: str
    quantization: str
    adapter_path: Path | None = None


def percentile(samples: list[float], quantile: float) -> float:
    """Use nearest rank so a result always corresponds to an observed wave."""
    if not samples:
        raise ValueError("model_runtime_latency_missing")
    return sorted(samples)[max(0, math.ceil(len(samples) * quantile) - 1)]


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Reject duplicate keys just as the service's strict JSON parser does."""
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("model_runtime_duplicate_json_key")
        result[key] = value
    return result


def object_from_text(text: str) -> dict[str, Any] | None:
    """Parse exactly one service-acceptable JSON object, with one optional full fence."""
    candidate = text.strip()
    fenced = _JSON_FENCE.fullmatch(candidate)
    if fenced is not None and "```" not in fenced[1]:
        candidate = fenced[1]
    try:
        value = json.loads(candidate, object_pairs_hook=_unique_object)
    except (json.JSONDecodeError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def _selection_lists(value: dict[str, Any]) -> tuple[list[str], list[str]] | None:
    """Parse the two list fields that the FinanceSelection contract permits."""
    facts, missing = value.get("fact_ids"), value.get("missing", [])
    if (
        not isinstance(facts, list)
        or not isinstance(missing, list)
        or not all(isinstance(item, str) for item in facts)
        or not all(isinstance(item, str) for item in missing)
    ):
        return None
    return facts, missing


def _selection_shape_reason(value: dict[str, Any], facts: list[str], missing: list[str]) -> str | None:
    """Reject fields and list values that Pydantic's FinanceSelection would reject."""
    if not set(value).issubset(_FINANCE_FIELDS) or value.get("status") not in _FINANCE_STATUSES:
        return "finance_schema"
    if (
        len(facts) > 3
        or len(missing) > 3
        or len(facts) != len(set(facts))
        or len(missing) != len(set(missing))
        or not set(missing).issubset(_FINANCE_MISSING)
    ):
        return "finance_schema"
    return None


def _selection_status_reason(status: str, facts: list[str], missing: list[str]) -> str | None:
    """Mirror status-dependent FinanceSelection invariants before scoring content."""
    if status == "answered" and (not facts or missing):
        return "finance_schema"
    if status in {"needs_data", "out_of_scope"} and (facts or missing):
        return "finance_schema"
    if status != "needs_source" and missing:
        return "finance_schema"
    return None


def finance_score(value: dict[str, Any], expected: dict[str, Any]) -> tuple[bool, str]:
    """Check the exact bounded FinanceSelection fields without retaining model wording."""
    lists = _selection_lists(value)
    if lists is None:
        return False, "finance_schema"
    facts, missing = lists
    shape_reason = _selection_shape_reason(value, facts, missing)
    if shape_reason is not None:
        return False, shape_reason
    status = value.get("status")
    if not isinstance(status, str):
        return False, "finance_schema"
    status_reason = _selection_status_reason(status, facts, missing)
    if status_reason is not None:
        return False, status_reason
    allowed, required = set(expected["allowed_fact_ids"]), set(expected["required_fact_ids"])
    permitted = expected.get("permitted_fact_ids")
    checks = (
        (status != expected["status"], "finance_status"),
        (not set(facts).issubset(allowed) or not required.issubset(facts), "finance_fact_ids"),
        (isinstance(permitted, list) and not set(facts).issubset(set(permitted)), "finance_extra_fact_ids"),
        (not set(expected["required_missing"]).issubset(missing), "finance_missing"),
    )
    reason = next((reason for failed, reason in checks if failed), "ok")
    return reason == "ok", reason


def score(case: dict[str, Any], output: str) -> tuple[bool, bool, str]:
    """Score only service-authoritative fields and return a payload-free failure family."""
    value = object_from_text(output)
    if value is None:
        return False, False, "json_unparseable"
    if case["kind"] == "route":
        if set(value) != {"mode"}:
            return False, True, "route_schema"
        return (True, True, "ok") if value.get("mode") == case["expected"]["mode"] else (
            False, True, "route_mode",
        )
    if case["kind"] == "finance_selection":
        passed, reason = finance_score(value, case["expected"])
        return passed, True, reason
    return False, True, "case_kind"


def semantic_ok(case: dict[str, Any], output: str) -> tuple[bool, bool]:
    """Preserve the concise scorer used by unit tests and external evaluators."""
    passed, parsed, _ = score(case, output)
    return passed, parsed


def score_with_route_pair(
    case: dict[str, Any], output: str,
) -> tuple[bool, bool, str, tuple[str, str] | None]:
    """Return the optional label-only route pair without persisting model text."""
    passed, parsed, reason = score(case, output)
    if case["kind"] != "route":
        return passed, parsed, reason, None
    value = object_from_text(output)
    expected_mode = case["expected"].get("mode")
    predicted_mode = value.get("mode") if isinstance(value, dict) else None
    pair = None
    if isinstance(expected_mode, str) and isinstance(predicted_mode, str):
        pair = (expected_mode, predicted_mode)
    return passed, parsed, reason, pair


def prompt(tokenizer: Any, messages: list[dict[str, str]]) -> str:
    """Use the candidate's chat template with thinking explicitly disabled when supported."""
    try:
        return tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True, enable_thinking=False,
        )
    except TypeError:
        return tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)


def run_wave(
    model: Any, tokenizer: Any, cases: list[dict[str, Any]],
) -> tuple[float, list[str], list[int], list[int]]:
    """Run a synchronized batch; all users see the same completion barrier here."""
    import torch

    prompts = [prompt(tokenizer, row["messages"]) for row in cases]
    inputs = tokenizer(prompts, return_tensors="pt", padding=True)
    inputs = {name: value.to(model.device) for name, value in inputs.items()}
    started = time.perf_counter()
    with torch.inference_mode():
        generated = model.generate(
            **inputs,
            do_sample=False,
            max_new_tokens=max(int(row["max_tokens"]) for row in cases),
            pad_token_id=tokenizer.eos_token_id,
        )
    elapsed_ms = (time.perf_counter() - started) * 1000
    width = inputs["input_ids"].shape[1]
    outputs = tokenizer.batch_decode(generated[:, width:], skip_special_tokens=True)
    prompt_tokens = [int(value.sum().item()) for value in inputs["attention_mask"]]
    output_tokens = [len(row) for row in generated[:, width:].tolist()]
    return elapsed_ms, outputs, prompt_tokens, output_tokens


def load_candidate(candidate: Candidate) -> tuple[Any, Any, float]:
    """Load BF16 and quantized candidates through separate, explicit contracts."""
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    started = time.perf_counter()
    tokenizer = AutoTokenizer.from_pretrained(candidate.path, local_files_only=True, padding_side="left")
    tokenizer.pad_token = tokenizer.eos_token
    if candidate.quantization == "bf16":
        model = AutoModelForCausalLM.from_pretrained(
            candidate.path, local_files_only=True, torch_dtype=torch.bfloat16, low_cpu_mem_usage=True,
        ).to("cuda").eval()
    elif candidate.quantization == "bnb4":
        # The 4-bit candidate is evaluated separately from BF16.  It keeps bf16
        # matrix operations and NF4 weights, but it must pass the same semantic
        # gates before it can be considered for a memory-constrained deployment.
        from transformers import BitsAndBytesConfig

        model = AutoModelForCausalLM.from_pretrained(
            candidate.path,
            local_files_only=True,
            low_cpu_mem_usage=True,
            device_map={"": 0},
            quantization_config=BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_use_double_quant=True,
                bnb_4bit_compute_dtype=torch.bfloat16,
            ),
        ).eval()
    else:
        raise ValueError("model_runtime_quantization_invalid")
    if candidate.adapter_path is not None:
        # The adapter is an evaluated candidate artifact, never a source of
        # finance facts. Keep the base checkpoint pinned and make the optional
        # dependency explicit so ordinary scorer tests stay import-free.
        from peft import PeftModel

        model = PeftModel.from_pretrained(
            model, candidate.adapter_path, local_files_only=True, is_trainable=False,
        ).eval()
    return model, tokenizer, (time.perf_counter() - started) * 1000


def run(
    manifest_path: Path,
    candidate: Candidate,
    rounds: int,
) -> dict[str, object]:
    """Load one pinned local checkpoint and record only aggregate candidate evidence."""
    if rounds < 1:
        raise ValueError("model_runtime_rounds_invalid")
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    cases = manifest.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("model_runtime_cases_invalid")
    model, tokenizer, load_ms = load_candidate(candidate)
    conditions: list[dict[str, object]] = []
    for concurrency in (1, 4, 8):
        latencies: list[float] = []
        semantic = 0
        parseable = 0
        requests = 0
        prompt_tokens = 0
        completion_tokens = 0
        by_kind: Counter[str] = Counter()
        passed_by_kind: Counter[str] = Counter()
        by_stratum: Counter[str] = Counter()
        passed_by_stratum: Counter[str] = Counter()
        failure_reasons: Counter[str] = Counter()
        failure_cases: Counter[tuple[str, str]] = Counter()
        route_confusion: Counter[tuple[str, str]] = Counter()
        for round_index in range(rounds):
            for offset in range(0, len(cases), concurrency):
                wave = [cases[(offset + slot + round_index) % len(cases)] for slot in range(concurrency)]
                elapsed, outputs, prompts, completions = run_wave(model, tokenizer, wave)
                latencies.append(elapsed)
                requests += len(wave)
                prompt_tokens += sum(prompts)
                completion_tokens += sum(completions)
                for case, output in zip(wave, outputs, strict=True):
                    passed, parsed, reason, route_pair = score_with_route_pair(case, output)
                    if route_pair is not None:
                        route_confusion[route_pair] += 1
                    semantic += int(passed)
                    parseable += int(parsed)
                    kind = str(case["kind"])
                    by_kind[kind] += 1
                    passed_by_kind[kind] += int(passed)
                    stratum = case.get("stratum")
                    if isinstance(stratum, str):
                        by_stratum[stratum] += 1
                        passed_by_stratum[stratum] += int(passed)
                    if not passed:
                        failure_reasons[reason] += 1
                        # Case identifiers are fixed public evaluation labels.  Keeping
                        # them here exposes a reproducible failure class without ever
                        # persisting the user prompt or the model completion.
                        failure_cases[(str(case["id"]), reason)] += 1
        conditions.append({
            "concurrency": concurrency,
            "requests": requests,
            "semantic_ok": semantic,
            "json_parseable": parseable,
            "p50_wave_ms": round(statistics.median(latencies), 3),
            "p95_wave_ms": round(percentile(latencies, 0.95), 3),
            "mean_completion_tokens": round(completion_tokens / requests, 3),
            "mean_prompt_tokens": round(prompt_tokens / requests, 3),
            "scheduler": "synchronous_transformers_batch",
            "quality_by_kind": {
                kind: {"requests": by_kind[kind], "semantic_ok": passed_by_kind[kind]}
                for kind in sorted(by_kind)
            },
            "quality_by_stratum": {
                stratum: {"requests": by_stratum[stratum], "semantic_ok": passed_by_stratum[stratum]}
                for stratum in sorted(by_stratum)
            },
            "failure_reasons": dict(sorted(failure_reasons.items())),
            "failure_cases": [
                {"id": case_id, "reason": reason, "count": count}
                for (case_id, reason), count in sorted(failure_cases.items())
            ],
            "route_confusion": [
                {"expected": expected, "predicted": predicted, "count": count}
                for (expected, predicted), count in sorted(route_confusion.items())
            ],
        })
    return {
        "schema": "keyfin-model-runtime-report/1",
        "model": candidate.name,
        "revision": candidate.revision,
        "quantization": candidate.quantization,
        "adapter": "lora" if candidate.adapter_path is not None else "none",
        "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "model_load_ms": round(load_ms, 3),
        "conditions": conditions,
        "scope": {
            "quality": "public_fixed_route_and_fact_selection_only",
            "customer_data_included": False,
            "fdt_prediction_accuracy_measured": False,
            "deployment_latency_measured": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument("--manifest", type=Path, required=True)
    _ = parser.add_argument("--model-path", type=Path, required=True)
    _ = parser.add_argument("--model-name", required=True)
    _ = parser.add_argument("--revision", required=True)
    _ = parser.add_argument("--rounds", type=int, default=3)
    _ = parser.add_argument("--quantization", choices=("bf16", "bnb4"), default="bf16")
    _ = parser.add_argument("--adapter-path", type=Path)
    _ = parser.add_argument("--output", type=Path, required=True)
    options = parser.parse_args()
    report = run(
        options.manifest,
        Candidate(
            options.model_path, options.model_name, options.revision, options.quantization,
            options.adapter_path,
        ),
        options.rounds,
    )
    serialized = json.dumps(report, ensure_ascii=False, indent=2)
    options.output.write_text(serialized, encoding="utf-8")
    case_count = len(json.loads(options.manifest.read_text(encoding="utf-8"))["cases"])
    print(json.dumps({"conditions": len(report["conditions"]), "case_count": case_count}))  # noqa: T201


if __name__ == "__main__":
    main()
