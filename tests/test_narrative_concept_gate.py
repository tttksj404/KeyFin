# ruff: noqa: INP001
"""Narrative general-concept requests must reach the same catalog gate as a definition."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Final

import httpx2
import pytest
from pydantic import JsonValue, SecretStr

from coaching_service.api import create_app
from coaching_service.finance_knowledge import (
    deterministic_finance_status,
    deterministic_finance_wording,
    finance_evidence,
)
from coaching_service.llm import OpenAICompatibleCoachModel
from coaching_service.llm_contract import ModelConfig
from coaching_service.schemas import JsonDocument, Session
from coaching_service.settings import Client, Settings

if TYPE_CHECKING:
    from pathlib import Path

TOKEN: Final = "test-only-narrative-gate-token-0000000000"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def completion(content: str) -> httpx2.Response:
    return httpx2.Response(200, json={"choices": [{
        "message": {"content": content}, "finish_reason": "stop",
    }]})


async def new_session(client: httpx2.AsyncClient) -> str:
    response = await client.post("/v1/sessions", json={}, headers={"Idempotency-Key": "session"})
    assert response.status_code == 200, response.text
    return Session.model_validate_json(response.content).id


def response_object(content: bytes) -> dict[str, JsonValue]:
    root = JsonDocument.model_validate_json(content).root
    assert isinstance(root, dict)
    return root


@pytest.mark.parametrize(("question", "reference_id"), [
    ("복리의 핵심 구조를 짧게 이해하고 싶어.", "compound_interest"),
    ("정기예금과 정기적금의 핵심 구조를 짧게 이해하고 싶어.", "deposits"),
    ("신용카드 리볼빙을 판단하기 전에 알아야 할 기본 개념을 정리해줘.", "revolving"),
    ("고정금리와 변동금리이 생활 금융에서 어떤 역할을 하는지 쉽게 풀어줘.", "interest_types"),
    ("채권을 생활 금융의 관점에서 차분히 풀어줘.", "bonds"),
    ("현금흐름 예산의 구조를 간단한 말로 풀어줘.", "cash_flow_budget"),
    ("명목금리·실질금리와 물가을 처음 배울 때 알아둘 내용을 정리해줘.", "real_interest"),
    ("고정금리 변동금리 적용 구조", "interest_types"),
])
def test_narrative_concept_request_selects_single_stable_fact(question: str, reference_id: str) -> None:
    """A narrative paraphrase without a definition suffix must still resolve deterministically."""
    evidence = finance_evidence(question)

    wording = deterministic_finance_wording(evidence)

    assert wording is not None
    assert wording.reference_ids == (reference_id,)
    assert wording.source == "template"


@pytest.mark.parametrize("question", [
    "복리의 핵심 구조를 짧게 이해하고 싶어.",
])
def test_narrative_concept_request_bypasses_model_over_http(question: str, tmp_path: Path) -> None:
    """The narrative gate must reach the same no-model HTTP contract as the definition path."""
    calls = 0

    def unexpected_model_call(_: httpx2.Request) -> httpx2.Response:
        nonlocal calls
        calls += 1
        raise AssertionError("a narrative catalog concept request must not call the model")

    config = ModelConfig(endpoint_url="http://model.test", token_preflight=False)

    async def run() -> dict[str, JsonValue]:
        async with httpx2.AsyncClient(transport=httpx2.MockTransport(unexpected_model_call)) as model_client:
            app = create_app(Settings(
                database=tmp_path / "narrative.sqlite3",
                clients=(Client(user_id="demo", token=SecretStr(TOKEN)),),
            ), OpenAICompatibleCoachModel(config, client=model_client))
            async with httpx2.AsyncClient(
                transport=httpx2.ASGITransport(app=app), base_url="http://test",
                headers={"Authorization": "Bearer " + TOKEN},
            ) as client:
                response = await client.post(
                    f"/v1/sessions/{await new_session(client)}/messages",
                    json={"question": question},
                    headers={"Idempotency-Key": "narrative-gate"},
                )
        assert response.status_code == 200, response.text
        return response_object(response.content)

    answer = asyncio.run(run())
    assert answer["model"] == "not_called"
    assert answer["wording_source"] == "template"
    assert calls == 0


@pytest.mark.parametrize("question", [
    "내 복리 이자 계산해줘",
    "내 복리 구조를 이해하고 싶어",
    "내 대출 계약의 중도상환수수료 구조를 정리해줘",
])
def test_personal_narrative_still_reaches_model(question: str) -> None:
    """Personal possessive language must never be admitted through the new anchor."""
    evidence = finance_evidence(question)

    assert deterministic_finance_wording(evidence) is None
    assert deterministic_finance_status(evidence) is None


@pytest.mark.parametrize(("question", "expect_needs_source"), [
    # Asking where today's highest rate is needs a current source, not a definition.
    ("지금 복리 이자율 제일 높은 곳", True),
    ("지금 금리가 가장 높은 예금의 구조를 이해하고 싶어", True),
    ("복리 예금 세후 이자 계산 구조를 정리해줘", True),
    ("2026년 복리 구조 정리해줘", False),
    ("ELS 구조를 이해하고 싶어", True),
])
def test_volatile_narrative_never_becomes_a_stable_answer(question: str, expect_needs_source: bool) -> None:
    """Volatile/decision or numeric narrative wording must not gain a stable template answer."""
    evidence = finance_evidence(question)

    assert deterministic_finance_wording(evidence) is None
    status = deterministic_finance_status(evidence)
    if expect_needs_source:
        assert status is not None
        assert status.answer_status == "needs_source"
        assert status.reference_ids == ()
    else:
        assert status is None


@pytest.mark.parametrize("question", [
    "블록체인의 핵심 구조를 짧게 이해하고 싶어",
    "토성 고리의 핵심 구조를 정리해줘",
    "이자의 핵심 구조를 짧게 이해하고 싶어",
])
def test_no_catalog_or_weak_anchor_narrative_stays_on_model(question: str) -> None:
    """A weak (G1-failing) or non-finance anchor must never resolve without the model."""
    evidence = finance_evidence(question)

    assert deterministic_finance_wording(evidence) is None


@pytest.mark.parametrize("question", [
    "복리와 단리의 핵심 구조를 정리해줘",
    "예금과 채권 위험의 구조를 정리해줘",
    "ETF와 채권의 구조를 정리해줘",
    "채권 듀레이션과 신용 위험의 핵심 구조를 정리해줘",
])
def test_multi_concept_narrative_never_returns_a_partial_answer(question: str) -> None:
    """A conjoined narrative subject must cover every named component or fall through."""
    evidence = finance_evidence(question)

    assert deterministic_finance_wording(evidence) is None


def test_existing_multi_concept_grammar_pair_is_unchanged() -> None:
    """Regression pin: the pre-existing comparison grammar must keep resolving both facts."""
    evidence = finance_evidence("채권 듀레이션과 신용 위험을 함께 이해할 때 핵심을 알려줘.")

    wording = deterministic_finance_wording(evidence)

    assert wording is not None
    assert wording.reference_ids == ("bond_duration", "bond_credit_risk")
