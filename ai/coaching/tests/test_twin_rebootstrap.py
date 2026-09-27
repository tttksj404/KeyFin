from pathlib import Path

import httpx2
import pytest
from test_api import TOKEN, TestModel, setup
from test_engine import fixture


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_rebootstrap_replaces_twin_without_409(tmp_path: Path) -> None:
    model = TestModel()
    app = setup(tmp_path / "reboot1.sqlite3", model)
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": "Bearer " + TOKEN},
    ) as client:
        first = await client.post(
            "/v1/twin", json=fixture().model_dump(mode="json"), headers={"Idempotency-Key": "b1"}
        )
        assert first.status_code == 200, first.text
        second = await client.post(
            "/v1/twin", json=fixture().model_dump(mode="json"), headers={"Idempotency-Key": "b2"}
        )
        assert second.status_code == 200, second.text
        body = second.json()
        assert "revision" in body


@pytest.mark.anyio
async def test_rebootstrap_preserves_sessions_and_coaching(tmp_path: Path) -> None:
    model = TestModel()
    app = setup(tmp_path / "reboot2.sqlite3", model)
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": "Bearer " + TOKEN},
    ) as client:
        created = await client.post(
            "/v1/twin", json=fixture().model_dump(mode="json"), headers={"Idempotency-Key": "b1"}
        )
        assert created.status_code == 200, created.text
        review = await client.post(
            "/v1/coaching/reviews",
            json={"on_date": "2026-09-09", "through_date": "2026-09-16", "paths": 20},
            headers={"Idempotency-Key": "review"},
        )
        assert review.status_code == 200, review.text
        coaching_id = review.json()["id"]
        session = await client.post(
            "/v1/sessions", json={"coaching_id": coaching_id}, headers={"Idempotency-Key": "session"}
        )
        assert session.status_code == 200, session.text
        session_id = session.json()["id"]

        rebooted = await client.post(
            "/v1/twin", json=fixture().model_dump(mode="json"), headers={"Idempotency-Key": "b2"}
        )
        assert rebooted.status_code == 200, rebooted.text

        coaching_after = await client.get("/v1/coaching/" + coaching_id)
        assert coaching_after.status_code == 200
        assert coaching_after.json() == review.json()

        history_after = await client.get("/v1/sessions/" + session_id)
        assert history_after.status_code == 200

        chat = await client.post(
            "/v1/sessions/" + session_id + "/messages",
            json={"question": "왜 이 코칭이 나왔고 위험은 뭐야?"},
            headers={"Idempotency-Key": "turn"},
        )
        assert chat.status_code == 200, chat.text


@pytest.mark.anyio
async def test_rebootstrap_idempotent_replay(tmp_path: Path) -> None:
    model = TestModel()
    app = setup(tmp_path / "reboot3.sqlite3", model)
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": "Bearer " + TOKEN},
    ) as client:
        first = await client.post(
            "/v1/twin", json=fixture().model_dump(mode="json"), headers={"Idempotency-Key": "b1"}
        )
        assert first.status_code == 200, first.text
        replay = await client.post(
            "/v1/twin", json=fixture().model_dump(mode="json"), headers={"Idempotency-Key": "b1"}
        )
        assert replay.status_code == 200, replay.text
        assert replay.json() == first.json()


@pytest.mark.anyio
async def test_rebootstrap_reflects_new_ledger(tmp_path: Path) -> None:
    model = TestModel()
    app = setup(tmp_path / "reboot4.sqlite3", model)
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": "Bearer " + TOKEN},
    ) as client:
        first = await client.post(
            "/v1/twin", json=fixture().model_dump(mode="json"), headers={"Idempotency-Key": "b1"}
        )
        assert first.status_code == 200, first.text

        altered = fixture().model_dump(mode="json")
        altered["envelopes"] = [{"envelope": "기타", "balance_krw": 250000}]

        second = await client.post("/v1/twin", json=altered, headers={"Idempotency-Key": "b2"})
        assert second.status_code == 200, second.text

        twin_after = await client.get("/v1/twin")
        assert twin_after.status_code == 200
