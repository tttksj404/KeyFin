"""Inbound half of the outbound GPU WebSocket tunnel (``COACH_GPU_LINK_MODE=ws``).

The GPU worker is outbound-only, so in ws mode it dials OUT to this API's
``/internal/gpu-link`` WebSocket instead of the API dialing IN over loopback HTTP
(``scripts/gpu_worker.py``'s uvicorn server, the default/loopback path). Frames are
``{type, id, op, payload}`` and multiplexed by ``id`` -- this mirrors the proven POC
described in SPEC-ws-tunnel.md. ``register_gpu_link`` is only ever called from
``api.py`` when the link mode is ``ws``; in the default ``loopback`` mode this module
is imported but never wired into the app, so it has zero runtime effect.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import secrets
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, Protocol, cast

from starlette.websockets import WebSocket, WebSocketDisconnect, WebSocketState

if TYPE_CHECKING:
    from collections.abc import Mapping

    from fastapi import FastAPI

GPU_LINK_PATH: Final = "/internal/gpu-link"
PING_INTERVAL_SECONDS: Final = 15.0
PING_MISS_LIMIT: Final = 2


def canonical_request_sha256(body: Mapping[str, object]) -> str:
    """Fingerprint tying a ``tokenize`` response to its exact ``complete`` body.

    The WS transport has no raw HTTP bytes to hash (unlike the loopback contract's
    ``hashlib.sha256(await raw.body())``), so both this API side and the worker side
    (``scripts/gpu_ws_worker.py``'s copy of this same function -- it MUST stay
    byte-identical) hash the same canonical JSON encoding of the request body dict.
    """
    encoded = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True)
class GpuLinkFailure:
    reason: str


@dataclass(frozen=True, slots=True)
class GpuLinkOk:
    result: dict[str, object]


GpuLinkOutcome = GpuLinkOk | GpuLinkFailure


class GpuLinkSubmit(Protocol):
    async def __call__(
        self, op: str, payload: dict[str, object], timeout: float,  # noqa: ASYNC109
    ) -> GpuLinkOutcome: ...


class WorkerSession:
    """One connected worker socket: owns its multiplexed pending-request map."""

    def __init__(self, ws: WebSocket) -> None:
        self.ws: WebSocket = ws
        self.pending: dict[str, asyncio.Future[dict[str, object]]] = {}
        self.alive: bool = True
        self.missed_pongs: int = 0
        self.awaiting_pong: bool = False
        self.ready_info: dict[str, object] | None = None

    async def send_request(
        self, op: str, payload: dict[str, object], timeout: float,  # noqa: ASYNC109
    ) -> dict[str, object]:
        req_id = str(uuid.uuid4())
        future: asyncio.Future[dict[str, object]] = asyncio.get_running_loop().create_future()
        self.pending[req_id] = future
        frame = {"type": "request", "id": req_id, "op": op, "payload": payload}
        try:
            await self.ws.send_json(frame)
        except Exception as error:
            _ = self.pending.pop(req_id, None)
            raise ConnectionError("gpu_link_send_failed") from error
        try:
            return await asyncio.wait_for(future, timeout=timeout)
        finally:
            _ = self.pending.pop(req_id, None)

    def resolve(self, req_id: object, payload: object) -> None:
        if not isinstance(req_id, str):
            return
        future = self.pending.get(req_id)
        if future is not None and not future.done():
            result = cast("dict[str, object]", payload) if isinstance(payload, dict) else {}
            future.set_result(result)

    def fail_all(self, error: Exception) -> None:
        for future in self.pending.values():
            if not future.done():
                future.set_exception(error)


class GpuLinkRegistry:
    """Holds the currently connected worker session (single worker; see SPEC)."""

    def __init__(self) -> None:
        self._session: WorkerSession | None = None
        self.stats: dict[str, int] = {"connects": 0, "rejects": 0, "drops": 0}

    def set(self, session: WorkerSession) -> None:
        self._session = session

    def clear(self, session: WorkerSession) -> None:
        if self._session is session:
            self._session = None

    def current(self) -> WorkerSession | None:
        return self._session

    @property
    def worker_connected(self) -> bool:
        return self._session is not None and self._session.alive

    async def submit(
        self, op: str, payload: dict[str, object], timeout: float,  # noqa: ASYNC109
    ) -> GpuLinkOutcome:
        """Send ``payload`` to the connected worker and await its id-correlated reply.

        Falls back immediately (no wait) when no worker is connected, and fails the
        same way on a timeout or a drop mid-flight -- ``llm.py`` treats every
        ``GpuLinkFailure`` exactly like today's httpx transport failure, so the
        template-fallback contract is unchanged by which transport is in use.
        """
        session = self._session
        if session is None or not session.alive:
            return GpuLinkFailure("worker_unavailable")
        try:
            frame_payload = await session.send_request(op, payload, timeout)
        except TimeoutError:
            return GpuLinkFailure("gpu_link_timeout")
        except ConnectionError:
            return GpuLinkFailure("worker_unavailable")
        error = frame_payload.get("error")
        if error is not None:
            detail: object = None
            if isinstance(error, dict):
                detail = cast("dict[str, object]", error).get("detail")
            return GpuLinkFailure(str(detail) if detail is not None else "gpu_link_error")
        result = frame_payload.get("result")
        if not isinstance(result, dict):
            return GpuLinkFailure("gpu_link_invalid_response")
        return GpuLinkOk(cast("dict[str, object]", result))


def register_gpu_link(  # noqa: C901, PLR0915 - one cohesive WS handshake/heartbeat/recv-loop unit.
    app: FastAPI, *, expected_token: str | None,
) -> GpuLinkRegistry:
    """Add the worker-facing ``/internal/gpu-link`` WS route; only called in ws mode.

    ``expected_token`` is the same ``worker.token`` value the loopback path already
    authenticates the API's outbound httpx client with (``ModelConfig.token``); here
    it authenticates the worker's inbound connection instead. ``None`` fails closed.
    """
    registry = GpuLinkRegistry()

    async def gpu_link(ws: WebSocket) -> None:  # noqa: C901 - one cohesive WS session lifecycle.
        auth = ws.headers.get("authorization", "")
        candidate = auth[7:] if auth.lower().startswith("bearer ") else ""
        if expected_token is None or not secrets.compare_digest(candidate, expected_token):
            registry.stats["rejects"] += 1
            await ws.close(code=4401)
            return
        await ws.accept()
        registry.stats["connects"] += 1
        session = WorkerSession(ws)
        registry.set(session)

        async def heartbeat() -> None:
            try:
                while session.alive:
                    await asyncio.sleep(PING_INTERVAL_SECONDS)
                    if session.awaiting_pong:
                        session.missed_pongs += 1
                    else:
                        session.missed_pongs = 0
                    session.awaiting_pong = True
                    if session.missed_pongs >= PING_MISS_LIMIT:
                        session.alive = False
                        if ws.client_state == WebSocketState.CONNECTED:
                            await ws.close(code=4408)
                        return
                    await ws.send_json(
                        {"type": "ping", "id": str(uuid.uuid4()), "op": None, "payload": None}
                    )
            except Exception:  # noqa: BLE001, S110 - a dead heartbeat loop must never crash the handler.
                pass

        heartbeat_task = asyncio.create_task(heartbeat())
        try:
            while True:
                received = cast("object", await ws.receive_json())
                if not isinstance(received, dict):
                    continue
                message = cast("dict[str, object]", received)
                mtype = message.get("type")
                if mtype == "ready":
                    ready_payload = message.get("payload")
                    session.ready_info = ready_payload if isinstance(ready_payload, dict) else None
                elif mtype == "pong":
                    session.awaiting_pong = False
                    session.missed_pongs = 0
                elif mtype == "response":
                    session.resolve(message.get("id"), message.get("payload"))
        except WebSocketDisconnect:
            pass
        finally:
            session.alive = False
            _ = heartbeat_task.cancel()
            registry.stats["drops"] += 1
            registry.clear(session)
            session.fail_all(ConnectionError("worker_disconnected"))

    app.add_api_websocket_route(GPU_LINK_PATH, gpu_link)
    app.state.gpu_link_registry = registry
    return registry
