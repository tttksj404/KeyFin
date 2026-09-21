"""Immutable official-source corpus loaded once; no user request can replace it."""

from __future__ import annotations

import hashlib
import os
from datetime import date  # noqa: TC003 - Pydantic resolves field types at runtime.
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Self
from urllib.parse import urlsplit

from pydantic import Field, model_validator

from coaching_service.llm_contract import FrozenContract

_MAX_BYTES = 512_000
_APPROVED_HOSTS = frozenset({
    "www.bok.or.kr", "www.fsc.go.kr", "www.fss.or.kr",
    "www.investor.gov", "www.consumerfinance.gov", "www.finra.org", "content.naic.org",
})


class KnowledgeFact(FrozenContract):
    id: str = Field(pattern=r"^[a-z][a-z0-9_]{1,63}$")
    title: str = Field(min_length=1, max_length=120)
    text: str = Field(min_length=1, max_length=600)
    source_title: str = Field(min_length=1, max_length=120)
    source_url: str = Field(max_length=600)
    aliases: Annotated[tuple[str, ...], Field(min_length=1, max_length=20)]
    reviewed_on: date
    review_due: date
    jurisdiction: str = Field(min_length=1, max_length=40)

    @property
    def cited_text(self) -> str:
        return self.text + "\n출처: [" + self.source_title + "](" + self.source_url + ")"

    @model_validator(mode="after")
    def valid_source(self) -> Self:
        source = urlsplit(self.source_url)
        if (
            source.scheme != "https" or source.hostname not in _APPROVED_HOSTS
            or source.username is not None or source.password is not None
            or source.port is not None or source.fragment
            or self.review_due < self.reviewed_on
            or any(not term.strip() or len(term) > 80 for term in self.aliases)
            or any("\ufffd" in value for value in (self.title, self.text, self.source_title, *self.aliases))
        ):
            raise ValueError("Invalid finance knowledge source")
        return self


class KnowledgeCatalog(FrozenContract):
    version: str = Field(min_length=1, max_length=100)
    facts: Annotated[tuple[KnowledgeFact, ...], Field(min_length=1, max_length=250)]

    @model_validator(mode="after")
    def unique_ids(self) -> Self:
        if len({fact.id for fact in self.facts}) != len(self.facts):
            raise ValueError("Duplicate finance knowledge id")
        # Reject a deployment corpus that could overflow the three-fact answer contract.
        largest = sorted((len(fact.cited_text) for fact in self.facts), reverse=True)[:3]
        if sum(largest) + 2 * (len(largest) - 1) > 2400:
            raise ValueError("Finance knowledge answer exceeds response limit")
        return self

    @property
    def digest(self) -> str:
        return hashlib.sha256(self.model_dump_json().encode()).hexdigest()


@lru_cache(maxsize=1)
def load_catalog() -> KnowledgeCatalog:
    """Require an exact SHA for external corpora; reload only on process restart."""
    configured = os.environ.get("COACHING_KNOWLEDGE_FILE")
    path = Path(configured) if configured else Path(__file__).with_name("knowledge") / "finance.json"
    with path.open("rb") as stream:
        raw = stream.read(_MAX_BYTES + 1)
    if len(raw) > _MAX_BYTES:
        raise ValueError("Finance knowledge corpus exceeds size limit")
    if configured:
        expected = os.environ.get("COACHING_KNOWLEDGE_SHA256", "")
        if len(expected) != 64 or hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError("Finance knowledge corpus hash mismatch")
    return KnowledgeCatalog.model_validate_json(raw)
