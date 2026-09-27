# /// script
# requires-python = ">=3.11"
# dependencies = ["pydantic"]
# ///
# How to run: imported by package tests or standalone gpu_worker.py.
"""Shared immutable worker contracts without HTTP execution or runtime imports."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import ClassVar, Literal, Protocol, Self, assert_never

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator


class Frozen(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")


class Message(Frozen):
    role: Literal["system", "user", "assistant"]
    content: str = Field(min_length=1, max_length=32000)


class SchemaRequest(Frozen):
    name: str
    strict: bool = True
    schema_: dict[str, JsonValue] = Field(alias="schema")


class ResponseFormat(Frozen):
    type: Literal["json_object", "json_schema", "text"]
    json_schema: SchemaRequest | None = None

    @model_validator(mode="after")
    def validates_schema_pair(self) -> Self:
        """Reject ambiguous response-format payloads at the worker boundary."""
        match self.type:
            case "json_schema":
                if self.json_schema is None:
                    raise ValueError("json_schema_required")
            case "json_object" | "text":
                if self.json_schema is not None:
                    raise ValueError("json_schema_not_allowed")
            case unreachable:
                assert_never(unreachable)
        return self


class CompletionRequest(Frozen):
    model: str
    messages: tuple[Message, ...] = Field(min_length=1, max_length=16)
    max_tokens: int = Field(default=256, ge=1, le=1536)
    # It is an opt-in experiment control, rather than an output guarantee. Keeping
    # it on the immutable request lets the worker reject mixed-seed batches.
    seed: int | None = Field(default=None, ge=0, le=4_294_967_295)
    temperature: Literal[0] = 0
    stream: Literal[False] = False
    response_format: ResponseFormat | None = None


class Metadata(Frozen):
    model: str
    model_id: str
    revision: str
    config_sha256: str
    runtime_sha256: str
    quantization: str
    # The hash is an attestation value only. It exposes neither an adapter path
    # nor training rows, and remains null when the reviewed base model is used.
    adapter_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    logical_gpu: Literal[0] = 0
    max_input_tokens: Literal[8192] = 8192
    max_output_tokens: Literal[1536] = 1536
    # This is decoder capability for JSON Schema requests. Plain-text requests
    # deliberately remain unconstrained even on the optional structured decoder.
    grammar_enforced: bool = False
    response_format_handling: Literal["schema_in_prompt", "vllm_json_schema"] = "schema_in_prompt"
    tokenizer_contract: Literal["coaching-token-budget/1"] = "coaching-token-budget/1"


class PromptCount(Frozen):
    prompt_tokens: int = Field(ge=1)
    prompt_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


@dataclass(frozen=True, slots=True)
class Generated:
    text: str
    prompt_tokens: int
    completion_tokens: int
    seconds: float


class Backend(Protocol):
    @property
    def metadata(self) -> Metadata: ...

    def complete(self, request: CompletionRequest) -> Generated: ...

    def measure(self, request: CompletionRequest) -> PromptCount: ...


def structured_json_schema(request: CompletionRequest) -> dict[str, JsonValue] | None:
    """Return the already-validated JSON Schema for a decoder that supports it."""
    response_format = request.response_format
    if response_format is None:
        return None
    match response_format.type:
        case "json_schema":
            # ``ResponseFormat`` validates this pairing at the HTTP boundary.
            if response_format.json_schema is None:
                raise ValueError("json_schema_required")
            return response_format.json_schema.schema_
        case "json_object" | "text":
            return None
        case unreachable:
            assert_never(unreachable)


def response_format_fingerprint(request: CompletionRequest) -> str:
    """Produce a canonical batch key without exposing response content or model output."""
    response_format = request.response_format
    if response_format is None:
        return "none"
    return json.dumps(
        response_format.model_dump(mode="json", by_alias=True, exclude_none=True),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
