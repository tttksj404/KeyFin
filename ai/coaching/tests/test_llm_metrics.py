"""Exercise measurements through the actual model adapter, including real TCP."""

# ruff: noqa: INP001
from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING, Literal, assert_never

import anyio
import httpx2
import pytest

from coaching_service.inference_metrics import InferenceTrace, capture_inference_metrics, measure_inference
from coaching_service.llm import OpenAICompatibleCoachModel, create_http_client
from coaching_service.llm_contract import EvidenceInput, ModelConfig
from tests.test_inference_metrics import ManualClock
from tests.test_llm import completion, model_server

if TYPE_CHECKING:
    from coaching_service.llm_contract import Operation


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def evidence() -> EvidenceInput:
    return EvidenceInput(question="어떤 자료를 확인하나요?", facts_json="{}")


@pytest.mark.anyio
@pytest.mark.parametrize("operation", ["route", "write"])
async def test_success_is_measured_through_real_tcp(operation: Literal["route", "write"]) -> None:
    # Given a real TCP endpoint and the production HTTP client factory.
    body = '{"mode":"finance"}' if operation == "route" else "확인할 자료를 알려 주세요."
    async with model_server(completion(body)) as endpoint:
        config = ModelConfig(endpoint_url=endpoint, token_preflight=False)
        async with create_http_client(config) as client:
            model = OpenAICompatibleCoachModel(config, client=client)
            # When the public adapter method runs inside a request observation scope.
            with capture_inference_metrics() as collector:
                match operation:
                    case "route":
                        result = await model.route(evidence())
                    case "write":
                        result = await model.write(evidence())
                    case unreachable:
                        assert_never(unreachable)
    # Then the valid public response has one transport measurement with no preflight.
    measurement, = collector.snapshot()
    assert result.source == "llm"
    assert measurement.operation == operation
    assert measurement.outcome == "success"
    assert measurement.token_preflight_ms is None
    assert measurement.generation_http_ms is not None
    assert measurement.limiter_wait_ms is not None
    assert measurement.total_ms >= measurement.generation_http_ms


@pytest.mark.anyio
async def test_preflight_rejection_has_no_generation_measurement() -> None:
    # Given a tokenizer that reports an input above its limit.
    paths: list[str] = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        paths.append(request.url.path)
        return httpx2.Response(200, json={
            "prompt_tokens": 8193, "max_input_tokens": 8192, "max_output_tokens": 1536,
            "request_sha256": hashlib.sha256(request.content).hexdigest(), "prompt_sha256": "a" * 64,
        })

    async with httpx2.AsyncClient(transport=httpx2.MockTransport(respond)) as client:
        model = OpenAICompatibleCoachModel(ModelConfig(endpoint_url="http://model.test"), client=client)
        # When the public adapter applies the real token-budget validation.
        with capture_inference_metrics() as collector:
            result = await model.write(evidence())
    # Then the safe rejection is distinct from a GPU/HTTP failure.
    measurement, = collector.snapshot()
    assert result.fallback_reason == "input_token_limit"
    assert measurement.outcome == "rejected"
    assert measurement.token_preflight_ms is not None
    assert measurement.generation_http_ms is None
    assert paths == ["/v1/tokenize"]


