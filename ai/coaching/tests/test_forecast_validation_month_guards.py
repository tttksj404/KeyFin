# ruff: noqa: INP001
"""월별 평가에서 사후 편성·부분 관측·타인 자료·확정 후 정답 수정을 차단한다."""

from pathlib import Path

import pytest
from test_api import OTHER
from test_forecast_validation_month_support import (
    BUDGETS,
    create_plan,
    month_forecast,
    month_outcomes,
    plan_body,
    register_month,
    registration_body,
    settle_month,
)
from test_forecast_validation_support import BASE, USER, Clock, build, client_for


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_budget_is_backend_only_idempotent_immutable_and_cannot_claim_owner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = Clock("2026-08-31T18:00:00")
    async with client_for(build(tmp_path / "budget.sqlite3", clock, monkeypatch)) as client:
        denied = await client.post(BUDGETS, json=plan_body(), headers={
            "Authorization": "Bearer " + USER, "Idempotency-Key": "user-plan",
        })
        assert denied.status_code == 403
        forged = await client.post(BUDGETS, json={**plan_body(), "owner": "other"},
                                   headers={"Idempotency-Key": "forged"})
        assert forged.status_code == 422
        plan = await create_plan(client, clock)
        assert plan["received_before_month_start"] is True
        repeated = await client.post(BUDGETS, json=plan_body(), headers={"Idempotency-Key": "plan"})
        assert repeated.json() == plan
        duplicate = await client.post(BUDGETS, json=plan_body(), headers={"Idempotency-Key": "plan-2"})
        assert duplicate.status_code == 409
        assert duplicate.json()["error"] == "validation_month_budget_already_registered"
        changed = await client.post(BUDGETS, json={**plan_body(), "source_reference": "changed"},
                                    headers={"Idempotency-Key": "plan"})
        assert changed.status_code == 409
        assert (await client.get(BUDGETS + f"/{plan['id']}")).json() == plan


@pytest.mark.anyio
async def test_claimed_past_approval_cannot_replace_server_pre_month_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = Clock()
    async with client_for(build(tmp_path / "late.sqlite3", clock, monkeypatch)) as client:
        response = await client.post(BUDGETS, json=plan_body(), headers={"Idempotency-Key": "late-plan"})
        assert response.status_code == 200
        plan = response.json()
        assert plan["received_before_month_start"] is False
        assert plan["approved_at"] < plan["received_at"]
        original = await month_forecast(client)
        rejected = await register_month(client, original["id"], plan["id"])
        assert rejected.status_code == 409
        assert rejected.json()["error"] == "validation_prospective_budget_received_too_late"


@pytest.mark.anyio
async def test_another_owners_existing_plan_cannot_be_attached_to_own_forecast(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = Clock("2026-08-31T18:00:00")
    async with client_for(build(tmp_path / "owner.sqlite3", clock, monkeypatch)) as client:
        plan = await client.post(BUDGETS, json=plan_body(), headers={
            "Authorization": "Bearer " + OTHER, "Idempotency-Key": "other-plan",
        })
        assert plan.status_code == 200
        clock.set("2026-09-09T18:00:00")
        original = await month_forecast(client)
        denied = await register_month(client, original["id"], plan.json()["id"])
        assert denied.status_code == 404
        assert (await client.get(BASE + f"/{original['id']}")).status_code == 404


@pytest.mark.anyio
async def test_budget_received_after_forecast_is_not_retrofitted_even_in_replay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = Clock()
    async with client_for(build(tmp_path / "retrofit.sqlite3", clock, monkeypatch)) as client:
        original = await month_forecast(client)
        clock.set("2026-09-09T19:00:00")
        response = await client.post(BUDGETS, json={**plan_body(), "data_origin": "historical_real"},
                                     headers={"Idempotency-Key": "late-plan"})
        assert response.status_code == 200
        body = {**registration_body(original["id"], response.json()["id"]), "data_origin": "historical_real"}
        rejected = await client.post(BASE, json=body, headers={"Idempotency-Key": "register"})
        assert rejected.status_code == 409
        assert rejected.json()["error"] == "validation_budget_received_after_forecast"


@pytest.mark.anyio
@pytest.mark.parametrize("question", ["앞으로 7일 예측", "앞으로 30일 예측"])
async def test_partial_or_cross_month_forecast_is_not_a_full_month_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, question: str,
) -> None:
    async with client_for(build(tmp_path / "period.sqlite3", Clock(), monkeypatch)) as client:
        original = await month_forecast(client, question=question)
        result = await register_month(client, original["id"])
        assert result.status_code == 422
        assert result.json()["error"] == "validation_requires_same_month_end_forecast"


@pytest.mark.anyio
async def test_month_requires_attestation_of_history_and_whole_month_outcomes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = Clock()
    async with client_for(build(tmp_path / "coverage.sqlite3", clock, monkeypatch)) as client:
        original = await month_forecast(client)
        body = registration_body(original["id"])
        monthly = body["monthly"]
        assert isinstance(monthly, dict)
        for patch in ({"history_complete": False}, {"history_coverage_start": "2026-09-02"}):
            result = await client.post(BASE, json={**body, "monthly": {**monthly, **patch}},
                                       headers={"Idempotency-Key": "partial"})
            assert result.status_code == 422
        frozen = await register_month(client, original["id"])
        assert frozen.status_code == 200
        await month_outcomes(client, clock)
        result = await client.post(BASE + f"/{frozen.json()['id']}/settlement", json={
            "coverage_start": "2026-09-10", "coverage_end": "2026-09-30", "complete": True,
            "source_reference": "future-only-export",
        }, headers={"Idempotency-Key": "partial-settle"})
        assert result.status_code == 422
        assert result.json()["error"] == "validation_coverage_period_mismatch"


@pytest.mark.anyio
@pytest.mark.parametrize("already_settled", [False, True])
async def test_correction_before_cutoff_cannot_keep_a_month_score_with_unchanged_future_total(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, already_settled: bool,
) -> None:
    clock = Clock()
    async with client_for(build(tmp_path / "correction.sqlite3", clock, monkeypatch)) as client:
        original = await month_forecast(client)
        frozen = (await register_month(client, original["id"])).json()
        await month_outcomes(client, clock)
        saved = None
        if already_settled:
            saved = (await settle_month(client, frozen["id"])).json()
        correction = await client.post("/v1/events", json={
            "expected_revision": 11, "cancellation_balance": {"envelope": "외식", "balance_krw": 10000},
            "event": {
            "type": "cancel_transaction", "event_id": "cancel-history", "user_id": "demo",
            "transaction_id": "history-0",
        }}, headers={"Idempotency-Key": "cancel-history"})
        assert correction.status_code == 200, correction.text
        if already_settled:
            result = await client.post(
                "/v1/forecast-validation/metrics", json={"registration_ids": [frozen["id"]]},
            )
            assert result.json()["error"] == "validation_observation_revised"
            assert (await client.get(BASE + f"/{frozen['id']}/settlement")).json() == saved
        else:
            result = await settle_month(client, frozen["id"])
            assert result.json()["error"] == "validation_month_history_revised"
        assert result.status_code == 409
