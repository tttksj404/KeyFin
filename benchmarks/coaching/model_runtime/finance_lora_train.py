"""Train a synthetic-only LoRA candidate for bounded FinanceSelection JSON.

The adapter learns the selection contract only. It receives no customer
transactions, balances, forecast outcomes, or FDT numeric targets; deployed
financial facts remain the immutable catalog and FDT rules.
"""

# ruff: noqa: ANN401, PLC0415

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class TrainExample:
    """One locally generated chat training row with no user financial data."""

    case_id: str
    messages: tuple[dict[str, str], ...]


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_examples(path: Path, maximum: int, seed: int) -> tuple[TrainExample, ...]:
    if maximum < 1:
        raise ValueError("finance_lora_max_examples_invalid")
    rows: list[TrainExample] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        value = json.loads(line)
        case_id, messages = value.get("case_id"), value.get("messages")
        if not isinstance(case_id, str) or not isinstance(messages, list) or len(messages) != 3:
            raise ValueError("finance_lora_training_row_invalid")
        if not all(
            isinstance(message, dict)
            and isinstance(message.get("role"), str)
            and isinstance(message.get("content"), str)
            for message in messages
        ):
            raise ValueError("finance_lora_training_message_invalid")
        rows.append(TrainExample(case_id, tuple(messages)))
    if len({row.case_id for row in rows}) != len(rows):
        raise ValueError("finance_lora_training_case_duplicate")
    # A seed-derived deterministic order samples facts and boundaries across
    # the compositional generator rather than fitting only its initial aliases.
    rows.sort(key=lambda row: hashlib.sha256(f"{seed}:{row.case_id}".encode()).hexdigest())
    return tuple(rows[:maximum])


def _chat_ids(
    tokenizer: Any, messages: tuple[dict[str, str], ...], max_length: int,
) -> tuple[list[int], list[int]]:
    """Mask every system/user token; loss applies only to the JSON completion."""
    try:
        prefix = tokenizer.apply_chat_template(
            list(messages[:-1]), tokenize=True, add_generation_prompt=True, enable_thinking=False,
        )
        complete = tokenizer.apply_chat_template(
            list(messages), tokenize=True, add_generation_prompt=False, enable_thinking=False,
        )
    except TypeError:
        prefix = tokenizer.apply_chat_template(list(messages[:-1]), tokenize=True, add_generation_prompt=True)
        complete = tokenizer.apply_chat_template(list(messages), tokenize=True, add_generation_prompt=False)
    if complete[:len(prefix)] != prefix:
        raise ValueError("finance_lora_chat_template_prefix_changed")
    if len(complete) > max_length:
        # A training target cannot be preserved after truncation. The caller
        # must lower its evidence payload or choose a longer reviewed context.
        raise ValueError("finance_lora_context_limit")
    labels = [-100] * len(prefix) + complete[len(prefix):]
    if all(value == -100 for value in labels):
        raise ValueError("finance_lora_completion_missing")
    return complete, labels


def _batch(
    rows: tuple[TrainExample, ...], tokenizer: Any, max_length: int, device: Any,
) -> dict[str, Any]:
    import torch

    converted = [_chat_ids(tokenizer, row.messages, max_length) for row in rows]
    width = max(len(input_ids) for input_ids, _ in converted)
    input_ids = torch.full((len(converted), width), tokenizer.pad_token_id, dtype=torch.long, device=device)
    attention_mask = torch.zeros((len(converted), width), dtype=torch.long, device=device)
    labels = torch.full((len(converted), width), -100, dtype=torch.long, device=device)
    for index, (tokens, target) in enumerate(converted):
        start = width - len(tokens)
        input_ids[index, start:] = torch.tensor(tokens, dtype=torch.long, device=device)
        attention_mask[index, start:] = 1
        labels[index, start:] = torch.tensor(target, dtype=torch.long, device=device)
    return {"input_ids": input_ids, "attention_mask": attention_mask, "labels": labels}


