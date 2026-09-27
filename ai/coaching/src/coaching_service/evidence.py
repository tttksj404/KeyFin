"""A model context limit never invalidates an otherwise valid financial event."""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING, assert_never

from pydantic import ValidationError

from coaching_service.evidence_encoding import EvidenceEncodingError, decode_facts, encode_facts
from coaching_service.evidence_projection import EvidenceProjection, canonical_json
from coaching_service.llm_contract import EvidenceInput
from coaching_service.schemas import JsonDocument

if TYPE_CHECKING:
    from coaching_service.llm_contract import ChatMessage, Operation
    from coaching_service.schemas import Receipt

LIMITED_CONTEXT = '{"model_context_status":"unavailable","reason":"context_limit"}'


def projected_facts_json(receipt: Receipt, *, requested_text: str = "") -> str:
    """Project a parsed copy before applying limits; the original Receipt remains lossless."""
    facts = JsonDocument.model_validate_json(receipt.model_dump_json())
    projected = EvidenceProjection(None, requested_text).project(facts)
    return canonical_json(projected.root) if "llm_projection" in projected.root else receipt.model_dump_json()


def bounded_evidence(
    receipt: Receipt, question: str = "", history: tuple[ChatMessage, ...] = ()
) -> EvidenceInput:
    try:
        requested_text = "\n".join((question, *(message.content for message in history)))
        return EvidenceInput(
            question=question,
            history=history,
            facts_json=projected_facts_json(receipt, requested_text=requested_text),
        )
    except ValidationError:
        # Core evidence still cannot be truncated to fit; the original receipt remains unchanged.
        return EvidenceInput(question=question, facts_json=LIMITED_CONTEXT)


def operation_evidence(evidence: EvidenceInput, operation: Operation) -> EvidenceInput:
    """Route uses intent/state; judge keeps P1 evidence; write keeps all structured financial facts."""
    if context_limited(evidence):
        return evidence
    if evidence.purpose == "finance":
        # These are already bounded concept facts, not a Twin document to project.
        return evidence
    requested_text = "\n".join((evidence.question, *(message.content for message in evidence.history)))
    projection = EvidenceProjection(operation, requested_text)
    try:
        plain = decode_facts(JsonDocument.model_validate_json(evidence.facts_json))
        facts = projection.project(plain)
        match operation:
            case "judge" | "write":
                model_facts = encode_facts(facts)
            case "route":
                model_facts = facts
            case unreachable:
                assert_never(unreachable)
        return EvidenceInput(
            purpose=evidence.purpose,
            question=evidence.question,
            history=evidence.history,
            facts_json=canonical_json(model_facts.root),
        )
    except (ValidationError, EvidenceEncodingError):
        return EvidenceInput(
            purpose=evidence.purpose,
            question=evidence.question,
            history=evidence.history,
            facts_json=LIMITED_CONTEXT,
        )


def context_limited(evidence: EvidenceInput) -> bool:
    return evidence.facts_json == LIMITED_CONTEXT


def token_retry_evidence(evidence: EvidenceInput) -> EvidenceInput | None:
    """Make one smaller, non-financial retry context after an exact token rejection.

    The model never owns FDT amounts, dates, risk results, or actions. For the
    remaining supplementary-coaching writer, an oversized evidence bundle can be
    replaced by a provenance-only context without changing the authoritative
    response that is already rendered by the service. Finance and chart fact
    selection are deliberately excluded: removing their approved source text
    could change which answer is correct, so those calls fail closed instead.

    This is invoked only after the serving tokenizer rejects the *exact* first
    request. It is not a character-to-token estimate and it never mutates the
    original receipt or stored session.
    """
    if evidence.purpose != "coaching" or context_limited(evidence):
        return None
    original_size = len(evidence.question) + len(evidence.facts_json) + sum(
        len(message.content) for message in evidence.history
    )
    # A short context cannot benefit from a second tokenization request; retain
    # the original fallback reason instead of adding avoidable latency.
    if original_size < 2048:
        return None
    shortened_history = tuple(
        message.model_copy(update={
            "content": message.content[:240] + (" [이력 일부 생략]" if len(message.content) > 240 else ""),
        })
        for message in evidence.history[-2:]
    )
    facts_json = json.dumps(
        {
            "model_context_status": "reduced_after_token_limit",
            "source_canonical_sha256": hashlib.sha256(evidence.facts_json.encode("utf-8")).hexdigest(),
            "source_chars": len(evidence.facts_json),
            "financial_result_authoritative": True,
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
    candidate = EvidenceInput(
        purpose=evidence.purpose,
        question=evidence.question,
        history=shortened_history,
        facts_json=facts_json,
    )
    compact_size = len(candidate.question) + len(candidate.facts_json) + sum(
        len(message.content) for message in candidate.history
    )
    # Retrying an almost-identical prompt cannot resolve a tokenizer limit.
    return candidate if compact_size * 2 < original_size else None
