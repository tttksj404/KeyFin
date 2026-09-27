"""Typed artifacts for the natural chat benchmark."""

from typing import Literal

from pydantic import Field

from coaching_service.chat_answers import ChatAnswer
from coaching_service.schemas import Coaching, Frozen, JsonDocument


class HttpStage(Frozen):
    status: int
    latency_ms: float = Field(ge=0)


class HttpResult(Frozen):
    status: int
    latency_ms: float = Field(ge=0)
    body: JsonDocument


class CaseResult(Frozen):
    id: str
    question: str
    setup: Literal["without_twin", "with_twin"]
    expected_kind: Literal["finance", "history", "forecast", "risk", "data_request"]
    expected_status: str | None
    reference_id: str | None
    request: JsonDocument
    http: dict[str, HttpStage]
    response: Coaching | ChatAnswer | JsonDocument | None = None
    stored_exact: bool = False
    history_isolated: bool = False


class RunReport(Frozen):
    suite_version: Literal["chat-response/1"] = "chat-response/1"
    api_origin_sha256: str
    fixture_sha256: str
    as_of: str
    analysis_forced: Literal[False] = False
    cases: tuple[CaseResult, ...]


class LayerScore(Frozen):
    passed: int = Field(ge=0)
    total: int = Field(ge=0)
    interpretation: str


class ModelObservation(Frozen):
    id: str
    role: Literal["evidence_selector", "supplementary_writer", "intent_router", "none"]
    outcome: Literal[
        "accepted",
        "template_fallback",
        "deterministic_scope_response",
        "deterministic_data_request",
        "engine_answer_no_writer",
        "invalid_metadata",
    ]
    fallback_reason: str | None


class ModelScore(Frozen):
    accepted: int = Field(ge=0)
    template_fallback: int = Field(ge=0)
    deterministic_scope_response: int = Field(ge=0)
    deterministic_data_request: int = Field(ge=0)
    engine_answer_no_writer: int = Field(ge=0)
    observations: tuple[ModelObservation, ...]
    interpretation: str


class LatencyScore(Frozen):
    observations: int = Field(ge=0)
    minimum_ms: float | None
    median_ms: float | None
    maximum_ms: float | None


class CaseScore(Frozen):
    id: str
    transport_passed: bool
    semantic_passed: bool


class ScoreReport(Frozen):
    report_sha256: str
    suite_version: str
    http: LayerScore
    semantic: LayerScore
    model_admission: ModelScore
    message_latency: LatencyScore
    cases: tuple[CaseScore, ...]
