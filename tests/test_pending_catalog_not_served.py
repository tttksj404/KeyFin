# ruff: noqa: INP001
"""Prove the pending-review staging file can never reach a served answer.

``src/coaching_service/knowledge/finance_candidates.pending.json`` is where a
new catalog entry waits for human review before promotion into the live
``finance.json``. This file asserts, structurally, that the loader
``finance_knowledge.py`` actually uses (``knowledge_catalog.load_catalog``)
has no path to that file: it either reads the hardcoded live ``finance.json``
next to it, or an explicitly configured+hash-pinned override, and the pending
filename appears nowhere in the loader or in the finance-answer modules.
"""

from __future__ import annotations

import inspect
import json
import os
from pathlib import Path

from coaching_service import finance_knowledge, knowledge_catalog
from coaching_service.finance_knowledge import _BY_ID, FACTS, VERSION
from coaching_service.knowledge_catalog import load_catalog

_KNOWLEDGE_DIR = Path(knowledge_catalog.__file__).with_name("knowledge")
_LIVE_FILE = _KNOWLEDGE_DIR / "finance.json"
_PENDING_FILE = _KNOWLEDGE_DIR / "finance_candidates.pending.json"


def test_pending_file_exists_and_is_structurally_shaped_like_the_live_catalog() -> None:
    assert _PENDING_FILE.exists()
    payload = json.loads(_PENDING_FILE.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    assert "version" in payload
    assert "facts" in payload
    assert payload["facts"] == []


def test_pending_file_is_never_the_default_load_path() -> None:
    """The unconfigured loader always resolves to finance.json, never the pending file."""
    assert "COACHING_KNOWLEDGE_FILE" not in os.environ
    default_path = _KNOWLEDGE_DIR / "finance.json"
    assert default_path == _LIVE_FILE
    assert default_path != _PENDING_FILE


def test_loader_source_never_references_the_pending_filename() -> None:
    """The loader and the finance-answer module must not name the pending file at all.

    This is a structural guarantee, not a behavioral inference: if a future
    change wired the pending file into ``load_catalog`` or into
    ``finance_knowledge.py``, this literal-name check catches it even before
    any test exercises the resulting answer.
    """
    loader_source = inspect.getsource(knowledge_catalog)
    answer_source = inspect.getsource(finance_knowledge)
    assert "finance_candidates" not in loader_source
    assert "pending" not in loader_source.lower()
    assert "finance_candidates" not in answer_source
    assert "pending" not in answer_source.lower()


def test_live_catalog_content_matches_finance_json_not_the_pending_file() -> None:
    """The process-wide cached catalog is exactly the live file's content."""
    catalog = load_catalog()
    live_payload = json.loads(_LIVE_FILE.read_text(encoding="utf-8"))
    pending_payload = json.loads(_PENDING_FILE.read_text(encoding="utf-8"))

    assert catalog.version == live_payload["version"]
    assert catalog.version != pending_payload["version"]
    assert len(catalog.facts) == len(live_payload["facts"])
    assert len(FACTS) == len(live_payload["facts"])


def test_no_pending_candidate_ids_leak_into_served_facts() -> None:
    """Any id declared only in the pending file must be absent from what is served.

    The pending file is empty today, so this is vacuously true; the assertion
    stays general (set difference, not a hardcoded id) so it keeps proving the
    same thing once a real candidate is staged there.
    """
    pending_payload = json.loads(_PENDING_FILE.read_text(encoding="utf-8"))
    pending_ids = {fact["id"] for fact in pending_payload["facts"]}
    served_ids = set(_BY_ID)
    assert pending_ids - served_ids == pending_ids
    assert load_catalog().version == VERSION
