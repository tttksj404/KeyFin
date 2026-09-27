"""요청 수·토큰 수를 제한한 FIFO 배치: GPU 생성은 한 소비자만 실행한다."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, final

import anyio
from fastapi import HTTPException

if TYPE_CHECKING:
    from .gpu_contracts import CompletionRequest, Generated

BatchComplete = Callable[[list["CompletionRequest"]], list["Generated"]]


@dataclass(slots=True)
class Pending:
    """요청자와 소비자가 공유하는 완료·취소 상태이며 결과는 요청별로 보관한다."""

    request: CompletionRequest
    prompt_tokens: int
    ready: anyio.Event = field(default_factory=anyio.Event)
    result: Generated | HTTPException | None = None
    cancelled: bool = False


@final
class BatchDispatcher:
    """출력 상한이 맞는 요청만 묶고 대기열·패딩 메모리의 증가를 제한한다."""

    def __init__(
        self,
        complete: BatchComplete,
        size: int,
        *,
        token_budget: int = 16384,
        require_matching_response_format: bool = False,
    ) -> None:
        # 단일 합법 요청(입력 8192 + 출력 1536)은 항상 들어갈 수 있어야 한다.
        if not 1 <= size <= 4 or token_budget < 9728:
            raise ValueError("invalid_batch_limits")
        self.complete = complete
        self.size = size
        self.token_budget = token_budget
        self.require_matching_response_format = require_matching_response_format
        self.sender, self.receiver = anyio.create_memory_object_stream[Pending](16)
        self.pending: list[Pending] = []
        self.running = False

    async def submit(self, request: CompletionRequest, prompt_tokens: int) -> Generated:
        if not self.running:
            raise HTTPException(status_code=503, detail="worker_not_ready")
        item = Pending(request, prompt_tokens)
        self.pending.append(item)
        try:
            try:
                self.sender.send_nowait(item)
            except anyio.WouldBlock as exc:
                raise HTTPException(status_code=429, detail="queue_full") from exc
            await item.ready.wait()
            match item.result:
                case HTTPException() as error:
                    raise error
                case None:
                    raise HTTPException(status_code=503, detail="worker_stopped")
                case result:
                    return result
        finally:
            # HTTP 연결 종료 감시가 요청을 취소하면 아직 생성하지 않은 항목을 건너뛴다.
            item.cancelled = True
            self.pending.remove(item)

    def compatible(self, batch: list[Pending], item: Pending) -> bool:
        """출력·시드·패딩 예산이 같은 요청만 한 decoder 호출로 묶는다."""
        same_limit = batch[0].request.max_tokens == item.request.max_tokens
        # vLLM SamplingParams is one object per batch. Mixing seeds would silently
        # apply the first request's experiment setting to another caller.
        same_seed = batch[0].request.seed == item.request.seed
        # Structured decoding applies one grammar to the complete generation
        # batch, so response formats cannot be mixed on that optional path.
        same_response_format = (
            not self.require_matching_response_format
            or batch[0].request.response_format == item.request.response_format
        )
        longest = max(job.prompt_tokens + job.request.max_tokens for job in [*batch, item])
        return (
            same_limit
            and same_seed
            and same_response_format
            and longest * (len(batch) + 1) <= self.token_budget
        )

    async def run(self, *, task_status: anyio.abc.TaskStatus[None] = anyio.TASK_STATUS_IGNORED) -> None:
        self.running = True
        task_status.started()
        carry: Pending | None = None
        try:
            while True:
                first = carry if carry is not None else await self.receiver.receive()
                carry = None
                if first.cancelled:
                    continue
                batch = [first]
                # 후속 요청이 없더라도 최대 8ms 뒤에는 단독 요청의 생성을 시작한다.
                with anyio.move_on_after(0.008):
                    while len(batch) < self.size:
                        item = await self.receiver.receive()
                        if item.cancelled:
                            continue
                        if not self.compatible(batch, item):
                            carry = item
                            break
                        batch.append(item)
                active = [item for item in batch if not item.cancelled]
                if active:
                    await self.generate(active)
        finally:
            self.running = False
            for item in self.pending:
                item.ready.set()

    async def generate(self, batch: list[Pending]) -> None:
        """실패한 배치의 모든 요청을 깨우고 소비자는 다음 배치를 계속 처리한다."""
        try:
            results = await anyio.to_thread.run_sync(self.complete, [item.request for item in batch])
            for item, result in zip(batch, results, strict=True):
                item.result = result
        except HTTPException as error:
            for item in batch:
                item.result = error
        except (RuntimeError, ValueError):
            # 모델 예외에는 입력 원문이 들어갈 수 있으므로 안전한 코드만 반환한다.
            for item in batch:
                item.result = HTTPException(status_code=503, detail="generation_failed")
        finally:
            for item in batch:
                item.ready.set()
