# ruff: noqa: INP001
"""Delayed outcome workflow over real service routes and SQLite persistence."""

from pathlib import Path

import pytest
from test_api import OTHER
from test_forecast_validation_support import (
    BASE,
    USER,
    Clock,
    build,
    client_for,
    forecast,
    outcomes,
    register,
    settle,
)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_future_forecast_is_frozen_then_settled_and_survives_restart(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: a real engine forecast with no future outcome in its input.
    clock = Clock()
    path = tmp_path / "validation.sqlite3"
    async with client_for(build(path, clock, monkeypatch)) as client:
        original = (await forecast(client)).json()
        frozen = await register(client, original["id"])
        assert frozen.status_code == 200, frozen.text
        body = frozen.json()
        assert body["evidence_tier"] == "prospective_attested"
        assert body["real_accuracy_validated"] is False
        assert (
            body["prediction"]["p50"]
            == original["receipt"]["numeric_result"]["metrics"]["total_expense_p50_krw"]["value"]
        )
        assert body["baseline"]["prediction_krw"] == pytest.approx(10000 / 71 * 2)
        clock.set("2026-09-12T00:01:00")
        await outcomes(client)
        # When: backend attests complete coverage after both forecast days closed.
        response = await settle(client, body["id"])
        assert response.status_code == 200, response.text
        settled = response.json()
        assert settled["actual_krw"] == 26000  # 20,000 + 6,000, independent of engine normalize().
        assert settled["actual_transaction_count"] == 2
        assert settled["registration"] == body
        assert settled["independent_human_oracle"] is False
        retry = await settle(client, body["id"])
        assert retry.json() == settled
    # Then: a new API instance reads precisely the same immutable records and metrics.
    async with client_for(build(path, clock, monkeypatch)) as restarted:
        saved = await restarted.get(BASE + f"/{body['id']}/settlement")
        assert saved.json() == settled
        report = await restarted.post(
            "/v1/forecast-validation/metrics", json={"registration_ids": [body["id"]]}
        )
        assert report.status_code == 200, report.text
        assert report.json()["values"]["mae_krw"] == abs(body["prediction"]["p50"] - 26000)
        assert report.json()["values"]["sample_count"] == 1
        assert report.json()["real_accuracy_validated"] is False


@pytest.mark.anyio
async def test_backdated_registration_cannot_become_prospective(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: the first forecast day has already begun at the registration server.
    clock = Clock()
    async with client_for(build(tmp_path / "late.sqlite3", clock, monkeypatch)) as client:
        original = (await forecast(client)).json()
        clock.set("2026-09-10T00:00:00")
        # When / Then: a backend 'real' label cannot turn replay into prospective evidence.
        response = await register(client, original["id"])
        assert response.status_code == 409
        assert response.json()["error"] == "validation_prospective_registration_too_late_or_unstamped"


@pytest.mark.anyio
async def test_no_early_settlement_or_caller_supplied_actual(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: a registered forecast whose window is still future.
    clock = Clock()
    async with client_for(build(tmp_path / "early.sqlite3", clock, monkeypatch)) as client:
        original = (await forecast(client)).json()
        frozen = (await register(client, original["id"])).json()
        # When / Then: neither premature settlement nor fabricated outcome amounts are accepted.
        response = await settle(client, frozen["id"])
        assert response.status_code == 409
        assert response.json()["error"] == "validation_outcome_not_mature"
        injected = await client.post(
            BASE + f"/{frozen['id']}/settlement",
            json={
                "coverage_start": "2026-09-10",
                "coverage_end": "2026-09-11",
                "complete": True,
                "source_reference": "test",
                "actual_krw": 1,
            },
            headers={"Idempotency-Key": "inject"},
        )
        assert injected.status_code == 422


@pytest.mark.anyio
async def test_user_role_owner_isolation_duplicate_and_erasure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: one owner has a frozen forecast.
    clock = Clock()
    async with client_for(build(tmp_path / "isolation.sqlite3", clock, monkeypatch)) as client:
        original = (await forecast(client)).json()
        frozen = (await register(client, original["id"])).json()
        body = {"coaching_id": original["id"], "data_origin": "synthetic", "source_reference": "other"}
        # When / Then: cross-owner read, unprivileged write and replacement are rejected.
        other = await client.get(BASE + f"/{frozen['id']}", headers={"Authorization": "Bearer " + OTHER})
        assert other.status_code == 404
        user = await client.post(
            BASE,
            json=body,
            headers={
                "Authorization": "Bearer " + USER,
                "Idempotency-Key": "user-write",
            },
        )
        assert user.status_code == 403
        replacement = await client.post(BASE, json=body, headers={"Idempotency-Key": "replace"})
        assert replacement.status_code == 409
        assert replacement.json()["error"] == "forecast_already_registered"
        deleted = await client.delete("/v1/me/data")
        assert deleted.status_code == 200
        missing = await client.get(BASE + f"/{frozen['id']}")
        assert missing.status_code == 404
