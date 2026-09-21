"""Numeric dialogue turns use their authoritative FDT result without a duplicate review."""

# ruff: noqa: INP001
from __future__ import annotations

from typing import TYPE_CHECKING

import httpx2
import pytest

from coaching_service.engine import EngineAdapter
from coaching_service.schemas import JsonDocument, Session
from tests.test_api import TOKEN, TestModel, setup
from tests.test_engine import fixture

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_explicit_forecast_does_not_run_a_second_coaching_review(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Numeric text is already rendered from the checked numeric receipt."""

    def unexpected_review(
        _self: EngineAdapter, _document: JsonDocument, _request: JsonDocument
    ) -> JsonDocument:
        raise AssertionError("numeric dialogue must not run a duplicate review simulation")

    monkeypatch.setattr(EngineAdapter, "review", unexpected_review)
    model = TestModel()
    app = setup(tmp_path / "numeric-no-review.sqlite3", model)
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": "Bearer " + TOKEN},
    ) as client:
        created = await client.post(
            "/v1/twin", json=fixture().model_dump(mode="json"), headers={"Idempotency-Key": "twin"},
        )
        assert created.status_code == 200, created.text
        session_response = await client.post("/v1/sessions", json={}, headers={"Idempotency-Key": "session"})
        session = Session.model_validate_json(session_response.content)
        response = await client.post(
            "/v1/sessions/" + session.id + "/messages",
            json={
                "question": "앞으로 7일 잔액 예측해줘",
                "analysis": {"mode": "forecast", "horizon_days": 7, "paths": 20, "seed": 42},
            },
            headers={"Idempotency-Key": "forecast"},
        )

    assert response.status_code == 200, response.text
    receipt = response.json()["receipt"]
    assert receipt["numeric_result"]["mode"] == "forecast"
    assert receipt["result"] == {"status": "not_run", "reason": "numeric_operation"}
    assert response.json()["wording_source"] == "template"
    assert response.json()["model"] == "not_called"
    assert model.routes == 0
    assert model.writes == 0
