# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
# How to run: imported by gpu_worker.py in the pinned existing GPU environment.
"""Token-budget enforcement over the explicitly configured model checkpoint."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
from copy import deepcopy
from threading import RLock
from typing import TYPE_CHECKING, Final

from fastapi import HTTPException
from gpu_registry import execution_backend

# Read once during worker import so an admitted request cannot switch decoder.
_EXECUTION_BACKEND: Final = execution_backend(os.environ)
if _EXECUTION_BACKEND == "vllm":
    from gpu_vllm_models import RUNTIME_SOURCE, generate, load_model
elif _EXECUTION_BACKEND == "vllm_async":
    from gpu_vllm_async_models import RUNTIME_SOURCE
    from gpu_vllm_async_models import generate as async_generate
    from gpu_vllm_async_models import load_model as load_async_model
    from gpu_vllm_async_models import shutdown as shutdown_async_model
else:
    from gpu_models import RUNTIME_SOURCE, generate, load_model

if TYPE_CHECKING:
    from .gpu_contracts import CompletionRequest, Generated, Metadata, PromptCount
    from .gpu_worker import generation_messages
else:  # noqa: PLR5501 - Keep the TYPE_CHECKING runtime boundary for basedpyright.
    if __package__:
        from .gpu_contracts import (
            CompletionRequest,
            Generated,
            Metadata,
            PromptCount,
            response_format_fingerprint,
            structured_json_schema,
        )
        from .gpu_worker import generation_messages
    else:
        from gpu_contracts import (
            CompletionRequest,
            Generated,
            Metadata,
            PromptCount,
            response_format_fingerprint,
            structured_json_schema,
        )
        from gpu_worker import generation_messages


class PinnedBackend:
    """Own the single loaded model and tokenizer for this worker process."""

    def __init__(self, tag: str) -> None:
        if _EXECUTION_BACKEND == "vllm_async":
            raise RuntimeError("async_vllm_requires_async_backend")
        # FP8 checkpoints load only under vLLM; the transformers path (gpu_models)
        # rejects the fp8 quantization pair, so gate prod27_fp8 to the vllm backend.
        allowed = {"base8", "latest27_nf4"}
        if _EXECUTION_BACKEND == "vllm":
            allowed = allowed | {"prod27_fp8"}
        if tag not in allowed:
            raise ValueError("unsupported_model_tag")
        self.model, self.tokenizer, entry = load_model(tag)
        # Rust tokenizers mutate padding/truncation configuration during batch encoding.
        # CPU preflight uses its own clone so it can run while the GPU is generating.
        self.count_tokenizer = deepcopy(self.tokenizer)
        self.count_lock = RLock()
        self.metadata = Metadata(
            model=tag,
            model_id=entry.model_id,
            revision=entry.revision,
            config_sha256=entry.config_sha256,
            quantization=entry.quantization,
            adapter_sha256=entry.adapter_sha256,
            runtime_sha256=hashlib.sha256(RUNTIME_SOURCE.read_bytes()).hexdigest(),
            grammar_enforced=_EXECUTION_BACKEND == "vllm",
            response_format_handling=(
                "vllm_json_schema" if _EXECUTION_BACKEND == "vllm" else "schema_in_prompt"
            ),
        )

    def measure(self, request: CompletionRequest) -> PromptCount:
        """생성과 같은 스키마·chat template·특수 토큰으로 센다.

        모델 ID·revision·token_ids로 지문을 만들어 사전 검사와 생성 사이의 입력
        변경을 감지한다. 단순 JSON 글자 수나 본문 해시로 이 지문을 대신하지 않는다.
        """
        chat = [
            {"role": message.role, "content": message.content} for message in generation_messages(request)
        ]
        with self.count_lock:
            prompt = self.count_tokenizer.apply_chat_template(
                chat, tokenize=False, add_generation_prompt=True, enable_thinking=False,
            )
            token_ids = self.count_tokenizer.encode(prompt)
        identity = json.dumps([self.metadata.model_id, self.metadata.revision, token_ids])
        return PromptCount(
            prompt_tokens=len(token_ids), prompt_sha256=hashlib.sha256(identity.encode()).hexdigest(),
        )

    def complete(self, request: CompletionRequest) -> Generated:
        """Single-request callers use the same batch implementation and guards."""
        return self.complete_batch([request])[0]

    def complete_batch(self, requests: list[CompletionRequest]) -> list[Generated]:
        """각 요청의 토큰·출력·시드 상한을 유지하며 한 번의 generate로 독립 답변을 만든다."""
        if (
            not requests
            or len({request.max_tokens for request in requests}) != 1
            or len({request.seed for request in requests}) != 1
            or (
                _EXECUTION_BACKEND == "vllm"
                and len({response_format_fingerprint(request) for request in requests}) != 1
            )
        ):
            raise ValueError("incompatible_generation_batch")
        counts = [self.measure(request) for request in requests]
        if any(count.prompt_tokens > self.metadata.max_input_tokens for count in counts):
            raise HTTPException(status_code=413, detail="input_token_limit")
        chats = [[{"role": message.role, "content": message.content}
                  for message in generation_messages(request)] for request in requests]
        schema = structured_json_schema(requests[0]) if _EXECUTION_BACKEND == "vllm" else None
        texts, seconds, input_tokens, output_tokens = generate(
            self.model,
            self.tokenizer,
            chats,
            max_tokens=requests[0].max_tokens,
            thinking=False,
            seed=requests[0].seed,
            structured_json_schema=schema,
        )
        if input_tokens != [count.prompt_tokens for count in counts]:
            raise HTTPException(status_code=500, detail="tokenizer_count_mismatch")
        return [Generated(text=text, prompt_tokens=inputs, completion_tokens=outputs, seconds=seconds)
                for text, inputs, outputs in zip(texts, input_tokens, output_tokens, strict=True)]


class AsyncPinnedBackend:
    """One-request bridge to vLLM's native continuous scheduler.

    It intentionally shares token preflight, metadata, and output contracts with
    ``PinnedBackend``.  The only changed dimension is request scheduling, which
    lets a measured candidate isolate concurrency latency from model quality.
    """

    def __init__(self, tag: str) -> None:
        if _EXECUTION_BACKEND != "vllm_async":
            raise RuntimeError("async_vllm_backend_not_selected")
        # vLLM async serves FP8 (prod27_fp8) alongside the bf16/nf4 checkpoints.
        if tag not in {"base8", "latest27_nf4", "prod27_fp8"}:
            raise ValueError("unsupported_model_tag")
        self.model, self.tokenizer, entry = load_async_model(tag)
        self.count_tokenizer = deepcopy(self.tokenizer)
        self.count_lock = RLock()
        self.metadata = Metadata(
            model=tag,
            model_id=entry.model_id,
            revision=entry.revision,
            config_sha256=entry.config_sha256,
            quantization=entry.quantization,
            adapter_sha256=entry.adapter_sha256,
            runtime_sha256=hashlib.sha256(RUNTIME_SOURCE.read_bytes()).hexdigest(),
            grammar_enforced=True,
            response_format_handling="vllm_json_schema",
        )

    def measure(self, request: CompletionRequest) -> PromptCount:
        """Count the exact same chat template used by asynchronous generation."""
        chat = [
            {"role": message.role, "content": message.content} for message in generation_messages(request)
        ]
        with self.count_lock:
            prompt = self.count_tokenizer.apply_chat_template(
                chat, tokenize=False, add_generation_prompt=True, enable_thinking=False,
            )
            token_ids = self.count_tokenizer.encode(prompt)
        identity = json.dumps([self.metadata.model_id, self.metadata.revision, token_ids])
        return PromptCount(
            prompt_tokens=len(token_ids), prompt_sha256=hashlib.sha256(identity.encode()).hexdigest(),
        )

    async def complete_async(self, request: CompletionRequest) -> Generated:
        """Generate one response without rebuilding an external completion batch."""
        count = self.measure(request)
        if count.prompt_tokens > self.metadata.max_input_tokens:
            raise HTTPException(status_code=413, detail="input_token_limit")
        chat = [
            {"role": message.role, "content": message.content} for message in generation_messages(request)
        ]
        text, seconds, input_tokens, output_tokens = await async_generate(
            self.model,
            self.tokenizer,
            chat,
            max_tokens=request.max_tokens,
            thinking=False,
            seed=request.seed,
            structured_json_schema=structured_json_schema(request),
            request_id="coach-" + secrets.token_hex(12),
        )
        if input_tokens != count.prompt_tokens:
            raise HTTPException(status_code=500, detail="tokenizer_count_mismatch")
        return Generated(
            text=text,
            prompt_tokens=input_tokens,
            completion_tokens=output_tokens,
            seconds=seconds,
        )

    async def close(self) -> None:
        """Release the native engine only after the FastAPI lifespan has ended."""
        await shutdown_async_model(self.model)
