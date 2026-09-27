"""Actual dialogue routing and explicit numeric-analysis evidence checks."""

from benchmarks.coaching.e2e.e2e_client import ScenarioIO, authoritative_fdt
from coaching_service.evidence_encoding import decode_facts
from coaching_service.fast_routes import deterministic_analysis_route
from coaching_service.numeric_rendering import numeric_text
from coaching_service.schemas import Coaching, JsonDocument, Receipt, Session


async def dialogue(flow: ScenarioIO, original: Coaching) -> Coaching:
    session = Session.model_validate(
        (await flow.request("POST", "/v1/sessions", JsonDocument({"coaching_id": original.id}))).root
    )
    latest = original
    for analysis in flow.case.analyses or (None,):
        explicit_route = analysis is not None
        natural_route = deterministic_analysis_route(flow.case.question) if analysis is None else None
        deterministic_route = explicit_route or natural_route is not None
        before = len(flow.gateway.preflights)
        payload = JsonDocument({"question": flow.case.question})
        if analysis is not None:
            payload.root["analysis"] = analysis.root
        latest = await flow.verify_coaching(
            await flow.request("POST", f"/v1/sessions/{session.id}/messages", payload),
            preflight_start=before,
        )
        receipt = latest.receipt
        mode = observe_routing(flow, receipt, deterministic_route=deterministic_route)
        flow.check(
            "dialogue_current_historical_separation",
            receipt.trigger in {"numeric_dialogue", "requested_review", "balance_check"}
            and receipt.payment is None
            and receipt.original_coaching_id == original.id
            and receipt.historical is not None
            and receipt.historical.engine_result == original.receipt.result,
        )
        flow.check(
            "numeric_policy_branch",
            (receipt.numeric_result is not None) == (analysis is not None or mode in {"risk", "forecast"}),
        )
        if analysis is not None:
            flow.check("explicit_analysis_exact", receipt.numeric_request == analysis)
        calls = flow.gateway.preflights[before:]
        routes = [row for row in calls if row.operation == "route"]
        writers = [row for row in calls if row.operation == "write"]
        authoritative = authoritative_fdt(receipt)
        flow.check(
            "dialogue_operations",
            len(routes) == (0 if deterministic_route else 1) and len(writers) == (0 if authoritative else 1),
        )
        if authoritative:
            flow.check(
                "dialogue_authoritative_receipt_no_writer",
                latest.wording_source == "template" and latest.model == "not_called" and not writers,
            )
        verify_deterministic_provenance(
            flow,
            receipt,
            analysis=analysis,
            natural_route=natural_route,
        )
        if routes:
            route_receipt = receipt.model_copy(
                update={"routing": None, "numeric_request": None, "numeric_result": None}
            )
            flow.verify_projection(route_receipt, "route", routes[0].evidence)
            route_facts = decode_facts(JsonDocument.model_validate_json(routes[0].evidence.facts_json))
            flow.check(
                "dialogue_router_has_no_numeric_result", route_facts.root.get("numeric_result") is None
            )
        if receipt.numeric_result is not None and writers:
            # Numeric grounding remains mandatory when an explicit mode eliminated routing.
            writer_facts = decode_facts(JsonDocument.model_validate_json(writers[0].evidence.facts_json))
            displayed = writer_facts.root.get("authoritative_answer")
            flow.check(
                "dialogue_writer_has_displayed_numeric_facts",
                isinstance(displayed, str)
                and bool(numeric_text(receipt))
                and all(line in displayed for line in numeric_text(receipt)),
            )
        stored = Session.model_validate((await flow.request("GET", "/v1/sessions/" + session.id)).root)
        flow.check(
            "dialogue_messages_persisted",
            stored.messages[-2].content == flow.case.question and stored.messages[-1].content == latest.text,
        )
    return latest


def observe_routing(flow: ScenarioIO, receipt: Receipt, *, deterministic_route: bool) -> str | None:
    """Record a route once while keeping deterministic FDT modes out of model denominators."""
    routing = receipt.routing
    mode_value = routing.root.get("mode") if routing else None
    mode = mode_value if isinstance(mode_value, str) else None
    flow.observed_route = mode
    source_value = routing.root.get("source") if routing else None
    source = source_value if isinstance(source_value, str) else None
    if deterministic_route:
        flow.deterministic_routes += 1
    elif source is not None:
        flow.routing_sources.append(source)
    reason_value = routing.root.get("fallback_reason") if routing else None
    reason = reason_value if isinstance(reason_value, str) else None
    if reason is not None:
        flow.fallbacks.append(reason)
    return mode


def verify_deterministic_provenance(
    flow: ScenarioIO,
    receipt: Receipt,
    *,
    analysis: JsonDocument | None,
    natural_route: str | None,
) -> None:
    """Require the declared template route before exempting a turn from model calls."""
    explicit_route = analysis is not None
    deterministic_route = explicit_route or natural_route is not None
    if not deterministic_route:
        return
    routing = receipt.routing
    source_value = routing.root.get("source") if routing else None
    source = source_value if isinstance(source_value, str) else None
    reason_value = routing.root.get("fallback_reason") if routing else None
    reason = reason_value if isinstance(reason_value, str) else None
    mode_value = routing.root.get("mode") if routing else None
    mode = mode_value if isinstance(mode_value, str) else None
    provenance_check = "explicit_routing_provenance" if explicit_route else "natural_routing_provenance"
    flow.check(
        provenance_check,
        source == "template"
        and reason == expected_deterministic_reason(analysis)
        and mode == expected_deterministic_mode(analysis, natural_route),
    )


def analysis_mode(analysis: JsonDocument | None) -> str | None:
    """Narrow a JSON analysis mode before comparing it with the routing contract."""
    if analysis is None:
        return None
    value = analysis.root.get("mode")
    return value if isinstance(value, str) else None


def expected_deterministic_mode(analysis: JsonDocument | None, natural_route: str | None) -> str | None:
    """Map structured non-router modes to their preserved routing contract."""
    if analysis is None:
        return natural_route
    mode = analysis_mode(analysis)
    return mode if mode in {"forecast", "risk"} else "review"


def expected_deterministic_reason(analysis: JsonDocument | None) -> str | None:
    """Structured goal, branch, and optimization modes preserve their explicit reason."""
    if analysis is None:
        return None
    return None if analysis_mode(analysis) in {"forecast", "risk"} else "structured_numeric"
