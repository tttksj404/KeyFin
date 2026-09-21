# ruff: noqa: INP001
import json

import pytest
from test_evidence_operation_projection import nested_receipt
from test_evidence_projection import receipt_with_numeric_result

from coaching_service.evidence import bounded_evidence, context_limited, decode_facts, operation_evidence
from coaching_service.llm_contract import EvidenceInput
from coaching_service.schemas import JsonDocument, Receipt


@pytest.mark.parametrize("field", ["visualizations", "datasets.projection"])
def test_unknown_payload_shape_remains_evidence_and_reaches_limit(field: str) -> None:
    # Given: a known field name carries an unknown scalar, not a chart or row collection.
    original = receipt_with_numeric_result().model_dump(mode="json")
    if field == "visualizations":
        original["numeric_result"]["visualizations"] = "가" * 65000
    else:
        original["numeric_result"]["datasets"] = {"projection": "가" * 65000}
    receipt = Receipt.model_validate(original)
    before = receipt.model_dump_json()

    # When: projection applies recognized structural rules.
    actual = bounded_evidence(receipt)

    # Then: an unknown shape cannot be silently discarded by its key alone.
    assert context_limited(actual)
    assert receipt.model_dump_json() == before


def test_nested_availability_and_missing_inputs_survive_route_aggregate_projection() -> None:
    # Given: a metric contains missing-input context needed to route safely.
    original = receipt_with_numeric_result().model_dump(mode="json")
    original["numeric_result"]["metrics"] = {
        "cash": {"availability": "unavailable", "missing_inputs": ["dated_card_bill"], "value": None}
    }
    evidence = bounded_evidence(Receipt.model_validate(original))

    # When: routing projects the evidence.
    projected = json.loads(operation_evidence(evidence, "route").facts_json)

    # Then: the complete source metric remains present with its original qualification.
    assert projected["numeric_result"]["metrics"] == original["numeric_result"]["metrics"]


def test_operation_projection_is_idempotent_and_preserves_unknown_source_metadata() -> None:
    # Given: caller-supplied metadata is an opaque source value, not a trusted projection instruction.
    evidence = EvidenceInput(facts_json='{"engine_status":"ready","llm_projection":{"note":"opaque"}}')

    # When: the same operation is applied twice.
    once = operation_evidence(evidence, "write")
    twice = operation_evidence(once, "write")

    # Then: source metadata survives and repeating an operation cannot grow the input.
    assert once == twice
    assert json.loads(once.facts_json)["llm_projection"]["source_metadata"] == {"note": "opaque"}


def test_different_original_charts_never_receive_a_false_original_analysis_fingerprint() -> None:
    # Given: two engine documents differ only in a presentation field omitted from model input.
    original = nested_receipt().model_dump(mode="json")
    original["result"]["original_core"] = "원문" * 300
    original["historical"]["engine_result"]["original_core"] = "원문" * 300
    original["historical"]["engine_result"]["visualizations"] = [{"dataset": "projection", "type": "bar"}]
    evidence = bounded_evidence(Receipt.model_validate(original))
    before = json.loads(evidence.facts_json)["llm_projection"]["deduplicated_fields"]

    # When: a later operation sees the now-equal projected analysis objects.
    scoped = operation_evidence(evidence, "write")
    restored = decode_facts(JsonDocument.model_validate_json(scoped.facts_json))

    # Then: new references cannot claim a projected-content hash describes either original engine document.
    assert restored.root["llm_projection"]["deduplicated_fields"] == before
