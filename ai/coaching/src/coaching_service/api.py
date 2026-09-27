"""Standalone authenticated financial coaching API."""

import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from coaching_service.auth import Authenticate
from coaching_service.chart_routes import register_charts
from coaching_service.coaching import CoachingCore, LanguageModel
from coaching_service.engine import ENGINE_COMMIT
from coaching_service.forecast_validation_routes import register_forecast_validation
from coaching_service.gpu_link import GpuLinkSubmit, register_gpu_link
from coaching_service.http_errors import register_errors
from coaching_service.llm import OpenAICompatibleCoachModel, create_http_client
from coaching_service.personal_routes import register_personal_context
from coaching_service.provenance import verify_engine
from coaching_service.repository import Repository
from coaching_service.request_timing import RequestTiming
from coaching_service.routes import register_coaching, register_records, register_twin
from coaching_service.schemas import (
    JsonDocument,
)
from coaching_service.settings import Settings
from coaching_service.store import Store
from coaching_service.transport import BodyLimit


def create_app(settings: Settings, model: LanguageModel | None = None) -> FastAPI:
    """고정 엔진 원본을 검증한 뒤 저장소·추론 클라이언트·인증 경계를 연결한다."""
    verified_files = verify_engine()
    client = create_http_client(settings.model)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
        async with client:
            yield

    app = FastAPI(title="FDT AI Coaching", version="0.3.0", lifespan=lifespan)

    # COACH_GPU_LINK_MODE mirrors scripts/gpu_worker.py's own unprefixed env var
    # (distinct from the COACHING_-prefixed Settings). Default "loopback" leaves
    # everything below exactly as it was: no route added, no submit callable, the
    # httpx client above is still what OpenAICompatibleCoachModel talks to.
    gpu_link_submit: GpuLinkSubmit | None = None
    if os.environ.get("COACH_GPU_LINK_MODE", "loopback") == "ws":
        expected_token = settings.model.token.get_secret_value() if settings.model.token else None
        registry = register_gpu_link(app, expected_token=expected_token)
        gpu_link_submit = registry.submit

    core = CoachingCore(
        Repository(Store(settings.database)),
        model or OpenAICompatibleCoachModel(settings.model, client=client, gpu_link_submit=gpu_link_submit),
        fdt_max_concurrency=settings.fdt_max_concurrency,
        persona=settings.persona,
    )
    auth = Authenticate(settings.clients)
    app.add_middleware(BodyLimit)
    # The timing middleware is outermost and inert unless a caller explicitly requests
    # a payload-free trace. It measures the same request that reaches the model adapter.
    app.add_middleware(RequestTiming)

    async def health() -> JsonDocument:
        """API의 기동 상태다. model_configured는 설정 유무이며 추론 성공을 뜻하지 않는다."""
        return JsonDocument.model_validate(
            {
                "status": "ok",
                "engine_commit": ENGINE_COMMIT,
                "engine_files_verified": verified_files,
                "model_configured": settings.model.endpoint_url is not None,
            }
        )

    register_errors(app)
    # /healthz는 의도한 상태 점검 경로다. GPU 준비·실제 추론 성공은 별도 요청으로 확인한다.
    app.add_api_route("/healthz", health, methods=["GET"])
    register_twin(app, core, auth)
    register_coaching(app, core, auth)
    register_records(app, core, auth)
    register_charts(app, core, auth)
    register_forecast_validation(app, core, auth)
    register_personal_context(app, core, auth)
    return app


def from_environment() -> FastAPI:
    return create_app(Settings())
