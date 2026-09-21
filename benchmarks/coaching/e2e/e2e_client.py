"""Shared real HTTP requests and receipt provenance checks."""

import time
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import anyio
import httpx2

from benchmarks.coaching.e2e.e2e_contracts import Check, E2ECase, HttpExchange
from benchmarks.coaching.e2e.e2e_runtime import Gateway
from coaching_service.engine import ENGINE_COMMIT, EngineAdapter
from coaching_service.evidence import bounded_evidence, operation_evidence
from coaching_service.llm_contract import EvidenceInput, Operation
from coaching_service.rendering import authoritative_text
from coaching_service.schemas import Coaching, JsonDocument, Receipt
from coaching_service.settings import Client


def authoritative_fdt(receipt: Receipt) -> bool:
    """Return whether a complete receipt deliberately has no supplementary writer."""
    return (
        receipt.numeric_request is not None
        and receipt.numeric_result is not None
    ) or (receipt.trigger == "requested_review" and receipt.payment is None)


class ScenarioIO:
    def __init__(
        self,
        case: E2ECase,
        client: httpx2.AsyncClient,
        base: str,
        credentials: tuple[Client, ...],
        gateway: Gateway,
    ) -> None:
        self.case: E2ECase = case
        self.client: httpx2.AsyncClient = client
        self.base: str = base
        self.credentials: tuple[Client, ...] = credentials
        self.gateway: Gateway = gateway
        self.day: date = gateway.config.as_of or datetime.now(ZoneInfo("Asia/Seoul")).date()
        self.checks: list[Check] = []
        self.http: list[HttpExchange] = []
        self.sources: list[str] = []
        self.judgment_sources: list[str] = []
        self.routing_sources: list[str] = []
        self.deterministic_routes: int = 0
        self.fallbacks: list[str] = []
        self.observed_route: str | None = None
        self.serial: int = 0
        self.engine: EngineAdapter = EngineAdapter()

    def check(self, name: str, passed: bool, detail: str = "") -> None:
        self.checks.append(Check(name=name, passed=passed, detail=detail))

    async def request(  # noqa: PLR0913 - explicit HTTP and credential controls stay visible in each audit call.
        self,
        method: str,
        path: str,
        body: JsonDocument | None = None,
        *,
        key: str | None = None,
        expected: int = 200,
        foreign: bool = False,
        invalid_token: bool = False,
    ) -> JsonDocument:
        credential = next(
            row
            for row in self.credentials
            if (row.user_id != self.case.owner if foreign else row.user_id == self.case.owner)
        )
        token = "invalid-synthetic-credential" if invalid_token else credential.token.get_secret_value()
        self.serial += 1
        headers = {"Authorization": "Bearer " + token, "Idempotency-Key": key or f"request-{self.serial}"}
        started = time.perf_counter()
        response = await self.client.request(
            method, self.base + path, json=body.root if body else None, headers=headers
        )
        result = JsonDocument.model_validate_json(response.text)
        self.http.append(
            HttpExchange(
                case_id=self.case.case_id,
                caller_user_id=None if invalid_token else credential.user_id,
                idempotency_key=headers["Idempotency-Key"],
                method=method,
                path=path,
                status_code=response.status_code,
                elapsed_seconds=time.perf_counter() - started,
                request_body=body,
                response_body=result,
            )
        )
        self.check(
            "http_expected_status",
            response.status_code == expected,
            f"{method} {path}: {response.status_code}, expected {expected}",
        )
        return result

    async def verify_coaching(self, raw: JsonDocument, *, preflight_start: int = 0) -> Coaching:
        """Check one saved answer against only the model calls made for that answer."""
        coaching = Coaching.model_validate(raw.root)
        self.sources.append(coaching.wording_source)
        if coaching.fallback_reason:
            self.fallbacks.append(coaching.fallback_reason)
        receipt = coaching.receipt
        stored = await self.request("GET", "/v1/coaching/" + coaching.id)
        self.check("stored_receipt_exact", Coaching.model_validate(stored.root) == coaching)
        self.check(
            "authoritative_text_preserved", coaching.text.startswith(authoritative_text(receipt) + "\n\n")
        )
        self.check("engine_commit_exact", receipt.engine_commit == ENGINE_COMMIT)
        twin = await self.request("GET", "/v1/twin")
        numeric_receipt = receipt.numeric_request is not None and receipt.numeric_result is not None
        if numeric_receipt:
            self.check(
                "original_engine_review_not_run",
                receipt.result == JsonDocument({"status": "not_run", "reason": "numeric_operation"}),
            )
        else:
            expected = await anyio.to_thread.run_sync(self.engine.review, twin, receipt.request)
            self.check("original_engine_review_exact", expected == receipt.result)
        calls = [
            row
            for row in self.gateway.preflights[preflight_start:]
            if row.case_id == self.case.case_id and row.operation == "write"
        ]
        if authoritative_fdt(receipt):
            self.check(
                "authoritative_receipt_no_writer",
                not calls and coaching.wording_source == "template" and coaching.model == "not_called",
            )
        elif calls:
            self.verify_projection(receipt, "write", calls[-1].evidence)
        else:
            self.check("writer_projection_exact", passed=False, detail="No writer preflight was observed")
        if receipt.numeric_request is not None:
            numeric = await anyio.to_thread.run_sync(self.engine.numeric, twin, receipt.numeric_request)
            self.check("numeric_engine_result_exact", numeric == receipt.numeric_result)
        return coaching

    def verify_projection(self, receipt: Receipt, operation: Operation, received: EvidenceInput) -> None:
        before = receipt.model_dump_json()
        # Reconstruct the declared wire contract independently of the product projection helper.
        # The full receipt is still compared against a separate engine call above.
        match operation:
            case "write":
                source = EvidenceInput(
                    question=received.question,
                    history=received.history,
                    facts_json=JsonDocument(
                        {"basis": "displayed_receipt", "authoritative_answer": authoritative_text(receipt)}
                    ).model_dump_json(),
                )
            case "route":
                source = EvidenceInput(
                    question=received.question,
                    history=received.history,
                    facts_json='{"operation":"dialogue"}',
                )
            case "judge":
                source = bounded_evidence(receipt, question=received.question, history=received.history)
        expected = operation_evidence(source, operation)
        name = "writer_projection_exact" if operation == "write" else operation + "_projection_exact"
        self.check(name, received == expected)
        self.check("projection_original_receipt_preserved", receipt.model_dump_json() == before)

    async def review(self) -> Coaching:
        request = JsonDocument(
            {
                "on_date": self.day.isoformat(),
                "through_date": (self.day + timedelta(days=7)).isoformat(),
                "paths": 20,
                "seed": 42,
            }
        )
        before = len(self.gateway.preflights)
        return await self.verify_coaching(
            await self.request("POST", "/v1/coaching/reviews", request), preflight_start=before
        )
