# ruff: noqa: INP001
"""소비 구성 차이는 금액으로 노출하고 예산 초과의 원인으로 단정하지 않는다."""

from datetime import date
from pathlib import Path

import pytest
from test_forecast_validation_month_integrity_support import replace, stored
from test_forecast_validation_month_support import (
    add_event,
    create_plan,
    month_forecast,
    month_outcomes,
    register_month,
    settle_month,
)
from test_forecast_validation_observations import raw
from test_forecast_validation_support import BASE, Clock, build, client_for

from coaching_service.forecast_validation_month_contracts import EnvelopeObservation
from coaching_service.forecast_validation_month_observations import observed_envelopes


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.parametrize("exclude_tag", ["DUTCH", "EMERGENCY", "CARRYOVER"])
def test_excluded_amount_uses_confirmed_consumption_without_netting_refunds(exclude_tag: str) -> None:
    # Given: 취소·입금 환불·고정비는 소비 정답이 아니며 원구매만 유지한다.
    rows = (
        raw(transaction_id="normal", amount_krw=20000),
        raw(transaction_id="excluded", amount_krw=3000, exclude_tag=exclude_tag),
        raw(transaction_id="canceled", amount_krw=8000, status="CANCELED", exclude_tag=exclude_tag),
        raw(transaction_id="refund", amount_krw=1000, transaction_type="DEPOSIT", subcategory="환불"),
        raw(transaction_id="fixed", amount_krw=90000, subcategory="월세", exclude_tag=exclude_tag),
    )

    # When
    observation = observed_envelopes(rows, date(2026, 9, 1), date(2026, 9, 30))[0]

    # Then: 기존 구매시점 평가 규약에서 부분 환불 입금은 구매를 소급 차감하지 않는다.
    assert observation.consumption_krw == 23000
    assert observation.budget_used_krw == 20000
    assert observation.budget_excluded_consumption_krw == 3000
    assert observation.consumption_count == 2
    assert observation.budget_transaction_count == 1


def test_legacy_observation_without_excluded_amount_remains_unknown() -> None:
    # Given: 새 메타데이터가 없던 저장 형식.
    legacy = {
        "envelope": "외식", "consumption_krw": 23000, "consumption_count": 2,
        "budget_used_krw": 20000, "budget_transaction_count": 1,
    }

    # When
    observation = EnvelopeObservation.model_validate(legacy)

    # Then
    assert observation.budget_excluded_consumption_krw is None
    assert observation.consumption_krw == 23000
    assert observation.budget_used_krw == 20000


@pytest.mark.anyio
async def test_excluded_consumption_before_forecast_also_prevents_month_budget_diagnosis(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: 제외 소비는 기준일 이전에만 있고 이후 소비는 모두 예산 대상이다.
    clock = Clock()
    async with client_for(build(tmp_path / "before-basis.sqlite3", clock, monkeypatch)) as client:
        plan = await create_plan(client, clock)
        await month_forecast(client)
        await add_event(client, 0, amount_krw=3000, subcategory="점심", exclude_tag="DUTCH",
                        transaction_date="2026-09-05")
        session = await client.post(
            "/v1/sessions", json={}, headers={"Idempotency-Key": "session-with-exclusion"},
        )
        assert session.status_code == 200, session.text
        forecast = await client.post(
            f"/v1/sessions/{session.json()['id']}/messages",
            json={"question": "이번 달 말까지 예측", "analysis": {"mode": "forecast", "paths": 20}},
            headers={"Idempotency-Key": "forecast-with-exclusion"},
        )
        assert forecast.status_code == 200, forecast.text
        registered = await register_month(client, forecast.json()["id"], plan["id"])
        assert registered.status_code == 200, registered.text
        clock.set("2026-10-01T00:01:00")
        await add_event(client, 1, amount_krw=20000, subcategory="점심")
        await add_event(client, 2, amount_krw=20000, transaction_type="CARD_SETTLEMENT",
                        transaction_date="2026-09-30")

        # When
        response = await settle_month(client, registered.json()["id"])

    # Then: 미래 구간만 확인해 기준 일치로 오판하지 않는다.
    assert response.status_code == 200, response.text
    food = response.json()["monthly"]["comparisons"][0]
    assert food["future_actual"]["budget_excluded_consumption_krw"] == 0
    assert food["month_actual"]["budget_excluded_consumption_krw"] == 3000
    assert food["budget_remaining_krw"] == -10000
    assert food["budget_comparison"]["observed_spending_basis"] == "different"
    assert food["budget_comparison"]["diagnosis"] == "indeterminate_target_mismatch"
    assert food["budget_comparison"]["causal_attribution_established"] is False


@pytest.mark.anyio
async def test_legacy_saved_settlement_readback_does_not_invent_a_diagnosis(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: 기존 정산에서 새 진단·관측 메타데이터만 빠진 저장 문서.
    clock, database = Clock(), tmp_path / "legacy-basis.sqlite3"
    async with client_for(build(database, clock, monkeypatch)) as client:
        plan = await create_plan(client, clock)
        original = await month_forecast(client)
        registered = await register_month(client, original["id"], plan["id"])
        assert registered.status_code == 200, registered.text
        registration_id = registered.json()["id"]
        await month_outcomes(client, clock)
        settled = await settle_month(client, registration_id)
        assert settled.status_code == 200, settled.text
        key = "forecast-settlement/" + registration_id
        legacy = stored(database, key)
        for row in legacy["registration"]["monthly"]["forecasts"]:
            del row["observed_before_forecast"]["budget_excluded_consumption_krw"]
        for row in legacy["monthly"]["comparisons"]:
            del row["budget_comparison"]
            del row["future_actual"]["budget_excluded_consumption_krw"]
            del row["month_actual"]["budget_excluded_consumption_krw"]
        replace(database, key, legacy)

    # When: 앱을 다시 열어 영속 문서를 조회한다.
    async with client_for(build(database, clock, monkeypatch)) as client:
        response = await client.get(BASE + f"/{registration_id}/settlement")

    # Then
    assert response.status_code == 200, response.text
    food = response.json()["monthly"]["comparisons"][0]
    assert food["budget_comparison"] is None
    assert food["future_actual"]["budget_excluded_consumption_krw"] is None
    assert food["month_actual"]["budget_excluded_consumption_krw"] is None
    assert food["month_actual"]["consumption_krw"] == 33000
    assert food["budget_remaining_krw"] == -10000
