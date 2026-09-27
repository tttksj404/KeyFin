# ruff: noqa: T201
"""Train fresh aggregate-target Chronos models without access to future target files."""

from __future__ import annotations

import gc
import json
import os
import random
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, TypedDict, Unpack

import numpy as np
import torch
from chronos import Chronos2Pipeline
from pydantic import TypeAdapter
from scripts.gpu_registry import validate_device
from transformers import TrainerCallback

from .arithmetic import rolling_sums
from .contracts import Case, Inputs, Prediction
from .worker_support import (
    BASE_NAME,
    SEED,
    TRAINING,
    QuantileAudit,
    RunConfig,
    TrainingSpec,
    UpdateAudit,
    array_hash,
    finish_run,
    terminal_prediction,
    weight_hash,
    write_runtime,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from torch.optim.lr_scheduler import LRScheduler
    from torch.utils.data import DataLoader
    from transformers import PreTrainedTokenizerBase, TrainerControl, TrainerState, TrainingArguments


class SkipAwareOptimizer(Protocol):
    @property
    def step_was_skipped(self) -> bool: ...


class CallbackInputs(TypedDict, total=False):
    model: torch.nn.Module
    processing_class: PreTrainedTokenizerBase | None
    optimizer: SkipAwareOptimizer
    lr_scheduler: LRScheduler
    train_dataloader: DataLoader[Mapping[str, torch.Tensor]]
    eval_dataloader: DataLoader[Mapping[str, torch.Tensor]] | None


class OptimizerObserver(TrainerCallback):
    """Observe post-optimizer events and post-increment TrainerState independently."""

    def __init__(self, path: Path, requested: int) -> None:
        self.path = path
        self.requested = requested
        self.audit = UpdateAudit()

    def on_optimizer_step(
        self,
        _args: TrainingArguments,
        _state: TrainerState,
        _control: TrainerControl,
        **inputs: Unpack[CallbackInputs],
    ) -> None:
        self.audit.optimizer_step(skipped=inputs["optimizer"].step_was_skipped)

    def on_step_end(
        self,
        _args: TrainingArguments,
        state: TrainerState,
        _control: TrainerControl,
        **_inputs: Unpack[CallbackInputs],
    ) -> None:
        self.audit.step_end(state.global_step)
        # A progress receipt survives interruption and never substitutes requested steps for observations.
        self.path.write_bytes(self.audit.snapshot(self.requested).model_dump_json().encode())


def release() -> None:
    gc.collect()
    torch.cuda.empty_cache()


def reset() -> None:
    torch.manual_seed(SEED)
    np.random.seed(SEED)  # noqa: NPY002 -- pin the installed training library RNG.
    random.seed(SEED)
    torch.cuda.synchronize()
    torch.cuda.reset_peak_memory_stats()


def infer(
    pipe: Chronos2Pipeline, config: RunConfig, cases: tuple[Case, ...], name: str, horizon: int
) -> list[Prediction]:
    contexts = [np.asarray(rolling_sums(case.history, horizon), dtype=np.float32) for case in cases]
    torch.cuda.synchronize()
    torch.cuda.reset_peak_memory_stats()
    started = time.perf_counter()
    quantiles, _means = pipe.predict_quantiles(
        contexts,
        prediction_length=horizon,
        quantile_levels=[0.1, 0.5, 0.9],
        context_length=365,
        batch_size=64,
        cross_learning=False,
    )
    audit = QuantileAudit()
    rows = [
        terminal_prediction(
            case.case_id,
            name,
            np.asarray(quantile.detach().float().cpu().numpy(), dtype=np.float64),
            horizon,
            audit,
        )
        for case, quantile in zip(cases, quantiles, strict=True)
    ]
    torch.cuda.synchronize()
    filename = f"{name}.h{horizon}"
    (config.output / "by_horizon" / f"{filename}.predictions.json").write_bytes(
        TypeAdapter(list[Prediction]).dump_json(rows)
    )
    record = {
        "model": name,
        "horizon": horizon,
        "cases": len(rows),
        "seconds": time.perf_counter() - started,
        "context_input_sha256": array_hash(contexts),
        "peak_allocated_gib": torch.cuda.max_memory_allocated() / 2**30,
        "peak_reserved_gib": torch.cuda.max_memory_reserved() / 2**30,
        "batch_size": 64,
        "context_length": 365,
        "cross_learning": False,
        **audit.values(),
    }
    (config.output / f"{filename}.inference.json").write_text(json.dumps(record), encoding="utf-8")
    print(f"AGGREGATE_INFERRED model={name} horizon={horizon} cases={len(rows)}", flush=True)
    return rows


def train(
    config: RunConfig, bundle: Inputs, spec: TrainingSpec, horizon: int, base_hash: str
) -> Chronos2Pipeline:
    reset()
    started = time.perf_counter()
    pipe = Chronos2Pipeline.from_pretrained(
        config.chronos_checkpoint, device_map="cuda", local_files_only=True
    )
    load_seconds = time.perf_counter() - started
    arrays = [np.asarray(rolling_sums(row.daily, horizon), dtype=np.float32) for row in bundle.training]
    name = f"{spec.name}.h{horizon}"
    checkpoint = config.output / "checkpoints" / name
    observer = OptimizerObserver(config.output / f"{name}.updates.json", spec.steps)
    started = time.perf_counter()
    tuned = pipe.fit(
        arrays,
        prediction_length=horizon,
        context_length=365,
        min_past=60,
        num_steps=spec.steps,
        batch_size=64,
        learning_rate=spec.learning_rate,
        finetune_mode="full",
        output_dir=checkpoint,
        callbacks=[observer],
        seed=SEED,
        data_seed=SEED,
        disable_tqdm=True,
        report_to="none",
        remove_printer_callback=True,
    )
    torch.cuda.synchronize()
    seconds = time.perf_counter() - started
    trained_hash = weight_hash(checkpoint / "finetuned-ckpt")
    evidence = observer.audit.snapshot(spec.steps)
    record = {
        "model": spec.name,
        "horizon": horizon,
        "learning_rate": spec.learning_rate,
        "num_steps_requested": spec.steps,
        "optimizer_evidence": json.loads(evidence.model_dump_json()),
        "batch_size": 64,
        "context_length": 365,
        "min_past": 60,
        "seed": SEED,
        "training_series": len(arrays),
        "training_end": str(bundle.training_end),
        "training_input_sha256": array_hash(arrays),
        "base_weights_sha256": base_hash,
        "trained_weights_sha256": trained_hash,
        "weights_changed": trained_hash != base_hash,
        "load_seconds": load_seconds,
        "seconds": seconds,
        "peak_allocated_gib": torch.cuda.max_memory_allocated() / 2**30,
        "peak_reserved_gib": torch.cuda.max_memory_reserved() / 2**30,
    }
    (config.output / f"{name}.training.json").write_text(json.dumps(record), encoding="utf-8")
    _ = observer.audit.finish(spec.steps)
    if trained_hash == base_hash:
        raise RuntimeError("Fine-tuning did not change checkpoint weights")
    print(f"AGGREGATE_TRAINED model={spec.name} horizon={horizon}", flush=True)
    del pipe
    release()
    return tuned


def run(config: RunConfig) -> None:
    validate_device(os.environ)
    if not torch.cuda.is_available() or torch.cuda.device_count() != 1:
        raise RuntimeError("Exactly one visible accelerator is required")
    config.output.mkdir(parents=True, exist_ok=False)
    (config.output / "by_horizon").mkdir()
    bundle = Inputs.model_validate_json(config.inputs.read_bytes())
    torch.set_num_threads(8)
    torch.cuda.set_per_process_memory_fraction(0.4)
    runtime = write_runtime(config, bundle)
    base_hash = runtime.base_weights_sha256
    predictions: dict[str, list[Prediction]] = {name: [] for name in runtime.candidates}
    for horizon in (7, 30):
        cases = tuple(case for case in bundle.cases if case.horizon == horizon)
        reset()
        pipe = Chronos2Pipeline.from_pretrained(
            config.chronos_checkpoint, device_map="cuda", local_files_only=True
        )
        predictions[BASE_NAME].extend(infer(pipe, config, cases, BASE_NAME, horizon))
        del pipe
        release()
        for spec in TRAINING:
            pipe = train(config, bundle, spec, horizon, base_hash)
            predictions[spec.name].extend(infer(pipe, config, cases, spec.name, horizon))
            del pipe
            release()
    for name, rows in predictions.items():
        if len(rows) != len(bundle.cases) or len({row.case_id for row in rows}) != len(bundle.cases):
            raise ValueError("Candidate does not cover every input case exactly once")
        (config.output / f"{name}.predictions.json").write_bytes(
            TypeAdapter(list[Prediction]).dump_json(rows)
        )
    finish_run(config, runtime, len(bundle.cases))
    print("AGGREGATE_GPU_COMPLETE", flush=True)


if __name__ == "__main__":
    run(RunConfig.model_validate_json(Path(sys.argv[1]).read_bytes()))
