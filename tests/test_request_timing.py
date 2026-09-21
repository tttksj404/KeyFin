"""The optional latency trace exposes no financial or prompt payload."""

# ruff: noqa: INP001

from __future__ import annotations

import anyio
import httpx2
import pytest
from fastapi import FastAPI, HTTPException

from coaching_service.inference_metrics import measure_inference
from coaching_service.request_timing import RequestTiming


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def application() -> FastAPI:
    app = FastAPI()
    app.add_middleware(RequestTiming)

    async def traced() -> dict[str, str]:
        # Deliberately include content which must never reach the timing header.
        private_question = "개인 금융 질문 원문은 timing header에 넣으면 안 됩니다."
        with measure_inference("route") as trace:
            with trace.phase("limiter_wait"):
                await anyio.lowlevel.checkpoint()
            with trace.phase("token_preflight"):
                await anyio.lowlevel.checkpoint()
            with trace.phase("generation_http"):
                await anyio.lowlevel.checkpoint()
        return {"status": "ok", "question": private_question}

    async def rejected() -> None:
        raise HTTPException(status_code=422, detail="invalid request")

    app.add_api_route("/traced", traced, methods=["GET"])
    app.add_api_route("/rejected", rejected, methods=["GET"])
    return app


@pytest.mark.anyio
async def test_request_timing_is_opt_in_and_reports_only_aggregate_phase_durations() -> None:
    # Given an API route that records model phases in the active request context.
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=application()), base_url="http://test"
    ) as client:
        # When no trace header is supplied.
        without_trace = await client.get("/traced")
        # And the caller explicitly requests the safe timing trace.
        with_trace = await client.get("/traced", headers={"X-Coaching-Trace": "1"})
    # Then normal responses have no operational header, while opt-in traces describe
    # only aggregate timing phases and never include the route operation or payload.
    assert without_trace.status_code == 200
    assert "server-timing" not in without_trace.headers
    assert with_trace.status_code == 200
    timing = with_trace.headers["server-timing"]
    metrics = ("api;dur=", "model;dur=", "limiter;dur=", "tokenize;dur=", "generation;dur=")
    assert all(metric in timing for metric in metrics)
    assert "route" not in timing
    assert "개인 금융 질문" not in timing


@pytest.mark.anyio
async def test_request_timing_captures_handled_error_without_enabling_other_header_values() -> None:
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=application()), base_url="http://test"
    ) as client:
        # Given a value other than the exact opt-in token.
        disabled = await client.get("/rejected", headers={"X-Coaching-Trace": "true"})
        # When an explicitly traced request ends in an HTTP error.
        traced = await client.get("/rejected", headers={"X-Coaching-Trace": "1"})
    # Then the opt-in rule stays strict and error traces still carry total API time.
    assert disabled.status_code == 422
    assert "server-timing" not in disabled.headers
    assert traced.status_code == 422
    assert traced.headers["server-timing"].startswith("api;dur=")
