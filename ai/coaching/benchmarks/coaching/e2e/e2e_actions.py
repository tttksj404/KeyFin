"""Cancellation, replay, isolation, and notification HTTP scenarios."""

from benchmarks.coaching.e2e.e2e_client import ScenarioIO
from benchmarks.coaching.e2e.e2e_dialogue import dialogue
from coaching_service.schemas import Coaching, JsonDocument, Session


async def bootstrap_cancel(flow: ScenarioIO) -> None:
    before = await flow.request("GET", "/v1/twin")
    payload = JsonDocument(
        {
            "expected_revision": 0,
            "event": {
                "type": "cancel_transaction",
                "event_id": "cancel-history",
                "user_id": flow.case.owner,
                "transaction_id": "opening-history",
            },
        }
    )
    _ = await flow.request("POST", "/v1/events", payload, expected=409)
    flow.check("bootstrap_cancel_rollback", await flow.request("GET", "/v1/twin") == before)
    payload = JsonDocument(
        {**payload.root, "cancellation_balance": {"envelope": flow.case.envelope, "balance_krw": 110000}}
    )
    canceled = await flow.request("POST", "/v1/events", payload)
    flow.check("bootstrap_cancel_reconciled", canceled.root.get("detection") == "cancellation_reconciled")
    payment = flow.case.payment_event(flow.day)
    identity = JsonDocument.model_validate(canceled.root["identity"])
    payment.root["expected_revision"] = identity.root["revision"]
    payment.root["event"] = {
        "type": "transaction",
        "event_id": "small-payment",
        "user_id": flow.case.owner,
        "transaction": flow.case.transaction(flow.day, "after-refund", 1000).root,
    }
    result = await flow.request("POST", "/v1/events", payment)
    facts = JsonDocument.model_validate(result.root["payment"])
    flow.check(
        "bootstrap_cancel_authoritative_ledger",
        facts.root.get("balance_before_krw") == 110000 and facts.root.get("balance_after_krw") == 109000,
    )


async def followup(
    flow: ScenarioIO, event: JsonDocument, result: JsonDocument, original: Coaching | None
) -> None:
    action = flow.case.action
    identity = JsonDocument.model_validate(result.root["identity"])
    revision = identity.root["revision"]
    if action in {"duplicate_key", "duplicate_event", "conflict"}:
        before = len(flow.gateway.generations)
        preflight_count = len(flow.gateway.preflights)
        twin = await flow.request("GET", "/v1/twin")
        if action == "duplicate_key":
            repeated = await flow.request("POST", "/v1/events", event, key="payment")
            flow.check("duplicate_response_exact", repeated == result)
        elif action == "duplicate_event":
            repeated = await flow.request(
                "POST", "/v1/events", JsonDocument({**event.root, "expected_revision": revision})
            )
            flow.check("duplicate_event_detected", repeated.root.get("detection") == "duplicate_transaction")
        else:
            _ = await flow.request(
                "POST",
                "/v1/events",
                JsonDocument({**event.root, "expected_revision": revision}),
                key="payment",
                expected=409,
            )
            _ = await flow.request("POST", "/v1/events", event, expected=409)
        flow.check("duplicate_no_generation", len(flow.gateway.generations) == before)
        flow.check("duplicate_no_tokenization", len(flow.gateway.preflights) == preflight_count)
        flow.check("duplicate_twin_unchanged", await flow.request("GET", "/v1/twin") == twin)
    elif action == "refresh":
        refreshed = await flow.request(
            "POST",
            "/v1/events",
            JsonDocument(
                {
                    "expected_revision": revision,
                    "event": flow.case.snapshot_event(flow.day, flow.case.amount_krw, "refresh-balance").root,
                }
            ),
        )
        flow.check("snapshot_refresh_detected", refreshed.root.get("detection") == "snapshot_updated")
        flow.check(
            "snapshot_ready_recovery", (await flow.review()).receipt.result.root.get("status") == "ready"
        )
    elif original is not None and action == "cancel":
        canceled = await flow.request(
            "POST",
            "/v1/events",
            JsonDocument(
                {
                    "expected_revision": revision,
                    "event": {
                        "type": "cancel_transaction",
                        "event_id": "cancel-payment",
                        "user_id": flow.case.owner,
                        "transaction_id": "current-payment",
                    },
                    "snapshot_event": flow.case.snapshot_event(flow.day, 0, "refund-balance").root,
                }
            ),
        )
        flow.check("cancellation_refunded", canceled.root.get("detection") == "cancellation_refunded")
        current = (await dialogue(flow, original)).receipt
        flow.check(
            "cancellation_historical_separation",
            current.historical is not None
            and current.historical.transaction_status == "canceled"
            and current.payment is None
            and any(row.balance_krw == flow.case.balance_krw for row in current.current_envelopes),
        )
    elif original is not None and action in {"dialogue", "analyses"}:
        _ = await dialogue(flow, original)
    elif original is not None and action in {"ack", "isolation"}:
        await notification_action(flow, original)


async def notification_action(flow: ScenarioIO, original: Coaching) -> None:
    action = flow.case.action
    notices = await flow.request("GET", "/v1/notifications")
    items = notices.root.get("items")
    if not isinstance(items, list) or not items:
        raise ValueError("Expected a P0 notification")
    notice = JsonDocument.model_validate(items[0])
    event_id = notice.root["event_id"]
    if not isinstance(event_id, str):
        raise TypeError("Invalid notification identifier")
    path = "/v1/notifications/" + event_id + "/ack"
    if action == "ack":
        ack = await flow.request("POST", path)
        flow.check("ack_repeat_exact", ack == await flow.request("POST", path))
        flow.check(
            "ack_removes_outbox", (await flow.request("GET", "/v1/notifications")).root.get("items") == []
        )
    else:
        session = Session.model_validate(
            (await flow.request("POST", "/v1/sessions", JsonDocument({"coaching_id": original.id}))).root
        )
        for method, target in (
            ("GET", "/v1/coaching/" + original.id),
            ("GET", "/v1/sessions/" + session.id),
            ("POST", path),
        ):
            _ = await flow.request(method, target, foreign=True, expected=404)
            flow.check("owner_isolation", flow.http[-1].status_code == 404)
        _ = await flow.request("GET", "/v1/twin", expected=401, invalid_token=True)
