"""Deterministic, source-traceable projection of opaque engine JSON for model input."""

from __future__ import annotations

import hashlib
import json
import re
from typing import TYPE_CHECKING, Final, assert_never

from coaching_service.schemas import JsonDocument

if TYPE_CHECKING:
    from pydantic import JsonValue

    from coaching_service.llm_contract import Operation

VERSION: Final = "evidence_projection/v2"
_ENGINE_FIELDS: Final = frozenset({"result", "numeric_result", "engine_result"})
_BULK_DATASETS: Final = frozenset({"projection", "branch_projection", "comparison"})
_ROUTE_DATASETS: Final = frozenset(
    {"envelopes", "fixed_groups", "account_risk", "first_shortfall", "budget_risk", "stress_scenarios"}
)
_SERIES_REQUEST: Final = re.compile(
    r"일별|날짜별|시계열|추이|daily|time.?series|\d{4}-\d{2}-\d{2}(?!\s*(?:마감\s*)?까지)",
    re.IGNORECASE,
)
_DEDUP_MIN_CHARS: Final = 512
_PRIORITY: Final = {"result": 0, "numeric_result": 1, "historical": 2}
_GUARD_FIELDS: Final = frozenset(
    {
        "status",
        "data_status",
        "availability",
        "warnings",
        "assumptions",
        "limitations",
        "required_inputs",
        "missing_data",
        "missing_inputs",
        "cash_requirements",
        "payment",
        "decision",
    }
)


def canonical_json(value: JsonValue) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def source_record(value: JsonValue, path: str) -> JsonDocument:
    serialized = canonical_json(value)
    encoded = serialized.encode("utf-8")
    return JsonDocument(
        {
            "receipt_path": path,
            "canonical_json_sha256": hashlib.sha256(encoded).hexdigest(),
            "canonical_json_chars": len(serialized),
            "canonical_json_bytes": len(encoded),
        }
    )


def child_path(parent: str, field: str) -> str:
    """Use unambiguous JSONPath even when an opaque upstream key contains punctuation."""
    return parent + "." + field if field.isidentifier() else parent + "[" + json.dumps(field) + "]"


def contains_guard(value: JsonValue) -> bool:
    """Protect nested missing-data state and qualifications even inside known aggregate containers."""
    match value:
        case dict():
            return bool(_GUARD_FIELDS.intersection(value)) or any(
                contains_guard(item) for item in value.values()
            )
        case list():
            return any(contains_guard(item) for item in value)
        case str() | int() | float() | bool() | None:
            return False
        case unreachable:
            assert_never(unreachable)


def structured_payload(value: JsonValue) -> bool:
    match value:
        case dict() | list():
            return True
        case str() | int() | float() | bool() | None:
            return False
        case unreachable:
            assert_never(unreachable)


