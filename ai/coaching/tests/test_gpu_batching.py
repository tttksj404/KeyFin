"""Concurrent requests must batch without mixing responses or weakening token checks."""
# ruff: noqa: INP001

import hashlib
import threading

import anyio
import httpx2
import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from scripts.gpu_batching import BatchDispatcher, Pending
from scripts.gpu_worker import CompletionRequest, Generated, Metadata, PromptCount, create_app


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class BatchBackend:
    metadata = Metadata(model="fixture", model_id="fixture", revision="a" * 40,
                        config_sha256="b" * 64, runtime_sha256="c" * 64, quantization="fixture")

    def __init__(self) -> None:
        self.batches: list[list[str]] = []
        self.entered = threading.Event()
        self.release = threading.Event()
        self.block = False

    def measure(self, request: CompletionRequest) -> PromptCount:
        text = request.messages[0].content
        return PromptCount(prompt_tokens=len(text), prompt_sha256=hashlib.sha256(text.encode()).hexdigest())

    def complete(self, request: CompletionRequest) -> Generated:
        return self.complete_batch([request])[0]

    def complete_batch(self, requests: list[CompletionRequest]) -> list[Generated]:
        texts = [request.messages[0].content for request in requests]
        self.batches.append(texts)
        self.entered.set()
        if self.block:
            assert self.release.wait(timeout=3), "test_release_missing"
        return [Generated(text=text, prompt_tokens=len(text), completion_tokens=1, seconds=0.01)
                for text in texts]


class AsyncBackend(BatchBackend):
    """A fake continuous engine that records whether requests reach it independently."""

    def __init__(self) -> None:
        super().__init__()
        self.active = 0
        self.maximum_active = 0
        self.calls: list[str] = []

    async def complete_async(self, request: CompletionRequest) -> Generated:
        text = request.messages[0].content
        self.calls.append(text)
        self.active += 1
        self.maximum_active = max(self.maximum_active, self.active)
        try:
            # A checkpoint gives the other HTTP request a chance to enter. A
            # serialized outer GPU limiter would keep this maximum at one.
            await anyio.sleep(0.02)
        finally:
            self.active -= 1
        return Generated(text=text, prompt_tokens=len(text), completion_tokens=1, seconds=0.01)


TOKEN = "synthetic-batching-test-worker-token"
HEADERS = {"Authorization": "Bearer " + TOKEN}


def body(
    text: str,
    max_tokens: int = 32,
    *,
    seed: int | None = None,
    schema: dict[str, object] | None = None,
) -> dict[str, object]:
    request: dict[str, object] = {
        "model": "fixture",
        "messages": [{"role": "user", "content": text}],
        "max_tokens": max_tokens,
    }
    if seed is not None:
        request["seed"] = seed
    if schema is not None:
        request["response_format"] = {
            "type": "json_schema",
            "json_schema": {"name": "fixture", "schema": schema},
        }
    return request


@pytest.mark.anyio
async def test_concurrent_requests_share_generation_and_preserve_each_response() -> None:
    # Given: a worker that can generate two independent replies in one batch.
    backend = BatchBackend()
    app = create_app(backend, TOKEN, batch_complete=backend.complete_batch, max_batch_size=2)
    replies: dict[str, httpx2.Response] = {}
    async with app.router.lifespan_context(app), httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=app), base_url="http://test",
    ) as client:
        # When: two different prompts arrive together.
        async def send(text: str) -> None:
            replies[text] = await client.post("/v1/chat/completions", headers=HEADERS, json=body(text))
        async with anyio.create_task_group() as group:
            group.start_soon(send, "first")
            group.start_soon(send, "second")
    # Then: a single generation returns each caller's own text and token counts.
    assert len(backend.batches) == 1
    assert len(backend.batches[0]) == 2
    assert all(reply.status_code == 200 and reply.json()["choices"][0]["message"]["content"] == text
               and reply.json()["usage"]["prompt_tokens"] == len(text) for text, reply in replies.items())