def _adapter_digest(directory: Path) -> str:
    digest = hashlib.sha256()
    files = tuple(sorted(path for path in directory.rglob("*") if path.is_file()))
    if not files:
        raise ValueError("finance_lora_adapter_missing")
    for path in files:
        digest.update(path.relative_to(directory).as_posix().encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def train(  # noqa: PLR0913 - the command-line experiment contract stays explicit.
    *,
    data_path: Path,
    model_path: Path,
    adapter_path: Path,
    report_path: Path,
    max_examples: int,
    epochs: int,
    batch_size: int,
    grad_accumulation: int,
    max_length: int,
    learning_rate: float,
    seed: int,
    quantization: str,
) -> dict[str, object]:
    """Fit and save one adapter; caller evaluates it separately on a frozen manifest."""
    if min(epochs, batch_size, grad_accumulation, max_length) < 1 or learning_rate <= 0:
        raise ValueError("finance_lora_training_config_invalid")
    import torch
    from peft import LoraConfig, TaskType, get_peft_model, prepare_model_for_kbit_training
    from transformers import AutoModelForCausalLM, AutoTokenizer

    torch.manual_seed(seed)
    rows = _load_examples(data_path, max_examples, seed)
    tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True, padding_side="left")
    tokenizer.pad_token = tokenizer.eos_token
    if quantization == "bf16":
        model = AutoModelForCausalLM.from_pretrained(
            model_path, local_files_only=True, torch_dtype=torch.bfloat16, low_cpu_mem_usage=True,
        ).to("cuda")
    elif quantization == "bnb4":
        from transformers import BitsAndBytesConfig

        model = AutoModelForCausalLM.from_pretrained(
            model_path,
            local_files_only=True,
            low_cpu_mem_usage=True,
            device_map={"": 0},
            quantization_config=BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_use_double_quant=True,
                bnb_4bit_compute_dtype=torch.bfloat16,
            ),
        )
        model = prepare_model_for_kbit_training(model)
    else:
        raise ValueError("finance_lora_quantization_invalid")
    model.config.use_cache = False
    model = get_peft_model(
        model,
        LoraConfig(
            task_type=TaskType.CAUSAL_LM,
            r=16,
            lora_alpha=32,
            lora_dropout=0.05,
            target_modules=("q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"),
        ),
    )
    trainable = tuple(parameter for parameter in model.parameters() if parameter.requires_grad)
    if not trainable:
        raise ValueError("finance_lora_trainable_parameters_missing")
    optimizer = torch.optim.AdamW(trainable, lr=learning_rate, weight_decay=0.01)
    losses: list[float] = []
    steps = 0
    model.train()
    for _epoch in range(epochs):
        for offset in range(0, len(rows), batch_size):
            batch = _batch(rows[offset:offset + batch_size], tokenizer, max_length, model.device)
            with torch.autocast(device_type="cuda", dtype=torch.bfloat16):
                output = model(**batch)
                if output.loss is None or not torch.isfinite(output.loss):
                    raise ValueError("finance_lora_nonfinite_loss")
                loss = output.loss / grad_accumulation
            loss.backward()
            losses.append(float(loss.detach().float().cpu()) * grad_accumulation)
            if ((offset // batch_size) + 1) % grad_accumulation == 0 or offset + batch_size >= len(rows):
                torch.nn.utils.clip_grad_norm_(trainable, 1.0)
                optimizer.step()
                optimizer.zero_grad(set_to_none=True)
                steps += 1
    adapter_path.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(adapter_path, safe_serialization=True)
    report = {
        "schema": "keyfin-finance-lora-train-report/1",
        "training_input_sha256": _digest(data_path),
        "examples": len(rows),
        "epochs": epochs,
        "optimizer_steps": steps,
        "mean_loss": round(statistics.mean(losses), 6),
        "final_loss": round(losses[-1], 6),
        "adapter_sha256": _adapter_digest(adapter_path),
        "quantization": quantization,
        "scope": {
            "synthetic_only": True,
            "customer_data_included": False,
            "fdt_prediction_accuracy_measured": False,
            "deployment_promoted": False,
        },
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument("--data", type=Path, required=True)
    _ = parser.add_argument("--model-path", type=Path, required=True)
    _ = parser.add_argument("--adapter-path", type=Path, required=True)
    _ = parser.add_argument("--report", type=Path, required=True)
    _ = parser.add_argument("--max-examples", type=int, default=256)
    _ = parser.add_argument("--epochs", type=int, default=1)
    _ = parser.add_argument("--batch-size", type=int, default=1)
    _ = parser.add_argument("--grad-accumulation", type=int, default=4)
    _ = parser.add_argument("--max-length", type=int, default=4096)
    _ = parser.add_argument("--learning-rate", type=float, default=2e-4)
    _ = parser.add_argument("--seed", type=int, default=715)
    _ = parser.add_argument("--quantization", choices=("bf16", "bnb4"), default="bf16")
    options = parser.parse_args()
    report = train(
        data_path=options.data,
        model_path=options.model_path,
        adapter_path=options.adapter_path,
        report_path=options.report,
        max_examples=options.max_examples,
        epochs=options.epochs,
        batch_size=options.batch_size,
        grad_accumulation=options.grad_accumulation,
        max_length=options.max_length,
        learning_rate=options.learning_rate,
        seed=options.seed,
        quantization=options.quantization,
    )
    print(json.dumps({"examples": report["examples"], "optimizer_steps": report["optimizer_steps"]}))  # noqa: T201


if __name__ == "__main__":
    main()
