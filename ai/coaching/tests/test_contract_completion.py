# noqa: INP001 - standalone pytest module
"""Exercise all engine modes and the final cross-module contracts."""

from pathlib import Path
from unittest.mock import patch

import httpx2
import pytest
from pydantic import SecretStr
from test_api import TOKEN, TestModel, event, setup
from test_engine import fixture

from coaching_service.admission import admit
from coaching_service.api import create_app
from coaching_service.errors import ServiceError
from coaching_service.provenance import verify_engine
from coaching_service.schemas import JsonDocument
from coaching_service.settings import Client, Settings


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
@pytest.mark.parametrize("mode", ["forecast", "what_if", "goal", "risk", "optimize"])
async def test_five_real_engine_modes_leave_twin_unchanged(tmp_path: Path, mode: str) -> None:
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=setup(tmp_path / "modes.sqlite3", TestModel())),
        base_url="http://test",
        headers={"Authorization": "Bearer " + TOKEN},
    ) as client:
        assert (
            await client.post(
                "/v1/twin", json=fixture().model_dump(mode="json"), headers={"Idempotency-Key": "init"}
            )
        ).status_code == 200
        before = (await client.get("/v1/twin")).json()
        reviewed = await client.post(
            "/v1/coaching/reviews",
            json={"on_date": "2026-09-09", "through_date": "2026-09-16", "paths": 20},
            headers={"Idempotency-Key": "review"},
        )
        assert reviewed.status_code == 200, reviewed.text
        session = (
            await client.post(
                "/v1/sessions",
                json={"coaching_id": reviewed.json()["id"]},
                headers={"Idempotency-Key": "session"},
            )
        ).json()
        analysis = {"mode": mode, "paths": 20, "horizon_days": 7, "seed": 42}
        if mode == "goal":
            analysis["goal"] = {"target_krw": 100000}
        if mode == "what_if":
            analysis["scenario"] = {"expense_reductions": {"기타": 0.2}}
        if mode == "optimize":
            analysis["optimization"] = {"envelopes": ["기타"], "reduction_grid": [0, 0.2]}
        result = await client.post(
            f"/v1/sessions/{session['id']}/messages",
            json={"question": "이 조건에서 결과를 확인해 줘", "analysis": analysis},
            headers={"Idempotency-Key": "turn"},
        )
        assert result.status_code == 200, result.text
        receipt = result.json()["receipt"]
        assert receipt["numeric_request"] == analysis
        assert receipt["numeric_result"]["mode"] == mode
        assert receipt["numeric_result"]["metrics"]
        assert "warnings" in receipt["numeric_result"]
        assert (await client.get("/v1/twin")).json() == before


@pytest.mark.anyio
async def test_companion_snapshot_is_atomic_and_owner_checked(tmp_path: Path) -> None:
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=setup(tmp_path / "snapshot.sqlite3", TestModel())),
        base_url="http://test",
        headers={"Authorization": "Bearer " + TOKEN},
    ) as client:
        assert (
            await client.post(
                "/v1/twin", json=fixture().model_dump(mode="json"), headers={"Idempotency-Key": "init"}
            )
        ).status_code == 200
        before = (await client.get("/v1/twin")).json()
        snapshot = fixture().snapshot
        assert snapshot is not None
        request = event()
        request["snapshot_event"] = {
            "type": "snapshot",
            "event_id": "snapshot",
            "user_id": "other",
            "snapshot": {
                **snapshot.root,
                "source": "LIVE",
                "accounts": [{"account_id": "a", "balance_krw": 950000}],
            },
        }
        invalid = await client.post("/v1/events", json=request, headers={"Idempotency-Key": "bad"})
        assert invalid.status_code == 422
        assert (await client.get("/v1/twin")).json() == before
        assert (await client.get("/v1/notifications")).json()["items"] == []
        request["snapshot_event"]["user_id"] = "demo"
        result = await client.post("/v1/events", json=request, headers={"Idempotency-Key": "good"})
        assert result.status_code == 200, result.text
        assert result.json()["payment"]["balance_before_krw"] == 100000
        assert result.json()["identity"]["revision"] == 1
        assert result.json()["coaching"]["receipt"]["result"]["context"]["absolute_cash_ready"] is True


@pytest.mark.anyio
async def test_roles_and_expiry(tmp_path: Path) -> None:
    settings = Settings(
        database=tmp_path / "roles.sqlite3",
        clients=(
            Client(user_id="demo", token=SecretStr(TOKEN)),
            Client(user_id="demo", token=SecretStr("user-test-token-000000000000000000000"), role="user"),
            Client(
                user_id="demo", token=SecretStr("notification-test-token-0000000000000"), role="notification"
            ),
        ),
    )
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=create_app(settings, TestModel())),
        base_url="http://test",
        headers={"Authorization": "Bearer " + TOKEN},
    ) as client:
        assert (
            await client.post(
                "/v1/twin", json=fixture().model_dump(mode="json"), headers={"Idempotency-Key": "init"}
            )
        ).status_code == 200
        result = (await client.post("/v1/events", json=event(), headers={"Idempotency-Key": "pay"})).json()
        session = (
            await client.post(
                "/v1/sessions",
                json={"coaching_id": result["coaching"]["id"]},
                headers={"Idempotency-Key": "session"},
            )
        ).json()
        assert (
            await client.get(
                "/v1/twin",
                headers={"Authorization": "Bearer " + settings.clients[1].token.get_secret_value()},
            )
        ).status_code == 403
        assert (
            await client.get(
                "/v1/coaching/" + result["coaching"]["id"],
                headers={"Authorization": "Bearer " + settings.clients[2].token.get_secret_value()},
            )
        ).status_code == 403
        with patch("coaching_service.dialogue.time.time", return_value=session["expires_at"] + 1):
            expired = await client.post(
                f"/v1/sessions/{session['id']}/messages",
                json={"question": "계속 알려 줘"},
                headers={"Idempotency-Key": "late"},
            )
        assert expired.status_code == 410
        assert (await client.get(f"/v1/sessions/{session['id']}")).json()["messages"] == []


def test_compute_admission_matches_engine_default_horizon() -> None:
    # 64 candidates * default 90 days * 400 paths exceeds the service ceiling.
    with pytest.raises(ServiceError, match="numeric_compute_budget_exceeded"):
        admit(
            JsonDocument.model_validate(
                {
                    "mode": "optimize",
                    "optimization": {
                        "envelopes": ["외식", "쇼핑", "기타"],
                        "reduction_grid": [0, 0.1, 0.2, 0.3],
                    },
                }
            )
        )


def test_imported_engine_sources_match_upstream_manifest() -> None:
    assert verify_engine() == 21
