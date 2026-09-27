"""Lossless dictionaries for repeated JSON values and object schemas in model-only evidence."""

import copy
import hashlib
from collections import Counter
from typing import Final, Literal, assert_never

from pydantic import JsonValue

from coaching_service.evidence_projection import canonical_json
from coaching_service.llm_contract import FrozenContract
from coaching_service.schemas import JsonDocument

ENCODING: Final = "coaching_evidence/shared-v1"
_MARKERS: Final = frozenset({"$v", "$k", "$literal"})


class SharedFacts(FrozenContract):
    encoding: Literal["coaching_evidence/shared-v1"] = ENCODING
    key_sets: dict[str, list[str]]
    shared_values: dict[str, JsonValue]
    facts: JsonValue
    decoded_canonical_json_sha256: str


class EvidenceEncodingError(ValueError):
    def __init__(self, reason: str) -> None:
        self.reason: str = reason
        super().__init__(reason)


class Encoder:
    """Mutable counters and used dictionaries belong to a single deterministic encoding pass."""

    def __init__(self) -> None:
        self.counts: Counter[str] = Counter()
        self.shapes: Counter[tuple[str, ...]] = Counter()
        self.value_ids: dict[str, str] = {}
        self.shape_ids: dict[tuple[str, ...], str] = {}
        self.values: dict[str, JsonValue] = {}
        self.keys: dict[str, list[str]] = {}

    def count(self, value: JsonValue) -> None:
        serialized = canonical_json(value)
        if len(serialized) >= 32:
            self.counts[serialized] += 1
        match value:
            case dict():
                self.shapes[tuple(sorted(value))] += 1
                for item in value.values():
                    self.count(item)
            case list():
                for item in value:
                    self.count(item)
            case str() | int() | float() | bool() | None:
                return
            case unreachable:
                assert_never(unreachable)

    def select(self) -> None:
        values = sorted(
            value for value, count in self.counts.items() if (len(value) - 14) * count > len(value) + 12
        )
        self.value_ids = {value: "v" + str(index) for index, value in enumerate(values)}
        shapes = sorted(
            keys
            for keys, count in self.shapes.items()
            if count >= 3
            and (len(canonical_json(list(keys))) - 14) * count > len(canonical_json(list(keys))) + 20
        )
        self.shape_ids = {keys: "k" + str(index) for index, keys in enumerate(shapes)}

    def encode(self, value: JsonValue) -> JsonValue:
        name = self.value_ids.get(canonical_json(value))
        if name is not None:
            self.values[name] = copy.deepcopy(value)
            return {"$v": name}
        match value:
            case dict():
                keys = tuple(sorted(value))
                name = self.shape_ids.get(keys)
                if name is not None:
                    self.keys[name] = list(keys)
                    return {"$k": [name, *(self.encode(value[key]) for key in keys)]}
                encoded: dict[str, JsonValue] = {key: self.encode(value[key]) for key in keys}
                return {"$literal": encoded} if len(keys) == 1 and keys[0] in _MARKERS else encoded
            case list():
                return [self.encode(item) for item in value]
            case str() | int() | float() | bool() | None:
                return value
            case unreachable:
                assert_never(unreachable)


class Decoder:
    def __init__(self, encoded: SharedFacts) -> None:
        self.encoded: SharedFacts = encoded

    def decode(self, value: JsonValue) -> JsonValue:
        match value:
            case dict():
                return self.mapping(JsonDocument(value))
            case list():
                return [self.decode(item) for item in value]
            case str() | int() | float() | bool() | None:
                return value
            case unreachable:
                assert_never(unreachable)

    def mapping(self, document: JsonDocument) -> JsonValue:
        value = document.root
        match value:
            case {"$v": str(name)} if len(value) == 1:
                try:
                    # Dictionary entries are literal source JSON, never executable references.
                    return copy.deepcopy(self.encoded.shared_values[name])
                except KeyError as error:
                    raise EvidenceEncodingError("unknown shared value reference") from error
            case {"$k": [str(name), *items]} if len(value) == 1:
                try:
                    keys = self.encoded.key_sets[name]
                except KeyError as error:
                    raise EvidenceEncodingError("unknown key set reference") from error
                if len(keys) != len(items) or len(set(keys)) != len(keys):
                    raise EvidenceEncodingError("key set arity mismatch")
                return {key: self.decode(item) for key, item in zip(keys, items, strict=True)}
            case {"$literal": dict(literal)} if len(value) == 1:
                return {key: self.decode(item) for key, item in literal.items()}
            case dict():
                return {key: self.decode(item) for key, item in value.items()}
            case unreachable:
                assert_never(unreachable)


def decode_facts(document: JsonDocument) -> JsonDocument:
    """Restore the exact canonical input, rejecting changed values or malformed dictionary references."""
    if document.root.get("encoding") != ENCODING:
        return document
    encoded = SharedFacts.model_validate(document.root)
    restored = JsonDocument.model_validate(Decoder(encoded).decode(encoded.facts))
    digest = hashlib.sha256(canonical_json(restored.root).encode("utf-8")).hexdigest()
    if digest != encoded.decoded_canonical_json_sha256:
        raise EvidenceEncodingError("decoded evidence digest mismatch")
    return restored


def encode_facts(document: JsonDocument) -> JsonDocument:
    """Send one representation only; keep ordinary JSON whenever encoding would increase its length."""
    plain = decode_facts(document)
    serialized = canonical_json(plain.root)
    encoder = Encoder()
    encoder.count(plain.root)
    encoder.select()
    facts = encoder.encode(plain.root)
    candidate = SharedFacts(
        key_sets=encoder.keys,
        shared_values=encoder.values,
        facts=facts,
        decoded_canonical_json_sha256=hashlib.sha256(serialized.encode("utf-8")).hexdigest(),
    )
    encoded = JsonDocument.model_validate_json(candidate.model_dump_json())
    return encoded if len(canonical_json(encoded.root)) < len(serialized) else plain
