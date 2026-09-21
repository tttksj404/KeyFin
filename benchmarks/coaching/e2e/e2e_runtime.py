"""Owned loopback server lifetimes and observable, credential-free generation gateway."""

import hashlib
import json
import secrets
import socket
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Literal, assert_never, cast

import anyio
import httpx2
import uvicorn
from fastapi import FastAPI, Request, Response
from pydantic import SecretStr, TypeAdapter

from benchmarks.coaching.e2e.e2e_auth import worker_token
from benchmarks.coaching.e2e.e2e_contracts import E2ECase, Generation, RunConfig, TokenPreflight
from benchmarks.coaching.e2e.e2e_fake import fake_completion
from benchmarks.coaching.e2e.e2e_tokenizer import synthetic_budget
from coaching_service.evidence_projection import canonical_json
from coaching_service.llm import create_http_client
from coaching_service.llm_contract import ChatMessage, EvidenceInput, ModelConfig, Operation
from coaching_service.llm_prompt import system_prompt
from coaching_service.schemas import Frozen, JsonDocument
from coaching_service.token_budget import TokenBudget


class PromptMessage(Frozen):
    role: Literal["system", "user"]
    content: str


class GenerationRequest(Frozen):
    model: str
    messages: tuple[PromptMessage, PromptMessage]
    temperature: float
    max_tokens: int
    stream: bool
    response_format: JsonDocument | None = None


class UserPayload(Frozen):
    untrusted_question: str
    evidence_json: str | JsonDocument
    untrusted_history: tuple[ChatMessage, ...]


def operation_input(request: GenerationRequest) -> tuple[Operation, EvidenceInput]:
    """Classify the real wire request rather than one fixed prompt string per operation.

    The adapter can select among several route/finance prompt variants (see
    ``ModelConfig.route_prompt_version``) and appends a chart/finance flag to the
    route and write system prompts. Comparing the system message against only the
    single default-variant prompt text made this classifier reject any other
    configured variant even though the request was a legitimate call. The
    ``response_format`` schema name is a stable, variant-independent signal for
    ``judge``/``route``/finance/chart selections; a plain coaching write never
    sets ``response_format`` at all, so its absence is the remaining case.
    """
    first, second = request.messages
    operation: Operation | None = None
    if request.response_format is not None:
        schema_name = request.response_format.root.get("json_schema", {})
        name = schema_name.get("name") if isinstance(schema_name, dict) else None
        if name in ("route", "judge"):
            operation = cast("Operation", name)
        elif name in ("finance_facts", "chart_facts"):
            operation = "write"
    elif first.content == system_prompt("write"):
        operation = "write"
    if first.role != "system" or second.role != "user" or operation is None:
        raise ValueError("Unexpected model instruction boundary")
    payload = UserPayload.model_validate_json(second.content)
    match payload.evidence_json:
        case str() as encoded:
            facts_json = encoded
        case JsonDocument() as document:
            facts_json = canonical_json(document.root)
        case unreachable:
            assert_never(unreachable)
    return operation, EvidenceInput(
        question=payload.untrusted_question,
        facts_json=facts_json,
        history=payload.untrusted_history,
    )


