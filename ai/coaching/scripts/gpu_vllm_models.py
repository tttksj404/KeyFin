"""Optional vLLM decoder for the same pinned model and token contract.

This module is imported only when ``COACH_GPU_EXECUTION_BACKEND=vllm`` is set.
The default Transformer decoder remains unchanged until a paired quality and
concurrency evaluation promotes a different deployment setting.
"""

from __future__ import annotations

import hashlib
import os
import time
from pathlib import Path
from typing import TYPE_CHECKING

from gpu_registry import ModelEntry, load_entry, validate_device, vllm_decoder_options
from transformers import AutoTokenizer, PreTrainedTokenizerBase

try:
    from vllm import LLM, SamplingParams
    from vllm.sampling_params import StructuredOutputsParams
except ModuleNotFoundError as error:
    if error.name != "vllm":
        raise
    raise RuntimeError("vllm_backend_dependency_missing") from None

if TYPE_CHECKING:
    from pydantic import JsonValue

RUNTIME_SOURCE = Path(__file__)


def load_model(tag: str) -> tuple[LLM, PreTrainedTokenizerBase, ModelEntry]:
    """Load one registered candidate with its explicit vLLM weight policy."""
    validate_device(os.environ)
    entry = load_entry(Path(os.environ["COACH_GPU_MODEL_REGISTRY"]), tag)
    if hashlib.sha256((entry.path / "config.json").read_bytes()).hexdigest() != entry.config_sha256:
        raise RuntimeError("model_config_changed")

    tokenizer = AutoTokenizer.from_pretrained(
        entry.path, padding_side="left", fix_mistral_regex=True, local_files_only=True,
    )
    tokenizer.pad_token = tokenizer.eos_token
    # Keep one explicitly authorized accelerator, bounded sequence count and the
    # same greedy output contract across candidates.  ``vllm_decoder_options``
    # is unit-tested without importing vLLM, so a missing local runtime cannot
    # weaken the tag/quantization boundary.
    model = LLM(
        model=str(entry.path),
        tokenizer=str(entry.path),
        **vllm_decoder_options(entry),
    )
    return model, tokenizer, entry


def generate(  # noqa: PLR0913 - The shared decoder boundary keeps all generation controls explicit.
    model: LLM,
    tokenizer: PreTrainedTokenizerBase,
    chats: list[list[dict[str, str]]],
    max_tokens: int = 220,
    *,
    thinking: bool = False,
    seed: int | None = None,
    structured_json_schema: dict[str, JsonValue] | None = None,
) -> tuple[list[str], float, list[int], list[int]]:
    """Generate a batch using the identical chat template and greedy sampling contract."""
    prompts = [
        tokenizer.apply_chat_template(
            chat, tokenize=False, add_generation_prompt=True, enable_thinking=thinking,
        )
        for chat in chats
    ]
    token_ids = [tokenizer.encode(prompt) for prompt in prompts]
    # Preserve the reviewed default. An explicit experiment seed is supplied by
    # the worker only after its request contract and batch boundary validate it.
    sampling_seed = 715 if seed is None else seed
    if structured_json_schema is None:
        sampling = SamplingParams(temperature=0, top_p=1, max_tokens=max_tokens, seed=sampling_seed)
    else:
        # The prompt still names the schema for semantic guidance. This decoder
        # constraint additionally prevents invalid JSON from consuming a retry.
        sampling = SamplingParams(
            temperature=0,
            top_p=1,
            max_tokens=max_tokens,
            seed=sampling_seed,
            structured_outputs=StructuredOutputsParams(json=structured_json_schema),
        )
    started = time.perf_counter()
    outputs = model.generate(
        [{"prompt_token_ids": row} for row in token_ids],
        sampling,
        use_tqdm=False,
    )
    elapsed = time.perf_counter() - started
    if len(outputs) != len(token_ids):
        raise RuntimeError("vllm_output_count_mismatch")
    if [list(row.prompt_token_ids) for row in outputs] != token_ids:
        raise RuntimeError("vllm_prompt_token_mismatch")
    if not all(row.finished and len(row.outputs) == 1 for row in outputs):
        raise RuntimeError("vllm_incomplete_generation")
    return (
        [row.outputs[0].text for row in outputs],
        elapsed,
        [len(row) for row in token_ids],
        [len(row.outputs[0].token_ids) for row in outputs],
    )
