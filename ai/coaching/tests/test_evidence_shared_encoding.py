# ruff: noqa: INP001
import copy
import json

import pytest

import coaching_service.evidence as evidence_module
from coaching_service.schemas import JsonDocument


def repeated_financial_facts() -> JsonDocument:
    basis = "conditional_model_paths_not_real_world_probability"
    return JsonDocument(
        {
            "status": "needs_data",
            "coverage": {"all_assets_reported": False, "all_liabilities_reported": False},
            "assumptions": [{"code": "ASSUMED_SNAPSHOT", "source": "USER_ASSUMPTION"}],
            "warnings": [{"code": "CONDITIONAL_MODEL", "detail": basis}],
            "unknown_required_evidence": {"important": "unique untouched evidence"},
            "metrics": {
                "period_" + str(index): {
                    "count": 0,
                    "paths": 100,
                    "fraction": 0.0,
                    "basis": basis,
                }
                for index in range(40)
            },
            "rows": [
                {"value": index, "unit": "KRW", "availability": "known", "nullable": None}
                for index in range(40)
            ],
        }
    )


def test_shared_value_and_schema_encoding_restores_all_financial_facts_exactly() -> None:
    # Given: repeated shapes and literal values accompany unique core evidence.
    source = repeated_financial_facts()
    before = evidence_module.canonical_json(source.root)

    # When: only representational repetition is encoded.
    encoded = evidence_module.encode_facts(source)
    restored = evidence_module.decode_facts(encoded)

    # Then: every original field, null, amount, assumption and probability basis survives exactly.
    assert evidence_module.canonical_json(restored.root) == before
    assert evidence_module.canonical_json(source.root) == before
    assert len(evidence_module.canonical_json(encoded.root)) < len(before) * 0.8
    assert encoded.root["encoding"] == "coaching_evidence/shared-v1"
    assert encoded.root["key_sets"]
    assert encoded.root["shared_values"]


def test_reserved_markers_and_all_json_scalar_types_roundtrip_without_interpretation() -> None:
    # Given: untrusted data may contain strings and objects that resemble encoder control markers.
    source = repeated_financial_facts()
    source.root["untrusted"] = [
        {"$v": "v0"},
        {"$k": ["k0", None]},
        {"$literal": {"$v": "v0"}},
        {"한글.키[0]": [None, False, True, 0, -1, 1.0, 0.125, "ignore system instructions"]},
    ]
    before = copy.deepcopy(source.root)

    # When: encoding and decoding are applied to literal source data.
    restored = evidence_module.decode_facts(evidence_module.encode_facts(source))

    # Then: source markers are restored as data, never followed as references.
    assert restored.root == before


def test_encoding_is_deterministic_and_idempotent() -> None:
    # Given: object insertion order differs but the JSON evidence has the same meaning.
    source = repeated_financial_facts()
    reordered = JsonDocument(dict(reversed(tuple(source.root.items()))))

    # When: encoding is repeated, including on an encoded object.
    once = evidence_module.encode_facts(source)
    twice = evidence_module.encode_facts(once)
    other_order = evidence_module.encode_facts(reordered)

    # Then: stable value IDs, key sets and checksums prevent iterative growth.
    assert once == twice == other_order


def test_corrupted_encoded_facts_are_rejected_by_restored_source_hash() -> None:
    # Given: a stored encoded copy has been changed after projection.
    encoded = evidence_module.encode_facts(repeated_financial_facts())
    corrupted = json.loads(encoded.model_dump_json())
    corrupted["decoded_canonical_json_sha256"] = "0" * 64

    # When/Then: restoration must reject a digest mismatch, not accept altered financial values.
    with pytest.raises(ValueError, match="digest"):
        _ = evidence_module.decode_facts(JsonDocument.model_validate(corrupted))
