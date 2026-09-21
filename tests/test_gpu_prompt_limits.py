"""Expanded response schemas must fail with a client error before GPU execution."""
# ruff: noqa: INP001

import hashlib
import json

import httpx2
import pytest

from scripts.gpu_worker import (
    CompletionRequest,
    Generated,
    Metadata,
    PromptCount,
    create_app,
    generation_messages,
)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class MeasuringBackend:
    metadata = Metadata(
        model="fixture", model_id="fixture", revision="a" * 40,
        config_sha256="a" * 64, runtime_sha256="b" * 64, quantization="fixture",
    )

    def measure(self, request: CompletionRequest) -> PromptCount:
        content = "".join(message.content for message in generation_messages(request))
        return PromptCount(
            prompt_tokens=len(content), prompt_sha256=hashlib.sha256(content.encode()).hexdigest(),
        )

    def complete(self, _request: CompletionRequest) -> Generated:
        pytest.fail("An oversized expanded prompt must never invoke inference")


@pytest.mark.anyio
@pytest.mark.parametrize("route", ["/v1/tokenize", "/v1/chat/completions"])
@pytest.mark.parametrize("role", ["system", "user"])
async def test_schema_expansion_exceeding_message_limit_is_413(route: str, role: str) -> None:
    token = "synthetic-worker-token-for-prompt-test"
    app = create_app(MeasuringBackend(), token)
    body = {
        "model": "fixture", "messages": [{"role": role, "content": "x" * 32000}],
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "fixture", "schema": {"description": "s" * 32000}},
        },
    }
    assert len(json.dumps(body).encode()) < 65536
    CompletionRequest.model_validate(body)
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test",
    ) as client:
        response = await client.post(route, json=body, headers={"Authorization": "Bearer " + token})
    assert response.status_code == 413, response.text
    assert response.json() == {"detail": "input_character_limit"}


@pytest.mark.anyio
@pytest.mark.parametrize("credential", [b"Bearer incorrect", b"Bearer \xff"])
async def test_invalid_worker_credentials_return_401(credential: bytes) -> None:
    app = create_app(MeasuringBackend(), "synthetic-worker-token-for-prompt-test")
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test",
    ) as client:
        response = await client.post(
            "/v1/tokenize", json={"model": "fixture", "messages": [{"role": "user", "content": "hello"}]},
            headers=[(b"authorization", credential)],
        )
    assert response.status_code == 401, response.text


@pytest.mark.anyio
@pytest.mark.parametrize("fingerprint", [b"a" * 64, b"\xff"])
async def test_invalid_worker_prompt_fingerprints_return_409(fingerprint: bytes) -> None:
    token = "synthetic-worker-token-for-prompt-test"
    app = create_app(MeasuringBackend(), token)
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test",
    ) as client:
        response = await client.post(
            "/v1/chat/completions",
            json={"model": "fixture", "messages": [{"role": "user", "content": "hello"}]},
            headers=[(b"authorization", ("Bearer " + token).encode()),
                     (b"x-coaching-prompt-sha256", fingerprint)],
        )
    assert response.status_code == 409, response.text
