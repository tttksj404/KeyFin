# /// script
# requires-python = ">=3.11"
# dependencies = ["fastapi", "uvicorn", "anyio", "pydantic", "websockets"]
# ///
# How to run: COACH_GPU_MODEL=latest27_nf4 pinned-python gpu_worker.py
"""Authenticated loopback OpenAI subset backed by the pinned GPU runtime."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import stat
import time
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Final, Literal, cast

import anyio
import uvicorn
from fastapi import FastAPI, Header, HTTPException, Request
from pydantic import Field
from starlette.responses import JSONResponse, Response

# Package imports support tests; standalone imports support the pinned GPU process.
if TYPE_CHECKING:
    from . import gpu_contracts as contracts
    from .gpu_execution import WorkerExecution
else:  # noqa: PLR5501 - Keep the TYPE_CHECKING runtime boundary for basedpyright.
    if __package__:
        from . import gpu_contracts as contracts
        from .gpu_execution import WorkerExecution
    else:
        import gpu_contracts as contracts
        from gpu_execution import WorkerExecution

if TYPE_CHECKING:
    from starlette.middleware.base import RequestResponseEndpoint

    from .gpu_batching import BatchComplete
    from .gpu_execution import AsyncComplete, Shutdown


Backend = contracts.Backend
CompletionRequest = contracts.CompletionRequest
# 입력 문자 상한. gpu_ws_worker.py와 공유해 WS·loopback 경로가 어긋나지 않게 한다.
INPUT_CHARACTER_LIMIT: Final = 48000
Frozen = contracts.Frozen
Generated = contracts.Generated
Message = contracts.Message
Metadata = contracts.Metadata
PromptCount = contracts.PromptCount
ResponseFormat = contracts.ResponseFormat
SchemaRequest = contracts.SchemaRequest


class TokenBudget(PromptCount):
    request_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    max_input_tokens: int = Field(ge=1)
    max_output_tokens: int = Field(ge=1)


class Choice(Frozen):
    index: Literal[0] = 0
    message: Message
    finish_reason: Literal["stop", "length"]


class Usage(Frozen):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class CompletionResponse(Frozen):
    id: str
    object: Literal["chat.completion"] = "chat.completion"
    created: int
    model: str
    system_fingerprint: str
    choices: tuple[Choice, ...]
    usage: Usage
    generation_seconds: float


def generation_messages(request: CompletionRequest) -> tuple[Message, ...]:
    """응답 스키마까지 포함한 실제 생성 메시지를 만든다.

    기본 decoder는 스키마를 지시문에 넣고 클라이언트가 결과를 다시 검증한다. 선택
    decoder는 같은 스키마를 생성 문법에도 전달하지만, 의미·근거 검증은 서비스가 계속 한다.
    합쳐진 내용도 메시지 한도를 검사해야 Pydantic 오류가 500이 되지 않는다.
    measure와 complete는 모두 이 함수를 사용해야 토큰 사전 검사가 같은 입력을 센다.
    """
    if request.response_format is None or request.response_format.type == "text":
        return request.messages
    specification = request.response_format.model_dump(mode="json", by_alias=True, exclude_none=True)
    content = json.dumps({"response_format": specification}, ensure_ascii=False)
    if request.messages[0].role == "system":
        content = request.messages[0].content + "\n" + content
        remaining = request.messages[1:]
    else:
        remaining = request.messages
    if len(content) > 32000:
        raise HTTPException(status_code=413, detail="input_character_limit")
    return (Message(role="system", content=content), *remaining)


async def bound_body(request: Request, call_next: RequestResponseEndpoint) -> Response:
    """Reject oversized or unbounded body framing before JSON parsing."""
    if request.method == "POST":
        raw_length = request.headers.get("content-length", "")
        if not raw_length.isdigit() or int(raw_length) > 65536:
            return JSONResponse(status_code=413, content={"detail": "request_body_limit"})
    return await call_next(request)


def validate_prompt_count(count: PromptCount, metadata: Metadata, expected: str | None) -> None:
    """실제 토큰 상한과 사전 검사 때의 프롬프트 지문을 생성 직전에 다시 확인한다.

    글자 수 검사는 토큰 검사를 대신하지 않는다. 지문 변경은 409로 중단하며
    비 ASCII 헤더는 compare_digest의 예외 대신 명시적인 오류로 처리한다.
    """
    if count.prompt_tokens > metadata.max_input_tokens:
        raise HTTPException(status_code=413, detail="input_token_limit")
    if expected is not None and (
        not expected.isascii() or not secrets.compare_digest(expected, count.prompt_sha256)
    ):
        raise HTTPException(status_code=409, detail="tokenizer_preflight_changed")


def create_app(  # noqa: PLR0913 - dependency injection keeps worker variants testable.
    backend: Backend,
    token: str,
    *,
    batch_complete: BatchComplete | None = None,
    async_complete: AsyncComplete | None = None,
    shutdown: Shutdown | None = None,
    max_batch_size: int = 1,
    require_matching_response_format: bool = False,
) -> FastAPI:
    """Keep the API contract while each decoder owns its reviewed scheduling policy."""
    if len(token) < 32:
        raise ValueError("token_too_short")
    execution = WorkerExecution(
        backend,
        batch_complete,
        max_batch_size,
        validate_prompt_count,
        async_complete=async_complete,
        shutdown=shutdown,
        require_matching_response_format=require_matching_response_format,
    )
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, lifespan=execution.lifespan)
    _ = app.middleware("http")(bound_body)

    async def health() -> Metadata:
        return backend.metadata

    def admit(request: CompletionRequest, authorization: str | None) -> None:
        """인증·모델·스키마를 합친 글자 수를 확인한 뒤에만 대기 슬롯을 점유한다."""
        if (
            authorization is None or not authorization.isascii()
            or not secrets.compare_digest(authorization, f"Bearer {token}")
        ):
            raise HTTPException(status_code=401, detail="unauthorized")
        if request.model not in {backend.metadata.model, backend.metadata.model_id}:
            raise HTTPException(status_code=404, detail="model_not_loaded")
        if sum(len(message.content) for message in generation_messages(request)) > INPUT_CHARACTER_LIMIT:
            raise HTTPException(status_code=413, detail="input_character_limit")
        try:
            execution.slots.acquire_nowait()
        except anyio.WouldBlock as exc:
            raise HTTPException(status_code=429, detail="queue_full") from exc

    async def tokenize(
        request: CompletionRequest, raw: Request,
        authorization: Annotated[str | None, Header()] = None,
    ) -> TokenBudget:
        """본문 원본 해시와 chat template 적용 후 토큰 수·지문을 함께 돌려준다.

        클라이언트는 원본 해시로 다른 요청의 검사값 혼용을 막고, 서버는 생성 전에
        프롬프트 지문을 재확인한다. 이 응답은 모델 답변 생성의 성공 증거가 아니다.
        """
        admit(request, authorization)
        try:
            count = await execution.measure(request)
        finally:
            execution.slots.release()
        return TokenBudget(
            prompt_tokens=count.prompt_tokens, prompt_sha256=count.prompt_sha256,
            request_sha256=hashlib.sha256(await raw.body()).hexdigest(),
            max_input_tokens=backend.metadata.max_input_tokens,
            max_output_tokens=backend.metadata.max_output_tokens,
        )

    async def complete(
        request: CompletionRequest, raw: Request,
        authorization: Annotated[str | None, Header()] = None,
        x_coaching_prompt_sha256: Annotated[str | None, Header()] = None,
    ) -> CompletionResponse:
        admit(request, authorization)
        try:
            result = await execution.connected_complete(request, x_coaching_prompt_sha256, raw.receive)
        finally:
            execution.slots.release()
        return CompletionResponse(
            id="chatcmpl-" + secrets.token_hex(12),
            created=int(time.time()),
            model=backend.metadata.model,
            system_fingerprint=backend.metadata.config_sha256,
            choices=(
                Choice(
                    message=Message(role="assistant", content=result.text),
                    finish_reason="length" if result.completion_tokens >= request.max_tokens else "stop",
                ),
            ),
            usage=Usage(
                prompt_tokens=result.prompt_tokens,
                completion_tokens=result.completion_tokens,
                total_tokens=result.prompt_tokens + result.completion_tokens,
            ),
            generation_seconds=result.seconds,
        )

    app.add_api_route("/health", health, methods=["GET"])
    app.add_api_route("/v1/tokenize", tokenize, methods=["POST"])
    app.add_api_route("/v1/chat/completions", complete, methods=["POST"])
    return app


def admission_limit(backend_kind: Literal["transformers", "vllm", "vllm_async"], batch_size: int) -> int:
    """ASGI-level in-flight cap: generation slot budget + 1 request queued behind it.

    Online batching already admits up to 16 concurrent requests (see gpu_execution's
    dispatcher CapacityLimiter), so its ASGI cap stays 32. The vllm_async backend now
    reserves 8 engine slots (gpu_execution.WorkerExecution.slots) instead of the old
    2-deep synchronous path, so its ASGI cap follows the same "slots + headroom" shape
    the batch branch already uses: 8 slots -> 16 (vs. the previous 2 slots -> 8).
    """
    if batch_size:
        return 32
    return 16 if backend_kind == "vllm_async" else 8


def main() -> None:  # noqa: C901 - one linear, ordered sequence of fail-closed startup checks.
    """Load only on the authorized device; read the private token from disk."""
    from gpu_registry import execution_backend, validate_device  # noqa: PLC0415

    validate_device(os.environ)
    # Validate the opt-in decoder before loading model weights. The default stays
    # on the established Transformer path unless a measured promotion changes it.
    backend_kind = execution_backend(os.environ)
    root = Path(os.environ["COACH_GPU_WORKSPACE"])
    if not root.is_absolute() or root.is_symlink() or root.stat().st_uid != os.getuid():
        raise RuntimeError("workspace_ownership_invalid")
    port = int(os.environ.get("COACH_GPU_PORT", "18743"))
    if not 1024 <= port <= 65535:
        raise RuntimeError("worker_port_invalid")
    # 온라인 배치는 실제 부하 비교를 통과한 환경에서만 명시적으로 켠다.
    batch_size = int(os.environ.get("COACH_GPU_BATCH_SIZE", "0"))
    if not 0 <= batch_size <= 4:
        raise RuntimeError("worker_batch_size_invalid")
    if backend_kind == "vllm_async" and batch_size:
        # AsyncLLM performs continuous scheduling itself.  An outer synchronous
        # batch queue would recreate the latency barrier this candidate removes.
        raise RuntimeError("async_vllm_external_batching_forbidden")
    token_path = root / "worker.token"
    file_stat = token_path.stat()
    if stat.S_IMODE(file_stat.st_mode) != 0o600 or file_stat.st_uid != os.getuid():
        raise RuntimeError("token_permissions_invalid")
    # Reverse-tunnel opt-in (SPEC-ws-tunnel.md): default "loopback" is today's exact
    # uvicorn-server behavior, unchanged below. "ws" dials OUT to the coaching API
    # instead, over an outbound WebSocket, for GPU boxes with no inbound connectivity.
    link_mode = os.environ.get("COACH_GPU_LINK_MODE", "loopback")
    if link_mode not in {"loopback", "ws"}:
        raise RuntimeError("gpu_link_mode_invalid")
    api_url = os.environ.get("COACH_GPU_API_URL", "")
    if link_mode == "ws" and not api_url.startswith(("ws://", "wss://")):
        raise RuntimeError("gpu_link_api_url_invalid")
    if backend_kind == "vllm_async":
        from gpu_runtime import AsyncPinnedBackend  # noqa: PLC0415

        backend = AsyncPinnedBackend(os.environ["COACH_GPU_MODEL"])
        async_complete = backend.complete_async
        shutdown: Shutdown | None = backend.close
    else:
        from gpu_runtime import PinnedBackend  # noqa: PLC0415

        backend = PinnedBackend(os.environ["COACH_GPU_MODEL"])
        async_complete = None
        shutdown = None
    _ = (root / "worker_metadata.json").write_text(
        backend.metadata.model_dump_json(indent=2), encoding="utf-8"
    )
    print("GPU_WORKER_MODEL_READY", flush=True)
    if link_mode == "ws":
        # Lazy: websockets is only needed on this rare path.
        if __package__:
            from .gpu_ws_worker import run_ws_worker  # noqa: PLC0415
        else:
            from gpu_ws_worker import run_ws_worker  # noqa: PLC0415

        execution = WorkerExecution(
            backend,
            backend.complete_batch if batch_size else None,
            max(1, batch_size),
            validate_prompt_count,
            async_complete=async_complete,
            shutdown=shutdown,
            require_matching_response_format=backend.metadata.grammar_enforced,
        )
        ready_payload = {
            "model_tag": backend.metadata.model,
            "revision": backend.metadata.revision,
            "max_input_tokens": backend.metadata.max_input_tokens,
            "max_output_tokens": backend.metadata.max_output_tokens,
        }
        token = token_path.read_text().strip()

        async def serve_ws() -> None:
            # ``execution.lifespan`` normally runs as a FastAPI ASGI lifespan; here it
            # is driven directly since there is no ASGI app on the outbound-only path.
            async with execution.lifespan(cast("FastAPI", None)):
                await run_ws_worker(api_url, token, execution, backend, ready_payload)

        anyio.run(serve_ws)
        return
    uvicorn.run(
        create_app(
            backend, token_path.read_text().strip(),
            batch_complete=backend.complete_batch if batch_size else None,
            async_complete=async_complete,
            shutdown=shutdown,
            max_batch_size=max(1, batch_size),
            require_matching_response_format=backend.metadata.grammar_enforced,
        ),
        host="127.0.0.1",
        port=port,
        access_log=False,
        log_level="warning",
        limit_concurrency=admission_limit(backend_kind, batch_size),
        timeout_keep_alive=5,
    )


if __name__ == "__main__":
    main()