class Gateway:
    """Mutable trace accumulator for one sequential suite; owns the upstream client and TCP app."""

    def __init__(self, config: RunConfig, *, client: httpx2.AsyncClient | None = None) -> None:
        self.config: RunConfig = config
        self.worker_token: SecretStr | None = worker_token(config)
        self.active_case: E2ECase | None = None
        self.generations: list[Generation] = []
        self.preflights: list[TokenPreflight] = []
        self.client: httpx2.AsyncClient = client or create_http_client(ModelConfig())
        self.app: FastAPI = FastAPI()
        self.app.add_api_route("/v1/chat/completions", self.generate, methods=["POST"])
        self.app.add_api_route("/v1/tokenize", self.tokenize, methods=["POST"])

    def contains_credential(self, text: str) -> bool:
        return self.worker_token is not None and self.worker_token.get_secret_value() in text

    async def forward(self, raw: bytes, *, tokenize: bool = False, fingerprint: str = "") -> Response:
        if self.worker_token is None:
            raise ValueError("GPU worker credential was not initialized")
        url = httpx2.URL(self.config.upstream_url)
        if tokenize:
            url = url.copy_with(path="/v1/tokenize")
        headers = {
            "Authorization": "Bearer " + self.worker_token.get_secret_value(),
            "Content-Type": "application/json",
        }
        if fingerprint:
            headers["X-Coaching-Prompt-Sha256"] = fingerprint
        outgoing = httpx2.Request("POST", url, content=raw, headers=headers)
        try:
            response = await self.client.send(outgoing, auth=None, follow_redirects=False)
            status, text = response.status_code, response.text
        except httpx2.TransportError as error:
            status = 502
            text = json.dumps({"error": "upstream_transport_error", "kind": type(error).__name__})
        if self.contains_credential(text):
            status, text = 502, '{"error":"upstream_credential_exposure_blocked"}'
        return Response(content=text, status_code=status, media_type="application/json")

    async def tokenize(self, request: Request) -> Response:
        if self.active_case is None:
            raise ValueError("Tokenization must belong to an active synthetic scenario")
        raw = await request.body()
        operation, evidence = operation_input(GenerationRequest.model_validate_json(raw))
        response = (
            Response(content=synthetic_budget(raw).model_dump_json(), media_type="application/json")
            if self.config.backend == "fake"
            else await self.forward(raw, tokenize=True)
        )
        budget = None
        if response.status_code == 200:
            try:
                budget = TokenBudget.model_validate_json(bytes(response.body))
            except ValueError:
                response = Response(status_code=502, content='{"error":"upstream_token_budget_schema"}')
            if budget is not None and budget.request_sha256 != hashlib.sha256(raw).hexdigest():
                budget = None
                response = Response(status_code=502, content='{"error":"upstream_request_sha256_mismatch"}')
        self.preflights.append(
            TokenPreflight(
                case_id=self.active_case.case_id,
                operation=operation,
                backend=self.config.backend,
                tokenizer=(
                    "synthetic_utf8_bytes_standin"
                    if self.config.backend == "fake"
                    else "upstream_serving_tokenizer"
                ),
                evidence=evidence,
                request_sha256=hashlib.sha256(raw).hexdigest(),
                status_code=response.status_code,
                response_body=bytes(response.body).decode("utf-8"),
                budget=budget,
            )
        )
        return response

    async def generate(self, request: Request) -> Response:
        if self.active_case is None:
            raise ValueError("Generation must belong to an active synthetic scenario")
        raw_request = await request.body()
        body = JsonDocument.model_validate_json(raw_request)
        parsed = GenerationRequest.model_validate(body.root)
        operation, evidence = operation_input(parsed)
        started = time.perf_counter()
        case = self.active_case
        request_sha = hashlib.sha256(raw_request).hexdigest()
        fingerprint = request.headers.get("X-Coaching-Prompt-Sha256", "")
        matching = next(
            (
                row
                for row in reversed(self.preflights)
                if row.case_id == case.case_id
                and row.request_sha256 == request_sha
                and row.budget is not None
            ),
            None,
        )
        if (
            matching is None
            or matching.budget is None
            or not secrets.compare_digest(fingerprint, matching.budget.prompt_sha256)
        ):
            return Response(status_code=409, content='{"error":"tokenizer_preflight_changed"}')
        index = len(self.generations)
        pending = Generation(
            case_id=case.case_id,
            operation=operation,
            backend=self.config.backend,
            request_body=body,
            evidence=evidence,
            status_code=0,
            response_body="generation_pending",
            elapsed_seconds=0.0,
            request_sha256=request_sha,
            prompt_sha256=fingerprint,
        )
        self.generations.append(pending)
        if self.config.backend == "fake":
            status, raw = fake_completion(case, operation, parsed.model)
        else:
            response = await self.forward(raw_request, fingerprint=fingerprint)
            status, raw = response.status_code, bytes(response.body).decode("utf-8")
        self.generations[index] = pending.model_copy(
            update={
                "status_code": status,
                "response_body": raw,
                "elapsed_seconds": time.perf_counter() - started,
            }
        )
        return Response(content=raw, status_code=status, media_type="application/json")


@asynccontextmanager
async def serve(app: FastAPI) -> AsyncGenerator[str]:
    """Bind an owned ephemeral TCP socket; never terminate or reuse another process."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(128)
        port = TypeAdapter(tuple[str, int]).validate_python(listener.getsockname())[1]
        server = uvicorn.Server(
            uvicorn.Config(
                app,
                host="127.0.0.1",
                port=port,
                log_level="critical",
                access_log=False,
                timeout_graceful_shutdown=5,
            )
        )
        stopped = anyio.Event()

        async def run_server() -> None:
            try:
                await server.serve(sockets=[listener])
            finally:
                stopped.set()

        async with anyio.create_task_group() as group:
            _ = group.start_soon(run_server)
            try:
                with anyio.fail_after(10):
                    while not server.started:  # noqa: ASYNC110 - uvicorn exposes a readiness flag, not an event.
                        await anyio.sleep(0.01)
                yield f"http://127.0.0.1:{port}"
            finally:
                server.should_exit = True
                with anyio.move_on_after(10, shield=True):
                    await stopped.wait()
                group.cancel_scope.cancel()
