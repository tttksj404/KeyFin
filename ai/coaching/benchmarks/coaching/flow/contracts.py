"""Credential-free evidence contracts for one complete account lifecycle."""

from typing import Literal

from pydantic import Field

from coaching_service.schemas import Frozen, JsonDocument

Backend = Literal["fake", "gpu"]


class Check(Frozen):
    name: str
    passed: bool


class Exchange(Frozen):
    stage: str
    method: str
    path: str
    status: int
    latency_ms: float = Field(ge=0)
    request: JsonDocument | None
    response: JsonDocument


class ModelObservation(Frozen):
    stage: str
    source: str
    model: str
    fallback_reason: str | None


class RoutingObservation(Frozen):
    stage: str
    metadata_available: bool
    mode: str | None
    source: str | None
    fallback_reason: str | None


class FlowReport(Frozen):
    version: Literal["payment-chat-restart/2"] = "payment-chat-restart/2"
    backend: Backend
    fixture: JsonDocument
    process_ids: tuple[int, int]
    original_process_exit_code: int
    final_process_stopped: bool
    checks: tuple[Check, ...]
    exchanges: tuple[Exchange, ...]
    model_observations: tuple[ModelObservation, ...]
    routing_observations: tuple[RoutingObservation, ...]
    completed: bool
    error_type: str | None = None


class SavedAnswer(Frozen):
    path: str
    body: JsonDocument


class Checkpoint(Frozen):
    session_id: str
    session: JsonDocument
    twin: JsonDocument
    answers: tuple[SavedAnswer, ...]
    payment_request: JsonDocument
    payment_response: JsonDocument
    ack_path: str
    ack: JsonDocument
    pending_notifications: JsonDocument
    last_question: str
    last_stage: str
    last_response: JsonDocument
