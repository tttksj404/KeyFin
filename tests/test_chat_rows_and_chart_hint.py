# ruff: noqa: INP001
"""ChatAnswer의 1급 소비 행과 예측 대화의 budget-forecast 차트 힌트를 검증한다."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Final

import httpx2
import pytest
from pydantic import SecretStr

from coaching_service.api import create_app
from coaching_service.chart_contract import budget_period
from coaching_service.chat_answers import ChatAnswer, out_of_scope_answer
from coaching_service.dialogue import chart_purchase_hint, forecast_chart_hint
from coaching_service.fast_routes import NaturalPurchase
from coaching_service.periods import RollingDays, resolve_period
from coaching_service.schemas import ChartHint, JsonDocument, Session
from coaching_service.settings import Client, Settings
from coaching_service.spending_history import SpendingRow
from tests.test_api import TestModel
from tests.test_engine import fixture
from tests.test_spending_history import raw_transactions

if TYPE_CHECKING:
    from pathlib import Path

TOKEN: Final = "test-only-chat-rows-chart-hint-token-00000000"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


async def _session_id(client: httpx2.AsyncClient) -> str:
    response = await client.post("/v1/sessions", json={}, headers={"Idempotency-Key": "session"})
    assert response.status_code == 200, response.text
    return Session.model_validate_json(response.content).id


# --- Feature #2: spending rows promoted to first-class ChatAnswer fields ---


def test_non_spending_answers_keep_empty_rows_and_null_total() -> None:
    # Given / When: 소비 조회가 아닌 답변 타입.
    answer = out_of_scope_answer()
    # Then: 새 필드는 기본값을 유지한다.
    assert answer.rows == ()
    assert answer.total_krw is None


def test_chat_answer_with_rows_round_trips_through_json() -> None:
    # Given: 소비 행을 담은 ChatAnswer.
    answer = ChatAnswer(
        id="a",
        answer_type="spending_history",
        status="answered",
        text="합계입니다.",
        wording_source="engine",
        model="not_called",
        evidence=JsonDocument({}),
        rows=(SpendingRow(envelope="외식", total_krw=12000, count=1),),
        total_krw=12000,
        created_at=1.0,
    )
    # When: JSON 왕복.
    restored = ChatAnswer.model_validate_json(answer.model_dump_json())
    # Then: 값이 보존된다.
    assert restored == answer
    assert restored.rows[0].total_krw == 12000
    assert restored.total_krw == 12000


@pytest.mark.anyio
async def test_spending_turn_exposes_rows_matching_evidence(tmp_path: Path) -> None:
    """소비 조회 응답은 evidence.spending와 동일한 행/총액을 1급 필드로도 노출한다."""
    app = create_app(
        Settings(
            database=tmp_path / "spending-rows.sqlite3",
            clients=(Client(user_id="demo", token=SecretStr(TOKEN)),),
        ),
        TestModel(),
    )
    booted = fixture().model_copy(
        update={"as_of": date(2028, 3, 15), "transactions": raw_transactions(), "snapshot": None}
    )
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": "Bearer " + TOKEN},
    ) as client:
        bootstrapped = await client.post(
            "/v1/twin", json=booted.model_dump(mode="json"), headers={"Idempotency-Key": "bootstrap"}
        )
        assert bootstrapped.status_code == 200, bootstrapped.text
        response = await client.post(
            f"/v1/sessions/{await _session_id(client)}/messages",
            json={"question": "현재까지 소비 알려줘"},
            headers={"Idempotency-Key": "spending"},
        )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["answer_type"] == "spending_history"
    assert payload["status"] == "answered"
    nested = payload["evidence"]["spending"]
    # 1급 필드가 중첩 evidence와 정확히 일치한다.
    assert payload["rows"] == nested["rows"]
    assert payload["total_krw"] == nested["total_krw"]
    assert payload["rows"]  # 실제로 집계된 봉투 행이 있다.
    # text는 사람 문장 그대로다(변경 없음).
    assert payload["text"] == nested["text"]


# --- Feature #3: forecast/purchase turn returns a chart_hint ---


def test_forecast_chart_hint_is_none_for_non_forecast() -> None:
    # Given: risk 수치 요청, 구매 없음.
    period = resolve_period(date(2026, 9, 9), RollingDays(days=7), "analysis")
    risk = JsonDocument({"mode": "risk", "horizon_days": 7})
    # When / Then: 예측도 구매도 아니면 힌트를 만들지 않는다.
    assert forecast_chart_hint(risk, None, period, "위험 알려줘") is None
    assert forecast_chart_hint(None, None, period, "위험 알려줘") is None


def test_forecast_chart_hint_covers_reference_budget_period() -> None:
    # Given: 2026-09-09 기준 7일 예측.
    reference = date(2026, 9, 9)
    period = resolve_period(reference, RollingDays(days=7), "analysis")
    forecast = JsonDocument({"mode": "forecast", "horizon_days": 7})
    # When: 예측 대화의 힌트를 만든다.
    hint = forecast_chart_hint(forecast, None, period, "이번 달 예측")
    # Then: 기준 예산 월의 1일이며, 그 기준일을 포함하는 유효한 예산 주기다.
    assert isinstance(hint, ChartHint)
    assert hint.period_start == date(2026, 9, 1)
    assert hint.endpoint == "/v1/charts/budget-forecast"
    assert hint.purchase is None
    covered = budget_period(hint.period_start, reference)  # 422를 던지지 않으면 유효.
    assert covered.period_start <= reference <= covered.horizon_end


def test_purchase_hint_carries_envelope_amount_date_within_budget_window() -> None:
    # Given a resolved future purchase inside the reference budget month.
    period = resolve_period(date(2026, 9, 9), RollingDays(days=7), "analysis")
    change = JsonDocument(
        {"kind": "expense", "date": "2026-09-20", "amount_krw": 50000, "envelope": "외식", "account_id": "a"}
    )
    # When the chart purchase hint is built.
    hint = chart_purchase_hint(change, period)
    # Then it carries envelope/amount/date the app can forward as the chart request purchase block.
    assert hint is not None
    assert (hint.envelope, hint.amount_krw, hint.on_date) == ("외식", 50000, date(2026, 9, 20))
    # And a same-day (non-future) purchase is dropped so the follow-up chart never 422s.
    today = JsonDocument({"date": "2026-09-09", "amount_krw": 50000, "envelope": "외식"})
    assert chart_purchase_hint(today, period) is None


def test_purchase_review_chart_hint_populates_purchase_slot() -> None:
    # Given a parsed purchase turn and its resolved chart purchase hint.
    period = resolve_period(date(2026, 9, 9), RollingDays(days=7), "analysis")
    change = JsonDocument({"date": "2026-09-20", "amount_krw": 50000, "envelope": "외식"})
    purchase = NaturalPurchase(
        amount_krw=50000,
        envelope="외식",
        date_token="2026-09-20",  # noqa: S106 - a calendar token, not a credential.
        payment_hint="cash",
        card_payment_date=None,
    )
    # When the purchase-review turn builds its chart hint.
    resolved = chart_purchase_hint(change, period)
    hint = forecast_chart_hint(None, purchase, period, "이 신발 사면 어때", resolved)
    # Then the hint carries the same budget month and a populated purchase slot.
    assert isinstance(hint, ChartHint)
    assert hint.period_start == date(2026, 9, 1)
    assert hint.purchase is not None
    assert hint.purchase.on_date == date(2026, 9, 20)


@pytest.mark.anyio
async def test_forecast_turn_returns_chart_hint_and_risk_turn_does_not(tmp_path: Path) -> None:
    """예측 대화는 chart_hint를, 위험 대화는 None을 반환하고 재시도는 동일하다."""
    app = create_app(
        Settings(
            database=tmp_path / "chart-hint.sqlite3",
            clients=(Client(user_id="demo", token=SecretStr(TOKEN)),),
        ),
        TestModel(),
    )
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": "Bearer " + TOKEN},
    ) as client:
        bootstrapped = await client.post(
            "/v1/twin", json=fixture().model_dump(mode="json"), headers={"Idempotency-Key": "bootstrap"}
        )
        assert bootstrapped.status_code == 200, bootstrapped.text
        session = await _session_id(client)
        forecast = await client.post(
            f"/v1/sessions/{session}/messages",
            json={
                "question": "앞으로 7일 잔액 예측해줘",
                "analysis": {"mode": "forecast", "horizon_days": 7, "paths": 20, "seed": 42},
            },
            headers={"Idempotency-Key": "forecast"},
        )
        retry = await client.post(
            f"/v1/sessions/{session}/messages",
            json={
                "question": "앞으로 7일 잔액 예측해줘",
                "analysis": {"mode": "forecast", "horizon_days": 7, "paths": 20, "seed": 42},
            },
            headers={"Idempotency-Key": "forecast"},
        )
        risk = await client.post(
            f"/v1/sessions/{session}/messages",
            json={"question": "이번 달 위험을 알려줘"},
            headers={"Idempotency-Key": "risk"},
        )

    assert forecast.status_code == 200, forecast.text
    hint = forecast.json()["chart_hint"]
    assert hint is not None
    assert hint["endpoint"] == "/v1/charts/budget-forecast"
    assert hint["period_start"] == "2026-09-01"
    assert hint["purchase"] is None
    # 멱등 재시도는 동일한 힌트를 돌려준다.
    assert retry.status_code == 200, retry.text
    assert retry.json()["chart_hint"] == hint
    # 예측이 아닌 위험 대화는 힌트를 남기지 않는다.
    assert risk.status_code == 200, risk.text
    assert risk.json()["chart_hint"] is None
