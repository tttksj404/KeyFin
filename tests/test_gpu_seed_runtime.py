"""Regression coverage for the optional seed from worker contract through the decoder call."""
# ruff: noqa: INP001

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Literal

import pytest

from scripts import gpu_contracts

ROOT = Path(__file__).resolve().parents[1]


def load_runtime_with_fake_decoder(
    monkeypatch: pytest.MonkeyPatch,
    calls: list[dict[str, object]],
    *,
    backend: Literal["transformers", "vllm"] = "transformers",
) -> ModuleType:
    """Load the worker bridge with a pure fake decoder, so local tests need no model runtime."""
    registry = ModuleType("gpu_registry")
    registry.execution_backend = lambda _environment: backend  # type: ignore[attr-defined]
    decoder_name = "gpu_vllm_models" if backend == "vllm" else "gpu_models"
    decoder = ModuleType(decoder_name)
    decoder.RUNTIME_SOURCE = ROOT / "scripts" / "gpu_models.py"  # type: ignore[attr-defined]
    decoder.load_model = lambda _tag: pytest.fail("model loading is outside this bridge test")  # type: ignore[attr-defined]

    def generate(
        _model: object,
        _tokenizer: object,
        chats: list[list[dict[str, str]]],
        *,
        max_tokens: int,
        thinking: bool,
        seed: int | None,
        structured_json_schema: dict[str, object] | None,
    ) -> tuple[list[str], float, list[int], list[int]]:
        calls.append({
            "max_tokens": max_tokens,
            "thinking": thinking,
            "seed": seed,
            "structured_json_schema": structured_json_schema,
        })
        return [chat[0]["content"] for chat in chats], 0.01, [1] * len(chats), [1] * len(chats)

    decoder.generate = generate  # type: ignore[attr-defined]
    worker = ModuleType("gpu_worker")
    worker.generation_messages = lambda request: request.messages  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "gpu_registry", registry)
    monkeypatch.setitem(sys.modules, decoder_name, decoder)
    monkeypatch.setitem(sys.modules, "gpu_worker", worker)
    monkeypatch.setitem(sys.modules, "gpu_contracts", gpu_contracts)
    spec = importlib.util.spec_from_file_location("seed_runtime_fixture", ROOT / "scripts" / "gpu_runtime.py")
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def request(
    seed: int | None,
    *,
    schema: dict[str, object] | None = None,
) -> gpu_contracts.CompletionRequest:
    """Build a production-shaped request without invoking HTTP or model dependencies."""
    payload: dict[str, object] = {
        "model": "fixture",
        "messages": [{"role": "user", "content": "hello"}],
        "max_tokens": 32,
    }
    if seed is not None:
        payload["seed"] = seed
    if schema is not None:
        payload["response_format"] = {
            "type": "json_schema",
            "json_schema": {"name": "fixture", "schema": schema},
        }
    return gpu_contracts.CompletionRequest.model_validate(payload)


def fixture_backend(runtime: ModuleType) -> object:
    """Construct initialized complete_batch state without loading model weights."""
    backend = runtime.PinnedBackend.__new__(runtime.PinnedBackend)
    backend.model = object()
    backend.tokenizer = object()
    backend.metadata = gpu_contracts.Metadata(
        model="fixture", model_id="fixture", revision="a" * 40,
        config_sha256="b" * 64, runtime_sha256="c" * 64, quantization="fixture",
    )
    backend.measure = lambda _request: gpu_contracts.PromptCount(prompt_tokens=1, prompt_sha256="d" * 64)
    return backend


def test_runtime_forwards_one_uniform_optional_seed_to_the_decoder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A supplied seed is forwarded exactly once after the token guard accepts the batch."""
    calls: list[dict[str, object]] = []
    runtime = load_runtime_with_fake_decoder(monkeypatch, calls)
    backend = fixture_backend(runtime)

    result = backend.complete_batch([request(715), request(715)])

    assert [item.text for item in result] == ["hello", "hello"]
    assert calls == [{
        "max_tokens": 32,
        "thinking": False,
        "seed": 715,
        "structured_json_schema": None,
    }]


def test_runtime_rejects_a_mixed_seed_batch_before_decoder_execution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Direct callers bypassing the dispatcher still cannot accidentally share one sampling parameter."""
    calls: list[dict[str, object]] = []
    runtime = load_runtime_with_fake_decoder(monkeypatch, calls)
    backend = fixture_backend(runtime)

    with pytest.raises(ValueError, match="incompatible_generation_batch"):
        backend.complete_batch([request(715), request(716)])

    assert calls == []


def test_vllm_runtime_forwards_a_uniform_json_schema_to_the_decoder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A vLLM candidate must constrain the same schema for every request in its generation batch."""
    calls: list[dict[str, object]] = []
    runtime = load_runtime_with_fake_decoder(monkeypatch, calls, backend="vllm")
    backend = fixture_backend(runtime)
    schema: dict[str, object] = {
        "type": "object",
        "properties": {"mode": {"type": "string"}},
        "required": ["mode"],
    }

    result = backend.complete_batch([request(715, schema=schema), request(715, schema=schema)])

    assert [item.text for item in result] == ["hello", "hello"]
    assert calls == [{
        "max_tokens": 32,
        "thinking": False,
        "seed": 715,
        "structured_json_schema": schema,
    }]


def test_vllm_runtime_rejects_mixed_json_schema_batch_before_decoder_execution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One vLLM SamplingParams object must never constrain two different response schemas."""
    calls: list[dict[str, object]] = []
    runtime = load_runtime_with_fake_decoder(monkeypatch, calls, backend="vllm")
    backend = fixture_backend(runtime)

    with pytest.raises(ValueError, match="incompatible_generation_batch"):
        backend.complete_batch([
            request(715, schema={"type": "object", "properties": {"mode": {"type": "string"}}}),
            request(715, schema={"type": "object", "properties": {"fact_ids": {"type": "array"}}}),
        ])

    assert calls == []
