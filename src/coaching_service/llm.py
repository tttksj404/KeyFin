"""Bounded OpenAI-compatible inference; original engine outputs remain authoritative."""

from __future__ import annotations

import json
import re
import socket
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, assert_never, cast

import anyio
import httpx2
from pydantic import ValidationError

from coaching_service.chart_wording import ChartSelection, selected_chart_wording
from coaching_service.dialogue_decision import DialogueDecision, DialogueSelection
from coaching_service.evidence import context_limited, operation_evidence, token_retry_evidence
from coaching_service.finance_knowledge import FinanceSelection, selected_finance_wording
from coaching_service.gpu_link import GpuLinkFailure, GpuLinkSubmit, canonical_request_sha256
from coaching_service.inference_metrics import InferenceTrace, measure_inference
from coaching_service.llm_contract import (
    CompletionEnvelope,
    EvidenceInput,
    Judgment,
    JudgmentDraft,
    ModelConfig,
    Operation,
    Routing,
    RoutingDraft,
    Wording,
)
from coaching_service.llm_prompt import TEMPLATE_TEXT, system_prompt, user_payload, wording_problem
from coaching_service.schemas import JsonDocument
from coaching_service.token_budget import BudgetFailure, TokenBudget, check_token_budget

if TYPE_CHECKING:
    from pydantic import BaseModel, JsonValue

    from coaching_service.gpu_link import GpuLinkOutcome

_LIMITS: Final = httpx2.Limits(max_connections=200, max_keepalive_connections=40, keepalive_expiry=30)
_JSON_FENCE: Final = re.compile(r"```(?:json)?\r?\n(.*?)\r?\n```", re.DOTALL)
_SELECTION_MAX_TOKENS: Final = 96
_COACHING_MAX_TOKENS: Final = 160


def unique_json_object(pairs: list[tuple[str, JsonValue]]) -> dict[str, JsonValue]:
    result: dict[str, JsonValue] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def structured_json(text: str) -> str:
    """Remove only one complete JSON fence; preserve all strict parsing requirements."""
    candidate = text.strip()
    fenced = _JSON_FENCE.fullmatch(candidate)
    if fenced is not None and "```" not in fenced[1]:
        candidate = fenced[1]
    _ = cast("object", json.loads(candidate, object_pairs_hook=unique_json_object))
    return candidate


@dataclass(frozen=True, slots=True)
class InferenceFailure:
    reason: str


@dataclass(frozen=True, slots=True)
class InferenceText:
    text: str


def finance_inference_wording(
    evidence: EvidenceInput, result: InferenceText | InferenceFailure, model: str,
) -> Wording:
    match result:
        case InferenceFailure(reason=reason):
            return selected_finance_wording(None, model, reason)
        case InferenceText(text=text):
            try:
                raw = structured_json(text)
            except (ValueError, RecursionError):
                return selected_finance_wording(None, model)
            return selected_finance_wording(raw, model, evidence=evidence)
        case unreachable:
            assert_never(unreachable)


def chart_inference_wording(
    evidence: EvidenceInput, result: InferenceText | InferenceFailure, model: str
) -> Wording:
    match result:
        case InferenceFailure(reason=reason):
            return selected_chart_wording(evidence, None, model, reason)
        case InferenceText(text=text):
            try:
                raw = structured_json(text)
            except (ValueError, RecursionError):
                return selected_chart_wording(evidence, None, model, "invalid_chart_fact_selection")
            return selected_chart_wording(evidence, raw, model)
        case unreachable:
            assert_never(unreachable)


def request_timeout(config: ModelConfig) -> httpx2.Timeout:
    return httpx2.Timeout(
        connect=config.connect_timeout_seconds,
        read=config.read_timeout_seconds,
        write=config.write_timeout_seconds,
        pool=config.pool_timeout_seconds,
    )


def create_http_client(config: ModelConfig) -> httpx2.AsyncClient:
    """Return a reusable caller-owned client; use it as an async context manager."""
    transport = httpx2.AsyncHTTPTransport(
        http2=True,
        retries=0,
        trust_env=False,
        limits=_LIMITS,
        socket_options=[(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)],
    )
    return httpx2.AsyncClient(
        transport=transport, timeout=request_timeout(config), follow_redirects=False, trust_env=False
    )


