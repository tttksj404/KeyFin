"""The optional AsyncLLM candidate must preserve the worker's schema/output contract."""
# ruff: noqa: INP001

from __future__ import annotations

import importlib
import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True, slots=True)
class CapturedStructuredOutputs:
    values: dict[str, object]

    def __init__(self, **values: object) -> None:
        object.__setattr__(self, "values", values)


@dataclass(frozen=True, slots=True)
class CapturedSampling:
    values: dict[str, object]

    def __init__(self, **values: object) -> None:
        object.__setattr__(self, "values", values)


@dataclass(frozen=True, slots=True)
class FakeCompletion:
    text: str
    token_ids: list[int]


@dataclass(frozen=True, slots=True)
class FakeOutput:
    prompt_token_ids: list[int]
    finished: bool
    outputs: list[FakeCompletion]


class FakeTokenizer:
    def apply_chat_template(self, chat: list[dict[str, str]], **_: object) -> str:
        return "|".join(row["content"] for row in chat)

    def encode(self, prompt: str) -> list[int]:
        return [len(prompt)]


class FakeAsyncLLM:
    """Mimic the one async-generator method used by the candidate adapter."""

    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self.abort_ids: list[str] = []

    def generate(
        self,
        *,
        request_id: str,
        prompt: dict[str, list[int]],
        sampling_params: CapturedSampling,
    ) -> AsyncIterator[FakeOutput]:
        self.calls.append({
            "request_id": request_id,
            "prompt": prompt,
            "sampling_params": sampling_params,
        })

        async def outputs() -> AsyncIterator[FakeOutput]:
            yield FakeOutput(
                prompt_token_ids=prompt["prompt_token_ids"],
                finished=True,
                outputs=[FakeCompletion(text="{}", token_ids=[1])],
            )

        return outputs()

    def abort(self, request_id: str) -> None:
        self.abort_ids.append(request_id)


def load_decoder(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    """Load against an in-memory vLLM API surface without weights or an accelerator."""
    vllm = ModuleType("vllm")
    vllm.SamplingParams = CapturedSampling  # type: ignore[attr-defined]
    engine_args = ModuleType("vllm.engine.arg_utils")
    engine_args.AsyncEngineArgs = object  # type: ignore[attr-defined]
    sampling = ModuleType("vllm.sampling_params")
    sampling.StructuredOutputsParams = CapturedStructuredOutputs  # type: ignore[attr-defined]
    async_engine = ModuleType("vllm.v1.engine.async_llm")
    async_engine.AsyncLLM = FakeAsyncLLM  # type: ignore[attr-defined]
    transformers = ModuleType("transformers")
    transformers.AutoTokenizer = object  # type: ignore[attr-defined]
    transformers.PreTrainedTokenizerBase = FakeTokenizer  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "vllm", vllm)
    monkeypatch.setitem(sys.modules, "vllm.engine.arg_utils", engine_args)
    monkeypatch.setitem(sys.modules, "vllm.sampling_params", sampling)
    monkeypatch.setitem(sys.modules, "vllm.v1.engine.async_llm", async_engine)
    monkeypatch.setitem(sys.modules, "transformers", transformers)
    monkeypatch.setitem(sys.modules, "gpu_registry", importlib.import_module("scripts.gpu_registry"))
    spec = importlib.util.spec_from_file_location(
        "gpu_vllm_async_output_fixture", ROOT / "scripts" / "gpu_vllm_async_models.py",
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.anyio
async def test_async_vllm_decoder_preserves_request_id_tokens_and_json_schema(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    decoder = load_decoder(monkeypatch)
    model = FakeAsyncLLM()
    schema: dict[str, object] = {
        "type": "object",
        "properties": {"mode": {"type": "string"}},
        "required": ["mode"],
    }

    text, _, input_tokens, output_tokens = await decoder.generate(
        model,
        FakeTokenizer(),
        [{"role": "user", "content": "select"}],
        max_tokens=32,
        structured_json_schema=schema,
        request_id="fixture-request",
    )

    assert text == "{}"
    assert input_tokens == 1
    assert output_tokens == 1
    assert model.abort_ids == []
    assert model.calls[0]["request_id"] == "fixture-request"
    assert model.calls[0]["prompt"] == {"prompt_token_ids": [len("select")]}
    sampling = model.calls[0]["sampling_params"]
    assert isinstance(sampling, CapturedSampling)
    structured = sampling.values["structured_outputs"]
    assert isinstance(structured, CapturedStructuredOutputs)
    assert structured.values == {"json": schema}
