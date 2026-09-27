"""HTTP 계약과 분리한 요청 수명·토큰 검사·GPU 생성 자원 관리."""

from __future__ import annotations

from contextlib import asynccontextmanager
from inspect import isawaitable
from typing import TYPE_CHECKING, final

import anyio
from fastapi import HTTPException

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Awaitable, Callable

    from fastapi import FastAPI
    from starlette.types import Receive

    from .gpu_batching import BatchComplete, BatchDispatcher
    from .gpu_contracts import Backend, CompletionRequest, Generated, Metadata, PromptCount

    AsyncComplete = Callable[[CompletionRequest], Awaitable[Generated]]
    Shutdown = Callable[[], object]
else:  # noqa: PLR5501 - Keep the TYPE_CHECKING runtime boundary for basedpyright.
    if __package__:
        from .gpu_batching import BatchDispatcher
    else:
        from gpu_batching import BatchDispatcher


@final
class WorkerExecution:
    """단일 GPU 소비자와 별도 CPU tokenizer를 사용하고 기존 backend도 지원한다."""

    def __init__(  # noqa: PLR0913 - worker scheduling contracts remain explicit at this boundary.
        self, backend: Backend, batch_complete: BatchComplete | None, size: int,
        validate: Callable[[PromptCount, Metadata, str | None], None],
        *,
        async_complete: AsyncComplete | None = None,
        shutdown: Shutdown | None = None,
        require_matching_response_format: bool = False,
    ) -> None:
        if batch_complete is not None and async_complete is not None:
            raise ValueError("external_batching_and_async_generation_are_incompatible")
        self.backend = backend
        self.validate = validate
        self.async_complete = async_complete
        self.shutdown = shutdown
        self.dispatcher = (
            BatchDispatcher(
                batch_complete,
                size,
                require_matching_response_format=require_matching_response_format,
            )
            if batch_complete is not None
            else None
        )
        # The asynchronous vLLM candidate has its own continuous scheduler.  A
        # second FIFO batcher would reintroduce a completion barrier, while more
        # than the engine's reviewed sequence limit would merely hide queue time.
        self.slots = anyio.CapacityLimiter(8 if self.async_complete is not None else (
            16 if self.dispatcher is not None else 2
        ))
        self.gpu = anyio.CapacityLimiter(1)
        self.tokenizer = anyio.CapacityLimiter(8) if self.async_complete is not None else (
            anyio.CapacityLimiter(1) if self.dispatcher is not None else self.gpu
        )

    @asynccontextmanager
    async def lifespan(self, _app: FastAPI) -> AsyncGenerator[None, None]:
        try:
            async with anyio.create_task_group() as group:
                if self.dispatcher is not None:
                    await group.start(self.dispatcher.run)
                try:
                    yield
                finally:
                    group.cancel_scope.cancel()
        finally:
            if self.shutdown is not None:
                result = self.shutdown()
                if isawaitable(result):
                    await result

    async def measure(self, request: CompletionRequest) -> PromptCount:
        async with self.tokenizer:
            return await anyio.to_thread.run_sync(self.backend.measure, request)

    async def connected_complete(
        self, request: CompletionRequest, expected: str | None, receive: Receive,
    ) -> Generated:
        """본문 파싱 이후 연결 종료를 감시해 취소된 대기 작업과 슬롯을 반환한다.

        이미 시작한 CUDA 호출은 강제로 중단하지 않는다. 배치 소비자는 별도 수명을
        가지므로 다른 사용자의 생성은 유지하고 끊긴 요청의 결과만 버린다.
        """
        result: Generated | HTTPException | None = None
        disconnected = False
        async with anyio.create_task_group() as group:
            async def disconnect() -> None:
                nonlocal disconnected
                while True:
                    message = await receive()
                    if message["type"] == "http.disconnect":
                        disconnected = True
                        group.cancel_scope.cancel()
                        return

            _ = group.start_soon(disconnect)
            try:
                result = await self.complete(request, expected)
            except HTTPException as error:
                # TaskGroup이 409/413/429를 ExceptionGroup으로 감싸 500으로 바꾸지 않게 한다.
                result = error
            finally:
                group.cancel_scope.cancel()
        # 기존 순차 경로의 CUDA 스레드는 취소를 차폐한다. 잠금은 끝까지 유지하되
        # 그 사이 연결이 끊겼다면 반환된 결과가 있어도 성공 응답을 만들지 않는다.
        if disconnected or result is None:
            raise HTTPException(status_code=499, detail="client_disconnected")
        if isinstance(result, HTTPException):
            raise result
        return result

    async def complete(self, request: CompletionRequest, expected: str | None) -> Generated:
        if self.async_complete is not None:
            count = await self.measure(request)
            self.validate(count, self.backend.metadata, expected)
            return await self.async_complete(request)
        if self.dispatcher is None:
            # 기존 backend는 tokenizer와 모델을 같은 잠금으로 보호해야 한다.
            async with self.gpu:
                count = await anyio.to_thread.run_sync(self.backend.measure, request)
                self.validate(count, self.backend.metadata, expected)
                return await anyio.to_thread.run_sync(self.backend.complete, request)
        count = await self.measure(request)
        self.validate(count, self.backend.metadata, expected)
        return await self.dispatcher.submit(request, count.prompt_tokens)
