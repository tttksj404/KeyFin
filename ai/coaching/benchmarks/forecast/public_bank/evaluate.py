# ruff: noqa: T201
"""Freeze a development-only choice before a separate command opens final truth."""

import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import numpy as np
from pydantic import TypeAdapter

from .baselines import BASELINES, predict
from .contracts import Case, Choice, Inputs, Selection, Split, Truth
from .data import sha256
from .metrics import Array, Sample, confidence, metrics
from .provenance import Manifest, RunManifest, verify_manifest, verify_run
from .validation import read_predictions, validate_frozen_grid

NEURAL: Final = ("chronos_base_daily", "chronos_base_cumulative",
                 "chronos_ft128_lr1e6_daily", "chronos_ft128_lr3e6_daily")
PAIRS: Final = (("recent90", "calendar_day"), ("calendar_day", "chronos_base_cumulative"),
               ("recent90", "chronos_base_daily"), ("calendar_day", "chronos_ft128_lr3e6_daily"))


@dataclass(frozen=True, slots=True)
class Prepared:
    bundle: Inputs
    values: dict[str, dict[str, float]]
    hashes: dict[str, str]
    run: RunManifest


def load(prepared: Path, neural: Path) -> Prepared:
    bundle = Inputs.model_validate_json((prepared / "model_inputs.json").read_bytes())
    if bundle.protocol_sha256 != sha256(Path(__file__).with_name("PROTOCOL.md")):
        raise ValueError("Protocol differs from frozen inputs")
    verify_manifest(prepared, bundle)
    validate_frozen_grid(bundle)
    run = verify_run(prepared, neural, bundle, NEURAL)
    values = {}
    hashes = {}
    expected = {case.case_id for case in bundle.cases}
    for model in (*BASELINES, *NEURAL):
        directory = prepared / "predictions" if model in BASELINES else neural
        path = directory / f"{model}.predictions.json"
        rows = read_predictions(path, expected)
        if any(row.model != model for row in rows):
            raise ValueError("Prediction model differs from filename")
        values[model] = {row.case_id: row.point for row in rows}
        hashes[model] = sha256(path)
    for case in bundle.cases:
        if any(not math.isclose(values[row.model][case.case_id], row.point, rel_tol=1e-12, abs_tol=1e-8)
               for row in predict(case)):
            raise ValueError("Stored baseline differs from observed-only recomputation")
    return Prepared(bundle, values, hashes, run)


def truth(prepared: Path, bundle: Inputs, split: Split) -> dict[str, float]:
    rows = TypeAdapter(list[Truth]).validate_json((prepared / f"{split}_truth.json").read_bytes())
    expected = {case.case_id for case in bundle.cases if case.split == split}
    ids = [row.case_id for row in rows]
    if len(ids) != len(set(ids)) or set(ids) != expected:
        raise ValueError("Truth grid is incomplete or duplicated")
    return {row.case_id: row.actual for row in rows}


def points(data: Prepared, cases: tuple[Case, ...], a: str, b: str, weight: float) -> Array:
    return np.asarray([weight * data.values[a][case.case_id] + (1 - weight) * data.values[b][case.case_id]
                       for case in cases], dtype=np.float64)


def build_choices(data: Prepared, targets: dict[str, float]) -> dict[int, Choice]:
    choices = {}
    for horizon in (7, 30):
        cases = tuple(case for case in data.bundle.cases
                      if case.split == "development" and case.horizon == horizon)
        actual = np.asarray([targets[case.case_id] for case in cases], dtype=np.float64)
        baseline = min(BASELINES, key=lambda name: (float(np.abs(
            points(data, cases, name, name, 1) - actual).mean()), name))
        candidates = [(name, name, 1.0) for name in (*BASELINES, *NEURAL)]
        candidates.extend((a, b, 0.5) for a, b in PAIRS)
        scored = [(float(np.abs(points(data, cases, a, b, weight) - actual).mean()), a, b, weight)
                  for a, b, weight in candidates]
        error, a, b, weight = min(scored)
        choices[horizon] = Choice(model_a=a, model_b=b, weight_a=weight, scale=1,
                                  development_mae=error, baseline=baseline)
    return choices


