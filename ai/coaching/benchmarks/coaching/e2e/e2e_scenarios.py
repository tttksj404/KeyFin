"""Payment-policy scenario execution; model quality does not determine HTTP success."""

from datetime import timedelta

import anyio
import httpx2
from pydantic import ValidationError

from benchmarks.coaching.e2e.e2e_actions import bootstrap_cancel, followup
from benchmarks.coaching.e2e.e2e_client import ScenarioIO
from benchmarks.coaching.e2e.e2e_contracts import CaseOutcome
from coaching_service.engine import ENGINE_COMMIT
from coaching_service.llm_contract import Judgment
from coaching_service.periods import ThroughDate, resolve_period
from coaching_service.schemas import JsonDocument, PaymentFacts, Receipt, ReviewRequest


class Scenario(ScenarioIO):
    async def run(self) -> CaseOutcome:
        start = len(self.gateway.generations)
        self.gateway.active_case = self.case
        try:
            health = await self.request("GET", "/healthz")
            verified = health.root.get("engine_files_verified")
            self.check(
                "http_engine_manifest_verified",
                health.root.get("engine_commit") == ENGINE_COMMIT
                and isinstance(verified, int)
                and verified > 0,
            )
            _ = await self.request(
                "POST",
                "/v1/twin",
                JsonDocument.model_validate_json(self.case.bootstrap(self.day).model_dump_json()),
            )
            if self.case.action == "bootstrap_cancel":
                await bootstrap_cancel(self)
            else:
                event = self.case.payment_event(self.day)
                raw = await self.request("POST", "/v1/events", event, key="payment")
                self.check(
                    "actual_payment_detection", raw.root.get("detection") == self.case.contract_detection
                )
                payment = JsonDocument.model_validate(raw.root["payment"])
                self.check(
                    "payment_ledger_exact",
                    payment.root.get("balance_before_krw") == self.case.balance_krw
                    and payment.root.get("balance_after_krw") == self.case.balance_krw - self.case.amount_krw,
                )
                original = None
                if raw.root.get("coaching") is not None:
                    original = await self.verify_coaching(JsonDocument.model_validate(raw.root["coaching"]))
                judgment_raw = raw.root.get("judgment")
                if judgment_raw is not None:
                    judgment = Judgment.model_validate(judgment_raw)
                    self.judgment_sources.append(judgment.source)
                    if judgment.fallback_reason:
                        self.fallbacks.append(judgment.fallback_reason)
                    expected = (
                        judgment.decision == "coach"
                        and judgment.confidence >= 0.8
                        and judgment.source == "llm"
                    )
                    self.check("p1_conditional_coaching", (original is not None) == expected)
                    judge_call = next(
                        (
                            row
                            for row in reversed(self.gateway.preflights)
                            if row.case_id == self.case.case_id and row.operation == "judge"
                        ),
                        None,
                    )
                    twin = await self.request("GET", "/v1/twin")
                    review = JsonDocument.model_validate_json(
                        ReviewRequest(
                            on_date=self.day, through_date=self.day + timedelta(days=7)
                        ).model_dump_json(exclude_none=True)
                    )
                    receipt = Receipt(
                        engine_commit=ENGINE_COMMIT,
                        identity=await anyio.to_thread.run_sync(self.engine.identity, twin),
                        request=review,
                        result=await anyio.to_thread.run_sync(self.engine.review, twin, review),
                        payment=PaymentFacts.model_validate(payment.root),
                        trigger="p1_ambiguous",
                        period=resolve_period(
                            self.day, ThroughDate(end_date=self.day + timedelta(days=7)), "review"
                        ),
                    )
                    if judge_call is not None:
                        self.verify_projection(receipt, "judge", judge_call.evidence)
                    else:
                        self.check("judge_projection_exact", passed=False, detail="No judge preflight")
                    self.check(
                        "actual_receipt_data_status",
                        receipt.result.root.get("status")
                        == ("ready" if self.case.snapshot == "fresh" else "needs_data"),
                    )
                elif self.case.contract_detection == "p0_half_balance":
                    self.check("p0_always_persists_coaching", original is not None)
                    if original:
                        self.check(
                            "actual_receipt_data_status",
                            original.receipt.result.root.get("status")
                            == ("ready" if self.case.snapshot == "fresh" else "needs_data"),
                        )
                else:
                    self.check("below_trigger_no_generation", len(self.gateway.generations) == start)
                notices = (await self.request("GET", "/v1/notifications")).root.get("items")
                self.check(
                    "notification_matches_policy",
                    isinstance(notices, list) and len(notices) == int(original is not None),
                )
                await followup(self, event, raw, original)
        except (ValidationError, ValueError, TypeError, httpx2.HTTPError) as error:
            self.check(
                "scenario_completed", passed=False, detail=type(error).__name__ + ": " + str(error)[:500]
            )
        expected_route = self.case.expected_route
        return CaseOutcome(
            case_id=self.case.case_id,
            owner=self.case.owner,
            checks=tuple(self.checks),
            wording_sources=tuple(self.sources),
            judgment_sources=tuple(self.judgment_sources),
            routing_sources=tuple(self.routing_sources),
            deterministic_routes=self.deterministic_routes,
            fallback_reasons=tuple(self.fallbacks),
            route_expected=expected_route,
            route_observed=self.observed_route,
            route_matches=self.observed_route == expected_route if expected_route else None,
            generation_calls=len(self.gateway.generations) - start,
        )
