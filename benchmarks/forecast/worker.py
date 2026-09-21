# /// script
# requires-python = ">=3.11"
# dependencies = ["chronos-forecasting==2.3.1", "timesfm==2.0.2", "torch==2.7.1", "pydantic", "numpy"]
# ///
# How to run: python -m benchmarks.forecast.worker /private/run-config.json
# ruff: noqa: T201
"""Real accelerator prediction and fold-specific training over observed-only arrays."""

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
import timesfm
import torch
from chronos import Chronos2Pipeline
from pydantic import TypeAdapter
from scripts.gpu_registry import validate_device

from .contracts import Forecast, ForecastCase, Frozen, InputBundle
from .neural_io import contexts, endpoint, training_inputs


class RunConfig(Frozen):
    inputs: Path
    output: Path
    chronos_checkpoint: Path
    timesfm_checkpoint: Path
    previous_checkpoint: Path


CONFIGS: Final = (("chronos_ft64", 64, 1e-6), ("chronos_ft128", 128, 3e-6))


def weight_hash(path: Path) -> str:
    digest = hashlib.sha256()
    files = sorted(path.glob("*.safetensors"))
    if not files:
        msg = "Checkpoint has no safetensors weights"
        raise ValueError(msg)
    for file in files:
        digest.update(file.name.encode())
        with file.open("rb") as stream:
            while chunk := stream.read(8 * 1024 * 1024):
                digest.update(chunk)
    return digest.hexdigest()


def save_predictions(config: RunConfig, rows: list[Forecast], name: str) -> None:
    _ = (config.output / f"{name}.predictions.json").write_bytes(TypeAdapter(list[Forecast]).dump_json(rows))


def chronos_predictions(
    pipeline: Chronos2Pipeline, cases: tuple[ForecastCase, ...], identity: tuple[str, str, bool],
) -> list[Forecast]:
    name, fold, cumulative = identity
    quantiles, means = pipeline.predict_quantiles(
        contexts(cases, cumulative=cumulative), prediction_length=30, quantile_levels=[0.1, 0.5, 0.9],
        context_length=128, batch_size=64, cross_learning=False,
    )
    rows = []
    for case, q, m in zip(cases, quantiles, means, strict=True):
        if cumulative:
            values = np.asarray(q.detach().float().cpu().numpy(), dtype=np.float64).reshape(30, 3)
            rows.append(endpoint(case, values[case.horizon-1], name, fold))
        else:
            daily = np.asarray(m.detach().float().cpu().numpy(), dtype=np.float64).reshape(30)
            point = float(np.maximum(daily[:case.horizon], 0).sum())
            rows.append(Forecast(case_id=case.case_id, model=name, fold=fold, point=point))
    return rows


def run_chronos(config: RunConfig, bundle: InputBundle) -> None:
    for family, checkpoint in (("chronos_base", config.chronos_checkpoint),
                               ("chronos_previous", config.previous_checkpoint)):
        start = time.perf_counter()
        pipe = Chronos2Pipeline.from_pretrained(checkpoint, device_map="cuda", local_files_only=True)
        for suffix, cumulative in (("daily", False), ("cumulative", True)):
            name = f"{family}_{suffix}"
            torch.cuda.synchronize()
            inference_start = time.perf_counter()
            rows = chronos_predictions(pipe, bundle.cases, (name, "common", cumulative))
            torch.cuda.synchronize()
            record = {"model": name, "cases": len(rows),
                      "inference_seconds": time.perf_counter()-inference_start,
                      "allocated_gib": torch.cuda.memory_allocated()/2**30}
            _ = (config.output / f"{name}.inference.json").write_text(
                json.dumps(record), encoding="utf-8",
            )
            save_predictions(config, rows, name)
            print(json.dumps({"completed": name, "cases": len(rows),
                              "seconds_from_load": time.perf_counter()-start}), flush=True)
        del pipe
        gc.collect()
        torch.cuda.empty_cache()


def run_timesfm(config: RunConfig, bundle: InputBundle) -> None:
    start = time.perf_counter()
    torch.cuda.reset_peak_memory_stats()
    model = timesfm.TimesFM_2p5_200M_torch.from_pretrained(config.timesfm_checkpoint)
    model.compile(timesfm.ForecastConfig(
        max_context=128, max_horizon=128, normalize_inputs=True, per_core_batch_size=64,
        use_continuous_quantile_head=True, force_flip_invariance=True, infer_is_positive=True,
        fix_quantile_crossing=True,
    ))
    torch.cuda.synchronize()
    inference_start = time.perf_counter()
    _, quantiles = model.forecast(horizon=30, inputs=contexts(bundle.cases, cumulative=True))
    torch.cuda.synchronize()
    record = {"model": "timesfm_cumulative", "cases": len(bundle.cases),
              "inference_seconds": time.perf_counter()-inference_start,
              "peak_allocated_gib": torch.cuda.max_memory_allocated()/2**30}
    if record["peak_allocated_gib"] <= 0:
        msg = "TimesFM did not allocate accelerator memory"
        raise RuntimeError(msg)
    _ = (config.output / "timesfm_cumulative.inference.json").write_text(
        json.dumps(record), encoding="utf-8",
    )
    array = np.asarray(quantiles, dtype=np.float64)
    rows = [endpoint(case, array[i, case.horizon-1, [1, 5, 9]], "timesfm_cumulative", "common")
            for i, case in enumerate(bundle.cases)]
    save_predictions(config, rows, "timesfm_cumulative")
    print(json.dumps({"completed": "timesfm_cumulative", "cases": len(rows),
                      "seconds_from_load": time.perf_counter()-start}), flush=True)
    del model
    gc.collect()
    torch.cuda.empty_cache()


