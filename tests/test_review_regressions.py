# ruff: noqa: INP001
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import httpx2
import pytest
from test_api import TOKEN, TestModel, event, setup
from test_engine import fixture

from coaching_service.payments import Ledger
from coaching_service.store import Store


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@asynccontextmanager
async def api_client(database: Path, model: TestModel) -> AsyncIterator[httpx2.AsyncClient]:
    app = setup(database, model)
    async with (
        app.router.lifespan_context(app),
        httpx2.AsyncClient(
            transport=httpx2.ASGITransport(app=app),
            base_url="http://test",
            headers={"Authorization": "Bearer " + TOKEN},
        ) as client,
    ):
        yield client


def saved_ledger(database: Path) -> Ledger:
    payload = Store(database).load("demo", "ledger")
    assert payload is not None
    return Ledger.model_validate_json(payload)


def cancellation(transaction_id: str, revision: int) -> dict[str, object]:
    return {
        "expected_revision": revision,
        "event": {
            "type": "cancel_transaction",
            "event_id": "cancel-" + transaction_id,
            "user_id": "demo",
            "transaction_id": transaction_id,
        },
    }


@pytest.mark.anyio
async def test_inconsistent_transfer_event_preserves_state_and_allows_corrected_retry(tmp_path: Path) -> None:
    async with api_client(tmp_path / "incoming.sqlite", TestModel()) as client:
        created = await client.post(
            "/v1/twin", json=fixture().model_dump(mode="json"), headers={"Idempotency-Key": "init"}
        )
        assert created.status_code == 200
        before = (await client.get("/v1/twin")).content
        request = event(10000)
        request["event"]["transaction"].update(transaction_type="TRANSFER_IN", direction="EXPENSE")
        response = await client.post("/v1/events", json=request, headers={"Idempotency-Key": "incoming"})
        assert response.status_code == 422, response.text
        assert (await client.get("/v1/twin")).content == before
        request["event"]["transaction"]["direction"] = "INCOME"
        accepted = await client.post("/v1/events", json=request, headers={"Idempotency-Key": "incoming"})
        assert accepted.status_code == 200, accepted.text
        assert accepted.json()["detection"] == "not_confirmed_envelope_debit"


@pytest.mark.anyio
async def test_refund_overflow_is_rejected_without_poisoning_ledger_or_consuming_retry(
    tmp_path: Path,
) -> None:
    database = tmp_path / "refund-limit.sqlite3"
    async with api_client(database, TestModel()) as client:
        created = await client.post(
            "/v1/twin", json=fixture().model_dump(mode="json"), headers={"Idempotency-Key": "init"}
        )
        assert created.status_code == 200, created.text
        for revision, transaction_id in enumerate(("first", "second")):
            request = event(10000)
            request["expected_revision"] = revision
            request["event"]["event_id"] = transaction_id
            request["event"]["transaction"]["transaction_id"] = transaction_id
            paid = await client.post("/v1/events", json=request, headers={"Idempotency-Key": transaction_id})
            assert paid.status_code == 200, paid.text
        reconciled = cancellation("second", 2)
        reconciled["cancellation_balance"] = {"envelope": "기타", "balance_krw": 10**12}
        response = await client.post("/v1/events", json=reconciled, headers={"Idempotency-Key": "reconcile"})
        assert response.status_code == 200, response.text
        before = (await client.get("/v1/twin")).content
        original_ledger = saved_ledger(database)
        request = cancellation("first", 3)
        rejected = await client.post("/v1/events", json=request, headers={"Idempotency-Key": "refund"})
        assert rejected.status_code == 422, rejected.text
        assert rejected.json() == {"error": "envelope_balance_limit"}
        assert (await client.get("/v1/twin")).content == before
        assert saved_ledger(database) == original_ledger
        request["cancellation_balance"] = {"envelope": "기타", "balance_krw": 10**12}
        accepted = await client.post("/v1/events", json=request, headers={"Idempotency-Key": "refund"})
        assert accepted.status_code == 200, accepted.text
        assert accepted.json()["identity"]["revision"] == 4
        assert saved_ledger(database).envelopes[0].balance_krw == 10**12
        repeated = await client.post("/v1/events", json=request, headers={"Idempotency-Key": "refund"})
        assert repeated.content == accepted.content


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("source", "count", "detection", "coaching_created"),
    [("SEED", 1, "below_trigger", False), ("LIVE", 5, "p1_ambiguous", True)],
)
async def test_weekly_payment_count_uses_live_transactions_only(
    tmp_path: Path, source: str, count: int, detection: str, coaching_created: bool
) -> None:
    model = TestModel()
    bootstrap = fixture().model_dump(mode="json")
    historical = bootstrap["transactions"][0]
    bootstrap["transactions"] += [
        {
            **historical,
            "source": source,
            "transaction_id": "historical-" + str(index),
            "transaction_date": "2026-09-08",
            "amount_krw": 1000,
        }
        for index in range(4)
    ]
    async with api_client(tmp_path / "weekly.sqlite3", model) as client:
        created = await client.post("/v1/twin", json=bootstrap, headers={"Idempotency-Key": "init"})
        assert created.status_code == 200, created.text
        response = await client.post("/v1/events", json=event(20000), headers={"Idempotency-Key": "pay"})
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["payment"]["weekly_count"] == count
        assert result["detection"] == detection
        assert (result["coaching"] is not None) is coaching_created
        assert model.judgments == int(coaching_created)
        assert model.writes == int(coaching_created)


