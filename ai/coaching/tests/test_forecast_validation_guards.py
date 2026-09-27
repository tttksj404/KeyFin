# ruff: noqa: INP001
"""Negative API cases for temporal leakage, missing coverage and immutable records."""

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

from coaching_service.forecast_validation_ingestion import IngestionStamp, ingestion_key
from coaching_service.schemas import TwinIdentity
from coaching_service.store import Store


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("patch", "status"),
    [
        ({"complete": False}, 422),
        ({"coverage_start": "2026-09-09"}, 422),
        ({"coverage_end": "2026-09-10"}, 422),
        ({"coverage_end": "2026-09-11T00:00:00"}, 422),
    ],
)
async def test_incomplete_or_different_period_cannot_be_scored(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    patch: dict[str, str | bool],
    status: int,
) -> None:
    # Given: mature source records and an exact frozen two-day target.
    clock = Clock()
    async with client_for(build(tmp_path / "coverage.sqlite3", clock, monkeypatch)) as client:
        original = (await forecast(client)).json()
        frozen = (await register(client, original["id"])).json()
        clock.set("2026-09-12T00:01:00")
        await outcomes(client)
        # When / Then: incomplete/different coverage never becomes a valid numeric score.
        response = await client.post(
            BASE + f"/{frozen['id']}/settlement",
            json={
                "coverage_start": "2026-09-10",
                "coverage_end": "2026-09-11",
                "complete": True,
                "source_reference": "test",
                **patch,
            },
            headers={"Idempotency-Key": "coverage"},
        )
        assert response.status_code == status, response.text
        assert (await client.get(BASE + f"/{frozen['id']}/settlement")).status_code == 404


