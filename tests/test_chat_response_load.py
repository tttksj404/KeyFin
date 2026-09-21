"""Concurrent live-benchmark aggregation is tested without a deployed model endpoint."""

# ruff: noqa: INP001
from __future__ import annotations

from datetime import date

import httpx2
import pytest

from benchmarks.coaching.chat_response.cases import CASES
from benchmarks.coaching.chat_response.load import (
    Target,
    case_digest,
    measure_condition,
    parse_server_timing,
)
from coaching_service.chat_answers import ChatAnswer
from coaching_service.schemas import JsonDocument


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def test_timing_parser_keeps_only_payload_free_documented_fields() -> None:
    parsed = parse_server_timing("api;dur=1.25, generation;dur=0.75, trace_id;dur=99, malformed")

    assert parsed == {"api": 1.25, "generation": 0.75}


@pytest.mark.anyio
async def test_concurrent_condition_aggregates_contract_and_trace_without_response_artifacts() -> None:
    case = next(row for row in CASES if row.id == "no_twin_compound")
    answer = ChatAnswer(
        id="answer",
        answer_type="finance_education",
        status="answered",
        text="복리는 이자에도 이자가 붙는 계산 방식입니다.",
        wording_source="template",
        model="not_called",
        evidence=JsonDocument({"references": [{"id": "compound_interest"}]}),
        created_at=0,
    ).model_dump(mode="json")
    sessions = 0

    def respond(request: httpx2.Request) -> httpx2.Response:
        nonlocal sessions
        if request.url.path == "/v1/sessions":
            sessions += 1
            return httpx2.Response(200, json={"id": f"session-{sessions}"})
        if request.url.path.endswith("/messages"):
            return httpx2.Response(
                200,
                json=answer,
                headers={"server-timing": "api;dur=1.0, model;dur=0.8, generation;dur=0.7"},
            )
        raise AssertionError("unexpected_load_request")

    async with httpx2.AsyncClient(transport=httpx2.MockTransport(respond)) as client:
        result = await measure_condition(
            Target(client, "http://service.test", "test-token", date(2026, 9, 9), "without_twin", 2),
            (case,),
            2,
            1,
        )

    assert sessions == 2
    assert result["requests"] == 2
    assert result["http_ok"] == 2
    assert result["semantic_ok"] == 2
    assert result["timing_phase_observations"] == {
        "fdt": 0,
        "fdt_compute": 0,
        "fdt_wait": 0,
        "generation": 2,
        "limiter": 0,
        "model": 2,
        "tokenize": 0,
    }
    assert len(case_digest((case,))) == 64