@pytest.mark.anyio
async def test_dialogue_keeps_canceled_payment_history_separate_from_current_balance(tmp_path: Path) -> None:
    database = tmp_path / "dialogue.sqlite3"
    model = TestModel()
    async with api_client(database, model) as client:
        created = await client.post(
            "/v1/twin", json=fixture().model_dump(mode="json"), headers={"Idempotency-Key": "init"}
        )
        assert created.status_code == 200, created.text
        paid = await client.post("/v1/events", json=event(), headers={"Idempotency-Key": "pay"})
        assert paid.status_code == 200, paid.text
        original = paid.json()["coaching"]
        canceled = await client.post(
            "/v1/events", json=cancellation("new", 1), headers={"Idempotency-Key": "cancel"}
        )
        assert canceled.status_code == 200, canceled.text
        assert canceled.json()["detection"] == "cancellation_refunded"
        assert saved_ledger(database).envelopes[0].balance_krw == 100000
        session = await client.post(
            "/v1/sessions", json={"coaching_id": original["id"]}, headers={"Idempotency-Key": "session"}
        )
        assert session.status_code == 200, session.text
        reply = await client.post(
            "/v1/sessions/" + session.json()["id"] + "/messages",
            json={"question": "결제를 취소했어요. 현재 봉투 잔액은 얼마인가요?"},
            headers={"Idempotency-Key": "turn", "X-Coaching-Trace": "1"},
        )
        assert reply.status_code == 200, reply.text
        current = reply.json()
        receipt = current["receipt"]
        assert receipt["identity"]["revision"] == 2
        assert receipt["trigger"] == "historical_coaching_followup"
        assert receipt["payment"] is None
        assert receipt["current_envelopes"] == [{"envelope": "기타", "balance_krw": 100000}]
        historical = receipt["historical"]
        assert historical["coaching_id"] == original["id"]
        assert historical["created_at"] == original["created_at"]
        assert historical["transaction_status"] == "canceled"
        assert historical["payment"] == original["receipt"]["payment"]
        assert historical["engine_result"] == original["receipt"]["result"]
        assert "당시 차감 후 50,000원이었습니다" in current["text"]
        assert "현재 취소 상태" in current["text"]
        assert "봉투 장부 잔액은 100,000원" in current["text"]
        # This is a stored-coaching follow-up, so a trace for this response must
        # contain neither a new FDT simulation nor a model operation.
        assert "fdt;dur=" not in reply.headers["server-timing"]
        assert "model;dur=" not in reply.headers["server-timing"]
        persisted = await client.get("/v1/coaching/" + original["id"])
        assert persisted.json() == original


@pytest.mark.anyio
async def test_imported_payment_cancel_requires_authoritative_balance_and_replays_once(
    tmp_path: Path,
) -> None:
    database = tmp_path / "imported.sqlite3"
    async with api_client(database, TestModel()) as client:
        created = await client.post(
            "/v1/twin", json=fixture().model_dump(mode="json"), headers={"Idempotency-Key": "init"}
        )
        assert created.status_code == 200, created.text
        before = (await client.get("/v1/twin")).json()
        request = cancellation("old", 0)
        rejected = await client.post("/v1/events", json=request, headers={"Idempotency-Key": "cancel"})
        assert rejected.status_code == 409, rejected.text
        assert rejected.json()["error"] == "cancel_requires_authoritative_envelope_balance"
        assert (await client.get("/v1/twin")).json() == before
        assert saved_ledger(database).envelopes[0].balance_krw == 100000
        request["cancellation_balance"] = {"envelope": "기타", "balance_krw": 110000}
        accepted = await client.post("/v1/events", json=request, headers={"Idempotency-Key": "cancel"})
        assert accepted.status_code == 200, accepted.text
        assert accepted.json()["detection"] == "cancellation_reconciled"
        assert accepted.json()["identity"]["revision"] == 1
        assert saved_ledger(database).envelopes[0].balance_krw == 110000
        replay = await client.post("/v1/events", json=request, headers={"Idempotency-Key": "cancel"})
        assert replay.json() == accepted.json()
        request["expected_revision"] = 1
        repeated = await client.post("/v1/events", json=request, headers={"Idempotency-Key": "cancel-again"})
        assert repeated.status_code == 200, repeated.text
        assert repeated.json()["detection"] == "duplicate_transaction"
        assert saved_ledger(database).envelopes[0].balance_krw == 110000


