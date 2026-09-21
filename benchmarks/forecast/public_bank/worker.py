# ruff: noqa: T201
"""Accelerator-only inference/training; this module cannot open a target file."""

import gc
import hashlib
import importlib.metadata
import json
import os
import sys
import time
from pathlib import Path
from typing import Final

import numpy as np
import torch
from chronos import Chronos2Pipeline
from pydantic import TypeAdapter
from scripts.gpu_registry import validate_device

from .contracts import Case, Frozen, Inputs, Prediction
from .data import sha256

CONFIGS: Final = (("chronos_ft128_lr1e6_daily", 1e-6), ("chronos_ft128_lr3e6_daily", 3e-6))


class RunConfig(Frozen):
    inputs: Path
    output: Path
    chronos_checkpoint: Path


def weight_hash(path: Path) -> str:
    digest = hashlib.sha256()
    files = sorted(path.glob("*.safetensors"))
    if not files:
        raise ValueError("Checkpoint has no safetensors weights")
    for file in files:
        digest.update(file.name.encode())
        with file.open("rb") as stream:
            while chunk := stream.read(8 * 1024 * 1024):
                digest.update(chunk)
    return digest.hexdigest()


def predict(
    pipeline: Chronos2Pipeline, cases: tuple[Case, ...], name: str, *, cumulative: bool,
) -> list[Prediction]:
    arrays = [np.asarray(case.history, dtype=np.float32) for case in cases]
    contexts = [np.cumsum(array, dtype=np.float32) if cumulative else array for array in arrays]
    quantiles, means = pipeline.predict_quantiles(
        contexts, prediction_length=30, quantile_levels=[0.1, 0.5, 0.9],
        context_length=365, batch_size=64, cross_learning=False,
    )
    predictions = []
    for case, context, quantile, mean in zip(cases, contexts, quantiles, means, strict=True):
        if cumulative:
            values = np.asarray(quantile.detach().float().cpu().numpy(), dtype=np.float64).reshape(30, 3)
            point = float(max(0, values[case.horizon - 1, 1] - context[-1]))
        else:
            daily = np.asarray(mean.detach().float().cpu().numpy(), dtype=np.float64).reshape(30)
            point = float(np.maximum(daily[:case.horizon], 0).sum())
        predictions.append(Prediction(case_id=case.case_id, model=name, point=point))
    return predictions


def save_inference(
    pipe: Chronos2Pipeline, config: RunConfig, bundle: Inputs, name: str, *, cumulative: bool,
) -> None:
    torch.cuda.synchronize()
    start = time.perf_counter()
    rows = predict(pipe, bundle.cases, name, cumulative=cumulative)
    torch.cuda.synchronize()
    (config.output / f"{name}.predictions.json").write_bytes(TypeAdapter(list[Prediction]).dump_json(rows))
    record = {"model": name, "cases": len(rows), "seconds": time.perf_counter() - start,
              "peak_reserved_gib": torch.cuda.max_memory_reserved() / 2**30,
              "peak_allocated_gib": torch.cuda.max_memory_allocated() / 2**30,
              "batch_size": 64, "context_length": 365, "cross_learning": False}
    (config.output / f"{name}.inference.json").write_text(json.dumps(record), encoding="utf-8")
    print(json.dumps({"completed": name, "cases": len(rows), "seconds": record["seconds"]}), flush=True)


def run(config: RunConfig) -> None:
    validate_device(os.environ)
    if not torch.cuda.is_available() or torch.cuda.device_count() != 1:
        raise RuntimeError("Exactly one visible accelerator is required")
    config.output.mkdir(parents=True, exist_ok=False)
    bundle = Inputs.model_validate_json(config.inputs.read_bytes())
    if bundle.protocol_sha256 != sha256(Path(__file__).with_name("PROTOCOL.md")):
        raise ValueError("Worker protocol differs from prepared input")
    torch.set_num_threads(8)
    torch.cuda.set_per_process_memory_fraction(0.4)
    torch.manual_seed(712)
    np.random.seed(712)  # noqa: NPY002 -- record-compatible library seed in isolated worker.
    torch.cuda.reset_peak_memory_stats()
    base_hash = weight_hash(config.chronos_checkpoint)
    source_hashes = {path.name: sha256(path) for path in sorted(Path(__file__).parent.glob("*.py"))}
    runtime = {"packages": {name: importlib.metadata.version(name) for name in
                            ("torch", "transformers", "chronos-forecasting", "numpy")},
               "input_sha256": sha256(config.inputs), "protocol_sha256": bundle.protocol_sha256,
               "base_weights_sha256": base_hash, "source_sha256": source_hashes,
               "cuda_available": True, "memory_fraction": 0.4, "seed": 712}
    (config.output / "runtime.json").write_text(json.dumps(runtime, indent=2), encoding="utf-8")
    pipe = Chronos2Pipeline.from_pretrained(
        config.chronos_checkpoint, device_map="cuda", local_files_only=True,
    )
    save_inference(pipe, config, bundle, "chronos_base_daily", cumulative=False)
    save_inference(pipe, config, bundle, "chronos_base_cumulative", cumulative=True)
    del pipe
    gc.collect()
    torch.cuda.empty_cache()
    inputs = [np.asarray(row.daily, dtype=np.float32) for row in bundle.training]
    input_hash = hashlib.sha256(b"".join(array.tobytes() for array in inputs)).hexdigest()
    for name, learning_rate in CONFIGS:
        torch.manual_seed(712)
        torch.cuda.reset_peak_memory_stats()
        start = time.perf_counter()
        pipe = Chronos2Pipeline.from_pretrained(
            config.chronos_checkpoint, device_map="cuda", local_files_only=True,
        )
        checkpoint = config.output / "checkpoints" / name
        tuned = pipe.fit(
            inputs, prediction_length=30, context_length=365, min_past=60, num_steps=128,
            batch_size=64, learning_rate=learning_rate, finetune_mode="full", output_dir=checkpoint,
            seed=712, disable_tqdm=True, report_to="none",
        )
        torch.cuda.synchronize()
        trained_hash = weight_hash(checkpoint / "finetuned-ckpt")
        record = {"model": name, "learning_rate": learning_rate, "steps": 128, "batch_size": 64,
                  "context_length": 365, "prediction_length": 30, "seed": 712,
                  "training_series": len(inputs), "training_end": str(bundle.training_end),
                  "training_input_sha256": input_hash, "base_weights_sha256": base_hash,
                  "trained_weights_sha256": trained_hash, "weights_changed": trained_hash != base_hash,
                  "seconds": time.perf_counter() - start,
                  "peak_reserved_gib": torch.cuda.max_memory_reserved() / 2**30}
        (config.output / f"{name}.training.json").write_text(json.dumps(record), encoding="utf-8")
        if trained_hash == base_hash:
            raise RuntimeError("Fine-tuning did not change checkpoint weights")
        save_inference(tuned, config, bundle, name, cumulative=False)
        del pipe, tuned
        gc.collect()
        torch.cuda.empty_cache()
    if source_hashes != {path.name: sha256(path) for path in sorted(Path(__file__).parent.glob("*.py"))}:
        raise RuntimeError("Worker source changed during execution")
    (config.output / "completed.json").write_text('{"completed":true}', encoding="utf-8")
    print("PUBLIC_BANK_GPU_COMPLETE", flush=True)


if __name__ == "__main__":
    run(RunConfig.model_validate_json(Path(sys.argv[1]).read_bytes()))