@pytest.mark.anyio
async def test_unchanged_twin_does_not_become_zero_spend_after_waiting(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: waiting until maturity has not supplied any new provider observations.
    clock = Clock()
    async with client_for(build(tmp_path / "missing.sqlite3", clock, monkeypatch)) as client:
        original = (await forecast(client)).json()
        frozen = (await register(client, original["id"])).json()
        clock.set("2026-09-12T00:01:00")
        # When / Then: empty future rows in the old snapshot are missing data, not zero consumption.
        response = await settle(client, frozen["id"])
        assert response.status_code == 409
        assert response.json()["error"] == "validation_observation_not_updated"


@pytest.mark.anyio
async def test_legacy_unstamped_receipt_is_replay_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: a persisted legacy forecast with no server ingestion timestamp.
    clock = Clock()
    path = tmp_path / "unstamped.sqlite3"
    async with client_for(build(path, clock, monkeypatch)) as client:
        original = (await forecast(client)).json()
        with Store(path).connection() as connection:
            _ = connection.execute("DELETE FROM items WHERE key LIKE 'forecast-ingestion/%'")
        # When / Then: even before the target starts, a missing server stamp cannot prove provenance.
        rejected = await register(client, original["id"])
        assert rejected.status_code == 409
        replay = await client.post(
            BASE,
            json={
                "coaching_id": original["id"],
                "data_origin": "historical_real",
                "source_reference": "test",
            },
            headers={"Idempotency-Key": "replay"},
        )
        assert replay.status_code == 200, replay.text
        assert replay.json()["evidence_tier"] == "replay"
        assert replay.json()["ingestion_received_at"] is None
        assert replay.json()["real_accuracy_validated"] is False


@pytest.mark.anyio
async def test_bootstrap_replacement_does_not_reuse_an_old_revision_stamp(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A full Twin replacement may reset revision zero without blocking the next event."""
    clock = Clock()
    path = tmp_path / "bootstrap-replacement.sqlite3"
    async with client_for(build(path, clock, monkeypatch)) as client:
        original = fixture().model_dump(mode="json")
        initialized = await client.post(
            "/v1/twin", json=original, headers={"Idempotency-Key": "bootstrap-one"}
        )
        assert initialized.status_code == 200, initialized.text
        source_row = original["transactions"][0]
        before_reset = await client.post(
            "/v1/events",
            json={
                "expected_revision": 0,
                "event": {
                    "type": "transaction",
                    "event_id": "before-reset",
                    "user_id": "demo",
                    "transaction": {
                        **source_row,
                        "transaction_id": "before-reset",
                        "transaction_date": "2026-09-10",
                        "amount_krw": 1000,
                    },
                },
            },
            headers={"Idempotency-Key": "event-before-reset"},
        )
        assert before_reset.status_code == 200, before_reset.text
        assert before_reset.json()["identity"]["revision"] == 1

        replacement = fixture().model_dump(mode="json")
        replacement["transactions"][0]["amount_krw"] = source_row["amount_krw"] + 1
        refreshed = await client.post(
            "/v1/twin", json=replacement, headers={"Idempotency-Key": "bootstrap-two"}
        )
        assert refreshed.status_code == 200, refreshed.text
        assert refreshed.json()["revision"] == 0
        assert refreshed.json()["input_digest"] != initialized.json()["input_digest"]

        after_reset = await client.post(
            "/v1/events",
            json={
                "expected_revision": 0,
                "event": {
                    "type": "transaction",
                    "event_id": "after-reset",
                    "user_id": "demo",
                    "transaction": {
                        **replacement["transactions"][0],
                        "transaction_id": "after-reset",
                        "transaction_date": "2026-09-11",
                        "amount_krw": 2000,
                    },
                },
            },
            headers={"Idempotency-Key": "event-after-reset"},
        )
        assert after_reset.status_code == 200, after_reset.text
        assert after_reset.json()["identity"]["revision"] == 1

    with Store(path).connection() as connection:
        keys = tuple(
            row[0]
            for row in connection.execute(
                "SELECT key FROM items WHERE owner=? AND key LIKE 'forecast-ingestion/%' ORDER BY key",
                ("demo",),
            ).fetchall()
        )
    assert sum(key.startswith("forecast-ingestion/revision-0/digest-") for key in keys) == 2
    assert sum(key.startswith("forecast-ingestion/revision-1/digest-") for key in keys) == 2


@pytest.mark.anyio
async def test_current_digest_stamp_wins_over_a_legacy_revision_collision(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A stale legacy row cannot shadow the current identity-bound receipt."""
    clock = Clock()
    path = tmp_path / "legacy-collision.sqlite3"
    async with client_for(build(path, clock, monkeypatch)) as client:
        original = (await forecast(client)).json()
        identity = TwinIdentity.model_validate(original["receipt"]["identity"])
        stale_identity = identity.model_copy(update={"input_digest": "f" * 64})
        stale_stamp = IngestionStamp(
            identity=stale_identity,
            received_at=clock.time(),
            request_digest="a" * 64,
        )
        with Store(path).connection() as connection:
            _ = connection.execute(
                "INSERT INTO items(owner,key,payload) VALUES(?,?,?)",
                ("demo", ingestion_key(identity.revision), stale_stamp.model_dump_json()),
            )

        registered = await register(client, original["id"])
        assert registered.status_code == 200, registered.text
        assert registered.json()["evidence_tier"] == "prospective_attested"


@pytest.mark.anyio
async def test_reused_key_with_changed_source_cannot_relabel_prediction(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: one backend attestation has been frozen under a request key.
    clock = Clock()
    async with client_for(build(tmp_path / "relabel.sqlite3", clock, monkeypatch)) as client:
        original = (await forecast(client)).json()
        frozen = (await register(client, original["id"])).json()
        # When / Then: changed body on the same key is a conflict, not relabeling.
        changed = await client.post(
            BASE,
            json={
                "coaching_id": original["id"],
                "data_origin": "synthetic",
                "source_reference": "changed",
            },
            headers={"Idempotency-Key": "register"},
        )
        assert changed.status_code == 409
        assert changed.json()["error"] == "idempotency_key_conflict"
        assert (await client.get(BASE + f"/{frozen['id']}")).json() == frozen


@pytest.mark.anyio
async def test_unsettled_and_duplicate_ids_cannot_produce_scores(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: a registered forecast has no actual outcome yet.
    clock = Clock()
    async with client_for(build(tmp_path / "metrics.sqlite3", clock, monkeypatch)) as client:
        original = (await forecast(client)).json()
        frozen = (await register(client, original["id"])).json()
        # When / Then: absent settlement is 404, and repeated IDs cannot inflate sample counts.
        missing = await client.post(
            "/v1/forecast-validation/metrics", json={"registration_ids": [frozen["id"]]}
        )
        assert missing.status_code == 404
        duplicate = await client.post(
            "/v1/forecast-validation/metrics",
            json={
                "registration_ids": [frozen["id"], frozen["id"]],
            },
        )
        assert duplicate.status_code == 422
        assert duplicate.json()["error"] == "validation_duplicate_registration"


@pytest.mark.anyio
async def test_origin_cohorts_are_not_pooled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: two independently stored engine answers with different source attestations.
    clock = Clock()
    async with client_for(build(tmp_path / "cohort.sqlite3", clock, monkeypatch)) as client:
        first = (await forecast(client)).json()
        first_id = (await register(client, first["id"])).json()["id"]
        session = await client.post("/v1/sessions", json={}, headers={"Idempotency-Key": "session-two"})
        second = await client.post(
            f"/v1/sessions/{session.json()['id']}/messages",
            json={
                "question": "앞으로 2일 예측",
                "analysis": {"mode": "forecast", "horizon_days": 2, "paths": 20},
            },
            headers={"Idempotency-Key": "forecast-two"},
        )
        assert second.status_code == 200, second.text
        second_frozen = await client.post(
            BASE,
            json={
                "coaching_id": second.json()["id"],
                "data_origin": "synthetic",
                "source_reference": "test",
            },
            headers={"Idempotency-Key": "register-two"},
        )
        assert second_frozen.status_code == 200, second_frozen.text
        second_id = second_frozen.json()["id"]
        clock.set("2026-09-12T00:01:00")
        await outcomes(client)
        assert (await settle(client, first_id)).status_code == 200
        assert (await settle(client, second_id)).status_code == 200
        # When / Then: synthetic and backend-attested future outcomes cannot be combined.
        combined = await client.post(
            "/v1/forecast-validation/metrics",
            json={
                "registration_ids": [first_id, second_id],
            },
        )
        assert combined.status_code == 422
        assert combined.json()["error"] == "validation_incomparable_cohort"