def transport_failure(error: httpx2.RequestError) -> InferenceFailure:
    match error:
        case httpx2.PoolTimeout():
            reason = "pool_timeout"
        case httpx2.ConnectTimeout():
            reason = "connect_timeout"
        case httpx2.ReadTimeout():
            reason = "read_timeout"
        case httpx2.WriteTimeout():
            reason = "write_timeout"
        case httpx2.TimeoutException():
            reason = "http_timeout"
        case httpx2.DecodingError():
            reason = "response_decoding_error"
        case httpx2.TransportError():
            reason = "transport_error"
        case httpx2.RequestError():
            reason = "request_error"
        case _ as unreachable:
            assert_never(unreachable)
    return InferenceFailure(reason)


class OpenAICompatibleCoachModel:
    """Supplementary wording, typed judgment and mode routing over one pinned model endpoint."""

    def __init__(
        self,
        config: ModelConfig,
        *,
        client: httpx2.AsyncClient | None = None,
        gpu_link_submit: GpuLinkSubmit | None = None,
    ) -> None:
        self._config: ModelConfig = config
        self._client: httpx2.AsyncClient | None = client
        # Only set in COACH_GPU_LINK_MODE=ws; the loopback (default) path never sets
        # this, so ``_execute`` keeps using ``self._client`` exactly as before.
        self._gpu_link_submit: GpuLinkSubmit | None = gpu_link_submit
        self._limiter: anyio.CapacityLimiter = anyio.CapacityLimiter(config.max_concurrency)

    @property
    def deterministic_finance_fast_path(self) -> bool:
        """Expose only the evaluated catalog-shortcut capability to dialogue code.

        Keeping the rest of ``ModelConfig`` private prevents another layer from
        changing transport limits or endpoint details at runtime.
        """
        return self._config.deterministic_finance_fast_path

    async def write(self, evidence: EvidenceInput) -> Wording:
        """차트는 주어진 근거 ID만 선택하고 일반 코칭은 제한된 보조 문장을 검증한다.

        모델 오류·형식 위반은 원인이 기록된 정형 문구로 전환한다. 이 성공 여부와
        FDT의 수치 정확성은 별개이며 LLM 출력으로 금융 수치를 덮어쓰지 않는다.
        """
        result = await self._infer(evidence, "write")
        match evidence.purpose:
            case "finance":
                return finance_inference_wording(evidence, result, self._config.model)
            case "chart":
                return chart_inference_wording(evidence, result, self._config.model)
            case "coaching":
                pass
            case unreachable:
                assert_never(unreachable)
        match result:
            case InferenceFailure(reason=reason):
                return self._fallback(reason)
            case InferenceText(text=text):
                problem = wording_problem(text)
                if problem:
                    return self._fallback(problem)
                return Wording(text=text.strip(), source="llm", model=self._config.model)
            case _ as unreachable:
                assert_never(unreachable)

    async def judge(self, evidence: EvidenceInput) -> Judgment:
        result = await self._infer(evidence, "judge")
        match result:
            case InferenceFailure(reason=reason):
                return Judgment(
                    decision="needs_data",
                    reason_code="insufficient_context",
                    confidence=0.0,
                    source="template",
                    fallback_reason=reason,
                )
            case InferenceText(text=text):
                try:
                    parsed = JudgmentDraft.model_validate_json(structured_json(text))
                except (ValueError, RecursionError):
                    return Judgment(
                        decision="needs_data",
                        reason_code="insufficient_context",
                        confidence=0.0,
                        source="template",
                        fallback_reason="invalid_schema",
                    )
                return Judgment(
                    decision=parsed.decision,
                    reason_code=parsed.reason_code,
                    confidence=parsed.confidence,
                    source="llm",
                )
            case _ as unreachable:
                assert_never(unreachable)

    async def route(self, evidence: EvidenceInput) -> Routing:
        result = await self._infer(evidence, "route")
        match result:
            case InferenceFailure(reason=reason):
                return Routing(mode="review", source="template", fallback_reason=reason)
            case InferenceText(text=text):
                try:
                    parsed = RoutingDraft.model_validate_json(structured_json(text))
                except (ValueError, RecursionError):
                    return Routing(mode="review", source="template", fallback_reason="invalid_schema")
                return Routing(mode=parsed.mode, source="llm")
            case _ as unreachable:
                assert_never(unreachable)

    async def decide(self, routing: EvidenceInput, finance: EvidenceInput) -> DialogueDecision:
        """Select the route and approved finance facts in one bounded inference.

        The switch preserves the frozen two-call baseline for paired experiments. Numeric
        routes still execute the original tools; this selection cannot supply FDT values.
        """
        if not self._config.combined_dialogue:
            return DialogueDecision(routing=await self.route(routing))
        result = await self._infer(finance, "route")
        match result:
            case InferenceFailure(reason=reason):
                return DialogueDecision(routing=Routing(
                    mode="review", source="template", fallback_reason=reason,
                ))
            case InferenceText(text=text):
                try:
                    selected = DialogueSelection.model_validate_json(structured_json(text))
                except (ValueError, RecursionError):
                    return DialogueDecision(routing=Routing(
                        mode="review", source="template", fallback_reason="invalid_schema",
                    ))
                wording = None if selected.finance is None else selected_finance_wording(
                    selected.finance.model_dump_json(), self._config.model, evidence=finance,
                )
                return DialogueDecision(routing=Routing(mode=selected.mode, source="llm"), finance=wording)
            case unreachable:
                assert_never(unreachable)

    def _fallback(self, reason: str) -> Wording:
        return Wording(
            text=TEMPLATE_TEXT,
            source="template",
            fallback_reason=reason,
            model=self._config.model,
        )

    def _request(self, evidence: EvidenceInput, operation: Operation) -> httpx2.Request:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self._config.token is not None:
            headers["Authorization"] = f"Bearer {self._config.token.get_secret_value()}"
        payload = self._payload(evidence, operation)
        # A fresh Request avoids copying unrelated client authorization, cookies, or base URL.
        return httpx2.Request(
            "POST",
            self._config.endpoint_url or "",
            headers=headers,
            json=payload,
            extensions={"timeout": request_timeout(self._config).as_dict()},
        )

    def _payload(self, evidence: EvidenceInput, operation: Operation) -> dict[str, JsonValue]:
        """Build the exact chat-completion body sent over httpx today.

        In ``COACH_GPU_LINK_MODE=ws`` this same dict travels as a WS request frame's
        ``payload["body"]`` instead of an httpx JSON body -- the request/response
        schema is unchanged, only the transport underneath it differs.
        """
        payload: dict[str, JsonValue] = {
            "model": self._config.model,
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt(
                        operation,
                        chart=evidence.purpose == "chart",
                        finance=evidence.purpose == "finance",
                        route_prompt_version=self._config.route_prompt_version,
                        finance_prompt_version=self._config.finance_prompt_version,
                    ),
                },
                {"role": "user", "content": user_payload(evidence)},
            ],
            "temperature": 0,
            "max_tokens": self._output_tokens(evidence, operation),
            "stream": False,
        }
        if self._config.generation_seed is not None:
            # The field is supported by the isolated OpenAI-compatible runtime.
            # It remains absent by default so existing deployments retain their
            # established sampling behavior until a candidate passes evaluation.
            payload["seed"] = self._config.generation_seed
        match operation:
            case "write":
                if evidence.purpose == "finance":
                    payload["response_format"] = {
                        "type": "json_schema",
                        "json_schema": {
                            "name": "finance_facts",
                            "strict": True,
                            "schema": FinanceSelection.model_json_schema(),
                        },
                    }
                if evidence.purpose == "chart":
                    payload["response_format"] = {
                        "type": "json_schema",
                        "json_schema": {
                            "name": "chart_facts",
                            "strict": True,
                            "schema": ChartSelection.model_json_schema(),
                        },
                    }
            case "judge" | "route":
                schema: type[BaseModel] = JudgmentDraft if operation == "judge" else RoutingDraft
                if operation == "route" and evidence.purpose == "finance":
                    schema = DialogueSelection
                payload["response_format"] = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": operation,
                        "strict": True,
                        "schema": schema.model_json_schema(),
                    },
                }
            case _ as unreachable:
                assert_never(unreachable)
        return payload

    async def _infer(self, evidence: EvidenceInput, operation: Operation) -> InferenceText | InferenceFailure:
        with measure_inference(operation) as trace:
            return await self._execute(evidence, operation, trace)

    async def _execute(  # noqa: PLR0911 - each terminal transport outcome preserves its exact fallback reason.
        self, evidence: EvidenceInput, operation: Operation, trace: InferenceTrace,
    ) -> InferenceText | InferenceFailure:
        # In COACH_GPU_LINK_MODE=ws the outbound tunnel (``_gpu_link_submit``) is the
        # transport, so no ``endpoint_url`` is needed; inference is only truly disabled
        # when neither an HTTP endpoint nor a ws submit path exists. The loopback
        # (default) path still requires ``endpoint_url`` exactly as before.
        if self._config.endpoint_url is None and self._gpu_link_submit is None:
            trace.set_outcome("rejected")
            return InferenceFailure("disabled")
        # In COACH_GPU_LINK_MODE=ws there is no httpx client transport; the loopback
        # (default) path is unchanged and still requires an open client.
        if self._gpu_link_submit is None and (self._client is None or self._client.is_closed):
            trace.set_outcome("rejected")
            return InferenceFailure("client_unavailable" if self._client is None else "client_closed")
        evidence = operation_evidence(evidence, operation)
        if context_limited(evidence):
            trace.set_outcome("rejected")
            return InferenceFailure("context_limit")
        try:
            with anyio.fail_after(self._config.timeout_seconds):
                # Measure only acquisition: wrapping the async-with block would count generation as wait.
                with trace.phase("limiter_wait"):
                    await self._limiter.acquire()
                try:
                    result = await self._dispatch(evidence, operation, trace)
                    # The first request is the only trustworthy way to learn the
                    # serving tokenizer's limit. A supplementary writer may then
                    # retry once with no financial payload; selection calls never
                    # lose their source facts merely to fit a context window.
                    if isinstance(result, InferenceFailure) and result.reason == "input_token_limit":
                        retry = token_retry_evidence(evidence)
                        if retry is not None:
                            return await self._dispatch(retry, operation, trace)
                    return result
                finally:
                    self._limiter.release()
        except TimeoutError:
            trace.set_outcome("timeout")
            return InferenceFailure("deadline_exceeded")
        except httpx2.RequestError as error:
            trace.set_outcome("timeout" if isinstance(error, httpx2.TimeoutException) else "failure")
            return transport_failure(error)

    async def _dispatch(
        self, evidence: EvidenceInput, operation: Operation, trace: InferenceTrace,
    ) -> InferenceText | InferenceFailure:
        """Route to the WS tunnel when configured, otherwise the unchanged httpx path."""
        max_tokens = self._output_tokens(evidence, operation)
        if self._gpu_link_submit is not None:
            return await self._send_ws(self._gpu_link_submit, evidence, operation, max_tokens, trace)
        assert self._client is not None  # noqa: S101 - guaranteed by the guard at the top of ``_execute``.
        return await self._send(self._client, self._request(evidence, operation), max_tokens, trace)

    async def _send(
        self,
        client: httpx2.AsyncClient,
        request: httpx2.Request,
        max_tokens: int,
        trace: InferenceTrace,
    ) -> InferenceText | InferenceFailure:
        if self._config.token_preflight:
            with trace.phase("token_preflight"):
                budget = await check_token_budget(client, request, max_tokens)
            if isinstance(budget, BudgetFailure):
                trace.set_outcome("rejected")
                return InferenceFailure(budget.reason)
            request.headers["X-Coaching-Prompt-Sha256"] = budget.prompt_sha256
        response: httpx2.Response | None = None
        try:
            # Roundtrip includes streamed body parsing. Cleanup belongs only to total elapsed time.
            with trace.phase("generation_http"):
                response = await client.send(request, stream=True, auth=None, follow_redirects=False)
                result = await self._read(response)
            trace.set_outcome("failure" if isinstance(result, InferenceFailure) else "success")
            return result
        finally:
            if response is not None:
                with anyio.move_on_after(0.1, shield=True):
                    await response.aclose()

    async def _send_ws(
        self,
        submit: GpuLinkSubmit,
        evidence: EvidenceInput,
        operation: Operation,
        max_tokens: int,
        trace: InferenceTrace,
    ) -> InferenceText | InferenceFailure:
        """WS-tunnel twin of ``_send``: same payload, timeouts and fallback contract.

        The frozen dict from ``_payload`` becomes ``payload["body"]`` on the request
        frame for both ``tokenize`` and ``complete`` ops, instead of an httpx JSON body.
        """
        body = self._payload(evidence, operation)
        expected_prompt_sha256: str | None = None
        if self._config.token_preflight:
            with trace.phase("token_preflight"):
                outcome = await submit("tokenize", {"body": body}, self._config.timeout_seconds)
            budget = self._ws_budget(outcome, body, max_tokens)
            if isinstance(budget, InferenceFailure):
                trace.set_outcome("rejected")
                return budget
            expected_prompt_sha256 = budget
        with trace.phase("generation_http"):
            outcome = await submit(
                "complete", {"body": body, "expected_prompt_sha256": expected_prompt_sha256},
                self._config.timeout_seconds,
            )
            result = self._read_ws(outcome)
        trace.set_outcome("failure" if isinstance(result, InferenceFailure) else "success")
        return result

    def _ws_budget(
        self, outcome: GpuLinkOutcome, body: dict[str, JsonValue], max_tokens: int,
    ) -> str | InferenceFailure:
        """WS-tunnel twin of ``token_budget.validate_budget`` operating on a parsed dict."""
        if isinstance(outcome, GpuLinkFailure):
            return InferenceFailure(outcome.reason)
        try:
            budget = TokenBudget.model_validate(outcome.result)
        except ValidationError:
            return InferenceFailure("token_preflight_invalid_schema")
        if budget.request_sha256 != canonical_request_sha256(body):
            return InferenceFailure("token_preflight_request_mismatch")
        if budget.prompt_tokens > budget.max_input_tokens:
            return InferenceFailure("input_token_limit")
        if max_tokens > budget.max_output_tokens:
            return InferenceFailure("output_token_limit")
        return budget.prompt_sha256

    def _read_ws(self, outcome: GpuLinkOutcome) -> InferenceText | InferenceFailure:
        """WS-tunnel twin of ``_read`` operating on an already-decoded response dict."""
        if isinstance(outcome, GpuLinkFailure):
            return InferenceFailure(outcome.reason)
        encoded = json.dumps(outcome.result, ensure_ascii=False).encode()
        if len(encoded) > self._config.max_response_bytes:
            return InferenceFailure("response_too_large")
        try:
            # ``model_validate_json`` (not ``model_validate``) so a JSON array survives
            # this strict contract's tuple-typed fields exactly like the httpx path,
            # which always validates raw response bytes rather than a parsed dict.
            completion = CompletionEnvelope.model_validate_json(encoded)
        except ValidationError:
            return InferenceFailure("invalid_response")
        return InferenceText(completion.choices[0].message.content)

    def _output_tokens(self, evidence: EvidenceInput, operation: Operation) -> int:
        """Match the generation ceiling to the validated response shape.

        Route and fact-selection responses are compact JSON, while supplementary
        coaching wording is capped at 400 characters by its admission boundary.
        Keeping those bounds small reduces single-request decoder time and uses the
        same value for token preflight as for generation.
        """
        if operation == "route" or evidence.purpose in {"finance", "chart"}:
            return min(self._config.max_tokens, _SELECTION_MAX_TOKENS)
        return min(self._config.max_tokens, _COACHING_MAX_TOKENS)

    async def _read(self, response: httpx2.Response) -> InferenceText | InferenceFailure:
        if response.status_code != 200:
            if response.status_code == 413:
                # A worker may return this before preflight is enabled or when a
                # proxy sits in front of it. Treat only its exact stable reason
                # as retriable; generic 413 responses can be body/route limits.
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    if len(body) + len(chunk) > 1024:
                        break
                    body.extend(chunk)
                try:
                    error = JsonDocument.model_validate_json(body).root
                except ValueError:
                    error = None
                if isinstance(error, dict) and error.get("detail") == "input_token_limit":
                    return InferenceFailure("input_token_limit")
            return InferenceFailure(f"http_status_{response.status_code}")
        body = bytearray()
        async for chunk in response.aiter_bytes():
            if len(body) + len(chunk) > self._config.max_response_bytes:
                return InferenceFailure("response_too_large")
            body.extend(chunk)
        try:
            _ = cast("object", json.loads(body, object_pairs_hook=unique_json_object))
            completion = CompletionEnvelope.model_validate_json(body)
        except (ValueError, RecursionError):
            return InferenceFailure("invalid_response")
        return InferenceText(completion.choices[0].message.content)
