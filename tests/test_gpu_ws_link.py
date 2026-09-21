"""COACH_GPU_LINK_MODE=ws: the outbound GPU tunnel must match today's loopback contract.

Mirrors the proven scratchpad POC's five checks -- (a) roundtrip, (b) concurrency,
(c) drop+auto-reconnect+fallback, (d) auth reject, (e) no-hang timeout+fallback -- but
against the REAL production pieces: ``coaching_service.gpu_link`` (API side, run behind
a real uvicorn server so ``scripts.gpu_ws_worker``'s real ``websockets`` client dials
into it) and ``scripts.gpu_ws_worker.Worker`` (worker side, dispatching into the real
``WorkerExecution``/tokenize+complete path ``gpu_worker.create_app`` uses for loopback).
No GPU or network beyond localhost is required.
"""
# ruff: noqa: INP001

import asyncio
import contextlib
import time
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

import anyio
import pytest
import uvicorn
from fastapi import FastAPI

from coaching_service.gpu_link import (
    GpuLinkFailure,
    GpuLinkOk,
    GpuLinkRegistry,
    canonical_request_sha256,
    register_gpu_link,
)
from coaching_service.llm import OpenAICompatibleCoachModel
from coaching_service.llm_contract import EvidenceInput, ModelConfig
from scripts.gpu_execution import WorkerExecution
from scripts.gpu_worker import validate_prompt_count
from scripts.gpu_ws_worker import Worker
from scripts.gpu_ws_worker import canonical_request_sha256 as worker_canonical_request_sha256
from tests.test_gpu_batching import TOKEN, AsyncBackend, BatchBackend, body


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


async def wait_until(
    predicate: Callable[[], bool], timeout: float = 5.0, interval: float = 0.02,  # noqa: ASYNC109
) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        await anyio.sleep(interval)
    return False


@asynccontextmanager
async def running_link(execution: WorkerExecution) -> AsyncIterator[tuple[GpuLinkRegistry, str]]:
    """Start a REAL uvicorn server hosting the gpu_link WS route on an OS-assigned port."""
    app = FastAPI()
    registry = register_gpu_link(app, expected_token=TOKEN)
    config = uvicorn.Config(app, host="127.0.0.1", port=0, log_level="warning")
    server = uvicorn.Server(config)
    server_task = asyncio.create_task(server.serve())
    try:
        assert await wait_until(lambda: server.started, timeout=5), "test_server_did_not_start"
        port = server.servers[0].sockets[0].getsockname()[1]
        yield registry, f"ws://127.0.0.1:{port}/internal/gpu-link"
    finally:
        server.should_exit = True
        with anyio.move_on_after(5):
            await server_task


@asynccontextmanager
async def running_worker(
    url: str, execution: WorkerExecution, backend: object, *, token: str = TOKEN,
) -> AsyncIterator[Worker]:
    worker = Worker(url, token, execution, backend, {"model_tag": "fixture"})  # type: ignore[arg-type]
    task = asyncio.create_task(worker.run_forever())
    try:
        yield worker
    finally:
        worker.stop_flag = True
        _ = task.cancel()
        with contextlib.suppress(asyncio.CancelledError), anyio.move_on_after(2):
            await task


def new_batch_execution() -> tuple[WorkerExecution, BatchBackend]:
    backend = BatchBackend()
    return WorkerExecution(backend, None, 8, validate_prompt_count), backend


@pytest.mark.anyio
async def test_a_roundtrip_over_ws() -> None:
    """(a) A single request/response round-trips end to end over the WS tunnel."""
    execution, backend = new_batch_execution()
    async with running_link(execution) as (registry, url), running_worker(url, execution, backend):
        assert await wait_until(lambda: registry.worker_connected, timeout=5)
        outcome = await registry.submit(
            "complete", {"body": body("hello"), "expected_prompt_sha256": None}, timeout=5,
        )
        assert isinstance(outcome, GpuLinkOk)
        assert outcome.result["choices"][0]["message"]["content"] == "hello"  # type: ignore[index]
        assert outcome.result["usage"]["prompt_tokens"] == len("hello")  # type: ignore[index]


