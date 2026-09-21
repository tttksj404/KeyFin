"""Bound request bodies before parsing and prevent caching private responses."""

from collections import deque

import anyio
from pydantic import TypeAdapter
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class BodyLimit:
    def __init__(self, app: ASGIApp) -> None:
        self.app: ASGIApp = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        messages: deque[Message] = deque()
        size = 0
        try:
            with anyio.fail_after(15):
                while True:
                    message = await receive()
                    if message["type"] == "http.disconnect":
                        return
                    body = TypeAdapter(bytes).validate_python(message.get("body", b""), strict=True)
                    size += len(body)
                    if size > 2_000_000:
                        await JSONResponse({"error": "request_body_too_large"}, status_code=413)(
                            scope, receive, send
                        )
                        return
                    messages.append(message)
                    if not message.get("more_body", False):
                        break
        except TimeoutError:
            await JSONResponse({"error": "request_body_timeout"}, status_code=408)(scope, receive, send)
            return

        async def replay() -> Message:
            return messages.popleft() if messages else await receive()

        async def send_private(message: Message) -> None:
            if message["type"] == "http.response.start":
                message = dict(message)
                message["headers"] = [
                    *message.get("headers", []),
                    (b"cache-control", b"no-store"),
                    (b"x-content-type-options", b"nosniff"),
                ]
            await send(message)

        await self.app(scope, replay, send_private)