@pytest.mark.anyio
async def test_async_engine_requests_do_not_wait_for_an_outer_completion_batch() -> None:
    """Native continuous scheduling must not be re-serialized by the HTTP worker."""
    backend = AsyncBackend()
    app = create_app(backend, TOKEN, async_complete=backend.complete_async)
    replies: dict[str, httpx2.Response] = {}
    async with app.router.lifespan_context(app), httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=app), base_url="http://test",
    ) as client:
        async def send(text: str) -> None:
            replies[text] = await client.post("/v1/chat/completions", headers=HEADERS, json=body(text))

        async with anyio.create_task_group() as group:
            group.start_soon(send, "first")
            group.start_soon(send, "second")

    assert sorted(backend.calls) == ["first", "second"]
    assert backend.maximum_active == 2
    assert backend.batches == []
    assert all(reply.status_code == 200 for reply in replies.values())


def test_async_engine_cannot_be_wrapped_in_an_external_batch_dispatcher() -> None:
    backend = AsyncBackend()

    with pytest.raises(ValueError, match="external_batching_and_async_generation_are_incompatible"):
        _ = create_app(
            backend,
            TOKEN,
            batch_complete=backend.complete_batch,
            async_complete=backend.complete_async,
            max_batch_size=2,
        )


@pytest.mark.anyio
async def test_worker_admits_a_bounded_generation_seed_without_changing_the_response_contract() -> None:
    """The experiment field must cross the HTTP boundary without becoming an output field."""
    backend = BatchBackend()
    app = create_app(backend, TOKEN, batch_complete=backend.complete_batch, max_batch_size=2)
    request = body("seeded", seed=715)
    async with app.router.lifespan_context(app), httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=app), base_url="http://test",
    ) as client:
        response = await client.post("/v1/chat/completions", headers=HEADERS, json=request)
    assert response.status_code == 200
    assert CompletionRequest.model_validate(request).seed == 715
    assert "seed" not in response.json()


@pytest.mark.parametrize("seed", [-1, 4_294_967_296])
def test_worker_rejects_generation_seeds_outside_the_explicit_unsigned_range(seed: int) -> None:
    """Malformed experiment controls must fail before they can reach a shared decoder."""
    with pytest.raises(ValidationError):
        CompletionRequest.model_validate(body("invalid", seed=seed))


@pytest.mark.anyio
async def test_tokenization_does_not_wait_for_an_active_generation() -> None:
    # Given: a running GPU generation held by a deterministic event.
    backend = BatchBackend()
    backend.block = True
    app = create_app(backend, TOKEN, batch_complete=backend.complete_batch, max_batch_size=2)
    async with app.router.lifespan_context(app), httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=app), base_url="http://test",
    ) as client:
        async def generate() -> None:
            response = await client.post("/v1/chat/completions", headers=HEADERS, json=body("active"))
            assert response.status_code == 200
        async with anyio.create_task_group() as group:
            group.start_soon(generate)
            assert await anyio.to_thread.run_sync(backend.entered.wait, 2)
            try:
                # When: a different request asks for a CPU token count.
                with anyio.fail_after(1):
                    counted = await client.post("/v1/tokenize", headers=HEADERS, json=body("count"))
                # Then: it finishes while generation is still blocked.
                assert counted.status_code == 200
                assert counted.json()["prompt_tokens"] == 5
            finally:
                backend.release.set()


@pytest.mark.parametrize(("second_limit", "second_length", "compatible"), [
    (32, 10, True), (64, 10, False), (32, 8192, False),
])
def test_batch_preserves_output_limit_and_padded_token_budget(
    second_limit: int, second_length: int, compatible: bool,
) -> None:
    backend = BatchBackend()
    dispatcher = BatchDispatcher(backend.complete_batch, 4)
    first = Pending(CompletionRequest.model_validate(body("first")), 10)
    second = Pending(CompletionRequest.model_validate(body("second", second_limit)), second_length)
    assert dispatcher.compatible([first], second) is compatible