class EvidenceProjection:
    """Mutable traversal accumulator; mutations affect only a model-owned parsed copy."""

    def __init__(self, operation: Operation | None, requested_text: str) -> None:
        self.operation: Operation | None = operation
        self.keep_series: bool = bool(_SERIES_REQUEST.search(requested_text))
        self.omitted: list[JsonValue] = []
        self.duplicates: list[JsonValue] = []
        self.sources: dict[str, str] = {}
        self.engine_paths: set[str] = set()
        self.original_sha: str | None = None
        self.source_metadata: JsonValue = None

    def project(self, document: JsonDocument) -> JsonDocument:
        original = document.root
        source = source_record(original, "$")
        facts = dict(original)
        prior = facts.get("llm_projection")
        inherited = self.inherit(prior)
        if inherited:
            _ = facts.pop("llm_projection")
            source.root["canonical_json_sha256"] = self.original_sha
        projected = JsonDocument.model_validate(self.walk(facts, "$"))
        if self.omitted or self.duplicates or self.operation is not None:
            metadata: dict[str, JsonValue] = {
                "version": VERSION,
                "operation": self.operation or "full",
                "original_retained": True,
                "source_canonical_json_sha256": source.root["canonical_json_sha256"],
                "omitted_fields": self.omitted,
                "deduplicated_fields": self.duplicates,
            }
            source_metadata = self.source_metadata if inherited else prior
            if source_metadata is not None:
                metadata["source_metadata"] = source_metadata
            projected.root["llm_projection"] = metadata
        return projected

    def inherit(self, prior: JsonValue) -> bool:
        match prior:
            case {
                "version": str(version),
                "source_canonical_json_sha256": str(digest),
                "omitted_fields": list(omitted),
                "deduplicated_fields": list(duplicates),
            } if version == VERSION:
                self.original_sha = digest
                self.source_metadata = prior.get("source_metadata")
                self.omitted.extend(omitted)
                self.duplicates.extend(duplicates)
                return True
            case dict() | list() | str() | int() | float() | bool() | None:
                return False
            case unreachable:
                assert_never(unreachable)

    def walk(self, value: JsonValue, path: str) -> JsonValue:
        match value:
            case dict():
                return self.mapping(JsonDocument(value), path).root
            case list():
                return [self.walk(item, f"{path}[{index}]") for index, item in enumerate(value)]
            case str() | int() | float() | bool() | None:
                return value
            case unreachable:
                assert_never(unreachable)

    def mapping(self, document: JsonDocument, path: str) -> JsonDocument:
        original = document.root
        if path.rsplit(".", 1)[-1] in _ENGINE_FIELDS:
            self.engine_paths.add(path)
        # Only complete original analyses can share a source fingerprint; later passes contain omissions.
        if self.operation is None and path in self.engine_paths:
            fingerprint = source_record(original, path)
            serialized = canonical_json(original)
            if len(serialized) >= _DEDUP_MIN_CHARS:
                digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
                if digest in self.sources:
                    source = self.sources[digest]
                    fingerprint.root["source_path"] = source
                    self.duplicates.append(fingerprint.root)
                    return JsonDocument({"$ref": source})
                self.sources[digest] = path
        retained: dict[str, JsonValue] = {}
        for field in sorted(original, key=lambda key: (_PRIORITY.get(key, 3), key)):
            value = original[field]
            target = child_path(path, field)
            reason = self.omission_reason(target, value)
            if reason:
                record = source_record(value, target)
                record.root["reason"] = reason
                self.omitted.append(record.root)
            else:
                retained[field] = self.walk(value, target)
        return JsonDocument(retained)

    def omission_reason(self, path: str, value: JsonValue) -> str | None:
        if contains_guard(value) or not structured_payload(value):
            return None
        parent, _, field = path.rpartition(".")
        if parent in self.engine_paths:
            if field == "visualizations":
                return "presentation_payload"
            if field == "datasets":
                match value:
                    case list() if not self.keep_series:
                        legacy_reason = "legacy_dataset_payload"
                    case dict() | list() | str() | int() | float() | bool() | None:
                        legacy_reason = None
                    case unreachable:
                        assert_never(unreachable)
                return legacy_reason
        engine_parent, _, container = parent.rpartition(".")
        if (
            engine_parent in self.engine_paths
            and container == "datasets"
            and field in _BULK_DATASETS
            and not self.keep_series
        ):
            return "bulk_time_series"
        match self.operation:
            case "route":
                return "route_uses_intent_and_data_state" if self.route_aggregate(path) else None
            case "judge" | "write" | None:
                return None
            case unreachable:
                assert_never(unreachable)

    def route_aggregate(self, path: str) -> bool:
        parent, _, field = path.rpartition(".")
        engine_parent, _, container = parent.rpartition(".")
        return (parent in self.engine_paths and field in {"metrics", "observed_budgets"}) or (
            engine_parent in self.engine_paths
            and (
                (container == "datasets" and field in _ROUTE_DATASETS)
                or (container == "projection" and field in {"cash", "budgets"})
            )
        )
