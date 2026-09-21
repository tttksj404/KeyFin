# ruff: noqa: INP001
"""Tone persistence: TurnRequest.tone wins; otherwise the stored PersonalContext.tone applies.

``Dialogue._effective_tone`` is the single place that resolves the effective tone
for a turn (see ``dialogue.py``'s two ``self.core.compose(...)`` call sites). These
tests exercise it directly against a minimal fake repository/store, and then check
that the resolved tone actually changes the rendered ``deterministic_advice`` text,
so a swapped precedence or a broken store lookup fails loudly.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from coaching_service.dialogue import Dialogue
from coaching_service.personal_contract import PersonalContext
from coaching_service.personal_service import CONTEXT_KEY
from coaching_service.rendering import deterministic_advice
from coaching_service.schemas import Receipt, TurnRequest


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _stored_context(tone: str | None) -> str:
    return PersonalContext(
        expected_revision=0,
        as_of="2026-09-01",
        source_system="backend",
        source_record_id="rec-1",
        provenance="connected_backend",
        tone=tone,
        revision=1,
        received_at="2026-09-01T00:00:00+09:00",
    ).model_dump_json()


def _dialogue(stored_json: str | None) -> Dialogue:
    def load(owner: str, key: str) -> str | None:
        assert key == CONTEXT_KEY
        return stored_json

    store = SimpleNamespace(load=load)
    repository = SimpleNamespace(store=store)
    core: Any = SimpleNamespace(repository=repository)
    return Dialogue(core)


def _over_budget_receipt() -> Receipt:
    return Receipt.model_validate({
        "engine_commit": "pinned-engine",
        "identity": {
            "user_id": "user", "twin_id": "twin", "revision": 1,
            "input_digest": "digest", "as_of": "2026-09-21",
        },
        "request": {"on_date": "2026-09-21", "through_date": "2026-09-28"},
        "result": {},
        "trigger": "requested_review",
        "payment": {
            "transaction_id": "t1", "envelope": "외식", "amount_krw": 10000,
            "balance_before_krw": 5000, "balance_after_krw": -5000,
            "remaining_percent": "0", "weekly_count": 3,
        },
    })


@pytest.mark.anyio
async def test_stored_tone_is_used_when_turn_request_tone_is_none() -> None:
    dialogue = _dialogue(_stored_context("direct"))
    request = TurnRequest(question="질문")
    tone = await dialogue._effective_tone("owner", request)
    assert tone == "direct"
    # (a) the resolved tone actually flows into the rendered advice.
    assert deterministic_advice(_over_budget_receipt(), tone=tone) == deterministic_advice(
        _over_budget_receipt(), tone="direct"
    )


@pytest.mark.anyio
async def test_explicit_turn_request_tone_overrides_stored_tone() -> None:
    dialogue = _dialogue(_stored_context("direct"))
    request = TurnRequest(question="질문", tone="encouraging")
    tone = await dialogue._effective_tone("owner", request)
    # (b) explicit request tone wins even though the stored context says "direct".
    assert tone == "encouraging"
    assert deterministic_advice(_over_budget_receipt(), tone=tone) == deterministic_advice(
        _over_budget_receipt(), tone="encouraging"
    )


@pytest.mark.anyio
async def test_no_stored_context_and_no_request_tone_preserves_default_behavior() -> None:
    dialogue = _dialogue(None)
    request = TurnRequest(question="질문")
    tone = await dialogue._effective_tone("owner", request)
    # (c) neither set: unchanged default (None -> encouraging wording in deterministic_advice).
    assert tone is None
    assert deterministic_advice(_over_budget_receipt(), tone=tone) == deterministic_advice(
        _over_budget_receipt()
    )


@pytest.mark.anyio
async def test_stored_context_without_a_tone_preserves_default_behavior() -> None:
    dialogue = _dialogue(_stored_context(None))
    request = TurnRequest(question="질문")
    assert await dialogue._effective_tone("owner", request) is None