@pytest.mark.anyio
async def test_http_timeout_preserves_public_fallback_and_records_timeout() -> None:
    # Given a transport that times out at the generation boundary.
    def respond(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ReadTimeout("synthetic private URL must not enter metrics", request=request)

    async with httpx2.AsyncClient(transport=httpx2.MockTransport(respond)) as client:
        model = OpenAICompatibleCoachModel(
            ModelConfig(endpoint_url="http://model.test", token_preflight=False), client=client,
        )
        # When the public adapter handles the timeout.
        with capture_inference_metrics() as collector:
            result = await model.route(evidence())
    # Then the operational outcome agrees with the public fallback category.
    measurement, = collector.snapshot()
    assert result.fallback_reason == "read_timeout"
    assert measurement.outcome == "timeout"
    assert measurement.generation_http_ms is not None


@pytest.mark.anyio
async def test_cleanup_error_is_not_counted_as_success_and_next_request_has_capacity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    async def failing_close() -> None:
        raise RuntimeError("synthetic cleanup failure")

    def respond(_request: httpx2.Request) -> httpx2.Response:
        nonlocal calls
        calls += 1
        response = httpx2.Response(200, content=completion('{"mode":"finance"}'))
        if calls == 1:
            monkeypatch.setattr(response, "aclose", failing_close)
        return response

    async with httpx2.AsyncClient(transport=httpx2.MockTransport(respond)) as client:
        model = OpenAICompatibleCoachModel(
            ModelConfig(endpoint_url="http://model.test", token_preflight=False, max_concurrency=1),
            client=client,
        )
        with capture_inference_metrics() as collector:
            with pytest.raises(RuntimeError, match="synthetic cleanup failure"):
                _ = await model.route(evidence())
            result = await model.route(evidence())
    assert result.source == "llm"
    assert [measurement.outcome for measurement in collector.snapshot()] == ["failure", "success"]


@pytest.mark.anyio
async def test_cancellation_propagates_and_releases_capacity_for_next_request() -> None:
    # Given one available permit and a transport cancelled by its caller.
    calls = 0

    async def respond(_request: httpx2.Request) -> httpx2.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            cancellation.cancel()
            await anyio.lowlevel.checkpoint()
        return httpx2.Response(200, content=completion('{"mode":"finance"}'))

    async with httpx2.AsyncClient(transport=httpx2.MockTransport(respond)) as client:
        model = OpenAICompatibleCoachModel(
            ModelConfig(endpoint_url="http://model.test", token_preflight=False, max_concurrency=1),
            client=client,
        )
        # When generation is cancelled and the same adapter immediately handles another request.
        with capture_inference_metrics() as collector:
            with anyio.CancelScope() as cancellation:
                _ = await model.route(evidence())
            result = await model.route(evidence())
    # Then cancellation was not converted to an answer and no permit leaked.
    assert cancellation.cancelled_caught
    assert result.source == "llm"
    assert [measurement.outcome for measurement in collector.snapshot()] == ["cancelled", "success"]


@pytest.mark.anyio
async def test_limiter_wait_and_generation_are_separate_under_contention(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given real limiter contention and a clock controlled only at transport boundaries.
    clock = ManualClock()
    first_generating, release_first, second_started = anyio.Event(), anyio.Event(), anyio.Event()
    calls = 0

    def timed(operation: Operation) -> InferenceTrace:
        return measure_inference(operation, clock=clock)

    monkeypatch.setattr("coaching_service.llm.measure_inference", timed)

    async def respond(_request: httpx2.Request) -> httpx2.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            first_generating.set()
            await release_first.wait()
        else:
            clock.advance(1)
        return httpx2.Response(200, content=completion('{"mode":"finance"}'))

    async with httpx2.AsyncClient(transport=httpx2.MockTransport(respond)) as client:
        model = OpenAICompatibleCoachModel(
            ModelConfig(endpoint_url="http://model.test", token_preflight=False, max_concurrency=1),
            client=client,
        )

        async def second() -> None:
            second_started.set()
            _ = await model.route(evidence())

        # When one request generates while the other waits on the capacity limiter.
        with capture_inference_metrics() as collector:
            async with anyio.create_task_group() as group:
                _ = group.start_soon(model.route, evidence())
                await first_generating.wait()
                _ = group.start_soon(second)
                await second_started.wait()
                # The second coroutine has no checkpoint between signalling and
                # attempting acquisition, so it is now queued behind generation.
                clock.advance(2)
                release_first.set()
    # Then queue time is not counted as generation or vice versa.
    first, second_measurement = collector.snapshot()
    assert (first.limiter_wait_ms, first.generation_http_ms, first.total_ms) == (0, 2000, 2000)
    assert (
        second_measurement.limiter_wait_ms,
        second_measurement.generation_http_ms,
        second_measurement.total_ms,
    ) == (2000, 1000, 3000)


@pytest.mark.anyio
async def test_observer_off_and_on_return_identical_public_answers() -> None:
    # Given a deterministic valid generation response.
    def respond(_request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, content=completion('{"mode":"finance"}'))

    async with httpx2.AsyncClient(transport=httpx2.MockTransport(respond)) as client:
        model = OpenAICompatibleCoachModel(
            ModelConfig(endpoint_url="http://model.test", token_preflight=False), client=client,
        )
        # When observation is enabled for one of two otherwise identical calls.
        without_observation = await model.route(evidence())
        with capture_inference_metrics() as collector:
            with_observation = await model.route(evidence())
    # Then observation has no effect on answer data or provenance.
    assert with_observation == without_observation
    assert len(collector.snapshot()) == 1
