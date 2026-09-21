from pathlib import Path

import httpx2
import pytest
from fastapi import FastAPI
from pydantic import SecretStr
from test_engine import fixture

from coaching_service.api import create_app
from coaching_service.llm_contract import EvidenceInput, Judgment, Routing, Wording
from coaching_service.settings import Client, Settings

TOKEN = "test-only-demo-token-000000000000000000"
OTHER = "test-only-other-token-00000000000000000"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class TestModel:
    __test__ = False

    def __init__(self) -> None:
        self.writes = 0
        self.judgments = 0
        self.routes = 0
        self.seen: list[EvidenceInput] = []

    async def write(self, evidence: EvidenceInput) -> Wording:
        self.writes += 1
        self.seen.append(evidence)
        return Wording(
            text="꼭 필요한 소비와 미룰 수 있는 소비를 나누어 점검해 보세요.",
            source="llm",
            model="injected-test-model",
        )

    async def judge(self, evidence: EvidenceInput) -> Judgment:
        self.judgments += 1
        self.seen.append(evidence)
        return Judgment(decision="coach", reason_code="context_concern", confidence=0.9, source="llm")

    async def route(self, evidence: EvidenceInput) -> Routing:
        self.routes += 1
        self.seen.append(evidence)
        return Routing(mode="risk", source="llm")


def setup(path: Path, model: TestModel) -> FastAPI:
    return create_app(
        Settings(
            database=path,
            clients=(
                Client(user_id="demo", token=SecretStr(TOKEN)),
                Client(user_id="other", token=SecretStr(OTHER)),
            ),
        ),
        model,
    )


def event(amount: int = 50000) -> dict:
    row = fixture().transactions[0].root
    return {
        "expected_revision": 0,
        "event": {
            "type": "transaction",
            "event_id": "event1",
            "user_id": "demo",
            "transaction": {
                **row,
                "transaction_id": "new",
                "transaction_date": "2026-09-09",
                "amount_krw": amount,
            },
        },
    }


@pytest.mark.anyio
async def test_full_payment_chat_outbox_restart_and_isolation(tmp_path: Path) -> None:
    model = TestModel()
    database = tmp_path / "api.sqlite3"
    app = setup(database, model)
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": "Bearer " + TOKEN},
    ) as client:
        created = await client.post(
            "/v1/twin", json=fixture().model_dump(mode="json"), headers={"Idempotency-Key": "init"}
        )
        assert created.status_code == 200, created.text
        result = await client.post("/v1/events", json=event(), headers={"Idempotency-Key": "pay"})
        assert result.status_code == 200, result.text
        body = result.json()
        assert body["detection"] == "p0_half_balance"
        assert body["payment"]["balance_before_krw"] == 100000
        assert body["coaching"]["receipt"]["result"]["status"] == "needs_data"
        assert body["coaching"]["receipt"]["result"]["next_action"]["kind"] == "complete_cash_state"
        assert model.writes == 1
        assert model.judgments == 0
        replay = await client.post("/v1/events", json=event(), headers={"Idempotency-Key": "pay"})
        assert replay.json() == body
        assert model.writes == 1
        altered = await client.post("/v1/events", json=event(50001), headers={"Idempotency-Key": "pay"})
        assert altered.status_code == 409
        new_event_id = event()
        new_event_id["event"]["event_id"] = "event2"
        new_event_id["expected_revision"] = 1
        duplicate = await client.post(
            "/v1/events", json=new_event_id, headers={"Idempotency-Key": "pay-again"}
        )
        assert duplicate.json()["detection"] == "duplicate_transaction"
        assert model.writes == 1
        notices = (await client.get("/v1/notifications")).json()["items"]
        assert len(notices) == 1
        assert notices[0]["type"] == "COACHING"
        coaching_id = body["coaching"]["id"]
        denied = await client.get("/v1/coaching/" + coaching_id, headers={"Authorization": "Bearer " + OTHER})
        assert denied.status_code == 404
        session = await client.post(
            "/v1/sessions", json={"coaching_id": coaching_id}, headers={"Idempotency-Key": "session"}
        )
        session_id = session.json()["id"]
        turn_url = "/v1/sessions/" + session_id + "/messages"
        chat = await client.post(
            turn_url,
            json={"question": "왜 이 코칭이 나왔고 위험은 뭐야?"},
            headers={"Idempotency-Key": "turn"},
        )
        assert chat.status_code == 200, chat.text
        assert chat.json()["receipt"]["original_coaching_id"] == coaching_id
        assert chat.json()["receipt"]["numeric_request"]["mode"] == "risk"
        assert chat.json()["receipt"]["numeric_result"]["status"] == "partial"
        assert chat.json()["receipt"]["numeric_result"]["warnings"]
        repeated = await client.post(
            turn_url,
            json={"question": "왜 이 코칭이 나왔고 위험은 뭐야?"},
            headers={"Idempotency-Key": "turn"},
        )
        assert repeated.json() == chat.json()
        history = (await client.get("/v1/sessions/" + session_id)).json()
        assert len(history["messages"]) == 2
        assert model.routes == 1
    restarted = setup(database, TestModel())
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=restarted),
        base_url="http://test",
        headers={"Authorization": "Bearer " + TOKEN},
    ) as client:
        assert (await client.get("/v1/coaching/" + coaching_id)).json() == body["coaching"]
        ack = await client.post(
            "/v1/notifications/" + notices[0]["event_id"] + "/ack", headers={"Idempotency-Key": "ack"}
        )
        assert ack.status_code == 200
        assert ack.json()["acknowledged"]
        assert (await client.get("/v1/notifications")).json()["items"] == []
        assert (await client.delete("/v1/me/data")).status_code == 200
        assert (await client.get("/v1/coaching/" + coaching_id)).status_code == 404


@pytest.mark.anyio
async def test_p1_model_is_supplementary(tmp_path: Path) -> None:
    model = TestModel()
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=setup(tmp_path / "p1.sqlite3", model)),
        base_url="http://test",
        headers={"Authorization": "Bearer " + TOKEN},
    ) as client:
        assert (
            await client.post(
                "/v1/twin", json=fixture().model_dump(mode="json"), headers={"Idempotency-Key": "init"}
            )
        ).status_code == 200
        result = await client.post("/v1/events", json=event(45000), headers={"Idempotency-Key": "p1"})
        assert result.status_code == 200, result.text
        assert result.json()["coaching"]["receipt"]["trigger"] == "p1_context_concern"
        assert model.judgments == 1
        assert model.writes == 1


@pytest.mark.anyio
async def test_missing_auth_and_foreign_bootstrap(tmp_path: Path) -> None:
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=setup(tmp_path / "auth.sqlite3", TestModel())),
        base_url="http://test",
    ) as client:
        assert (await client.get("/v1/notifications")).status_code == 401
        result = await client.post(
            "/v1/twin",
            json=fixture("other").model_dump(mode="json"),
            headers={"Authorization": "Bearer " + TOKEN, "Idempotency-Key": "init"},
        )
        assert result.status_code == 403
