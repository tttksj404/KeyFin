# ruff: noqa: INP001
"""원거래가 같더라도 관측 정책이 바뀌면 기존 전향 평가를 새 규칙으로 채점하지 않는다."""

from datetime import date
from pathlib import Path

import pytest
from test_forecast_validation_month_integrity_support import replace, stored
from test_forecast_validation_month_support import (
    month_forecast,
    month_outcomes,
    register_month,
    settle_month,
)
from test_forecast_validation_support import BASE, Clock, build, client_for

from coaching_service import forecast_validation_month as consumer
from coaching_service import forecast_validation_month_observations as monthly
from coaching_service import forecast_validation_observations as observations
from coaching_service.forecast_validation_month_contracts import EnvelopeObservation
from coaching_service.forecast_validation_month_policy import observation_policy_sha256
from coaching_service.forecast_validation_observations import RawTransaction


def changed_consumption(_row: RawTransaction) -> int:
    return 0


def changed_consumer(
    rows: tuple[RawTransaction, ...], start: date, end: date,
) -> tuple[EnvelopeObservation, ...]:
    return tuple(
        row.model_copy(update={"consumption_krw": 0, "budget_used_krw": 0})
        if row.envelope == "외식" else row
        for row in monthly.observed_envelopes(rows, start, end)
    )


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
@pytest.mark.parametrize("phase", ["settle", "metrics"])
@pytest.mark.parametrize("changed", ["category", "subcategory", "order", "fixed", "helper", "consumer"])
async def test_changed_observation_policy_blocks_new_evaluation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, phase: str, changed: str,
) -> None:
    clock, database = Clock(), tmp_path / "policy.sqlite3"
    async with client_for(build(database, clock, monkeypatch)) as client:
        original = await month_forecast(client)
        frozen = (await register_month(client, original["id"])).json()
        assert len(frozen["monthly"]["policy_sha256"]) == 64
        await month_outcomes(client, clock)
        if phase == "metrics":
            assert (await settle_month(client, frozen["id"])).status_code == 200
        if changed == "category":
            monkeypatch.setitem(monthly.CATEGORIES, "업무", "외식")
        elif changed == "subcategory":
            monkeypatch.setitem(monthly.SUBCATEGORIES, "외식", monthly.SUBCATEGORIES["외식"] | {"택시"})
        elif changed == "order":
            monkeypatch.setattr(monthly, "SUBCATEGORIES", dict(reversed(monthly.SUBCATEGORIES.items())))
        elif changed == "fixed":
            monkeypatch.setattr(
                observations, "FIXED_SUBCATEGORIES", observations.FIXED_SUBCATEGORIES | {"택시"},
            )
        elif changed == "consumer":
            monkeypatch.setattr(consumer, "observed_envelopes", changed_consumer)
        else:
            monkeypatch.setattr(monthly, "consumption_amount", changed_consumption)
        assert observation_policy_sha256() != frozen["monthly"]["policy_sha256"]
        response = (await settle_month(client, frozen["id"])) if phase == "settle" else await client.post(
            "/v1/forecast-validation/metrics", json={"registration_ids": [frozen["id"]]},
        )
        assert response.status_code == 409
        assert response.json()["error"] == "validation_month_policy_changed"
        # 원본 저장 문서의 조회는 정책 변경 뒤에도 사용할 수 있다.
        assert (await client.get(BASE + "/" + frozen["id"])).status_code == 200


@pytest.mark.anyio
@pytest.mark.parametrize("phase", ["settle", "metrics"])
async def test_legacy_month_without_policy_is_readable_but_cannot_be_rescored(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, phase: str,
) -> None:
    clock, database = Clock(), tmp_path / "legacy.sqlite3"
    async with client_for(build(database, clock, monkeypatch)) as client:
        original = await month_forecast(client)
        frozen = (await register_month(client, original["id"])).json()
        await month_outcomes(client, clock)
        if phase == "metrics":
            assert (await settle_month(client, frozen["id"])).status_code == 200
        frozen["monthly"].pop("policy_sha256", None)
        replace(database, "forecast-registration/" + frozen["id"], frozen)
        if phase == "metrics":
            key = "forecast-settlement/" + frozen["id"]
            saved = stored(database, key)
            saved["registration"]["monthly"].pop("policy_sha256", None)
            replace(database, key, saved)
    async with client_for(build(database, clock, monkeypatch)) as client:
        loaded = await client.get(BASE + "/" + frozen["id"])
        assert loaded.status_code == 200, loaded.text
        assert loaded.json()["monthly"].get("policy_sha256") is None
        response = (await settle_month(client, frozen["id"])) if phase == "settle" else await client.post(
            "/v1/forecast-validation/metrics", json={"registration_ids": [frozen["id"]]},
        )
        assert response.status_code == 409
        assert response.json()["error"] == "validation_month_policy_missing"
