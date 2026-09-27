"""Verify the recorded accelerator run before accepting neural model names."""

import hashlib
from datetime import datetime
from pathlib import Path
from typing import ClassVar, Literal, Self

import numpy as np
from pydantic import BaseModel, ConfigDict, TypeAdapter, model_validator

from .contracts import Frozen, Inputs
from .data import EXPECTED, sha256
from .source_verification import SourceEvidence, verify_sources


class Projection(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="ignore", allow_inf_nan=False)


class Manifest(Frozen):
    protocol_sha256: str
    created_at: datetime
    source_accounts: Literal[4500]
    transaction_type_counts: dict[str, int]
    excluded_unsupported_accounts: Literal[1144]
    eligible_accounts: Literal[2674]
    training_accounts: Literal[2374]
    cases_by_split: dict[str, int]
    currency: Literal["CZK"]
    target: Literal["gross_account_outflow"]
    data_provenance: Literal["historical_bank_ledger"]
    files: dict[str, str]
    source_files: dict[str, str]

    @model_validator(mode="after")
    def frozen_source_profile(self) -> Self:
        if (self.source_files != EXPECTED or self.cases_by_split != {"development": 600, "evaluation": 1200}
                or self.transaction_type_counts != {"PRIJEM": 405083, "VYDAJ": 634571, "VYBER": 16666}
                or self.created_at.tzinfo is None
                or set(self.files) != {"model_inputs.json", "development_truth.json",
                                       "evaluation_truth.json", "protocol.lock.json"}):
            raise ValueError("Prepared manifest differs from frozen source profile")
        return self


class ProtocolLock(Frozen):
    protocol_sha256: str
    created_at: datetime


def verify_manifest(prepared: Path, bundle: Inputs) -> Manifest:
    manifest = Manifest.model_validate_json((prepared / "manifest.json").read_bytes())
    lock = ProtocolLock.model_validate_json((prepared / "protocol.lock.json").read_bytes())
    if (manifest.protocol_sha256 != bundle.protocol_sha256 or lock.protocol_sha256 != bundle.protocol_sha256
            or manifest.created_at != lock.created_at
            or any(manifest.files[name] != sha256(prepared / name) for name in
                   ("model_inputs.json", "development_truth.json", "protocol.lock.json"))):
        raise ValueError("Prepared inputs differ from frozen manifest")
    return manifest


class Runtime(Projection):
    input_sha256: str
    protocol_sha256: str
    base_weights_sha256: str
    source_sha256: dict[str, str]
    cuda_available: bool
    seed: int


class Training(Projection):
    model: str
    learning_rate: float
    steps: int
    batch_size: int
    context_length: int
    prediction_length: int
    seed: int
    training_series: int
    training_end: str
    training_input_sha256: str
    base_weights_sha256: str
    trained_weights_sha256: str
    weights_changed: bool


class Inference(Projection):
    model: str
    cases: int
    batch_size: int
    context_length: int
    cross_learning: bool


class RunManifest(Frozen):
    collected_file_hashes_sha256: str
    file_sha256: dict[str, str]
    runtime: Runtime
    source_evidence: SourceEvidence


def verify_run(prepared: Path, directory: Path, bundle: Inputs, models: tuple[str, ...]) -> RunManifest:
    recorded = TypeAdapter(dict[str, str]).validate_json((directory / "file_hashes.json").read_bytes())
    expected = {"runtime.json", "completed.json"}
    expected.update(f"{model}.{kind}.json" for model in models for kind in ("inference", "predictions"))
    expected.update(f"{model}.training.json" for model in models if "ft128" in model)
    if set(recorded) != expected or any(
        sha256(directory / name) != value for name, value in recorded.items()
    ):
        raise ValueError("Neural run files differ from collected accelerator hashes")
    completed = TypeAdapter(dict[str, bool]).validate_json((directory / "completed.json").read_bytes())
    runtime = Runtime.model_validate_json((directory / "runtime.json").read_bytes())
    if (completed != {"completed": True} or not runtime.cuda_available or runtime.seed != 712
            or runtime.input_sha256 != sha256(prepared / "model_inputs.json")
            or runtime.protocol_sha256 != bundle.protocol_sha256
            or len(runtime.base_weights_sha256) != 64):
        raise ValueError("Neural runtime completion or frozen inputs do not match")
    source_evidence = verify_sources(directory, runtime.source_sha256)
    training_hash = hashlib.sha256(b"".join(np.asarray(row.daily, dtype=np.float32).tobytes()
                                           for row in bundle.training)).hexdigest()
    for model in models:
        inference = Inference.model_validate_json((directory / f"{model}.inference.json").read_bytes())
        if (inference.model != model or inference.cases != len(bundle.cases) or inference.batch_size != 64
                or inference.context_length != 365 or inference.cross_learning):
            raise ValueError("Neural inference conditions differ from protocol")
        if "ft128" not in model:
            continue
        training = Training.model_validate_json((directory / f"{model}.training.json").read_bytes())
        rate = 1e-6 if "lr1e6" in model else 3e-6
        if (training.model != model or training.learning_rate != rate or training.steps != 128
                or training.batch_size != 64 or training.context_length != 365
                or training.prediction_length != 30
                or training.seed != 712 or training.training_series != len(bundle.training)
                or training.training_end != str(bundle.training_end)
                or training.training_input_sha256 != training_hash
                or training.base_weights_sha256 != runtime.base_weights_sha256 or not training.weights_changed
                or training.trained_weights_sha256 == runtime.base_weights_sha256
                or len(training.trained_weights_sha256) != 64):
            raise ValueError("Fine-tuning provenance differs from frozen training conditions")
    return RunManifest(collected_file_hashes_sha256=sha256(directory / "file_hashes.json"),
                       file_sha256=recorded, runtime=runtime, source_evidence=source_evidence)
