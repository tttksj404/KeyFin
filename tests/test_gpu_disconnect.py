"""실제 ASGI 연결 종료가 대기 GPU 작업과 admission 슬롯을 해제하는지 검증한다."""
# ruff: noqa: INP001

import inspect
import json
from typing import TYPE_CHECKING, cast

import anyio
import httpx2
import pytest
from fastapi.routing import APIRoute
from starlette.types import Message, Scope

from scripts.gpu_worker import create_app
from tests.test_gpu_batching import HEADERS, TOKEN, BatchBackend, body

if TYPE_CHECKING:
    from scripts.gpu_execution import WorkerExecution


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def scope_for(raw: bytes) -> Scope:
    return {
        "type": "http", "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1", "method": "POST", "scheme": "http",
        "path": "/v1/chat/completions", "raw_path": b"/v1/chat/completions",
        "query_string": b"", "root_path": "",
        "headers": [(b"host", b"test"), (b"content-type", b"application/json"),
                    (b"content-length", str(len(raw)).encode()),
                    (b"authorization", ("Bearer " + TOKEN).encode())],
        "client": ("127.0.0.1", 1), "server": ("127.0.0.1", 80), "state": {},
    }


@pytest.mark.anyio
async def test_http_disconnect_cancels_queued_generation_and_returns_slot() -> None:
    backend = BatchBackend()
    backend.block = True
    app = create_app(backend, TOKEN, batch_complete=backend.complete_batch, max_batch_size=1)
    route = next(route for route in app.routes if isinstance(route, APIRoute)
                 and route.path == "/v1/chat/completions")
    execution = cast("WorkerExecution", inspect.getclosurevars(route.endpoint).nonlocals["execution"])
    raw = json.dumps(body("second")).encode()
    receive_calls = 0
    disconnected_done = anyio.Event()
    first_response: httpx2.Response | None = None

    async def receive() -> Message:
        nonlocal receive_calls
        receive_calls += 1
        if receive_calls == 1:
            return {"type": "http.request", "body": raw, "more_body": False}
        return {"type": "http.disconnect"}

    async def send(_message: Message) -> None:
        pass

    async def disconnected_request() -> None:
        try:
            await app(scope_for(raw), receive, send)
        finally:
            disconnected_done.set()

    async def first_request(client: httpx2.AsyncClient) -> None:
        nonlocal first_response
        first_response = await client.post("/v1/chat/completions", headers=HEADERS, json=body("first"))

    async with (
        app.router.lifespan_context(app),
        httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app), base_url="http://test") as client,
        anyio.create_task_group() as group,
    ):
        try:
            group.start_soon(first_request, client)
            assert await anyio.to_thread.run_sync(backend.entered.wait, 2)
            group.start_soon(disconnected_request)
            with anyio.move_on_after(1):
                await disconnected_done.wait()
            done_before_release = disconnected_done.is_set()
            receive_calls_before_release = receive_calls
            borrowed_before_release = execution.slots.statistics().borrowed_tokens
        finally:
            backend.release.set()

    assert first_response is not None
    assert first_response.status_code == 200
    assert done_before_release
    assert receive_calls_before_release >= 2
    assert borrowed_before_release == 1
    assert backend.batches == [["first"]]


@pytest.mark.anyio
async def test_disconnect_during_legacy_generation_discards_result_after_gpu_finishes() -> None:
    backend = BatchBackend()
    backend.block = True
    app = create_app(backend, TOKEN)
    route = next(route for route in app.routes if isinstance(route, APIRoute)
                 and route.path == "/v1/chat/completions")
    execution = cast("WorkerExecution", inspect.getclosurevars(route.endpoint).nonlocals["execution"])
    raw = json.dumps(body("active")).encode()
    receive_calls = 0
    disconnected = anyio.Event()
    request_done = anyio.Event()
    sent: list[Message] = []

    async def receive() -> Message:
        nonlocal receive_calls
        receive_calls += 1
        if receive_calls == 1:
            return {"type": "http.request", "body": raw, "more_body": False}
        assert await anyio.to_thread.run_sync(backend.entered.wait, 2)
        disconnected.set()
        return {"type": "http.disconnect"}

    async def send(message: Message) -> None:
        sent.append(message)

    async def invoke() -> None:
        try:
            await app(scope_for(raw), receive, send)
        finally:
            request_done.set()

    async with app.router.lifespan_context(app), anyio.create_task_group() as group:
        try:
            group.start_soon(invoke)
            with anyio.fail_after(2):
                await disconnected.wait()
            with anyio.move_on_after(0.1):
                await request_done.wait()
            done_before_gpu_release = request_done.is_set()
            borrowed_during_generation = execution.slots.statistics().borrowed_tokens
        finally:
            backend.release.set()

    statuses = [message["status"] for message in sent if message["type"] == "http.response.start"]
    assert receive_calls >= 2
    assert not done_before_gpu_release
    assert borrowed_during_generation == 1
    assert statuses == [499]
    assert backend.batches == [["active"]]
    assert execution.slots.statistics().borrowed_tokens == 0
