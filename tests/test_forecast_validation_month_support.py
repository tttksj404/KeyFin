# ruff: noqa: INP001
"""월 예산과 거래 정답을 손으로 정한 API 시험 자료."""

from datetime import datetime

import httpx2
from test_engine import fixture
from test_forecast_validation_support import BASE, Clock

from coaching_service.forecast_validation_observations import SEOUL
from coaching_service.forecast_validation_values import ENVELOPES
from coaching_service.schemas import JsonDocument

BUDGETS = "/v1/forecast-validation/monthly-budgets"
LABELS = ("점심", "택시", "약국", "영화/공연", "의류", "장보기", "경조사")


def plan_body() -> dict[str, object]:
    return {
        "month_start": "2026-09-01",
        "approved_at": datetime(2026, 8, 31, 12, tzinfo=SEOUL).timestamp(),
        "data_origin": "backend_attested_real", "source_reference": "synthetic-original-plan-attestation",
        "allocations": [
            {"envelope": name, "original_budget_krw": 20000 if i == 0 else 0 if i in (1, 6) else 200000,
             "planned_saving_krw": 5000 if i == 0 else None}
            for i, name in enumerate(ENVELOPES)
        ],
    }


async def create_plan(client: httpx2.AsyncClient, clock: Clock) -> dict[str, object]:
    clock.set("2026-08-31T18:00:00")
    response = await client.post(BUDGETS, json=plan_body(), headers={"Idempotency-Key": "plan"})
    assert response.status_code == 200, response.text
    clock.set("2026-09-09T18:00:00")
    return response.json()


async def month_forecast(client: httpx2.AsyncClient, *, question: str = "이번 달 말까지 예측") -> dict:
    original = fixture()
    raw = original.transactions[0].root
    history = [JsonDocument({
        **raw, "transaction_id": f"history-{i}", "transaction_date": "2026-09-02",
        "subcategory": label, "amount_krw": (i + 1) * 10000 if i < 6 else 0,
    }) for i, label in enumerate(LABELS)]
    initial = original.model_copy(update={
        "transactions": (*original.transactions, *history),
    })
    initialized = await client.post(
        "/v1/twin", json=initial.model_dump(mode="json"), headers={"Idempotency-Key": "init"},
    )
    assert initialized.status_code == 200, initialized.text
    session = await client.post("/v1/sessions", json={}, headers={"Idempotency-Key": "session"})
    response = await client.post(
        f"/v1/sessions/{session.json()['id']}/messages",
        json={"question": question, "analysis": {"mode": "forecast", "paths": 20}},
        headers={"Idempotency-Key": "forecast"},
    )
    assert response.status_code == 200, response.text
    return response.json()


def registration_body(coaching_id: str, plan_id: object = None) -> dict[str, object]:
    return {
        "coaching_id": coaching_id, "data_origin": "backend_attested_real",
        "source_reference": "synthetic-month-registration-attestation",
        "monthly": {"budget_plan_id": plan_id, "history_coverage_start": "2026-09-01",
                    "history_coverage_end": "2026-09-09", "history_complete": True,
                    "source_reference": "synthetic-complete-history-attestation"},
    }


async def register_month(
    client: httpx2.AsyncClient, coaching_id: str, plan_id: object = None,
) -> httpx2.Response:
    return await client.post(
        BASE, json=registration_body(coaching_id, plan_id), headers={"Idempotency-Key": "register"},
    )


async def add_event(client: httpx2.AsyncClient, revision: int, **changes: str | int) -> None:
    raw = fixture().transactions[0].root
    response = await client.post(
        "/v1/events", headers={"Idempotency-Key": f"event-{revision}"},
        json={"expected_revision": revision, "event": {
            "type": "transaction", "event_id": f"event-{revision}", "user_id": "demo",
            "transaction": {**raw, "transaction_id": f"future-{revision}",
                            "transaction_date": "2026-09-15", **changes},
        }},
    )
    assert response.status_code == 200, response.text


async def month_outcomes(client: httpx2.AsyncClient, clock: Clock) -> None:
    clock.set("2026-10-01T00:01:00")
    for i, label in enumerate(LABELS):
        await add_event(client, i, subcategory=label, amount_krw=(i + 1) * 20000 if i < 6 else 0)
    await add_event(client, 7, subcategory="점심", amount_krw=3000, exclude_tag="DUTCH")
    await add_event(client, 8, subcategory="월세", amount_krw=500000)
    await add_event(client, 9, subcategory="점심", amount_krw=8000, status="CANCELED")
    await add_event(client, 10, transaction_type="CARD_SETTLEMENT", amount_krw=20000,
                    transaction_date="2026-09-30")


async def settle_month(client: httpx2.AsyncClient, registration_id: str) -> httpx2.Response:
    return await client.post(
        BASE + f"/{registration_id}/settlement", headers={"Idempotency-Key": "settle"},
        json={"coverage_start": "2026-09-01", "coverage_end": "2026-09-30", "complete": True,
              "source_reference": "synthetic-full-month-attestation"},
    )