@pytest.mark.anyio
async def test_non_ascii_bearer_is_unauthorized_and_does_not_disrupt_valid_auth(tmp_path: Path) -> None:
    async with api_client(tmp_path / "auth.sqlite3", TestModel()) as client:
        created = await client.post(
            "/v1/twin", json=fixture().model_dump(mode="json"), headers={"Idempotency-Key": "init"}
        )
        assert created.status_code == 200, created.text
        malformed = await client.get("/v1/twin", headers=[(b"Authorization", b"Bearer " + b"\xe9" * 40)])
        assert malformed.status_code == 401, malformed.text
        assert malformed.json() == {"error": "authentication_required"}
        assert (await client.get("/v1/twin")).status_code == 200


@pytest.mark.anyio
async def test_large_receipt_preserves_p0_and_outbox_without_recomputing_or_model_fallback(
    tmp_path: Path,
) -> None:
    database = tmp_path / "large-p0.sqlite3"
    model = TestModel()
    account_id = "a" * 65000
    request = event()
    request["event"]["transaction"]["account_id"] = account_id
    async with api_client(database, model) as client:
        created = await client.post(
            "/v1/twin", json=fixture().model_dump(mode="json"), headers={"Idempotency-Key": "init"}
        )
        assert created.status_code == 200, created.text
        response = await client.post("/v1/events", json=request, headers={"Idempotency-Key": "pay"})
        assert response.status_code == 200, response.text
        result = response.json()
        coaching = result["coaching"]
        assert result["detection"] == "p0_half_balance"
        assert result["identity"]["revision"] == 1
        assert coaching["wording_source"] == "template"
        assert coaching["fallback_reason"] == "context_limit"
        assert coaching["model"] == "not_called"
        assert len(json.dumps(coaching["receipt"], ensure_ascii=False)) > 64000
        assert (
            "snapshot.accounts/" + account_id
            in coaching["receipt"]["result"]["next_action"]["required_inputs"]
        )
        assert saved_ledger(database).envelopes[0].balance_krw == 50000
        persisted = await client.get("/v1/coaching/" + coaching["id"])
        assert persisted.json() == coaching
        assert (await client.get("/v1/twin")).json()["revision"] == 1
        replay = await client.post("/v1/events", json=request, headers={"Idempotency-Key": "pay"})
        assert replay.json() == result
        notifications = (await client.get("/v1/notifications")).json()["items"]
        assert len(notifications) == 1
        assert notifications[0]["coaching_id"] == coaching["id"]
        session = await client.post(
            "/v1/sessions", json={"coaching_id": coaching["id"]}, headers={"Idempotency-Key": "session"}
        )
        assert session.status_code == 200, session.text
        reply = await client.post(
            "/v1/sessions/" + session.json()["id"] + "/messages",
            json={"question": "이 코칭이 나온 이유를 확인하고 싶어요."},
            headers={"Idempotency-Key": "turn"},
        )
        assert reply.status_code == 200, reply.text
        follow_up = reply.json()
        assert follow_up["wording_source"] == "template"
        assert follow_up["fallback_reason"] is None
        assert follow_up["receipt"]["routing"] == {
            "mode": "review",
            "source": "template",
            "fallback_reason": None,
        }
        assert follow_up["receipt"]["historical"]["engine_result"] == coaching["receipt"]["result"]
        assert model.writes == 0
        assert model.judgments == 0
        # The session itself identifies the prior coaching. Its immutable receipt and
        # current ledger answer this follow-up without serializing the giant document
        # into a route or generation prompt.
        assert model.routes == 0
        assert all(account_id not in evidence.facts_json for evidence in model.seen)


@pytest.mark.anyio
async def test_large_p1_receipt_keeps_debit_and_reports_insufficient_model_context(tmp_path: Path) -> None:
    database = tmp_path / "large-p1.sqlite3"
    model = TestModel()
    request = event(45000)
    request["event"]["transaction"]["account_id"] = "a" * 65000
    async with api_client(database, model) as client:
        created = await client.post(
            "/v1/twin", json=fixture().model_dump(mode="json"), headers={"Idempotency-Key": "init"}
        )
        assert created.status_code == 200, created.text
        response = await client.post("/v1/events", json=request, headers={"Idempotency-Key": "pay"})
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["detection"] == "p1_ambiguous"
        assert result["identity"]["revision"] == 1
        assert result["coaching"] is None
        assert result["judgment"] == {
            "decision": "needs_data",
            "reason_code": "insufficient_context",
            "confidence": 0.0,
            "source": "template",
            "fallback_reason": "context_limit",
        }
        assert saved_ledger(database).envelopes[0].balance_krw == 55000
        assert (await client.get("/v1/notifications")).json()["items"] == []
        assert model.judgments == 0
        assert model.writes == 0