@pytest.mark.anyio
async def test_a_roundtrip_through_the_llm_client_including_token_preflight() -> None:
    """(a) End to end through OpenAICompatibleCoachModel, exactly as llm.py would call it."""

    class FixedTextBackend(BatchBackend):
        """Echoes a fixed, wording-problem-clean reply instead of the request text."""

        def complete_batch(self, requests: list[object]) -> list[object]:
            from scripts.gpu_worker import Generated  # noqa: PLC0415 - test-local, avoids a module cycle.

            return [Generated(text="확인해 주세요.", prompt_tokens=1, completion_tokens=1, seconds=0.01)
                    for _ in requests]

    backend = FixedTextBackend()
    execution = WorkerExecution(backend, None, 8, validate_prompt_count)
    async with running_link(execution) as (registry, url), running_worker(url, execution, backend):
        assert await wait_until(lambda: registry.worker_connected, timeout=5)
        config = ModelConfig(
            endpoint_url="http://ignored.invalid/v1/chat/completions", token_preflight=True, model="fixture",
        )
        model = OpenAICompatibleCoachModel(config, gpu_link_submit=registry.submit)
        evidence = EvidenceInput(purpose="coaching", question="", facts_json='{"a":1}')
        wording = await model.write(evidence)
        assert wording.source == "llm"
        assert wording.fallback_reason is None
        assert wording.text == "확인해 주세요."


@pytest.mark.anyio
async def test_a_roundtrip_over_ws_needs_no_endpoint_url() -> None:
    """ws 모드에선 endpoint_url 없이도 추론이 disabled로 막히지 않고 왕복해야 한다.

    ws 역터널이 전송을 대신하므로 endpoint_url은 불필요하다. 이전에는 endpoint_url이
    None이면 _execute가 "disabled"로 즉시 폴백해, 호출자가 더미 URL로 우회해야 했다.
    """

    class FixedTextBackend(BatchBackend):
        def complete_batch(self, requests: list[object]) -> list[object]:
            from scripts.gpu_worker import Generated  # noqa: PLC0415 - test-local, avoids a module cycle.

            return [Generated(text="확인해 주세요.", prompt_tokens=1, completion_tokens=1, seconds=0.01)
                    for _ in requests]

    backend = FixedTextBackend()
    execution = WorkerExecution(backend, None, 8, validate_prompt_count)
    async with running_link(execution) as (registry, url), running_worker(url, execution, backend):
        assert await wait_until(lambda: registry.worker_connected, timeout=5)
        config = ModelConfig(endpoint_url=None, token_preflight=False, model="fixture")
        model = OpenAICompatibleCoachModel(config, gpu_link_submit=registry.submit)
        evidence = EvidenceInput(purpose="coaching", question="", facts_json='{"a":1}')
        wording = await model.write(evidence)
        assert wording.source == "llm"
        assert wording.fallback_reason is None
        assert wording.text == "확인해 주세요."


@pytest.mark.anyio
async def test_b_concurrent_requests_do_not_cross_talk() -> None:
    """(b) N in-flight requests on one multiplexed socket resolve to their OWN id."""
    backend = AsyncBackend()
    execution = WorkerExecution(
        backend, None, 1, validate_prompt_count, async_complete=backend.complete_async,
    )
    async with running_link(execution) as (registry, url), running_worker(url, execution, backend):
        assert await wait_until(lambda: registry.worker_connected, timeout=5)
        texts = [f"concurrent-{i}" for i in range(8)]

        async def one(text: str) -> tuple[str, object]:
            outcome = await registry.submit(
                "complete", {"body": body(text), "expected_prompt_sha256": None}, timeout=5,
            )
            return text, outcome

        results = await asyncio.gather(*[one(text) for text in texts])
        for text, outcome in results:
            assert isinstance(outcome, GpuLinkOk), (text, outcome)
            assert outcome.result["choices"][0]["message"]["content"] == text  # type: ignore[index]
        assert backend.maximum_active >= 2


