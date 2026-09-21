from pathlib import Path

import httpx2
import pytest
from pydantic import SecretStr, ValidationError
from test_api import TOKEN, TestModel, event, setup
from test_engine import fixture

from coaching_service.api import create_app
from coaching_service.llm_contract import ModelConfig
from coaching_service.settings import Client, Settings


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_p0_survives_disabled_model_and_snapshot_recovers(tmp_path: Path) -> None:
    settings = Settings(
        database=tmp_path / "disabled.sqlite3",
        clients=(Client(user_id="demo", token=SecretStr(TOKEN)),),
        model=ModelConfig(endpoint_url=None),
    )
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=create_app(settings)),
        base_url="http://test",
        headers={"Authorization": "Bearer " + TOKEN},
    ) as client:
        assert (
            await client.post(
                "/v1/twin", json=fixture().model_dump(mode="json"), headers={"Idempotency-Key": "init"}
            )
        ).status_code == 200
        result = (await client.post("/v1/events", json=event(), headers={"Idempotency-Key": "pay"})).json()
        assert result["coaching"]["wording_source"] == "template"
        assert result["coaching"]["fallback_reason"] == "disabled"
        assert result["coaching"]["receipt"]["result"]["status"] == "needs_data"
        assert len((await client.get("/v1/notifications")).json()["items"]) == 1
        snap = fixture().snapshot
        assert snap is not None
        payload = {**snap.root, "source": "LIVE", "accounts": [{"account_id": "a", "balance_krw": 950000}]}
        update = {
            "expected_revision": 1,
            "event": {"type": "snapshot", "event_id": "snap1", "user_id": "demo", "snapshot": payload},
        }
        response = await client.post("/v1/events", json=update, headers={"Idempotency-Key": "snap"})
        assert response.status_code == 200
        assert response.json()["detection"] == "snapshot_updated"
        review = await client.post(
            "/v1/coaching/reviews",
            json={"on_date": "2026-09-09", "through_date": "2026-09-16"},
            headers={"Idempotency-Key": "review"},
        )
        assert review.json()["receipt"]["result"]["context"]["absolute_cash_ready"] is True


@pytest.mark.anyio
async def test_pending_confirmation_zero_missing_and_roles(tmp_path: Path) -> None:
    model = TestModel()
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=setup(tmp_path / "pending.sqlite3", model)),
        base_url="http://test",
        headers={"Authorization": "Bearer " + TOKEN},
    ) as client:
        assert (
            await client.post(
                "/v1/twin", json=fixture().model_dump(mode="json"), headers={"Idempotency-Key": "init"}
            )
        ).status_code == 200
        pending = event()
        pending["event"]["transaction"]["confirm_status"] = "PENDING"
        one = await client.post("/v1/events", json=pending, headers={"Idempotency-Key": "pending"})
        assert one.json()["detection"] == "not_confirmed_envelope_debit"
        confirm = event()
        confirm["expected_revision"] = 1
        confirm["event"]["event_id"] = "confirm"
        two = await client.post("/v1/events", json=confirm, headers={"Idempotency-Key": "confirm"})
        assert two.json()["payment"]["balance_before_krw"] == 100000
        assert model.writes == 1


def test_configuration_fails_closed() -> None:
    with pytest.raises(ValidationError):
        Settings(clients=())


@pytest.mark.anyio
async def test_body_limit(tmp_path: Path) -> None:
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=setup(tmp_path / "body.sqlite3", TestModel())),
        base_url="http://test",
    ) as client:
        response = await client.post("/v1/twin", content=b"x" * 2_000_001)
        assert response.status_code == 413
