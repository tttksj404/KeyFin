"""Verify the serving tokenizer's budget for the exact bytes sent to generation."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Annotated

import anyio
import httpx2
from pydantic import Field

from coaching_service.llm_contract import FrozenContract


class TokenBudget(FrozenContract):
    prompt_tokens: Annotated[int, Field(ge=1)]
    max_input_tokens: Annotated[int, Field(ge=1)]
    max_output_tokens: Annotated[int, Field(ge=1)]
    request_sha256: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    prompt_sha256: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]


@dataclass(frozen=True, slots=True)
class BudgetFailure:
    reason: str


def validate_budget(body: bytearray, request: httpx2.Request, max_tokens: int) -> TokenBudget | BudgetFailure:
    """사전 검사 응답이 이번 요청의 원본 바이트와 입출력 한도에 대응하는지 확인한다.

    request_sha256은 전송 본문, prompt_sha256은 서버가 적용한 템플릿 이후의 지문이다.
    서로 역할이 다르므로 한 해시로 대신하거나 글자 수에서 토큰 수를 추정하지 않는다.
    """
    try:
        budget = TokenBudget.model_validate_json(body)
    except ValueError:
        return BudgetFailure("token_preflight_invalid_schema")
    if budget.request_sha256 != hashlib.sha256(request.content).hexdigest():
        return BudgetFailure("token_preflight_request_mismatch")
    if budget.prompt_tokens > budget.max_input_tokens:
        return BudgetFailure("input_token_limit")
    if max_tokens > budget.max_output_tokens:
        return BudgetFailure("output_token_limit")
    return budget


async def check_token_budget(
    client: httpx2.AsyncClient, request: httpx2.Request, max_tokens: int,
) -> TokenBudget | BudgetFailure:
    """생성과 같은 본문·인증으로 사전 검사한다. 리다이렉트와 큰 응답은 허용하지 않는다."""
    preflight = httpx2.Request(
        "POST", request.url.copy_with(path="/v1/tokenize"),
        headers=request.headers, content=request.content, extensions=request.extensions,
    )
    response = await client.send(preflight, stream=True, auth=None, follow_redirects=False)
    try:
        if response.status_code != 200:
            return BudgetFailure(f"token_preflight_http_status_{response.status_code}")
        body = bytearray()
        async for chunk in response.aiter_bytes():
            if len(body) + len(chunk) > 4096:
                return BudgetFailure("token_preflight_response_limit")
            body.extend(chunk)
        return validate_budget(body, request, max_tokens)
    finally:
        with anyio.move_on_after(0.1, shield=True):
            await response.aclose()
