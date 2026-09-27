"""Pure prediction and optimizer-audit boundaries for the aggregate GPU worker."""

import hashlib
import importlib.metadata
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

import numpy as np
from numpy.typing import NDArray
from pydantic import Field, FiniteFloat, TypeAdapter

from benchmarks.forecast.public_bank.contracts import Frozen
from benchmarks.forecast.public_bank.data import sha256

from .contracts import Inputs, Prediction


class RunConfig(Frozen):
    inputs: Path
    output: Path
    chronos_checkpoint: Path
    expected_base_weights_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


@dataclass(frozen=True, slots=True)
class TrainingSpec:
    name: str
    steps: int
    learning_rate: float


TRAINING: Final = (
    TrainingSpec("chronos_aggregate_ft128_lr1e6", 128, 1e-6),
    TrainingSpec("chronos_aggregate_ft256_lr3e6", 256, 3e-6),
)
BASE_NAME: Final = "chronos_aggregate_base"
SEED: Final = 715


class UpdateEvidence(Frozen):
    requested_updates: int
    optimizer_step_events: int
    optimizer_updates: int
    skipped_updates: int
    global_step: int
    observed_global_steps: tuple[int, ...]


class UpdateEvidenceError(ValueError):
    def __init__(self, expected: int, observed: int) -> None:
        self.expected: int = expected
        self.observed: int = observed
        super().__init__(f"optimizer update evidence mismatch: expected {expected}, observed {observed}")


@dataclass(slots=True)
class UpdateAudit:
    """Mutable callback ledger: record optimizer events separately from completed trainer steps."""

    optimizer_events: int = 0
    updates: int = 0
    skipped: int = 0
    steps: list[int] = field(default_factory=list)

    def optimizer_step(self, *, skipped: bool) -> None:
        self.optimizer_events += 1
        self.skipped += int(skipped)
        self.updates += int(not skipped)

    def step_end(self, global_step: int) -> None:
        expected = len(self.steps) + 1
        if global_step != expected:
            raise UpdateEvidenceError(expected, global_step)
        self.steps.append(global_step)

    def finish(self, requested: int) -> UpdateEvidence:
        if self.updates != requested or self.optimizer_events != requested or len(self.steps) != requested:
            raise UpdateEvidenceError(requested, self.updates)
        return self.snapshot(requested)

    def snapshot(self, requested: int) -> UpdateEvidence:
        """Preserve observed counts even when training ends before its requested updates."""
        return UpdateEvidence(
            requested_updates=requested,
            optimizer_step_events=self.optimizer_events,
            optimizer_updates=self.updates,
            skipped_updates=self.skipped,
            global_step=self.steps[-1] if self.steps else 0,
            observed_global_steps=tuple(self.steps),
        )


@dataclass(slots=True)
class QuantileAudit:
    quantile_crossings_raw: int = 0
    quantile_crossings_after_clip: int = 0
    quantile_intervals_widened: int = 0

    def values(self) -> dict[str, int]:
        return {
            "quantile_crossings_raw": self.quantile_crossings_raw,
            "quantile_crossings_after_clip": self.quantile_crossings_after_clip,
            "quantile_intervals_widened": self.quantile_intervals_widened,
        }


def terminal_prediction(
    case_id: str,
    model: str,
    quantiles: NDArray[np.float64],
    horizon: int,
    audit: QuantileAudit | None = None,
) -> Prediction:
    """Use the last rolling sum, which covers exactly the unseen target; never sum rows."""
    if quantiles.shape not in ((horizon, 3), (1, horizon, 3)):
        raise ValueError("Unexpected forecast quantile shape")
    rows = TypeAdapter(tuple[tuple[FiniteFloat, FiniteFloat, FiniteFloat], ...]).validate_python(
        quantiles.reshape(horizon, 3)
    )
    values = rows[-1]
    lower, point, upper = (max(value, 0) for value in values)
    crossed = not lower <= point <= upper
    if audit is not None:
        audit.quantile_crossings_raw += int(not values[0] <= values[1] <= values[2])
        audit.quantile_crossings_after_clip += int(crossed)
        audit.quantile_intervals_widened += int(crossed)
    # Widen the interval around the unchanged clipped median; sorting would change the point forecast.
    return Prediction(
        case_id=case_id,
        model=model,
        lower=min(lower, point),
        point=point,
        upper=max(upper, point),
    )


def array_hash(arrays: Sequence[NDArray[np.float32]]) -> str:
    """Include each series length so concatenations cannot hide changed series boundaries."""
    digest = hashlib.sha256()
    for array in arrays:
        digest.update(len(array).to_bytes(8, "big"))
        digest.update(array.tobytes())
    return digest.hexdigest()


def weight_hash(path: Path) -> str:
    """Hash all weight shards by filename and bytes; paths themselves are never published."""
    digest = hashlib.sha256()
    files = sorted(path.glob("*.safetensors"))
    if not files:
        raise FileNotFoundError("Checkpoint has no safetensors weights")
    for file in files:
        digest.update(file.name.encode())
        with file.open("rb") as stream:
            while chunk := stream.read(8 * 1024 * 1024):
                digest.update(chunk)
    return digest.hexdigest()


class SourceHashes(Frozen):
    files: dict[str, str]


def source_hashes() -> SourceHashes:
    return SourceHashes(
        files={path.name: sha256(path) for path in sorted(Path(__file__).parent.glob("*.py"))}
    )


class Runtime(Frozen):
    packages: dict[str, str]
    input_sha256: str
    protocol_sha256: str
    base_weights_sha256: str
    source_sha256: dict[str, str]
    candidates: tuple[str, ...]
    cuda_available: bool = True
    memory_fraction: float = 0.4
    seed: int = SEED


def write_runtime(config: RunConfig, bundle: Inputs) -> Runtime:
    """Reject changed protocol or base weights before inference and record source provenance."""
    protocol_hash = sha256(Path(__file__).with_name("PROTOCOL.md"))
    if bundle.protocol_sha256 != protocol_hash:
        raise ValueError("Worker protocol differs from prepared input")
    base_hash = weight_hash(config.chronos_checkpoint)
    if base_hash != config.expected_base_weights_sha256:
        raise ValueError("Fresh base checkpoint does not match the recorded base weights")
    result = Runtime(
        packages={
            name: importlib.metadata.version(name)
            for name in ("torch", "transformers", "chronos-forecasting", "numpy")
        },
        input_sha256=sha256(config.inputs),
        protocol_sha256=protocol_hash,
        base_weights_sha256=base_hash,
        source_sha256=source_hashes().files,
        candidates=(BASE_NAME, *(spec.name for spec in TRAINING)),
    )
    _ = (config.output / "runtime.json").write_text(result.model_dump_json(indent=2), encoding="utf-8")
    return result


class Completion(Frozen):
    completed: bool = True
    training_runs: int = 4
    inference_runs: int = 6
    candidates: int = 3
    cases_per_candidate: int
    protocol_sha256: str
    input_sha256: str


def finish_run(config: RunConfig, runtime: Runtime, cases: int) -> None:
    """Require unchanged sources, input bytes and base weights before completion."""
    if (
        runtime.source_sha256 != source_hashes().files
        or runtime.base_weights_sha256 != weight_hash(config.chronos_checkpoint)
        or runtime.input_sha256 != sha256(config.inputs)
    ):
        raise RuntimeError("Source, input or base weights changed during execution")
    result = Completion(
        cases_per_candidate=cases, protocol_sha256=runtime.protocol_sha256, input_sha256=runtime.input_sha256
    )
    _ = (config.output / "completed.json").write_text(result.model_dump_json(), encoding="utf-8")
