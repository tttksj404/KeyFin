"""Private deployment configuration; machine identity is never a response field."""

import hashlib
from collections.abc import Mapping
from pathlib import Path
from typing import ClassVar, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ModelEntry(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")
    tag: Literal["base8", "latest27_nf4", "prod27_fp8"]
    model_id: str
    path: Path
    revision: str = Field(pattern=r"^[0-9a-f]{40}$")
    config_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    quantization: Literal["bf16", "nf4", "fp8"]
    # An adapter remains opt-in and is bound to the exact bytes that cleared a
    # separate quality screen. A path alone is not enough to select it.
    adapter_path: Path | None = None
    adapter_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def adapter_fields_are_paired(self) -> Self:
        """Reject partial or unsupported adapter registrations before runtime startup."""
        if (self.adapter_path is None) != (self.adapter_sha256 is None):
            raise ValueError("adapter_fields_must_be_paired")
        if self.adapter_path is not None and (self.tag, self.quantization) != ("base8", "bf16"):
            raise ValueError("unsupported_adapter_model_pair")
        return self


class Registry(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")
    models: tuple[ModelEntry, ...] = Field(min_length=1, max_length=2)


ExecutionBackend = Literal["transformers", "vllm", "vllm_async"]


def execution_backend(environment: Mapping[str, str]) -> ExecutionBackend:
    """Read the decoder selection; vllm_async is now the default, pending GPU A/B evidence.

    The checkpoint, prompts, token budget, and API contract remain the same. This
    default flip (SPEC-latency C1) is code-reachability only — it has not been
    promoted by a measured E1/E2 gate yet; that A/B run happens separately. A
    deployment can opt out to the legacy transformers path explicitly (see
    docs/operations.md rollback). An invalid setting stops before a worker could
    choose an arbitrary implementation or device.
    """
    selected = environment.get("COACH_GPU_EXECUTION_BACKEND", "vllm_async").strip()
    match selected:
        case "transformers":
            return "transformers"
        case "vllm":
            return "vllm"
        case "vllm_async":
            return "vllm_async"
        case _:
            raise RuntimeError("unsupported_gpu_execution_backend")


def validate_device(environment: Mapping[str, str]) -> None:
    """운영자가 허용한 장치 중 하나를 명시한 경우만 기동한다. 장치를 자동 선택하지 않는다."""
    selected = environment.get("CUDA_VISIBLE_DEVICES", "").strip()
    allowed = environment.get("COACH_GPU_ALLOWED_DEVICES", "").split(",")
    if not selected or "," in selected or selected not in {item.strip() for item in allowed if item.strip()}:
        raise RuntimeError("explicit_single_authorized_accelerator_required")


def load_entry(path: Path, tag: str) -> ModelEntry:
    """허용된 태그의 체크포인트·revision·설정 해시를 개인 설정에서 한 건만 읽는다.

    태그는 지원 런타임의 계약이고 모델 경로·물리 자원은 저장소의 상수가 아니다.
    중복 태그는 첫 항목을 임의 선택하지 않고 기동 오류로 처리한다.
    """
    registry = Registry.model_validate_json(path.read_bytes())
    if len({entry.tag for entry in registry.models}) != len(registry.models):
        raise ValueError("duplicate_model_tag")
    matches = [entry for entry in registry.models if entry.tag == tag]
    if len(matches) != 1:
        raise ValueError("model_tag_not_registered")
    return matches[0]


def adapter_digest(directory: Path) -> str:
    """Hash adapter-relative paths and bytes in the same order used by the trainer.

    The checkpoint configuration is already verified separately. This digest binds
    the optional LoRA files so a changed adapter cannot silently fall back to the
    base model or inherit a different experiment's weights.
    """
    files = tuple(sorted(path for path in directory.rglob("*") if path.is_file()))
    if not files:
        raise RuntimeError("model_adapter_missing")
    digest = hashlib.sha256()
    for path in files:
        digest.update(path.relative_to(directory).as_posix().encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def vllm_decoder_options(entry: ModelEntry) -> dict[str, object]:
    """Return a reviewed vLLM load policy for one registered checkpoint only.

    The small BF16 candidate and the larger NF4 candidate deliberately share the
    request/token contract, while their weight-loading settings remain explicit.
    This function does not select a candidate or claim that either one has passed
    quality or latency evaluation; deployment still has to opt in by model tag.
    """
    if entry.adapter_path is not None:
        # The reviewed adapter loader is Transformer-only. vLLM must stop here
        # rather than load the base checkpoint and misrepresent the candidate.
        raise RuntimeError("adapter_requires_transformers_backend")
    common: dict[str, object] = {
        "dtype": "bfloat16",
        "trust_remote_code": False,
        "tensor_parallel_size": 1,
        "distributed_executor_backend": "uni",
        "max_model_len": 9728,
        "gpu_memory_utilization": 0.75,
        # C1 (SPEC-latency): 8 -> 16. max_num_batched_tokens stays 8192 and
        # max_model_len stays 9728 (unchanged): both bound a single sequence's
        # prefill/decode budget, not sequence count, and 16 short (<=96 token)
        # coaching/route calls still fit the scheduler's token budget per step.
        # Judgement call: raised only after confirming max_num_batched_tokens
        # (8192) comfortably covers the realistic per-step token mix at 16
        # concurrent sequences of this call shape; not re-derived from a formula.
        "max_num_seqs": 16,
        "max_num_batched_tokens": 8192,
        # C1: prefix caching reuses the shared system-prompt/JSON-schema prefix
        # across route/finance/coaching calls. Same greedy decode (temperature 0,
        # seed 715) and StructuredOutputsParams grammar keep the KV reuse from
        # changing the emitted tokens; E2 identity is the gate that confirms it
        # in practice, not assumed here.
        "enable_prefix_caching": True,
        "enable_chunked_prefill": True,
        "limit_mm_per_prompt": {"image": 0, "video": 0},
        "seed": 715,
        "disable_log_stats": True,
        "enforce_eager": False,
    }
    match entry.tag, entry.quantization:
        case "base8", "bf16":
            # Let vLLM select its normal BF16 loader.  Passing an NF4 loader here
            # would silently turn a small-model comparison into a different model.
            return common
        case "latest27_nf4", "nf4":
            return {**common, "quantization": "bitsandbytes", "load_format": "bitsandbytes"}
        case "prod27_fp8", "fp8":
            # The checkpoint (Qwen/Qwen3.8-27B-FP8) is a pre-quantized
            # fine-grained FP8 (compressed-tensors) checkpoint. vLLM 0.19
            # auto-detects its quantization scheme from the checkpoint's own
            # config; passing an explicit "quantization"/"load_format" here
            # (e.g. bitsandbytes) would misrepresent it as a different
            # loader and can break auto-detection. Common options only.
            return common
        case _:
            raise RuntimeError("unsupported_vllm_model_quantization_pair")