@pytest.mark.anyio
async def test_c_drop_triggers_fallback_then_auto_reconnect_resumes() -> None:
    """(c) A mid-flight drop fails fast to fallback; auto-reconnect then resumes traffic."""
    execution, backend = new_batch_execution()
    async with running_link(execution) as (registry, url), running_worker(url, execution, backend) as worker:
        assert await wait_until(lambda: registry.worker_connected, timeout=5)
        first_connect_count = worker.connect_count

        current = worker.current_ws
        assert current is not None
        await current.close()

        assert await wait_until(lambda: not registry.worker_connected, timeout=3)
        gap_outcome = await registry.submit(
            "complete", {"body": body("during-gap"), "expected_prompt_sha256": None}, timeout=2,
        )
        assert isinstance(gap_outcome, GpuLinkFailure)
        assert gap_outcome.reason == "worker_unavailable"

        assert await wait_until(lambda: worker.connect_count > first_connect_count, timeout=10)
        assert await wait_until(lambda: registry.worker_connected, timeout=5)

        resumed_outcome = await registry.submit(
            "complete", {"body": body("after-reconnect"), "expected_prompt_sha256": None}, timeout=5,
        )
        assert isinstance(resumed_outcome, GpuLinkOk)
        assert resumed_outcome.result["choices"][0]["message"]["content"] == "after-reconnect"  # type: ignore[index]


@pytest.mark.anyio
async def test_d_wrong_token_is_rejected() -> None:
    """(d) A worker presenting the wrong bearer token is refused, never registered."""
    execution, backend = new_batch_execution()
    async with running_link(execution) as (registry, url):
        bad_worker = Worker(url, "wrong-token-entirely", execution, backend, {"model_tag": "fixture"})
        with pytest.raises(Exception):  # noqa: B017, PT011 - websockets raises its own status-code error type.
            await bad_worker.run_once()
        assert registry.stats["rejects"] >= 1
        assert not registry.worker_connected


@pytest.mark.anyio
async def test_e_no_worker_connected_is_immediate_fallback_no_hang() -> None:
    """(e) Submitting with no worker connected never waits -- immediate fallback."""
    execution, _backend = new_batch_execution()
    async with running_link(execution) as (registry, _url):
        started = time.monotonic()
        submit_call = registry.submit(
            "complete", {"body": body("no-worker"), "expected_prompt_sha256": None}, timeout=5,
        )
        outcome = await asyncio.wait_for(submit_call, timeout=1)
        elapsed = time.monotonic() - started
        assert isinstance(outcome, GpuLinkFailure)
        assert outcome.reason == "worker_unavailable"
        assert elapsed < 0.5


@pytest.mark.anyio
async def test_e_a_stalled_worker_times_out_into_fallback_not_a_hang() -> None:
    """(e) A worker that never answers a specific request times out -- no hang."""
    execution, backend = new_batch_execution()

    class SilentWorker(Worker):
        async def _handle_request(self, ws: object, message: dict[str, object]) -> None:
            # Deliberately never respond: exercises the API's own per-call deadline.
            return

    async with running_link(execution) as (registry, url):
        worker = SilentWorker(url, TOKEN, execution, backend, {"model_tag": "fixture"})
        task = asyncio.create_task(worker.run_forever())
        try:
            assert await wait_until(lambda: registry.worker_connected, timeout=5)
            started = time.monotonic()
            outcome = await asyncio.wait_for(
                registry.submit(
                    "complete", {"body": body("stall"), "expected_prompt_sha256": None}, timeout=0.3,
                ),
                timeout=3,
            )
            elapsed = time.monotonic() - started
            assert isinstance(outcome, GpuLinkFailure)
            assert outcome.reason == "gpu_link_timeout"
            assert elapsed < 2
        finally:
            worker.stop_flag = True
            _ = task.cancel()
            with contextlib.suppress(asyncio.CancelledError), anyio.move_on_after(2):
                await task


def test_canonical_request_sha256_matches_between_api_and_worker_sides() -> None:
    """The API-side and worker-side copies of this hash function must never drift."""
    samples: list[dict[str, object]] = [
        {"model": "fixture", "messages": [{"role": "user", "content": "hi"}], "max_tokens": 16},
        {"z": 1, "a": [1, 2, 3], "nested": {"b": None, "a": "x"}},
    ]
    for sample in samples:
        assert canonical_request_sha256(sample) == worker_canonical_request_sha256(sample)
