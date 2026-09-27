# ruff: noqa: INP001
"""사용자 지정 예산 시작일: 기간 계산·차트 힌트·계약·영속·경계값을 검증한다.

날짜 기대값은 모두 손으로 지정한 달력 오라클이며 FDT·AI가 정하지 않는다.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Final

import httpx2
import pytest
from pydantic import SecretStr, ValidationError

from coaching_service.api import create_app
from coaching_service.chart_contract import budget_period
from coaching_service.dialogue import forecast_chart_hint
from coaching_service.errors import ServiceError
from coaching_service.period_request import turn_period
from coaching_service.periods import MonthEnd, RollingDays, budget_cycle, resolve_period
from coaching_service.schemas import Bootstrap, BudgetConfig, ChartHint, JsonDocument, Session
from coaching_service.settings import Client, Settings
from tests.test_api import TestModel
from tests.test_engine import fixture

if TYPE_CHECKING:
    from pathlib import Path

TOKEN: Final = "test-only-budget-start-day-token-000000000000"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


# --- 1. budget_start_day=1 은 기존 달력 월과 정확히 동일하다(회귀 핀) ---


@pytest.mark.parametrize(
    ("reference", "start", "end"),
    [
        ("2026-09-20", "2026-09-01", "2026-09-30"),
        ("2027-02-15", "2027-02-01", "2027-02-28"),
        ("2028-02-15", "2028-02-01", "2028-02-29"),
        ("2026-12-20", "2026-12-01", "2026-12-31"),
        ("2026-01-01", "2026-01-01", "2026-01-31"),
    ],
)
def test_default_start_day_matches_calendar_month(reference: str, start: str, end: str) -> None:
    ref = date.fromisoformat(reference)
    assert budget_cycle(ref) == (date.fromisoformat(start), date.fromisoformat(end))
    # resolve_period 도 기본값에서 달력 월과 같은 예산 경계를 남긴다.
    period = resolve_period(ref, MonthEnd(), "request")
    assert period.budget_month_start == date.fromisoformat(start)
    assert period.budget_month_end == date.fromisoformat(end)


# --- 2. 설정 시작일(예: 15일) 기준으로 주기가 잡힌다 ---


def test_start_day_15_on_or_after_start_uses_current_cycle() -> None:
    # 기준일이 시작일 당일/이후이면 이번 주기: 09-15~10-14.
    assert budget_cycle(date(2026, 9, 20), 15) == (date(2026, 9, 15), date(2026, 10, 14))
    assert budget_cycle(date(2026, 9, 15), 15) == (date(2026, 9, 15), date(2026, 10, 14))


def test_start_day_15_before_start_uses_previous_cycle() -> None:
    # 기준일이 시작일 이전이면 지난 주기: 08-15~09-14.
    assert budget_cycle(date(2026, 9, 10), 15) == (date(2026, 8, 15), date(2026, 9, 14))


def test_previous_cycle_crosses_year_boundary() -> None:
    # 1월·시작일 이전이면 전년 12월 시작일로 넘어간다.
    assert budget_cycle(date(2027, 1, 5), 15) == (date(2026, 12, 15), date(2027, 1, 14))


# --- 3. 기준일이 이동하면 주기도 이동한다(같은 달력 월 안에서 경계를 넘음) ---


def test_period_moves_with_reference_across_start_day_boundary() -> None:
    # 같은 2026년 9월이지만 시작일(15) 경계 전/후는 서로 다른 예산 주기다.
    before = resolve_period(date(2026, 9, 10), MonthEnd(), "request", 15)
    on_after = resolve_period(date(2026, 9, 20), MonthEnd(), "request", 15)
    assert before.budget_month_start == date(2026, 8, 15)
    assert before.budget_month_end == date(2026, 9, 14)
    assert on_after.budget_month_start == date(2026, 9, 15)
    assert on_after.budget_month_end == date(2026, 10, 14)
    assert before.budget_month_start != on_after.budget_month_start


def test_month_end_window_follows_configured_start_day() -> None:
    # "이번 달"(MonthEnd) 창이 설정 시작일 주기를 따른다.
    period = resolve_period(date(2026, 9, 20), MonthEnd(), "question", 15)
    assert period.window_start == date(2026, 9, 15)
    assert period.window_end == date(2026, 10, 14)
    assert period.reference_in_window
    assert period.budget_future_coverage_complete


def test_turn_period_threads_start_day_for_this_month() -> None:
    # 턴 경로에서 "이번 달" 질문이 설정 시작일을 반영한다.
    period = turn_period(date(2026, 9, 20), "이번 달 예산 위험", None, None, 15)
    assert period.window_start == date(2026, 9, 15)
    assert period.window_end == date(2026, 10, 14)


# --- 4. 차트: chart_hint.period_start 와 budget_period 422 경계 ---


def test_forecast_chart_hint_period_start_reflects_configured_day() -> None:
    reference = date(2026, 9, 20)
    period = resolve_period(reference, RollingDays(days=7), "analysis", 15)
    forecast = JsonDocument({"mode": "forecast", "horizon_days": 7})
    hint = forecast_chart_hint(forecast, None, period, "이번 달 예측")
    assert isinstance(hint, ChartHint)
    assert hint.period_start == date(2026, 9, 15)
    # 힌트가 가리키는 주기는 기준일을 포함하는 유효 예산 주기다(422 없음).
    covered = budget_period(hint.period_start, reference)
    assert covered.period_start == date(2026, 9, 15)
    assert covered.horizon_end == date(2026, 10, 14)
    assert covered.period_start <= reference <= covered.horizon_end


def test_budget_period_accepts_inside_and_422s_outside_shifted_window() -> None:
    start = date(2026, 9, 15)
    # 이동한 창 안의 기준일은 허용.
    inside = budget_period(start, date(2026, 10, 1))
    assert (inside.period_start, inside.horizon_end) == (start, date(2026, 10, 14))
    # 창 밖(다음 주기 시작 이후)은 422로 거부하고 다른 주기로 추정하지 않는다.
    with pytest.raises(ServiceError, match="chart_reference_outside_period"):
        budget_period(start, date(2026, 10, 15))
    # 창 시작 이전(지난 주기)도 거부.
    with pytest.raises(ServiceError, match="chart_reference_outside_period"):
        budget_period(start, date(2026, 9, 14))


# --- 5. 말일 없는 달 경계(28일)와 범위 초과 값 처리 ---


def test_start_day_28_exists_every_month_including_february() -> None:
    # 28일은 2월에도 존재하므로 말일 보정 없이 정확히 잡힌다.
    assert budget_cycle(date(2027, 2, 28), 28) == (date(2027, 2, 28), date(2027, 3, 27))
    assert budget_cycle(date(2027, 2, 27), 28) == (date(2027, 1, 28), date(2027, 2, 27))
    # 윤년 2월도 동일하게 28일 시작.
    assert budget_cycle(date(2028, 2, 28), 28) == (date(2028, 2, 28), date(2028, 3, 27))


@pytest.mark.parametrize("bad", [0, 29, 31, -1])
def test_contract_rejects_out_of_range_start_day(bad: int) -> None:
    # 계약에서 1~28 밖 값은 거부한다(엔진이 임의 보정하지 않는다).
    with pytest.raises(ValidationError):
        BudgetConfig(start_day=bad)
    with pytest.raises(ValidationError):
        Bootstrap.model_validate({**fixture().model_dump(mode="json"), "budget_start_day": bad})


# --- 6. 부재(구버전 Twin) 기본 1일 + HTTP 왕복 스레딩 ---


def test_absent_config_defaults_to_day_one() -> None:
    assert BudgetConfig().start_day == 1
    # budget_start_day 를 생략한 부트스트랩은 값이 없다.
    assert Bootstrap.model_validate(fixture().model_dump(mode="json")).budget_start_day is None


async def _session_id(client: httpx2.AsyncClient) -> str:
    response = await client.post("/v1/sessions", json={}, headers={"Idempotency-Key": "session"})
    assert response.status_code == 200, response.text
    return Session.model_validate_json(response.content).id


@pytest.mark.anyio
async def test_turn_chart_hint_end_to_end_reflects_stored_start_day(tmp_path: Path) -> None:
    """부트스트랩에 실은 예산 시작일이 저장돼 예측 턴 chart_hint.period_start를 이동시킨다."""
    app = create_app(
        Settings(
            database=tmp_path / "budget-start-day.sqlite3",
            clients=(Client(user_id="demo", token=SecretStr(TOKEN)),),
        ),
        TestModel(),
    )
    # fixture as_of=2026-09-09, 시작일 15 → 기준일이 시작일 이전이라 지난 주기 08-15 시작.
    booted = fixture().model_copy(update={"budget_start_day": 15})
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": "Bearer " + TOKEN},
    ) as client:
        bootstrapped = await client.post(
            "/v1/twin", json=booted.model_dump(mode="json"), headers={"Idempotency-Key": "bootstrap"}
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

    assert forecast.status_code == 200, forecast.text
    hint = forecast.json()["chart_hint"]
    assert hint is not None
    assert hint["period_start"] == "2026-08-15"


@pytest.mark.anyio
async def test_turn_without_config_keeps_day_one_behavior(tmp_path: Path) -> None:
    """예산 시작일을 생략한 부트스트랩은 예전처럼 달력 월 1일 힌트를 남긴다."""
    app = create_app(
        Settings(
            database=tmp_path / "budget-default.sqlite3",
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

    assert forecast.status_code == 200, forecast.text
    assert forecast.json()["chart_hint"]["period_start"] == "2026-09-01"
