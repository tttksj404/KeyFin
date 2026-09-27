# /// script
# requires-python = ">=3.11"
# dependencies = ["anyio", "pydantic", "websockets", "fastapi"]
# ///
# How to run: imported by gpu_worker.py's main() when COACH_GPU_LINK_MODE=ws.
"""Outbound WS worker client for ``COACH_GPU_LINK_MODE=ws`` (see SPEC-ws-tunnel.md).

The GPU box is outbound-only: instead of ``gpu_worker.py``'s uvicorn server accepting
inbound loopback HTTP, this dials OUT to the coaching API's ``/internal/gpu-link``
WebSocket, sends ``ready``, then services ``request`` frames concurrently (dispatched
to tasks so one slow generation never blocks the recv loop) by calling the SAME
``WorkerExecution`` tokenize/complete logic ``gpu_worker.create_app`` uses for the
loopback HTTP path. Any drop triggers infinite exponential-backoff+jitter reconnection.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import random
import secrets
import time
from typing import TYPE_CHECKING, Final

import anyio
import websockets
from fastapi import HTTPException
from pydantic import ValidationError

if TYPE_CHECKING:
    from collections.abc import Callable

    from gpu_contracts import Backend
    from gpu_execution import WorkerExecution

if __package__:
    from . import gpu_contracts as contracts
    from .gpu_worker import INPUT_CHARACTER_LIMIT, generation_messages
else:
    import gpu_contracts as contracts  # type: ignore[no-redef]
    from gpu_worker import INPUT_CHARACTER_LIMIT, generation_messages  # type: ignore[no-redef]

CompletionRequest = contracts.CompletionRequest

RECONNECT_MIN_SECONDS: Final = 0.5
RECONNECT_MAX_SECONDS: Final = 30.0
RECONNECT_JITTER_RATIO: Final = 0.3


def canonical_request_sha256(body: dict[str, object]) -> str:
    """MUST stay byte-identical to ``coaching_service.gpu_link.canonical_request_sha256``."""
    encoded = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


async def dispatch_op(  # noqa: PLR0911 - each terminal outcome carries a distinct error/result shape.
    execution: WorkerExecution,
    backend: Backend,
    op: str | None,
    body: dict[str, object],
    expected_prompt_sha256: str | None,
) -> dict[str, object]:
    """Run one ``tokenize``/``complete`` op through the real worker execution path.

    Mirrors ``gpu_worker.create_app``'s ``admit()`` + route handlers, minus the HTTP
    authorization check (the WS socket itself is already authenticated) and minus
    ASGI-disconnect cancellation (no per-request cancel signal exists over a
    multiplexed WS frame stream; a dropped requester's in-flight op still finishes).
    """
    if op not in {"tokenize", "complete"}:
        return {"error": {"status": 400, "detail": "unknown_op"}}
    try:
        request = CompletionRequest.model_validate(body)
    except ValidationError:
        return {"error": {"status": 422, "detail": "invalid_request"}}
    if request.model not in {backend.metadata.model, backend.metadata.model_id}:
        return {"error": {"status": 404, "detail": "model_not_loaded"}}
    character_count = sum(len(message.content) for message in generation_messages(request))
    if character_count > INPUT_CHARACTER_LIMIT:
        return {"error": {"status": 413, "detail": "input_character_limit"}}
    try:
        execution.slots.acquire_nowait()
    except anyio.WouldBlock:
        return {"error": {"status": 429, "detail": "queue_full"}}
    try:
        if op == "tokenize":
            count = await execution.measure(request)
            return {
                "result": {
                    "prompt_tokens": count.prompt_tokens,
                    "prompt_sha256": count.prompt_sha256,
                    "request_sha256": canonical_request_sha256(body),
                    "max_input_tokens": backend.metadata.max_input_tokens,
                    "max_output_tokens": backend.metadata.max_output_tokens,
                },
            }
        generated = await execution.complete(request, expected_prompt_sha256)
        return {
            "result": {
                "id": "chatcmpl-" + secrets.token_hex(12),
                "object": "chat.completion",
                "created": int(time.time()),
                "model": backend.metadata.model,
                "system_fingerprint": backend.metadata.config_sha256,
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": generated.text},
                        "finish_reason": (
                            "length" if generated.completion_tokens >= request.max_tokens else "stop"
                        ),
                    },
                ],
                "usage": {
                    "prompt_tokens": generated.prompt_tokens,
                    "completion_tokens": generated.completion_tokens,
                    "total_tokens": generated.prompt_tokens + generated.completion_tokens,
                },
                "generation_seconds": generated.seconds,
            },
        }
    except HTTPException as error:
        return {"error": {"status": error.status_code, "detail": str(error.detail)}}
    finally:
        execution.slots.release()


class Worker:
    """Outbound WS client: mirrors the POC's worker_side.py, dispatching real ops.

    Exposes ``connect_count``/``current_ws``/``last_error`` so tests can observe
    reconnect behavior the same way the POC's driver did.
    """

    def __init__(
        self,
        url: str,
        token: str,
        execution: WorkerExecution,
        backend: Backend,
        ready_payload: dict[str, object],
    ) -> None:
        self.url = url
        self.token = token
        self.execution = execution
        self.backend = backend
        self.ready_payload = ready_payload
        self.stop_flag = False
        self.connect_count = 0
        self.last_error: str | None = None
        self.current_ws: object | None = None

    async def _handle_request(self, ws: object, message: dict[str, object]) -> None:
        req_id = message.get("id")
        op = message.get("op")
        payload = message.get("payload")
        body_payload = payload.get("body") if isinstance(payload, dict) else None
        expected = payload.get("expected_prompt_sha256") if isinstance(payload, dict) else None
        result = await dispatch_op(
            self.execution, self.backend,
            op if isinstance(op, str) else None,
            body_payload if isinstance(body_payload, dict) else {},
            expected if isinstance(expected, str) else None,
        )
        frame = json.dumps({"type": "response", "id": req_id, "op": op, "payload": result})
        send: Callable[[str], object] = ws.send  # type: ignore[attr-defined]
        with contextlib.suppress(Exception):  # a dead socket surfaces via the recv loop, not here.
            await send(frame)

    async def run_once(self) -> None:
        headers = {"Authorization": f"Bearer {self.token}"}
        async with websockets.connect(
            self.url, additional_headers=headers, open_timeout=10, close_timeout=2,
        ) as ws:
            self.connect_count += 1
            self.current_ws = ws
            await ws.send(
                json.dumps({"type": "ready", "id": "0", "op": None, "payload": self.ready_payload})
            )
            tasks: set[asyncio.Task[None]] = set()
            try:
                async for raw in ws:
                    message = json.loads(raw)
                    if not isinstance(message, dict):
                        continue
                    mtype = message.get("type")
                    if mtype == "ping":
                        await ws.send(
                            json.dumps(
                                {"type": "pong", "id": message.get("id"), "op": None, "payload": None}
                            )
                        )
                    elif mtype == "request":
                        task = asyncio.create_task(self._handle_request(ws, message))
                        tasks.add(task)
                        task.add_done_callback(tasks.discard)
            finally:
                self.current_ws = None
                for task in tasks:
                    _ = task.cancel()

    async def run_forever(self) -> None:
        backoff = RECONNECT_MIN_SECONDS
        while not self.stop_flag:
            try:
                await self.run_once()
                backoff = RECONNECT_MIN_SECONDS  # a clean loop exit resets the backoff
            except asyncio.CancelledError:
                raise
            except Exception as error:  # noqa: BLE001 - every drop reason must retry, not crash.
                self.last_error = repr(error)
            if self.stop_flag:
                break
            jitter = random.uniform(0, backoff * RECONNECT_JITTER_RATIO)  # noqa: S311 - reconnect jitter only.
            await asyncio.sleep(min(backoff + jitter, RECONNECT_MAX_SECONDS))
            backoff = min(backoff * 2, RECONNECT_MAX_SECONDS)


async def run_ws_worker(
    api_url: str,
    token: str,
    execution: WorkerExecution,
    backend: Backend,
    ready_payload: dict[str, object],
) -> None:
    """Entry point called by ``gpu_worker.main()`` when ``COACH_GPU_LINK_MODE=ws``."""
    worker = Worker(api_url, token, execution, backend, ready_payload)
    await worker.run_forever()
