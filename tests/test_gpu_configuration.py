from pathlib import Path

import pytest
from pydantic import ValidationError

from scripts.gpu_contracts import CompletionRequest, structured_json_schema
from scripts.gpu_registry import ModelEntry, execution_backend, validate_device, vllm_decoder_options
from scripts.gpu_worker import admission_limit


@pytest.mark.parametrize("environment", [
    {}, {"CUDA_VISIBLE_DEVICES": "GPU-a"},
    {"CUDA_VISIBLE_DEVICES": "GPU-a,GPU-b", "COACH_GPU_ALLOWED_DEVICES": "GPU-a,GPU-b"},
    {"CUDA_VISIBLE_DEVICES": "GPU-c", "COACH_GPU_ALLOWED_DEVICES": "GPU-a"},
])
def test_unassigned_or_multiple_devices_are_rejected(environment: dict[str, str]) -> None:
    with pytest.raises(RuntimeError, match="explicit_single_authorized_accelerator_required"):
        validate_device(environment)


def test_only_explicitly_selected_authorized_device_is_accepted() -> None:
    validate_device({"CUDA_VISIBLE_DEVICES": "GPU-a", "COACH_GPU_ALLOWED_DEVICES": "GPU-a,GPU-b"})


@pytest.mark.parametrize(("environment", "expected"), [
    ({}, "vllm_async"),
    ({"COACH_GPU_EXECUTION_BACKEND": "transformers"}, "transformers"),
    ({"COACH_GPU_EXECUTION_BACKEND": "vllm"}, "vllm"),
    ({"COACH_GPU_EXECUTION_BACKEND": "vllm_async"}, "vllm_async"),
])
def test_execution_backend_defaults_to_vllm_async_and_is_overridable(
    environment: dict[str, str], expected: str,
) -> None:
    assert execution_backend(environment) == expected


@pytest.mark.parametrize("value", ["", "Transformer", "vllm,transformers", "unknown"])
def test_unknown_execution_backend_fails_closed(value: str) -> None:
    with pytest.raises(RuntimeError, match="unsupported_gpu_execution_backend"):
        execution_backend({"COACH_GPU_EXECUTION_BACKEND": value})


def model_entry(tag: str, quantization: str) -> ModelEntry:
    return ModelEntry(
        tag=tag,
        model_id="fixture/" + tag,
        path=Path("C:/models/") / tag,
        revision="a" * 40,
        config_sha256="b" * 64,
        quantization=quantization,
    )


def test_vllm_small_candidate_keeps_the_same_request_budget_without_nf4_loader() -> None:
    """The small candidate must not inherit the larger candidate's quantization loader."""
    options = vllm_decoder_options(model_entry("base8", "bf16"))

    assert options["dtype"] == "bfloat16"
    assert options["max_model_len"] == 9728
    assert options["max_num_batched_tokens"] == 8192
    assert options["max_num_seqs"] == 16
    assert options["enable_prefix_caching"] is True
    assert "quantization" not in options
    assert "load_format" not in options


def test_vllm_large_candidate_keeps_its_nf4_loader_explicit() -> None:
    options = vllm_decoder_options(model_entry("latest27_nf4", "nf4"))

    assert options["quantization"] == "bitsandbytes"
    assert options["load_format"] == "bitsandbytes"


def test_vllm_rejects_a_model_tag_and_quantization_pair_not_in_the_registry_contract() -> None:
    with pytest.raises(RuntimeError, match="unsupported_vllm_model_quantization_pair"):
        _ = vllm_decoder_options(model_entry("base8", "nf4"))


def test_vllm_fp8_candidate_uses_checkpoint_native_quantization_without_bitsandbytes() -> None:
    """prod27_fp8 is a pre-quantized compressed-tensors/FP8 checkpoint; vLLM
    auto-detects its quantization from the checkpoint config, so this loader
    must not pass a bitsandbytes load_format (that would misrepresent the
    checkpoint's own quantization scheme)."""
    options = vllm_decoder_options(model_entry("prod27_fp8", "fp8"))

    assert options["dtype"] == "bfloat16"
    assert options["max_model_len"] == 9728
    assert options["max_num_batched_tokens"] == 8192
    assert options["max_num_seqs"] == 16
    assert options["enable_prefix_caching"] is True
    assert options["seed"] == 715
    assert "load_format" not in options
    assert "quantization" not in options


def test_vllm_rejects_prod27_tag_paired_with_a_non_fp8_quantization() -> None:
    with pytest.raises(RuntimeError, match="unsupported_vllm_model_quantization_pair"):
        _ = vllm_decoder_options(model_entry("prod27_fp8", "nf4"))


def test_vllm_small_candidate_options_are_unchanged_by_the_fp8_addition() -> None:
    """Pin base8's exact dict so adding the fp8 branch cannot alter it."""
    options = vllm_decoder_options(model_entry("base8", "bf16"))

    assert options == {
        "dtype": "bfloat16",
        "trust_remote_code": False,
        "tensor_parallel_size": 1,
        "distributed_executor_backend": "uni",
        "max_model_len": 9728,
        "gpu_memory_utilization": 0.75,
        "max_num_seqs": 16,
        "max_num_batched_tokens": 8192,
        "enable_prefix_caching": True,
        "enable_chunked_prefill": True,
        "limit_mm_per_prompt": {"image": 0, "video": 0},
        "seed": 715,
        "disable_log_stats": True,
        "enforce_eager": False,
    }


def test_vllm_large_nf4_candidate_options_are_unchanged_by_the_fp8_addition() -> None:
    """Pin latest27_nf4's exact dict so adding the fp8 branch cannot alter it."""
    options = vllm_decoder_options(model_entry("latest27_nf4", "nf4"))

    assert options == {
        "dtype": "bfloat16",
        "trust_remote_code": False,
        "tensor_parallel_size": 1,
        "distributed_executor_backend": "uni",
        "max_model_len": 9728,
        "gpu_memory_utilization": 0.75,
        "max_num_seqs": 16,
        "max_num_batched_tokens": 8192,
        "enable_prefix_caching": True,
        "enable_chunked_prefill": True,
        "limit_mm_per_prompt": {"image": 0, "video": 0},
        "seed": 715,
        "disable_log_stats": True,
        "enforce_eager": False,
        "quantization": "bitsandbytes",
        "load_format": "bitsandbytes",
    }


@pytest.mark.parametrize(("backend_kind", "batch_size", "expected"), [
    ("transformers", 0, 8),
    ("vllm", 0, 8),
    ("vllm_async", 0, 16),
    ("vllm", 2, 32),
])
def test_admission_limit_matches_the_backend_slot_budget(
    backend_kind: str, batch_size: int, expected: int,
) -> None:
    """C1: vllm_async's ASGI cap follows its 8-slot engine budget (was 2 slots -> 8)."""
    assert admission_limit(backend_kind, batch_size) == expected  # type: ignore[arg-type]


def test_json_schema_response_format_requires_and_returns_an_object_schema() -> None:
    """The worker receives a parsed object schema before it reaches a decoder implementation."""
    schema: dict[str, object] = {"type": "object", "properties": {"mode": {"type": "string"}}}
    request = CompletionRequest.model_validate({
        "model": "fixture",
        "messages": [{"role": "user", "content": "hello"}],
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "route", "schema": schema},
        },
    })

    assert structured_json_schema(request) == schema

    with pytest.raises(ValidationError, match="json_schema_required"):
        CompletionRequest.model_validate({
            "model": "fixture",
            "messages": [{"role": "user", "content": "hello"}],
            "response_format": {"type": "json_schema"},
        })
