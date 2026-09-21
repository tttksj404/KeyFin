"""Trace real TCP calls and explicit pass/fail checks; never record authentication."""

import time
from typing import final

import httpx2

from benchmarks.coaching.flow.contracts import Check, Exchange, ModelObservation, RoutingObservation
from coaching_service.chat_answers import ChatAnswer
from coaching_service.llm_contract import Routing
from coaching_service.schemas import Coaching, JsonDocument


@final
class Flow:
    def __init__(self, client: httpx2.Client) -> None:
        self.client: httpx2.Client = client
        self.checks: list[Check] = []
        self.exchanges: list[Exchange] = []
        self.observations: list[ModelObservation] = []
        self.routes: list[RoutingObservation] = []

    def check(self, name: str, *, passed: bool) -> None:
        self.checks.append(Check(name=name, passed=passed))

    def request(
        self,
        stage: str,
        method: str,
        path: str,
        body: JsonDocument | None = None,
        *,
        key: str | None = None,
    ) -> JsonDocument:
        started = time.perf_counter()
        response = self.client.request(
            method,
            path,
            json=body.root if body else None,
            headers={"Idempotency-Key": key or stage},
            follow_redirects=False,
        )
        result = JsonDocument.model_validate_json(response.content)
        self.exchanges.append(
            Exchange(
                stage=stage,
                method=method,
                path=path,
                status=response.status_code,
                latency_ms=round((time.perf_counter() - started) * 1000, 3),
                request=body,
                response=result,
            )
        )
        self.check(stage + ":http", passed=response.status_code == 200)
        if response.status_code != 200:
            raise RuntimeError("unexpected_flow_http_status:" + stage)
        return result

    def observe(self, stage: str, answer: Coaching | ChatAnswer) -> None:
        self.observations.append(
            ModelObservation(
                stage=stage,
                source=answer.wording_source,
                model=answer.model,
                fallback_reason=answer.fallback_reason,
            )
        )
        match answer:
            case Coaching():
                route = answer.receipt.routing
                required = answer.receipt.numeric_request is not None
                numeric_mode = (
                    answer.receipt.numeric_request.root.get("mode")
                    if answer.receipt.numeric_request is not None
                    else None
                )
                allows_deterministic = numeric_mode in {"forecast", "risk"} or (
                    answer.receipt.trigger in {"requested_review", "historical_coaching_followup"}
                    and answer.model == "not_called"
                )
            case ChatAnswer():
                raw = answer.evidence.root.get("routing")
                route = JsonDocument.model_validate(raw) if raw is not None else None
                required = answer.answer_type in {"spending_history", "personal_context"}
                # Exact personal/history grammars are evaluated by the engine after
                # routing.  They do not need an LLM decision, but they must retain
                # explicit template provenance and an engine-only response receipt.
                deterministic_modes = (
                    frozenset({"history", "personal"})
                    if (
                        required
                        and answer.wording_source == "engine"
                        and answer.model == "not_called"
                        and answer.fallback_reason is None
                    )
                    else frozenset()
                )
                self.observe_route(
                    stage,
                    route,
                    required=required,
                    deterministic_modes=deterministic_modes,
                )
                return
        self.observe_route(stage, route, required=required, allows_deterministic=allows_deterministic)

    def observe_route(
        self,
        stage: str,
        route: JsonDocument | None,
        *,
        required: bool,
        allows_deterministic: bool = False,
        deterministic_modes: frozenset[str] = frozenset(),
    ) -> None:
        parsed = Routing.model_validate(route.root) if route is not None else None
        self.routes.append(
            RoutingObservation(
                stage=stage,
                metadata_available=parsed is not None,
                mode=parsed.mode if parsed is not None else None,
                source=parsed.source if parsed is not None else None,
                fallback_reason=parsed.fallback_reason if parsed is not None else None,
            )
        )
        if required or parsed is not None:
            # Ordinary routes still need an adopted model decision.  The only template
            # route that is admissible here is an independently checked FDT result or
            # a stored-coaching follow-up that reads the current ledger exactly.
            model_accepted = parsed is not None and parsed.source == "llm" and parsed.fallback_reason is None
            deterministic_accepted = (
                parsed is not None
                and parsed.source == "template"
                and parsed.fallback_reason is None
                and parsed.mode in (
                    {"forecast", "risk", "review"} if allows_deterministic else deterministic_modes
                )
            )
            self.check(
                stage + ":router_accepted",
                passed=model_accepted or deterministic_accepted,
            )

    def turn(self, stage: str, session: str, question: str) -> JsonDocument:
        return self.request(
            stage, "POST", f"/v1/sessions/{session}/messages", JsonDocument({"question": question})
        )
