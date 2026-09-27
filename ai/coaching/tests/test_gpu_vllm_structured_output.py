"""The optional vLLM decoder must bind JSON Schema to its sampling parameters."""
# ruff: noqa: INP001

from __future__ import annotations

import importlib
import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pytest

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True, slots=True)
class CapturedStructuredOutputs:
    """Record the only structured-output argument accepted by the fake vLLM runtime."""

    values: dict[str, object]

    def __init__(self, **values: object) -> None:
        object.__setattr__(self, "values", values)


@dataclass(frozen=True, slots=True)
class CapturedSampling:
    """Record sampling values without importing the optional local dependency."""

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
    """Create a deterministic token sequence for the real decoder adapter."""

    def apply_chat_template(self, chat: list[dict[str, str]], **_: object) -> str:
        return "|".join(row["content"] for row in chat)

    def encode(self, prompt: str) -> list[int]:
        return [len(prompt)]


class FakeLLM:
    """Capture the sampling contract passed to the optional decoder."""

    def __init__(self) -> None:
        self.sampling: CapturedSampling | None = None

    def generate(
        self,
        prompts: list[dict[str, list[int]]],
        sampling_params: CapturedSampling,
        *,
        use_tqdm: bool,
    ) -> list[FakeOutput]:
        assert use_tqdm is False
        self.sampling = sampling_params
        return [
            FakeOutput(
                prompt_token_ids=row["prompt_token_ids"],
                finished=True,
                outputs=[FakeCompletion(text="{}", token_ids=[1])],
            )
            for row in prompts
        ]


def load_decoder(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    """Import the decoder with an in-memory vLLM API surface and no model weights."""
    vllm = ModuleType("vllm")
    vllm.LLM = FakeLLM  # type: ignore[attr-defined]
    vllm.SamplingParams = CapturedSampling  # type: ignore[attr-defined]
    sampling = ModuleType("vllm.sampling_params")
    sampling.StructuredOutputsParams = CapturedStructuredOutputs  # type: ignore[attr-defined]
    transformers = ModuleType("transformers")
    transformers.AutoTokenizer = object  # type: ignore[attr-defined]
    transformers.PreTrainedTokenizerBase = FakeTokenizer  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "vllm", vllm)
    monkeypatch.setitem(sys.modules, "vllm.sampling_params", sampling)
    monkeypatch.setitem(sys.modules, "transformers", transformers)
    monkeypatch.setitem(sys.modules, "gpu_registry", importlib.import_module("scripts.gpu_registry"))
    spec = importlib.util.spec_from_file_location(
        "gpu_vllm_structured_output_fixture", ROOT / "scripts" / "gpu_vllm_models.py",
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_vllm_decoder_passes_json_schema_to_structured_output_sampling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """JSON schema selection is enforced at the decoder instead of only described in prompt text."""
    decoder = load_decoder(monkeypatch)
    model = FakeLLM()
    schema: dict[str, object] = {
        "type": "object",
        "properties": {"mode": {"type": "string"}},
        "required": ["mode"],
    }

    texts, _, _, _ = decoder.generate(
        model,
        FakeTokenizer(),
        [[{"role": "user", "content": "select"}]],
        max_tokens=32,
        structured_json_schema=schema,
    )

    assert texts == ["{}"]
    assert model.sampling is not None
    structured = model.sampling.values["structured_outputs"]
    assert isinstance(structured, CapturedStructuredOutputs)
    assert structured.values == {"json": schema}
