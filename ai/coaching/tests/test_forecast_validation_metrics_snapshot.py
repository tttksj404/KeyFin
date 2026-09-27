# ruff: noqa: INP001
"""관측 확인 도중 실제 이벤트가 확정되면 이전 snapshot의 지표를 새 결과로 내보내지 않는다."""

from pathlib import Path

import pytest
from test_forecast_validation_month_support import (
    add_event,
    month_forecast,
    month_outcomes,
    register_month,
    settle_month,
)
from test_forecast_validation_support import Clock, build, client_for

from coaching_service.coaching import CoachingCore
from coaching_service.schemas import JsonDocument


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_metrics_rejects_a_committed_event_after_its_initial_observation_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = Clock()
    async with client_for(build(tmp_path / "race.sqlite3", clock, monkeypatch)) as client:
        original = await month_forecast(client)
        frozen = (await register_month(client, original["id"])).json()
        await month_outcomes(client, clock)
        assert (await settle_month(client, frozen["id"])).status_code == 200
        read_twin = CoachingCore.twin
        pending = True

        async def read_then_commit(self: CoachingCore, owner: str) -> JsonDocument:
            nonlocal pending
            captured = await read_twin(self, owner)
            if pending:
                pending = False
                # 원장 read 이후, 지표 응답 이전에 실제 이벤트 API가 늦게 수신한 소비를 확정한다.
                await add_event(client, 11, subcategory="점심", amount_krw=1234)
            return captured

        monkeypatch.setattr(CoachingCore, "twin", read_then_commit)
        response = await client.post(
            "/v1/forecast-validation/metrics", json={"registration_ids": [frozen["id"]]},
        )
        assert response.status_code == 409
        assert response.json()["error"] == "validation_observation_changed_during_metrics"
        # 다시 호출하면 새 원거래를 읽고 기존 정산과 달라졌음을 명시한다.
        retried = await client.post(
            "/v1/forecast-validation/metrics", json={"registration_ids": [frozen["id"]]},
        )
        assert retried.status_code == 409
        assert retried.json()["error"] == "validation_observation_revised"


@pytest.mark.anyio
async def test_successful_metrics_identifies_the_snapshot_it_checked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = Clock()
    async with client_for(build(tmp_path / "checked.sqlite3", clock, monkeypatch)) as client:
        original = await month_forecast(client)
        frozen = (await register_month(client, original["id"])).json()
        await month_outcomes(client, clock)
        settlement = (await settle_month(client, frozen["id"])).json()
        response = await client.post(
            "/v1/forecast-validation/metrics", json={"registration_ids": [frozen["id"]]},
        )
        assert response.status_code == 200, response.text
        assert response.json()["observed_identity"] == settlement["observed_identity"]
        assert response.json()["observed_checked_at"] == clock.now
