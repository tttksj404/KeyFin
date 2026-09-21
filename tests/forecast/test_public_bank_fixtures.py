"""Synthetic full-grid fixtures; no real banking rows enter the test repository."""

import hashlib
import json
from datetime import timedelta
from pathlib import Path

import numpy as np
from pydantic import TypeAdapter

from benchmarks.forecast import public_bank
from benchmarks.forecast.public_bank.baselines import BASELINES
from benchmarks.forecast.public_bank.contracts import Case, Inputs, Prediction, TrainingSeries, Truth
from benchmarks.forecast.public_bank.data import EXPECTED, sha256
from benchmarks.forecast.public_bank.evaluate import NEURAL
from benchmarks.forecast.public_bank.prepare import CUTOFFS


def final_targets(prepared: Path, amount: float = 20.0) -> list[Truth]:
    bundle = Inputs.model_validate_json((prepared / "model_inputs.json").read_bytes())
    return [Truth(case_id=case.case_id, actual=amount * case.horizon)
            for case in bundle.cases if case.split == "evaluation"]


def prepared_fixture(root: Path) -> tuple[Path, Path]:
    prepared, neural = root / "prepared", root / "neural"
    prepared.mkdir()
    neural.mkdir()
    (prepared / "predictions").mkdir()
    protocol = Path(public_bank.__file__).with_name("PROTOCOL.md")
    cases = []
    for split, count in (("development", 100), ("evaluation", 200)):
        for index in range(count):
            account = f"{split}-{index}"
            for cutoff in CUTOFFS[split]:
                cases.extend(Case.model_validate({
                        "case_id": f"{account}:{cutoff}:{horizon}", "account": account, "split": split,
                        "cutoff": cutoff, "first_date": cutoff - timedelta(days=364),
                        "end_date": cutoff + timedelta(days=horizon), "horizon": horizon,
                        "history": (10.0,) * 365}) for horizon in (7, 30))
    training = tuple(TrainingSeries(account=f"training-{index}", daily=(10.0,) * 365)
                     for index in range(2374))
    bundle = Inputs(protocol_sha256=sha256(protocol), training=training, cases=tuple(cases))
    (prepared / "model_inputs.json").write_text(bundle.model_dump_json(), encoding="utf-8")
    for model in (*BASELINES, *NEURAL):
        directory = prepared / "predictions" if model in BASELINES else neural
        rows = [Prediction(case_id=row.case_id, model=model, point=10.0 * row.horizon) for row in cases]
        (directory / f"{model}.predictions.json").write_bytes(TypeAdapter(list[Prediction]).dump_json(rows))
    targets = [Truth(case_id=row.case_id, actual=10.0 * row.horizon)
               for row in cases if row.split == "development"]
    (prepared / "development_truth.json").write_bytes(TypeAdapter(list[Truth]).dump_json(targets))
    final_hash = hashlib.sha256(TypeAdapter(list[Truth]).dump_json(final_targets(prepared))).hexdigest()
    created = "2026-09-14T00:00:00+00:00"
    (prepared / "protocol.lock.json").write_text(json.dumps({"protocol_sha256": bundle.protocol_sha256,
                                                            "created_at": created}), encoding="utf-8")
    (prepared / "manifest.json").write_text(json.dumps({"protocol_sha256": bundle.protocol_sha256,
        "created_at": created, "source_accounts": 4500, "excluded_unsupported_accounts": 1144,
        "eligible_accounts": 2674, "training_accounts": 2374, "currency": "CZK",
        "target": "gross_account_outflow", "data_provenance": "historical_bank_ledger",
        "transaction_type_counts": {"PRIJEM": 405083, "VYDAJ": 634571, "VYBER": 16666},
        "cases_by_split": {"development": 600, "evaluation": 1200}, "source_files": EXPECTED, "files": {
        "model_inputs.json": sha256(prepared / "model_inputs.json"),
        "development_truth.json": sha256(prepared / "development_truth.json"),
        "protocol.lock.json": sha256(prepared / "protocol.lock.json"),
        "evaluation_truth.json": final_hash}}), encoding="utf-8")
    write_run(neural, prepared, bundle)
    return prepared, neural


def write_run(neural: Path, prepared: Path, bundle: Inputs) -> None:
    base_hash = "a" * 64
    snapshot = neural / "source_snapshot" / "benchmarks" / "forecast" / "public_bank"
    snapshot.mkdir(parents=True)
    sources = list(Path(public_bank.__file__).parent.glob("*.py"))
    for path in sources:
        (snapshot / path.name).write_bytes(path.read_bytes())
    runtime = {"input_sha256": sha256(prepared / "model_inputs.json"),
               "protocol_sha256": bundle.protocol_sha256, "base_weights_sha256": base_hash,
               "source_sha256": {path.name: sha256(path) for path in sources},
               "cuda_available": True, "seed": 712}
    (neural / "runtime.json").write_text(json.dumps(runtime), encoding="utf-8")
    (neural / "completed.json").write_text('{"completed":true}', encoding="utf-8")
    training_hash = hashlib.sha256(b"".join(np.asarray(row.daily, dtype=np.float32).tobytes()
                                           for row in bundle.training)).hexdigest()
    for model in NEURAL:
        inference = {"model": model, "cases": len(bundle.cases), "batch_size": 64,
                     "context_length": 365, "cross_learning": False}
        (neural / f"{model}.inference.json").write_text(json.dumps(inference), encoding="utf-8")
        if "ft128" in model:
            training = {"model": model, "learning_rate": 1e-6 if "lr1e6" in model else 3e-6,
                        "steps": 128, "batch_size": 64, "context_length": 365, "prediction_length": 30,
                        "seed": 712, "training_series": len(bundle.training), "training_end": "1997-12-31",
                        "training_input_sha256": training_hash, "base_weights_sha256": base_hash,
                        "trained_weights_sha256": "b" * 64, "weights_changed": True}
            (neural / f"{model}.training.json").write_text(json.dumps(training), encoding="utf-8")
    (neural / "file_hashes.json").write_text(json.dumps({path.name: sha256(path)
                                                        for path in neural.glob("*.json")}), encoding="utf-8")
