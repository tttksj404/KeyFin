"""Verify completed training evidence and actual executed source, not a success filename."""

import ast
from pathlib import Path

import numpy as np
from pydantic import Field, TypeAdapter

from benchmarks.forecast.public_bank.contracts import Frozen
from benchmarks.forecast.public_bank.data import sha256

from .arithmetic import NEURAL, rolling_sums
from .contracts import Inputs
from .worker_support import Completion, Runtime, UpdateEvidence, array_hash


class TrainingRecord(Frozen):
    model: str
    horizon: int
    learning_rate: float
    num_steps_requested: int
    optimizer_evidence: UpdateEvidence
    batch_size: int
    context_length: int
    min_past: int
    seed: int
    training_series: int
    training_end: str
    training_input_sha256: str
    base_weights_sha256: str
    trained_weights_sha256: str
    weights_changed: bool
    load_seconds: float
    seconds: float
    peak_allocated_gib: float
    peak_reserved_gib: float


class InferenceRecord(Frozen):
    model: str
    horizon: int
    cases: int
    seconds: float
    context_input_sha256: str
    peak_allocated_gib: float
    peak_reserved_gib: float
    batch_size: int
    context_length: int
    cross_learning: bool
    quantile_crossings_raw: int = Field(ge=0)
    quantile_crossings_after_clip: int = Field(ge=0)
    quantile_intervals_widened: int = Field(ge=0)


def validate_completion(gpu: Path, inputs_path: Path, inputs: Inputs, runtime: Runtime) -> None:
    """Completion markers are necessary, but actual source and step records are checked separately."""
    complete = Completion.model_validate_json((gpu / "completed.json").read_bytes())
    if (not complete.completed or complete.training_runs != 4 or complete.inference_runs != 6
            or complete.candidates != 3 or complete.cases_per_candidate != len(inputs.cases)):
        raise ValueError("GPU run did not complete the full frozen comparison")
    expected_input = sha256(inputs_path)
    if runtime.input_sha256 != expected_input or complete.input_sha256 != expected_input:
        raise ValueError("GPU predictions used different inputs")
    if (runtime.protocol_sha256 != inputs.protocol_sha256
            or complete.protocol_sha256 != inputs.protocol_sha256
            or set(runtime.candidates) != set(NEURAL) or runtime.seed != 715 or not runtime.cuda_available):
        raise ValueError("GPU runtime differs from the frozen protocol")


def validate_sources(gpu: Path, runtime: Runtime) -> None:
    for name, digest in runtime.source_sha256.items():
        path = gpu / "source_snapshot" / name
        if Path(name).name != name or sha256(path) != digest:
            raise ValueError("Executed source bytes are missing or changed")
    # Evaluation/report code may evolve before truth is opened; inference semantics may not.
    for name in ("worker.py", "worker_support.py", "arithmetic.py", "contracts.py"):
        executed = ast.dump(ast.parse((gpu / "source_snapshot" / name).read_text(encoding="utf-8")))
        reviewed = ast.dump(ast.parse(Path(__file__).with_name(name).read_text(encoding="utf-8")))
        if executed != reviewed:
            raise ValueError("Executed inference source differs from reviewed code")


def validate_updates(observed: UpdateEvidence, updates: int) -> None:
    """Require observed optimizer updates independently of the requested count."""
    if (observed.optimizer_updates != updates or observed.optimizer_step_events != updates
            or observed.global_step != updates or observed.requested_updates != updates
            or observed.skipped_updates != 0
            or observed.observed_global_steps != tuple(range(1, updates + 1))):
        raise ValueError("Actual optimizer updates are incomplete")


def validate_training(gpu: Path, inputs: Inputs, runtime: Runtime) -> None:
    expected_hashes = {h: array_hash(tuple(np.asarray(rolling_sums(row.daily, h), dtype=np.float32)
                                         for row in inputs.training)) for h in (7, 30)}
    for name, updates, rate in ((NEURAL[1], 128, 1e-6), (NEURAL[2], 256, 3e-6)):
        for horizon in (7, 30):
            path = gpu / f"{name}.h{horizon}.training.json"
            record = TrainingRecord.model_validate_json(path.read_bytes())
            if (record.model != name or record.horizon != horizon or record.num_steps_requested != updates
                    or record.learning_rate != rate or record.batch_size != 64 or record.seed != 715
                    or record.training_series != len(inputs.training) or record.training_end != "1997-12-31"
                    or record.context_length != 365 or record.min_past != 60
                    or record.training_input_sha256 != expected_hashes[horizon]):
                raise ValueError("Training settings differ from frozen protocol")
            validate_updates(record.optimizer_evidence, updates)
            if (record.base_weights_sha256 != runtime.base_weights_sha256 or not record.weights_changed
                    or record.trained_weights_sha256 == record.base_weights_sha256):
                raise ValueError("Training did not start from base or change weights")


def validate_inference(gpu: Path, inputs: Inputs) -> None:
    for horizon in (7, 30):
        cases = tuple(row for row in inputs.cases if row.horizon == horizon)
        expected = array_hash(tuple(np.asarray(rolling_sums(row.history, horizon), dtype=np.float32)
                                    for row in cases))
        for name in NEURAL:
            record = InferenceRecord.model_validate_json(
                (gpu / f"{name}.h{horizon}.inference.json").read_bytes())
            if (record.model != name or record.horizon != horizon or record.cases != len(cases)
                    or record.batch_size != 64 or record.context_length != 365 or record.cross_learning
                    or record.context_input_sha256 != expected
                    or record.quantile_intervals_widened != record.quantile_crossings_after_clip
                    or not (record.quantile_crossings_after_clip
                            <= record.quantile_crossings_raw <= len(cases))):
                raise ValueError("Inference did not use the full frozen contexts and settings")


def validate_gpu(gpu: Path, inputs_path: Path, inputs: Inputs) -> None:
    """Require four actual optimizer runs, six inferences, and aligned frozen inputs."""
    runtime = Runtime.model_validate_json((gpu / "runtime.json").read_bytes())
    validate_completion(gpu, inputs_path, inputs, runtime)
    validate_sources(gpu, runtime)
    validate_training(gpu, inputs, runtime)
    validate_inference(gpu, inputs)
    hashes = TypeAdapter(dict[str, str]).validate_json((gpu / "file_hashes.json").read_bytes())
    required = {f"{name}.h{h}.training.json" for name in NEURAL[1:] for h in (7, 30)}
    required.update(f"{name}.h{h}.inference.json" for name in NEURAL for h in (7, 30))
    required.update(f"source_snapshot/{name}" for name in runtime.source_sha256)
    if not required <= hashes.keys():
        raise ValueError("Run records or source snapshots are absent from the remote checksum manifest")
