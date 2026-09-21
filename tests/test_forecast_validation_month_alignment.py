# ruff: noqa: INP001
"""봉투 이름은 영속 계약이며 배열 순서로 예측과 실제를 연결하지 않는다."""

from pathlib import Path

import pytest
from pydantic import ValidationError
from test_forecast_validation_month_integrity_support import replace, stored
from test_forecast_validation_month_support import (
    BUDGETS,
    create_plan,
    month_forecast,
    month_outcomes,
    register_month,
    settle_month,
)
from test_forecast_validation_support import BASE, Clock, build, client_for

from coaching_service.forecast_validation_contracts import Registration


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_reordered_saved_forecasts_join_actuals_by_envelope_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock, database = Clock(), tmp_path / "order.sqlite3"
    async with client_for(build(database, clock, monkeypatch)) as client:
        original = await month_forecast(client)
        response = await register_month(client, original["id"])
        assert response.status_code == 200, response.text
        frozen = response.json()
        forecasts = frozen["monthly"]["forecasts"]
        # 서로 다른 유효 금액을 사용해 이름이 뒤바뀌는 오류를 확실히 구별한다.
        for row, point in zip(forecasts[:2], (10000, 90000), strict=True):
            row["future_prediction"] = dict.fromkeys(("p10", "p50", "p90"), point)
            row["month_prediction"] = dict.fromkeys(
                ("p10", "p50", "p90"), point + row["observed_before_forecast"]["consumption_krw"],
            )
        frozen["monthly"]["forecasts"] = [forecasts[1], forecasts[0], *forecasts[2:]]
        Registration.model_validate(frozen)
        replace(database, "forecast-registration/" + frozen["id"], frozen)
        await month_outcomes(client, clock)
        settled = await settle_month(client, frozen["id"])
        assert settled.status_code == 200, settled.text
        rows = {row["envelope"]: row for row in settled.json()["monthly"]["comparisons"]}
        assert rows["외식"]["future_error_krw"] == -13000
        assert rows["교통비"]["future_error_krw"] == 50000
        report = await client.post(
            "/v1/forecast-validation/metrics", json={"registration_ids": [frozen["id"]]},
        )
        assert report.status_code == 200, report.text
        metrics = {row["envelope"]: row["values"] for row in report.json()["envelopes"]}
        assert metrics["외식"]["mae_krw"] == 13000
        assert metrics["교통비"]["mae_krw"] == 50000


@pytest.mark.anyio
@pytest.mark.parametrize("corruption", ["duplicate", "nested_name"])
async def test_saved_month_contract_rejects_duplicate_or_mismatched_names(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, corruption: str,
) -> None:
    clock, database = Clock(), tmp_path / "broken.sqlite3"
    async with client_for(build(database, clock, monkeypatch)) as client:
        original = await month_forecast(client)
        registered = await register_month(client, original["id"])
        frozen = registered.json()
        if corruption == "duplicate":
            frozen["monthly"]["forecasts"][1] = frozen["monthly"]["forecasts"][0]
        else:
            frozen["monthly"]["forecasts"][0]["observed_before_forecast"]["envelope"] = "교통비"
        with pytest.raises(ValidationError):
            Registration.model_validate(frozen)
        replace(database, "forecast-registration/" + frozen["id"], frozen)
        response = await client.get(BASE + "/" + frozen["id"])
        assert response.status_code == 409
        assert response.json()["error"] == "validation_saved_registration_invalid"


@pytest.mark.anyio
@pytest.mark.parametrize("corruption", ["missing", "duplicate"])
async def test_saved_month_plan_requires_seven_unique_allocations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, corruption: str,
) -> None:
    clock, database = Clock(), tmp_path / "broken-plan.sqlite3"
    async with client_for(build(database, clock, monkeypatch)) as client:
        plan = await create_plan(client, clock)
        original = await month_forecast(client)
        frozen = (await register_month(client, original["id"], plan["id"])).json()
        allocations = frozen["monthly"]["budget_plan"]["allocations"]
        if corruption == "missing":
            allocations.pop(0)
        else:
            allocations[1] = allocations[0]
        with pytest.raises(ValidationError):
            Registration.model_validate(frozen)
        replace(database, "forecast-registration/" + frozen["id"], frozen)
        await month_outcomes(client, clock)
        for response in (
            await client.get(BASE + "/" + frozen["id"]),
            await settle_month(client, frozen["id"]),
        ):
            assert response.status_code == 409
            assert response.json()["error"] == "validation_saved_registration_invalid"


@pytest.mark.anyio
@pytest.mark.parametrize("corruption", ["missing", "duplicate"])
async def test_saved_standalone_plan_fails_closed_on_get_and_registration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, corruption: str,
) -> None:
    clock, database = Clock(), tmp_path / "broken-standalone-plan.sqlite3"
    async with client_for(build(database, clock, monkeypatch)) as client:
        plan = await create_plan(client, clock)
        key = "forecast-budget/" + str(plan["id"])
        saved = stored(database, key)
        if corruption == "missing":
            saved["allocations"].pop(0)
        else:
            saved["allocations"][1] = saved["allocations"][0]
        replace(database, key, saved)
        original = await month_forecast(client)
        for response in (
            await client.get(BUDGETS + "/" + str(plan["id"])),
            await register_month(client, original["id"], plan["id"]),
        ):
            assert response.status_code == 409
            assert response.json()["error"] == "validation_saved_budget_invalid"


@pytest.mark.anyio
async def test_duplicate_saved_settlement_comparisons_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock, database = Clock(), tmp_path / "broken-settlement.sqlite3"
    async with client_for(build(database, clock, monkeypatch)) as client:
        original = await month_forecast(client)
        frozen = (await register_month(client, original["id"])).json()
        await month_outcomes(client, clock)
        assert (await settle_month(client, frozen["id"])).status_code == 200
        key = "forecast-settlement/" + frozen["id"]
        payload = stored(database, key)
        payload["monthly"]["comparisons"][1] = payload["monthly"]["comparisons"][0]
        replace(database, key, payload)
        response = await client.post(
            "/v1/forecast-validation/metrics", json={"registration_ids": [frozen["id"]]},
        )
        assert response.status_code == 409
        assert response.json()["error"] == "validation_saved_settlement_invalid"
