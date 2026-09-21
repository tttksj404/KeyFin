"""The committed registry template must actually pass gpu_registry's strict loader.

scripts/gpu_model_registry.example.json documents the exact JSON schema
COACH_GPU_MODEL_REGISTRY is expected to point at (docs/gpu-deploy.md). This
file is pure pydantic/stdlib (no torch/vllm import), so it is safe to import
and exercise without a GPU.
"""

from pathlib import Path

import pytest

from scripts.gpu_registry import load_entry, vllm_decoder_options

_REGISTRY_PATH = Path(__file__).resolve().parent.parent / "scripts" / "gpu_model_registry.example.json"


def test_example_registry_file_exists() -> None:
    assert _REGISTRY_PATH.is_file()


def test_example_registry_resolves_prod27_fp8_with_expected_fields() -> None:
    entry = load_entry(_REGISTRY_PATH, "prod27_fp8")

    assert entry.tag == "prod27_fp8"
    assert entry.model_id == "Qwen/Qwen3.8-27B-FP8"
    assert entry.quantization == "fp8"
    assert len(entry.revision) == 40
    assert len(entry.config_sha256) == 64
    assert entry.adapter_path is None


def test_example_registry_entry_yields_the_documented_vllm_decoder_options() -> None:
    entry = load_entry(_REGISTRY_PATH, "prod27_fp8")

    options = vllm_decoder_options(entry)

    assert options["max_model_len"] == 9728
    assert options["gpu_memory_utilization"] == 0.75
    assert options["enable_prefix_caching"] is True
    assert options["enforce_eager"] is False
    assert options["dtype"] == "bfloat16"
    assert options["tensor_parallel_size"] == 1
    # prod27_fp8 relies on vLLM auto-detecting FP8 from the checkpoint config;
    # an explicit bitsandbytes-style loader here would misrepresent it.
    assert "quantization" not in options
    assert "load_format" not in options


def test_example_registry_rejects_an_unregistered_tag() -> None:
    with pytest.raises(ValueError, match="model_tag_not_registered"):
        load_entry(_REGISTRY_PATH, "latest27_nf4")
