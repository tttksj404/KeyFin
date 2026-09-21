# ruff: noqa: INP001
"""Settled records stay immutable while new reports reject revised observations."""

from pathlib import Path

import pytest
from test_engine import fixture
from test_forecast_validation_support import (
    BASE,
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
async def test_late_cancellation_blocks_new_metrics_but_preserves_original_settlement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: the original complete outcome is 20,000 + 6,000 = 26,000.
    clock = Clock()
    async with client_for(build(tmp_path / "cancel.sqlite3", clock, monkeypatch)) as client:
        original = (await forecast(client)).json()
        registration_id = (await register(client, original["id"])).json()["id"]
        clock.set("2026-09-12T00:01:00")
        await outcomes(client)
        settled = await settle(client, registration_id)
        assert settled.status_code == 200, settled.text
        clock.set("2026-09-13T00:01:00")
        canceled = await client.post(
            "/v1/events",
            json={
                "expected_revision": 2,
                "event": {
                    "type": "cancel_transaction",
                    "event_id": "late-cancel",
                    "user_id": "demo",
                    "transaction_id": "outcome-0",
                },
            },
            headers={"Idempotency-Key": "late-cancel"},
        )
        assert canceled.status_code == 200, canceled.text
        # When: request a fresh evaluation after the 20,000 purchase was canceled.
        response = await client.post(
            "/v1/forecast-validation/metrics",
            json={
                "registration_ids": [registration_id],
            },
        )
        # Then: historical scores cannot masquerade as the revised outcome's evaluation.
        assert response.status_code == 409
        assert response.json()["error"] == "validation_observation_revised"
        assert (await client.get(BASE + f"/{registration_id}/settlement")).json() == settled.json()


@pytest.mark.anyio
async def test_later_transaction_outside_window_does_not_invalidate_metrics(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: a complete frozen outcome for September 10-11.
    clock = Clock()
    async with client_for(build(tmp_path / "later.sqlite3", clock, monkeypatch)) as client:
        original = (await forecast(client)).json()
        registration_id = (await register(client, original["id"])).json()["id"]
        clock.set("2026-09-12T00:01:00")
        await outcomes(client)
        settled = await settle(client, registration_id)
        assert settled.status_code == 200, settled.text
        before = await client.post(
            "/v1/forecast-validation/metrics",
            json={
                "registration_ids": [registration_id],
            },
        )
        assert before.status_code == 200
        clock.set("2026-09-13T00:01:00")
        row = fixture().transactions[0].root
        later = await client.post(
            "/v1/events",
            json={
                "expected_revision": 2,
                "event": {
                    "type": "transaction",
                    "event_id": "later",
                    "user_id": "demo",
                    "transaction": {
                        **row,
                        "transaction_id": "later",
                        "transaction_date": "2026-09-12",
                        "amount_krw": 3000,
                    },
                },
            },
            headers={"Idempotency-Key": "later"},
        )
        assert later.status_code == 200, later.text
        # When: the whole Twin digest changed, but this evaluated window did not.
        after = await client.post(
            "/v1/forecast-validation/metrics",
            json={
                "registration_ids": [registration_id],
            },
        )
        # Then: compare the target's raw sum/count, not the global digest.
        assert after.status_code == 200, after.text
        assert after.json()["values"] == before.json()["values"]


@pytest.mark.anyio
async def test_changed_count_with_same_total_still_requires_outcome_revision(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: the settled 20,000 + 6,000 consisted of two purchases.
    clock = Clock()
    async with client_for(build(tmp_path / "split.sqlite3", clock, monkeypatch)) as client:
        original = (await forecast(client)).json()
        registration_id = (await register(client, original["id"])).json()["id"]
        clock.set("2026-09-12T00:01:00")
        await outcomes(client)
        settled = await settle(client, registration_id)
        assert settled.status_code == 200, settled.text
        clock.set("2026-09-13T00:01:00")
        canceled = await client.post(
            "/v1/events",
            json={
                "expected_revision": 2,
                "event": {
                    "type": "cancel_transaction",
                    "event_id": "split-cancel",
                    "user_id": "demo",
                    "transaction_id": "outcome-0",
                },
            },
            headers={"Idempotency-Key": "split-cancel"},
        )
        assert canceled.status_code == 200, canceled.text
        raw = fixture().transactions[0].root
        for revision in (3, 4):
            replacement = await client.post(
                "/v1/events",
                json={
                    "expected_revision": revision,
                    "event": {
                        "type": "transaction",
                        "event_id": f"split-{revision}",
                        "user_id": "demo",
                        "transaction": {
                            **raw,
                            "transaction_id": f"split-{revision}",
                            "transaction_date": "2026-09-10",
                            "amount_krw": 10000,
                        },
                    },
                },
                headers={"Idempotency-Key": f"split-{revision}"},
            )
            assert replacement.status_code == 200, replacement.text
        # When: 10,000 + 10,000 + 6,000 has the same sum but different observation count.
        response = await client.post(
            "/v1/forecast-validation/metrics",
            json={
                "registration_ids": [registration_id],
            },
        )
        # Then: agreement on total alone cannot retain the stale observation record.
        assert response.status_code == 409
        assert response.json()["error"] == "validation_observation_revised"
        assert (await client.get(BASE + f"/{registration_id}/settlement")).json() == settled.json()
