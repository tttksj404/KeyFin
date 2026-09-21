"""Verify source and record bytes before the one-way select/calibrate/evaluate stages."""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from pydantic import TypeAdapter

from benchmarks.forecast.public_bank.contracts import Frozen, Truth
from benchmarks.forecast.public_bank.data import sha256

from .arithmetic import NEURAL, predict
from .contracts import Inputs, Prediction, Split
from .protocol_boundary import Manifest, ProtocolLock, validate_inputs, validate_manifest
from .provenance import validate_gpu
from .selection import Bank, Choice, candidate_bank


class SelectionLock(Frozen):
    hashes: dict[str, str]
    choices: dict[int, Choice]


class CalibrationLock(Frozen):
    selection_sha256: str
    calibration_truth_sha256: str
    radii: dict[int, dict[str, float]]


@dataclass(frozen=True, slots=True)
class Prepared:
    inputs: Inputs
    bank: Bank
    hashes: Mapping[str, str]


def freeze(prepared: Path, gpu: Path) -> Prepared:
    """Hash targets without parsing them; target values belong to later explicit stages."""
    manifest = Manifest.model_validate_json((prepared / "manifest.json").read_bytes())
    validate_manifest(manifest)
    if manifest.protocol_sha256 != sha256(Path(__file__).with_name("PROTOCOL.md")):
        raise ValueError("Protocol changed after preparation")
    for name, digest in manifest.files.items():
        if Path(name).name != name or sha256(prepared / name) != digest:
            raise ValueError("Prepared artifact changed or path is unsafe")
    lock = ProtocolLock.model_validate_json((prepared / "protocol.lock.json").read_bytes())
    if lock.sha256 != manifest.protocol_sha256 or sha256(prepared / "PROTOCOL.md") != lock.sha256:
        raise ValueError("Preparation protocol lock differs from reviewed protocol")
    inputs = Inputs.model_validate_json((prepared / "model_inputs.json").read_bytes())
    validate_inputs(inputs, manifest)
    if inputs.protocol_sha256 != manifest.protocol_sha256:
        raise ValueError("Input protocol differs")
    hashes = {f"prepared/{name}": digest for name, digest in manifest.files.items()}
    hashes["prepared/manifest.json"] = sha256(prepared / "manifest.json")
    adapter = TypeAdapter(tuple[Prediction, ...])
    arithmetic = adapter.validate_json((prepared / "arithmetic.json").read_bytes())
    # Recompute these cheap references from inputs to detect a saved-prediction error.
    recomputed = tuple(row for case in inputs.cases for row in predict(case))
    if arithmetic != recomputed:
        raise ValueError("Arithmetic predictions do not match observed-only inputs")
    file_hashes = checked_gpu_hashes(gpu)
    validate_gpu(gpu, prepared / "model_inputs.json", inputs)
    hashes.update({f"gpu/{name}": digest for name, digest in file_hashes.items()})
    hashes["gpu/file_hashes.json"] = sha256(gpu / "file_hashes.json")
    forecasts = list(arithmetic)
    for name in NEURAL:
        rows = adapter.validate_json((gpu / f"{name}.predictions.json").read_bytes())
        if any(row.model != name for row in rows):
            raise ValueError("Candidate file contains a different model")
        forecasts.extend(rows)
    return Prepared(inputs, candidate_bank(inputs.cases, tuple(forecasts)), hashes)


def checked_gpu_hashes(gpu: Path) -> dict[str, str]:
    """Read bounded file-name hashes; nested source files must remain inside the artifact root."""
    file_hashes = TypeAdapter(dict[str, str]).validate_json((gpu / "file_hashes.json").read_bytes())
    required = {"completed.json", "runtime.json", *(f"{name}.predictions.json" for name in NEURAL)}
    if not required <= file_hashes.keys():
        raise ValueError("Incomplete GPU evidence")
    for name, digest in file_hashes.items():
        path = (gpu / name).resolve()
        if not path.is_relative_to(gpu.resolve()) or sha256(path) != digest:
            raise ValueError("GPU artifact changed or path is unsafe")
    return file_hashes


def truth_for(prepared: Path, inputs: Inputs, split: Split) -> tuple[Truth, ...]:
    """Reject incomplete, duplicate and cross-partition observations."""
    rows = TypeAdapter(tuple[Truth, ...]).validate_json((prepared / f"{split}_truth.json").read_bytes())
    expected = {case.case_id for case in inputs.cases if case.split == split}
    if len(rows) != len(expected) or {row.case_id for row in rows} != expected:
        raise ValueError("Targets missing, duplicated, or outside requested partition")
    return rows


def verify_lock(lock: SelectionLock, prepared: Prepared) -> None:
    if lock.hashes != prepared.hashes:
        raise ValueError("Artifacts changed after model selection")


def write_new(path: Path, value: Frozen) -> None:
    """Never replace a previous model selection or calibration record."""
    with path.open("x", encoding="utf-8") as stream:
        _ = stream.write(value.model_dump_json(indent=2))
