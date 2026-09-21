"""Continuous-scheduling vLLM candidate for the pinned worker contract.

The synchronous ``LLM.generate`` candidate remains separately available for a
paired comparison.  This module deliberately accepts one request at a time and
lets ``AsyncLLM`` schedule compatible work internally, so the HTTP worker does
not add another batch-completion barrier ahead of the engine.
"""

from __future__ import annotations

import hashlib
import inspect
import os
import time
from pathlib import Path
from typing import TYPE_CHECKING

from gpu_registry import ModelEntry, load_entry, validate_device, vllm_decoder_options
from transformers import AutoTokenizer, PreTrainedTokenizerBase

try:
    from vllm import SamplingParams
    from vllm.engine.arg_utils import AsyncEngineArgs
    from vllm.sampling_params import StructuredOutputsParams
    from vllm.v1.engine.async_llm import AsyncLLM
except ModuleNotFoundError as error:
    if not error.name.startswith("vllm"):
        raise
    raise RuntimeError("vllm_async_backend_dependency_missing") from None

if TYPE_CHECKING:
    from pydantic import JsonValue

RUNTIME_SOURCE = Path(__file__)


def load_model(tag: str) -> tuple[AsyncLLM, PreTrainedTokenizerBase, ModelEntry]:
    """Load one registered checkpoint into the engine that owns continuous batching."""
    validate_device(os.environ)
    entry = load_entry(Path(os.environ["COACH_GPU_MODEL_REGISTRY"]), tag)
    if hashlib.sha256((entry.path / "config.json").read_bytes()).hexdigest() != entry.config_sha256:
        raise RuntimeError("model_config_changed")
    tokenizer = AutoTokenizer.from_pretrained(
        entry.path, padding_side="left", fix_mistral_regex=True, local_files_only=True,
    )
    tokenizer.pad_token = tokenizer.eos_token
    engine = AsyncLLM.from_engine_args(AsyncEngineArgs(
        model=str(entry.path), tokenizer=str(entry.path), **vllm_decoder_options(entry),
    ))
    return engine, tokenizer, entry


def _sampling(
    max_tokens: int, seed: int | None, structured_json_schema: dict[str, JsonValue] | None,
) -> SamplingParams:
    """Build one request-local greedy sampling contract, including JSON grammar when requested."""
    arguments: dict[str, object] = {
        "temperature": 0,
        "top_p": 1,
        "max_tokens": max_tokens,
        "seed": 715 if seed is None else seed,
    }
    if structured_json_schema is not None:
        arguments["structured_outputs"] = StructuredOutputsParams(json=structured_json_schema)
    return SamplingParams(**arguments)


async def generate(  # noqa: PLR0913 - Keep the shared worker contract explicit.
    model: AsyncLLM,
    tokenizer: PreTrainedTokenizerBase,
    chat: list[dict[str, str]],
    max_tokens: int = 220,
    *,
    thinking: bool = False,
    seed: int | None = None,
    structured_json_schema: dict[str, JsonValue] | None = None,
    request_id: str,
) -> tuple[str, float, int, int]:
    """Await one final output while the engine interleaves it with other HTTP requests.

    The generator's cancellation cleanup explicitly asks the engine to abort an
    unfinished request.  It is intentionally best effort because vLLM versions
    expose either a synchronous or asynchronous abort method; the client request
    still receives its original cancellation if the cleanup itself is unavailable.
    """
    prompt = tokenizer.apply_chat_template(
        chat, tokenize=False, add_generation_prompt=True, enable_thinking=thinking,
    )
    token_ids = tokenizer.encode(prompt)
    final: object | None = None
    completed = False
    started = time.perf_counter()
    try:
        async for output in model.generate(
            request_id=request_id,
            prompt={"prompt_token_ids": token_ids},
            sampling_params=_sampling(max_tokens, seed, structured_json_schema),
        ):
            final = output
            if output.finished:
                completed = True
                break
    finally:
        if not completed:
            abort = getattr(model, "abort", None)
            if abort is not None:
                aborted = abort(request_id)
                if inspect.isawaitable(aborted):
                    await aborted
    elapsed = time.perf_counter() - started
    if final is None or not final.finished or len(final.outputs) != 1:
        raise RuntimeError("vllm_incomplete_generation")
    if list(final.prompt_token_ids) != token_ids:
        raise RuntimeError("vllm_prompt_token_mismatch")
    completion = final.outputs[0]
    return completion.text, elapsed, len(token_ids), len(completion.token_ids)


async def shutdown(model: AsyncLLM) -> None:
    """Release engine resources when the worker lifespan ends without assuming awaitability."""
    close = getattr(model, "shutdown", None)
    if close is not None:
        result = close()
        if inspect.isawaitable(result):
            await result
