"""The deployed deterministic decoders, independent of research directories."""

from __future__ import annotations

import hashlib
import os
import time
from importlib import import_module
from pathlib import Path
from typing import TYPE_CHECKING

import torch
from gpu_registry import ModelEntry, adapter_digest, load_entry, validate_device
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    PreTrainedModel,
    PreTrainedTokenizerBase,
    Qwen3_5ForConditionalGeneration,
)

if TYPE_CHECKING:
    from pydantic import JsonValue

# ``gpu_runtime`` records this file's digest so receipts identify the exact
# decoder implementation without exposing machine-specific settings.
RUNTIME_SOURCE = Path(__file__)


def load_verified_adapter(model: PreTrainedModel, entry: ModelEntry) -> PreTrainedModel:
    """Attach only the exact BF16 selector adapter registered for this base model.

    No adapter registration returns the untouched base model. Any missing runtime
    dependency, byte mismatch, or unsupported registry pair stops startup instead
    of silently answering with a lower-quality base checkpoint.
    """
    if entry.adapter_path is None:
        return model
    if entry.adapter_sha256 is None:
        raise RuntimeError("adapter_fields_must_be_paired")
    if adapter_digest(entry.adapter_path) != entry.adapter_sha256:
        raise RuntimeError("model_adapter_changed")
    try:
        peft = import_module("peft")
    except ModuleNotFoundError as error:
        if error.name != "peft":
            raise
        raise RuntimeError("adapter_runtime_dependency_missing") from None
    peft_model = peft.PeftModel
    return peft_model.from_pretrained(
        model, entry.adapter_path, local_files_only=True, is_trainable=False,
    )


def load_model(tag: str) -> tuple[PreTrainedModel, PreTrainedTokenizerBase, ModelEntry]:
    validate_device(os.environ)
    entry = load_entry(Path(os.environ["COACH_GPU_MODEL_REGISTRY"]), tag)
    if hashlib.sha256((entry.path / "config.json").read_bytes()).hexdigest() != entry.config_sha256:
        raise RuntimeError("model_config_changed")
    tokenizer = AutoTokenizer.from_pretrained(
        entry.path, padding_side="left", fix_mistral_regex=True, local_files_only=True,
    )
    tokenizer.pad_token = tokenizer.eos_token
    match entry.tag, entry.quantization:
        case "base8", "bf16":
            model = AutoModelForCausalLM.from_pretrained(
                entry.path, dtype=torch.bfloat16, device_map={"": 0},
                attn_implementation="sdpa", local_files_only=True,
            )
        case "latest27_nf4", "nf4":
            model = Qwen3_5ForConditionalGeneration.from_pretrained(
                entry.path, dtype=torch.bfloat16, device_map={"": 0},
                attn_implementation="sdpa", local_files_only=True,
                quantization_config=BitsAndBytesConfig(
                    load_in_4bit=True, bnb_4bit_quant_type="nf4",
                    bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True,
                ),
            )
        case _:
            raise ValueError("unsupported_model_quantization_pair")
    return load_verified_adapter(model, entry).eval(), tokenizer, entry


def generate(  # noqa: PLR0913 - The shared decoder boundary keeps all generation controls explicit.
    model: PreTrainedModel, tokenizer: PreTrainedTokenizerBase,
    chats: list[list[dict[str, str]]], max_tokens: int = 220, *, thinking: bool = False,
    seed: int | None = None, structured_json_schema: dict[str, JsonValue] | None = None,
) -> tuple[list[str], float, list[int], list[int]]:
    # Greedy Transformer decoding never samples, but the argument keeps both
    # decoder implementations behind the same validated worker interface.
    del seed, structured_json_schema
    prompts = [tokenizer.apply_chat_template(
        chat, tokenize=False, add_generation_prompt=True, enable_thinking=thinking,
    ) for chat in chats]
    batch = tokenizer(prompts, return_tensors="pt", padding=True).to("cuda:0")
    lengths = batch["attention_mask"].sum(dim=1).tolist()
    torch.cuda.synchronize()
    started = time.perf_counter()
    with torch.inference_mode():
        output = model.generate(
            **batch, max_new_tokens=max_tokens, do_sample=False,
            pad_token_id=tokenizer.pad_token_id, use_cache=True,
        )
    torch.cuda.synchronize()
    elapsed = time.perf_counter() - started
    generated = output[:, batch["input_ids"].shape[1]:]
    texts = tokenizer.batch_decode(generated, skip_special_tokens=True)
    counts = (generated != tokenizer.pad_token_id).sum(dim=1).tolist()
    return texts, elapsed, lengths, counts