def select(prepared: Path, neural: Path) -> None:
    """Open only development truth and persist the selected model before final scoring."""
    destination = prepared / "selection.json"
    if destination.exists():
        raise ValueError("Selection already frozen; use a new experiment instead of overwriting")
    data = load(prepared, neural)
    targets = truth(prepared, data.bundle, "development")
    run_path = prepared / "neural_run_manifest.json"
    with run_path.open("x", encoding="utf-8") as stream:
        stream.write(data.run.model_dump_json())
    manifest = Manifest.model_validate_json((prepared / "manifest.json").read_bytes())
    selection = Selection(protocol_sha256=data.bundle.protocol_sha256,
                          input_sha256=sha256(prepared / "model_inputs.json"),
                          prepared_manifest_sha256=sha256(prepared / "manifest.json"),
                          evaluation_truth_sha256=manifest.files["evaluation_truth.json"],
                          neural_run_manifest_sha256=sha256(run_path),
                          development_truth_sha256=sha256(prepared / "development_truth.json"),
                          prediction_sha256=data.hashes, choices=build_choices(data, targets))
    with destination.open("x", encoding="utf-8") as stream:
        stream.write(selection.model_dump_json(indent=2))
    print("PUBLIC_BANK_SELECTION_FROZEN", flush=True)


def evaluate(prepared: Path, neural: Path) -> None:
    """Only a persisted, unchanged development selection admits final scoring."""
    selection_path = prepared / "selection.json"
    selection = Selection.model_validate_json(selection_path.read_bytes())
    data = load(prepared, neural)
    if (selection.protocol_sha256 != data.bundle.protocol_sha256
            or selection.input_sha256 != sha256(prepared / "model_inputs.json")
            or selection.prepared_manifest_sha256 != sha256(prepared / "manifest.json")
            or selection.development_truth_sha256 != sha256(prepared / "development_truth.json")
            or selection.prediction_sha256 != data.hashes):
        raise ValueError("Frozen selection inputs or predictions changed")
    run_path = prepared / "neural_run_manifest.json"
    if (sha256(run_path) != selection.neural_run_manifest_sha256
            or RunManifest.model_validate_json(run_path.read_bytes()) != data.run):
        raise ValueError("Frozen neural run provenance changed")
    if selection.choices != build_choices(data, truth(prepared, data.bundle, "development")):
        raise ValueError("Frozen choice differs from development-only selection")
    if selection.evaluation_truth_sha256 != sha256(prepared / "evaluation_truth.json"):
        raise ValueError("Frozen evaluation truth changed")
    targets = truth(prepared, data.bundle, "evaluation")
    results = {}
    for horizon in (7, 30):
        cases = tuple(case for case in data.bundle.cases
                      if case.split == "evaluation" and case.horizon == horizon)
        actual = np.asarray([targets[case.case_id] for case in cases], dtype=np.float64)
        choice = selection.choices[horizon]
        selected = points(data, cases, choice.model_a, choice.model_b, choice.weight_a) * choice.scale
        reference = points(data, cases, choice.baseline, choice.baseline, 1)
        independent = {model: metrics(actual, points(data, cases, model, model, 1)).model_dump()
                       for model in (*BASELINES, *NEURAL)}
        results[str(horizon)] = {
            "choice": choice.model_dump(), "selected": metrics(actual, selected).model_dump(),
            "baseline": metrics(actual, reference).model_dump(), "individual_candidates": independent,
            "confidence": confidence(Sample(tuple(case.account for case in cases), actual,
                                              selected, reference)).model_dump(),
        }
    report = {"target": "gross_account_outflow", "currency": "CZK", "split": "evaluation",
              "data_provenance": "historical_bank_ledger", "real_korean_customer_validation": False,
              "model_provenance": "recorded local Chronos2Pipeline checkpoint",
              "limitations": ["Czech historical gross outflow; not consumption or account balance",
                              "Transaction-time availability assumed; available_at absent",
                              "Unsupported transaction types excluded across whole account history",
                              "Account clusters may share a customer; pretrained data overlap unknown",
                              ("Exact checkpoint hash was recorded at runtime, not preregistered; "
                               "canonical base identity is not claimed"),
                              ("128 training steps were requested and fitting completed with changed "
                               "weights; 128 optimizer updates were not independently confirmed")],
              "selection_sha256": sha256(selection_path), "protocol_sha256": data.bundle.protocol_sha256,
              "evaluation_truth_sha256": sha256(prepared / "evaluation_truth.json"), "horizons": results}
    with (prepared / "report.json").open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2)
    print("PUBLIC_BANK_EVALUATION_COMPLETE", flush=True)


if __name__ == "__main__":
    command, directory, model_output = sys.argv[1:]
    actions = {"select": select, "evaluate": evaluate}
    actions[command](Path(directory), Path(model_output))