@pytest.mark.parametrize(
    ("first_seed", "second_seed", "compatible"),
    [(None, None, True), (715, 715, True), (715, 716, False), (None, 715, False)],
)
def test_batch_never_mixes_generation_seeds(
    first_seed: int | None, second_seed: int | None, compatible: bool,
) -> None:
    """A decoder sampling parameter is batch-wide, so differently seeded requests stay separate."""
    backend = BatchBackend()
    dispatcher = BatchDispatcher(backend.complete_batch, 4)
    first = Pending(CompletionRequest.model_validate(body("first", seed=first_seed)), 10)
    second = Pending(CompletionRequest.model_validate(body("second", seed=second_seed)), 10)
    assert dispatcher.compatible([first], second) is compatible


def test_structured_decoder_batch_never_mixes_response_formats() -> None:
    """A grammar-constrained decoder receives only requests sharing one response format."""
    backend = BatchBackend()
    dispatcher = BatchDispatcher(backend.complete_batch, 4, require_matching_response_format=True)
    first = Pending(
        CompletionRequest.model_validate(body(
            "first", schema={"type": "object", "properties": {"mode": {"type": "string"}}},
        )),
        10,
    )
    second = Pending(
        CompletionRequest.model_validate(body(
            "second", schema={"type": "object", "properties": {"fact_ids": {"type": "array"}}},
        )),
        10,
    )

    assert dispatcher.compatible([first], second) is False


@pytest.mark.anyio
async def test_failed_batch_wakes_every_caller_and_next_batch_can_recover() -> None:
    calls = 0

    def complete(requests: list[CompletionRequest]) -> list[Generated]:
        nonlocal calls
        calls += 1
        if calls == 1:
            # Wrong output cardinality must fail the entire batch, including its first item.
            return []
        return [Generated(text="recovered", prompt_tokens=1, completion_tokens=1, seconds=0.01)]

    dispatcher = BatchDispatcher(complete, 2)
    failed = [Pending(CompletionRequest.model_validate(body(text)), 1) for text in ("a", "b")]
    await dispatcher.generate(failed)
    assert all(item.ready.is_set() and isinstance(item.result, HTTPException)
               and item.result.status_code == 503 for item in failed)
    recovered = Pending(CompletionRequest.model_validate(body("c")), 1)
    await dispatcher.generate([recovered])
    assert isinstance(recovered.result, Generated)
    assert recovered.result.text == "recovered"


@pytest.mark.anyio
async def test_cancelled_queued_request_is_not_generated_and_shutdown_wakes_waiters() -> None:
    backend = BatchBackend()
    dispatcher = BatchDispatcher(backend.complete_batch, 2)
    skipped = Pending(CompletionRequest.model_validate(body("cancelled")), 1, cancelled=True)
    live = Pending(CompletionRequest.model_validate(body("live")), 1)
    dispatcher.sender.send_nowait(skipped)
    dispatcher.sender.send_nowait(live)
    waiting = Pending(CompletionRequest.model_validate(body("waiting")), 1)
    dispatcher.pending.append(waiting)
    async with anyio.create_task_group() as group:
        await group.start(dispatcher.run)
        with anyio.fail_after(2):
            await live.ready.wait()
        group.cancel_scope.cancel()
    assert backend.batches == [["live"]]
    assert waiting.ready.is_set()
    assert not dispatcher.running


@pytest.mark.anyio
async def test_batch_mode_rejects_long_input_before_generation() -> None:
    backend = BatchBackend()
    app = create_app(backend, TOKEN, batch_complete=backend.complete_batch, max_batch_size=2)
    async with app.router.lifespan_context(app), httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=app), base_url="http://test",
    ) as client:
        response = await client.post("/v1/chat/completions", headers=HEADERS, json=body("x" * 8193))
    assert response.status_code == 413
    assert response.json()["detail"] == "input_token_limit"
    assert backend.batches == []