def run_training(config: RunConfig, bundle: InputBundle) -> None:
    base_hash = weight_hash(config.chronos_checkpoint)
    for excluded in sorted({row.user for row in bundle.training}):
        inputs = training_inputs(bundle.training, excluded)
        cases = tuple(case for case in bundle.cases if (
            (case.split == "development" and case.user != excluded)
            or (case.split == "evaluation" and case.user == excluded)
        ))
        input_hash = hashlib.sha256(b"".join(value.tobytes() for value in inputs)).hexdigest()
        for name, steps, learning_rate in CONFIGS:
            torch.manual_seed(712)
            torch.cuda.reset_peak_memory_stats()
            start = time.perf_counter()
            pipe = Chronos2Pipeline.from_pretrained(
                config.chronos_checkpoint, device_map="cuda", local_files_only=True,
            )
            directory = config.output / "checkpoints" / excluded / name
            tuned = pipe.fit(inputs, prediction_length=7, context_length=64, min_past=7,
                             num_steps=steps, batch_size=32, learning_rate=learning_rate,
                             finetune_mode="full",
                             output_dir=directory, seed=712, disable_tqdm=True, report_to="none")
            torch.cuda.synchronize()
            trained_hash = weight_hash(directory / "finetuned-ckpt")
            record = {"model": name, "excluded_user": excluded, "steps": steps,
                      "learning_rate": learning_rate, "batch_size": 32, "seed": 712,
                      "training_series": len(inputs), "last_training_date": str(bundle.training_end),
                      "training_input_sha256": input_hash, "base_weights_sha256": base_hash,
                      "trained_weights_sha256": trained_hash, "weights_changed": trained_hash != base_hash,
                      "training_seconds": time.perf_counter()-start,
                      "peak_reserved_gib": torch.cuda.max_memory_reserved()/2**30}
            _ = (config.output / f"{name}.{excluded}.training.json").write_text(
                json.dumps(record), encoding="utf-8",
            )
            predictions = chronos_predictions(tuned, cases, (name, excluded, True))
            save_predictions(config, predictions, f"{name}.{excluded}")
            print(json.dumps({"completed": name, "fold": excluded,
                              "training_seconds": record["training_seconds"]}), flush=True)
            del pipe, tuned
            gc.collect()
            torch.cuda.empty_cache()


def main() -> None:
    validate_device(os.environ)
    config = RunConfig.model_validate_json(Path(sys.argv[1]).read_bytes())
    config.output.mkdir(exist_ok=False)
    bundle = InputBundle.model_validate_json(config.inputs.read_bytes())
    if not torch.cuda.is_available():
        msg = "This protocol requires accelerator execution"
        raise RuntimeError(msg)
    torch.set_num_threads(8)
    torch.cuda.set_per_process_memory_fraction(0.25)
    packages = {name: importlib.metadata.version(name) for name in
                ("torch", "transformers", "chronos-forecasting", "timesfm", "numpy")}
    record = {"packages": packages, "cuda_available": torch.cuda.is_available(),
              "input_sha256": hashlib.sha256(config.inputs.read_bytes()).hexdigest(),
              "source_sha256": {file.name: hashlib.sha256(file.read_bytes()).hexdigest()
                                for file in sorted(Path(__file__).parent.glob("*.py"))},
              "checkpoints": {name: weight_hash(path) for name, path in (
                  ("chronos_base", config.chronos_checkpoint), ("timesfm", config.timesfm_checkpoint),
                  ("chronos_previous", config.previous_checkpoint))}}
    _ = (config.output / "runtime.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    run_chronos(config, bundle)
    run_timesfm(config, bundle)
    run_training(config, bundle)
    after_hash = {file.name: hashlib.sha256(file.read_bytes()).hexdigest()
                  for file in sorted(Path(__file__).parent.glob("*.py"))}
    if after_hash != record["source_sha256"]:
        msg = "Frozen worker source changed during execution"
        raise RuntimeError(msg)
    _ = (config.output / "completed.json").write_text('{"completed":true}', encoding="utf-8")
    print("R7_NEURAL_COMPLETE", flush=True)


if __name__ == "__main__":
    main()
