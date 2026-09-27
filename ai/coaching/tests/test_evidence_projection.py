# ruff: noqa: INP001
import copy
import hashlib
import json

import pytest

from coaching_service.evidence import bounded_evidence, context_limited
from coaching_service.llm_contract import ChatMessage, EvidenceInput
from coaching_service.schemas import JsonDocument, Receipt


def receipt_with_numeric_result() -> Receipt:
    return Receipt.model_validate(
        {
            "engine_commit": "pinned-engine",
            "identity": {
                "user_id": "demo",
                "twin_id": "demo-twin",
                "revision": 2,
                "input_digest": "original-digest",
                "as_of": "2026-09-09",
            },
            "request": {"on_date": "2026-09-09", "through_date": "2026-09-16"},
            "result": {
                "status": "needs_data",
                "next_action": {"kind": "complete_cash_state", "detail": "잔액 자료를 확인해 주세요."},
                "warnings": [{"code": "CURRENT_WARNING", "detail": "현재 경고 원문"}],
            },
            "trigger": "dialogue",
            "original_coaching_id": "original",
            "historical": {
                "coaching_id": "original",
                "created_at": 1.0,
                "payment": {
                    "transaction_id": "payment",
                    "envelope": "기타",
                    "amount_krw": 50000,
                    "balance_before_krw": 100000,
                    "balance_after_krw": 50000,
                    "remaining_percent": "50.0",
                    "weekly_count": 1,
                },
                "trigger": "p0_half_balance",
                "engine_result": {"warnings": [{"code": "ORIGINAL_WARNING", "detail": "당시 경고 원문"}]},
                "transaction_status": "canceled",
            },
            "current_envelopes": [{"envelope": "기타", "balance_krw": 100000}],
            "numeric_request": {"mode": "risk", "paths": 100, "horizon_days": 7},
            "numeric_result": {
                "status": "partial",
                "decision": {"kind": "needs_data", "reason": "원인 원문"},
                "model": {"version": "original", "seed": 42},
                "metrics": [{"name": "cash", "value": 12500, "unit": "KRW"}],
                "assumptions": [{"code": "ASSUMED_SNAPSHOT", "detail": "가정 원문"}],
                "warnings": [{"code": "NUMERIC_WARNING", "detail": "수치 경고 원문"}],
                "limitations": ["확률로 해석하지 않는다는 한계 원문"],
                "datasets": [{"값": 12500, "날짜": "2026-09-09"}],
                "visualizations": {"차트": "cash", "축": ["날짜", "금액"]},
            },
        }
    )


def test_projection_keeps_receipt_immutable_and_preserves_all_non_payload_fields() -> None:
    receipt = receipt_with_numeric_result()
    before = receipt.model_dump_json()
    original = json.loads(before)
    history = (ChatMessage(role="user", content="당시 코칭을 다시 확인하고 싶어요."),)
    evidence = bounded_evidence(receipt, "현재 위험을 확인해 주세요.", history)
    projected = json.loads(evidence.facts_json)
    _ = projected.pop("llm_projection")
    expected = copy.deepcopy(original)
    del expected["numeric_result"]["datasets"]
    del expected["numeric_result"]["visualizations"]
    assert projected == expected
    assert receipt.model_dump_json() == before
    assert evidence.history == history
    assert evidence.question == "현재 위험을 확인해 주세요."
    assert not context_limited(evidence)


def test_projection_records_canonical_hash_lengths_and_original_receipt_paths() -> None:
    receipt = receipt_with_numeric_result()
    original = receipt.model_dump(mode="json")
    projected = json.loads(bounded_evidence(receipt).facts_json)
    metadata = projected["llm_projection"]
    assert metadata["version"] == "evidence_projection/v2"
    expected = []
    for field in ("datasets", "visualizations"):
        canonical = json.dumps(
            original["numeric_result"][field],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        encoded = canonical.encode("utf-8")
        expected.append(
            {
                "receipt_path": "$.numeric_result." + field,
                "canonical_json_sha256": hashlib.sha256(encoded).hexdigest(),
                "canonical_json_chars": len(canonical),
                "canonical_json_bytes": len(encoded),
                "reason": "legacy_dataset_payload" if field == "datasets" else "presentation_payload",
            }
        )
        assert len(encoded) > len(canonical)
    assert metadata["omitted_fields"] == expected


def test_projection_is_deterministic_across_json_object_key_order() -> None:
    receipt = receipt_with_numeric_result()
    reordered = copy.deepcopy(receipt.model_dump(mode="json"))
    numeric = dict(reversed(tuple(reordered["numeric_result"].items())))
    numeric["datasets"][0] = dict(reversed(tuple(numeric["datasets"][0].items())))
    numeric["visualizations"] = dict(reversed(tuple(numeric["visualizations"].items())))
    reordered["numeric_result"] = numeric
    assert (
        bounded_evidence(receipt).facts_json == bounded_evidence(Receipt.model_validate(reordered)).facts_json
    )


@pytest.mark.parametrize("numeric_result", [None, JsonDocument({"status": "ok", "metrics": [12500]})])
def test_absent_payload_fields_add_no_projection_metadata(numeric_result: JsonDocument | None) -> None:
    receipt = receipt_with_numeric_result().model_copy(update={"numeric_result": numeric_result})
    actual = bounded_evidence(receipt)
    assert actual == EvidenceInput(facts_json=receipt.model_dump_json())
    assert "llm_projection" not in json.loads(actual.facts_json)


@pytest.mark.parametrize("field", ["datasets", "visualizations"])
def test_single_payload_field_records_only_the_field_actually_omitted(field: str) -> None:
    receipt = receipt_with_numeric_result()
    original = receipt.model_dump(mode="json")
    other = "datasets" if field == "visualizations" else "visualizations"
    del original["numeric_result"][other]
    evidence = bounded_evidence(Receipt.model_validate(original))
    projected = json.loads(evidence.facts_json)
    assert [item["receipt_path"] for item in projected["llm_projection"]["omitted_fields"]] == [
        "$.numeric_result." + field
    ]


@pytest.mark.parametrize("field", ["metrics", "warnings", "assumptions"])
def test_oversized_core_financial_evidence_still_uses_context_limit_fallback(field: str) -> None:
    original = receipt_with_numeric_result().model_dump(mode="json")
    original["numeric_result"][field] = ["가" * 65000]
    receipt = Receipt.model_validate(original)
    before = receipt.model_dump_json()
    evidence = bounded_evidence(receipt)
    assert context_limited(evidence)
    assert receipt.model_dump_json() == before
