# ruff: noqa: INP001
"""Deterministic clock around real API routes, real SQLite and the actual FDT."""

from datetime import datetime
from pathlib import Path

import httpx2
import pytest
from fastapi import FastAPI
from pydantic import SecretStr
from test_api import OTHER, TOKEN, TestModel
from test_engine import fixture

from coaching_service import coaching, forecast_validation_ingestion
from coaching_service.auth import Authenticate
from coaching_service.coaching import CoachingCore
from coaching_service.forecast_validation_observations import SEOUL
from coaching_service.forecast_validation_routes import register_forecast_validation
from coaching_service.http_errors import register_errors
from coaching_service.repository import Repository
from coaching_service.routes import register_coaching, register_records, register_twin
from coaching_service.settings import Client
from coaching_service.store import Store

USER = "test-only-user-token-000000000000000000"
BASE = "/v1/forecast-validation/registrations"


class Clock:
    def __init__(self, stamp: str = "2026-09-09T18:00:00") -> None:
        self.now = datetime.fromisoformat(stamp).replace(tzinfo=SEOUL).timestamp()

    def time(self) -> float:
        return self.now

    def set(self, stamp: str) -> None:
        self.now = datetime.fromisoformat(stamp).replace(tzinfo=SEOUL).timestamp()


def build(path: Path, clock: Clock, monkeypatch: pytest.MonkeyPatch) -> FastAPI:
    monkeypatch.setattr(coaching, "time", clock)
    monkeypatch.setattr(forecast_validation_ingestion, "time", clock)
    core = CoachingCore(Repository(Store(path)), TestModel())
    auth = Authenticate(
        (
            Client(user_id="demo", token=SecretStr(TOKEN)),
            Client(user_id="other", token=SecretStr(OTHER)),
            Client(user_id="demo", token=SecretStr(USER), role="user"),
        )
    )
    app = FastAPI()
    register_errors(app)
    register_twin(app, core, auth)
    register_coaching(app, core, auth)
    register_records(app, core, auth)
    register_forecast_validation(app, core, auth, clock=clock.time)
    return app


def client_for(app: FastAPI) -> httpx2.AsyncClient:
    return httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": "Bearer " + TOKEN},
    )


async def forecast(client: httpx2.AsyncClient) -> httpx2.Response:
    initialized = await client.post(
        "/v1/twin", json=fixture().model_dump(mode="json"), headers={"Idempotency-Key": "init"}
    )
    assert initialized.status_code == 200, initialized.text
    session = await client.post("/v1/sessions", json={}, headers={"Idempotency-Key": "session"})
    result = await client.post(
        f"/v1/sessions/{session.json()['id']}/messages",
        json={
            "question": "앞으로 2일 예측",
            "analysis": {"mode": "forecast", "horizon_days": 2, "paths": 20},
        },
        headers={"Idempotency-Key": "forecast"},
    )
    assert result.status_code == 200, result.text
    return result


async def register(client: httpx2.AsyncClient, coaching_id: str) -> httpx2.Response:
    return await client.post(
        BASE,
        json={
            "coaching_id": coaching_id,
            "data_origin": "backend_attested_real",
            "source_reference": "test-backend-attestation-not-a-real-customer",
        },
        headers={"Idempotency-Key": "register"},
    )


async def outcomes(client: httpx2.AsyncClient) -> None:
    for revision, day, amount in ((0, "2026-09-10", 20000), (1, "2026-09-11", 6000)):
        row = fixture().transactions[0].root
        result = await client.post(
            "/v1/events",
            json={
                "expected_revision": revision,
                "event": {
                    "type": "transaction",
                    "event_id": f"out-{revision}",
                    "user_id": "demo",
                    "transaction": {
                        **row,
                        "transaction_id": f"outcome-{revision}",
                        "transaction_date": day,
                        "amount_krw": amount,
                    },
                },
            },
            headers={"Idempotency-Key": f"out-{revision}"},
        )
        assert result.status_code == 200, result.text


async def settle(client: httpx2.AsyncClient, registration_id: str) -> httpx2.Response:
    return await client.post(
        BASE + f"/{registration_id}/settlement",
        json={
            "coverage_start": "2026-09-10",
            "coverage_end": "2026-09-11",
            "complete": True,
            "source_reference": "test-complete-provider-export",
        },
        headers={"Idempotency-Key": "settle"},
    )
