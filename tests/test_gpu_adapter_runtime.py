"""An evaluated selector adapter must be explicit, verified, and never silently skipped."""

# ruff: noqa: INP001

from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING

import pytest
from pydantic import ValidationError

from scripts.gpu_registry import ModelEntry, adapter_digest, vllm_decoder_options

if TYPE_CHECKING:
    from _pytest.monkeypatch import MonkeyPatch

ROOT = Path(__file__).resolve().parents[1]


class FakeTokenizer:
    """Supply only the tokenizer fields used while loading a decoder."""

    eos_token = "<eos>"
    pad_token: str | None = None


class FakeModel:
    """Represent the base decoder without loading any real model weights."""

    def eval(self) -> FakeModel:
        return self


def entry(
    model_path: Path,
    *,
    adapter_path: Path | None = None,
    adapter_sha256: str | None = None,
) -> ModelEntry:
    """Build one BF16 small-model entry matching the evaluated adapter boundary."""
    return ModelEntry(
        tag="base8",
        model_id="fixture/base8",
        path=model_path,
        revision="a" * 40,
        config_sha256=hashlib.sha256((model_path / "config.json").read_bytes()).hexdigest(),
        quantization="bf16",
        adapter_path=adapter_path,
        adapter_sha256=adapter_sha256,
    )


def load_decoder(
    monkeypatch: MonkeyPatch,
    configured: ModelEntry,
    calls: list[tuple[str, str]],
) -> ModuleType:
    """Import the real decoder against lightweight fakes and a fixed registry entry."""
    torch = ModuleType("torch")
    torch.bfloat16 = "bf16"  # type: ignore[attr-defined]
    transformers = ModuleType("transformers")

    class AutoTokenizer:
        @staticmethod
        def from_pretrained(*_: object, **__: object) -> FakeTokenizer:
            return FakeTokenizer()

    class AutoModelForCausalLM:
        @staticmethod
        def from_pretrained(*_: object, **__: object) -> FakeModel:
            return FakeModel()

    class _Qwen35ForConditionalGeneration:
        @staticmethod
        def from_pretrained(*_: object, **__: object) -> FakeModel:
            return FakeModel()

    transformers.AutoTokenizer = AutoTokenizer  # type: ignore[attr-defined]
    transformers.AutoModelForCausalLM = AutoModelForCausalLM  # type: ignore[attr-defined]
    transformers.BitsAndBytesConfig = lambda **_: object()  # type: ignore[attr-defined]
    transformers.PreTrainedModel = FakeModel  # type: ignore[attr-defined]
    transformers.PreTrainedTokenizerBase = FakeTokenizer  # type: ignore[attr-defined]
    transformers.Qwen3_5ForConditionalGeneration = _Qwen35ForConditionalGeneration  # type: ignore[attr-defined]

    class PeftModel:
        @staticmethod
        def from_pretrained(model: FakeModel, path: Path, **kwargs: object) -> FakeModel:
            calls.append((str(path), str(kwargs)))
            return model

    peft = ModuleType("peft")
    peft.PeftModel = PeftModel  # type: ignore[attr-defined]
    registry = ModuleType("gpu_registry")
    registry.ModelEntry = ModelEntry  # type: ignore[attr-defined]
    registry.load_entry = lambda _path, _tag: configured  # type: ignore[attr-defined]
    registry.validate_device = lambda _environment: None  # type: ignore[attr-defined]
    registry.adapter_digest = adapter_digest  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "torch", torch)
    monkeypatch.setitem(sys.modules, "transformers", transformers)
    monkeypatch.setitem(sys.modules, "peft", peft)
    monkeypatch.setitem(sys.modules, "gpu_registry", registry)
    monkeypatch.setenv("COACH_GPU_MODEL_REGISTRY", "fixture-registry.json")
    spec = importlib.util.spec_from_file_location(
        "gpu_adapter_runtime_fixture", ROOT / "scripts" / "gpu_models.py",
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_adapter_digest_binds_relative_names_and_contents(tmp_path: Path) -> None:
    """A registry checksum changes for either an adapter filename or its bytes."""
    adapter = tmp_path / "adapter"
    adapter.mkdir()
    (adapter / "adapter_config.json").write_text("{}", encoding="utf-8")
    (adapter / "adapter_model.safetensors").write_bytes(b"first")
    first = adapter_digest(adapter)
    (adapter / "adapter_model.safetensors").write_bytes(b"second")

    assert len(first) == 64
    assert adapter_digest(adapter) != first


def test_registry_requires_both_adapter_path_and_checksum(tmp_path: Path) -> None:
    """A deployment cannot point at unverified adapter files or a detached digest."""
    model = tmp_path / "model"
    model.mkdir()
    (model / "config.json").write_text("{}", encoding="utf-8")

    with pytest.raises(ValidationError, match="adapter_fields_must_be_paired"):
        _ = entry(model, adapter_path=tmp_path / "adapter")
    with pytest.raises(ValidationError, match="adapter_fields_must_be_paired"):
        _ = entry(model, adapter_sha256="c" * 64)


def test_vllm_rejects_an_adapter_that_only_the_transformer_loader_can_verify(tmp_path: Path) -> None:
    """A vLLM configuration must fail instead of serving the base checkpoint by accident."""
    model = tmp_path / "model"
    adapter = tmp_path / "adapter"
    model.mkdir()
    adapter.mkdir()
    (model / "config.json").write_text("{}", encoding="utf-8")
    (adapter / "adapter_config.json").write_text("{}", encoding="utf-8")

    with pytest.raises(RuntimeError, match="adapter_requires_transformers_backend"):
        _ = vllm_decoder_options(entry(model, adapter_path=adapter, adapter_sha256=adapter_digest(adapter)))


def test_transformer_loader_applies_the_verified_adapter_before_returning_the_model(
    tmp_path: Path, monkeypatch: MonkeyPatch,
) -> None:
    """The loader may return only the adapter-wrapped model, never its untouched base."""
    model = tmp_path / "model"
    adapter = tmp_path / "adapter"
    model.mkdir()
    adapter.mkdir()
    (model / "config.json").write_text("{}", encoding="utf-8")
    (adapter / "adapter_config.json").write_text("{}", encoding="utf-8")
    configured = entry(model, adapter_path=adapter, adapter_sha256=adapter_digest(adapter))
    calls: list[tuple[str, str]] = []
    decoder = load_decoder(monkeypatch, configured, calls)

    loaded, tokenizer, returned = decoder.load_model("base8")

    assert isinstance(loaded, FakeModel)
    assert isinstance(tokenizer, FakeTokenizer)
    assert returned == configured
    assert calls == [(str(adapter), "{'local_files_only': True, 'is_trainable': False}")]


def test_transformer_loader_rejects_a_changed_adapter_before_loading_it(
    tmp_path: Path, monkeypatch: MonkeyPatch,
) -> None:
    """Changing adapter bytes after approval stops startup rather than falling back to base weights."""
    model = tmp_path / "model"
    adapter = tmp_path / "adapter"
    model.mkdir()
    adapter.mkdir()
    (model / "config.json").write_text("{}", encoding="utf-8")
    (adapter / "adapter_config.json").write_text("{}", encoding="utf-8")
    configured = entry(model, adapter_path=adapter, adapter_sha256="d" * 64)
    calls: list[tuple[str, str]] = []
    decoder = load_decoder(monkeypatch, configured, calls)

    with pytest.raises(RuntimeError, match="model_adapter_changed"):
        _ = decoder.load_model("base8")

    assert calls == []
