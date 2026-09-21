# ruff: noqa: INP001
"""당월 예산·미래 예측·확정 소비의 분모와 날짜를 실제 API에서 검증한다."""

from pathlib import Path

import pytest
from test_api import OTHER
from test_forecast_validation_month_support import (
    BUDGETS,
    add_event,
    create_plan,
    month_forecast,
    month_outcomes,
    register_month,
    settle_month,
)
from test_forecast_validation_support import BASE, Clock, build, client_for


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_month_compares_exact_forecast_and_independent_seven_envelope_outcomes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock, database = Clock(), tmp_path / "month.sqlite3"
    async with client_for(build(database, clock, monkeypatch)) as client:
        plan = await create_plan(client, clock)
        original = await month_forecast(client)
        response = await register_month(client, original["id"], plan["id"])
        assert response.status_code == 200, response.text
        frozen = response.json()
        assert frozen["monthly"]["budget_plan"] == plan
        assert frozen["forecast_start"] == "2026-09-10"
        assert frozen["forecast_end"] == "2026-09-30"
        predictions = {
            row["envelope"]: row for row in original["receipt"]["numeric_result"]["datasets"]["envelopes"]
        }
        for row in frozen["monthly"]["forecasts"]:
            assert row["future_prediction"] == {
                f"p{q}": predictions[row["envelope"]][f"p{q}_krw"] for q in (10, 50, 90)
            }
            assert row["month_prediction"]["p50"] == (
                row["observed_before_forecast"]["consumption_krw"] + row["future_prediction"]["p50"]
            )
        # 기준모델도 71일의 식비 1만 원에서 동일 미래 21일만 계산한다.
        assert frozen["monthly"]["forecasts"][0]["baseline_future_krw"] == pytest.approx(10000 / 71 * 21)
        assert (await register_month(client, original["id"], plan["id"])).json() == frozen
        await month_outcomes(client, clock)
        response = await settle_month(client, frozen["id"])
        assert response.status_code == 200, response.text
        settled = response.json()
        assert settled["actual_krw"] == 423000
        rows = {row["envelope"]: row for row in settled["monthly"]["comparisons"]}
        food = rows["외식"]
        assert food["future_actual"]["consumption_krw"] == 23000
        assert food["future_actual"]["budget_used_krw"] == 20000
        assert food["future_actual"]["budget_excluded_consumption_krw"] == 3000
        assert food["month_actual"]["consumption_krw"] == 33000
        assert food["month_actual"]["budget_used_krw"] == 30000
        assert food["month_actual"]["budget_excluded_consumption_krw"] == 3000
        assert food["original_budget_krw"] == 20000
        assert food["budget_usage_ratio"] == 1.5
        assert food["budget_remaining_krw"] == -10000
        assert food["budget_state"] == "over"
        assert food["planned_saving_krw"] == 5000
        assert food["future_error_krw"] == predictions["외식"]["p50_krw"] - 23000
        assert food["budget_comparison"] == {
            "forecast_target": "future_total_variable_consumption",
            "budget_target": "full_month_consumption_with_exclude_tag_NONE",
            "observed_spending_basis": "different",
            "diagnosis": "indeterminate_target_mismatch",
            "causal_attribution_established": False,
        }
        assert rows["교통비"]["month_actual"]["budget_excluded_consumption_krw"] == 0
        assert rows["교통비"]["budget_comparison"]["observed_spending_basis"] == "aligned"
        assert rows["교통비"]["budget_comparison"]["diagnosis"] == "indeterminate_causal_evidence"
        assert rows["교통비"]["budget_comparison"]["causal_attribution_established"] is False
        assert rows["교통비"]["budget_usage_ratio"] is None
        assert rows["교통비"]["budget_state"] == "zero_budget_exceeded"
        assert rows["기타"]["budget_state"] == "zero_budget_unused"
        assert rows["기타"]["month_actual"]["consumption_krw"] == 0
        assert settled["monthly"]["saving_effect_estimated"] is False
        assert (await settle_month(client, frozen["id"])).json() == settled
    # 재생성한 앱은 같은 원본 편성과 정산을 읽고 예측값을 다시 만들지 않는다.
    async with client_for(build(database, clock, monkeypatch)) as client:
        assert (await client.get(BUDGETS + f"/{plan['id']}")).json() == plan
        assert (await client.get(BASE + f"/{frozen['id']}/settlement")).json() == settled
        report = await client.post(
            "/v1/forecast-validation/metrics", json={"registration_ids": [frozen["id"]]},
        )
        assert report.status_code == 200, report.text
        envelopes = {row["envelope"]: row["values"] for row in report.json()["envelopes"]}
        assert len(envelopes) == 7
        assert envelopes["외식"]["mae_krw"] == abs(predictions["외식"]["p50_krw"] - 23000)
        assert envelopes["외식"]["wape"] == pytest.approx(envelopes["외식"]["mae_krw"] / 23000)
        assert envelopes["외식"]["baseline_mae_krw"] == pytest.approx(abs(10000 / 71 * 21 - 23000))
        assert envelopes["기타"]["wape"] is None
        assert report.json()["real_accuracy_validated"] is False
        for path in (BUDGETS + f"/{plan['id']}", BASE + f"/{frozen['id']}/settlement"):
            assert (await client.get(path, headers={"Authorization": "Bearer " + OTHER})).status_code == 404
        # 다음 달 새 거래는 평가 월의 정답을 바꾸지 않는다.
        clock.set("2026-10-02T00:01:00")
        await add_event(client, 11, transaction_date="2026-10-01", amount_krw=7000)
        refreshed = await client.post(
            "/v1/forecast-validation/metrics", json={"registration_ids": [frozen["id"]]},
        )
        before_report, after_report = report.json(), refreshed.json()
        checks = {"observed_identity", "observed_checked_at"}
        assert {k: v for k, v in after_report.items() if k not in checks} == {
            k: v for k, v in before_report.items() if k not in checks
        }
        assert after_report["observed_identity"]["revision"] == (
            before_report["observed_identity"]["revision"] + 1
        )
        assert after_report["observed_checked_at"] > before_report["observed_checked_at"]
        assert (await client.delete("/v1/me/data")).status_code == 200
        assert (await client.get(BUDGETS + f"/{plan['id']}")).status_code == 404


@pytest.mark.anyio
async def test_missing_plan_is_unknown_and_not_a_zero_budget(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = Clock()
    async with client_for(build(tmp_path / "unknown.sqlite3", clock, monkeypatch)) as client:
        original = await month_forecast(client)
        frozen = await register_month(client, original["id"])
        assert frozen.status_code == 200, frozen.text
        assert frozen.json()["monthly"]["budget_plan"] is None
        await month_outcomes(client, clock)
        response = await settle_month(client, frozen.json()["id"])
        assert response.status_code == 200, response.text
        for row in response.json()["monthly"]["comparisons"]:
            assert row["original_budget_krw"] is row["budget_usage_ratio"] is None
            assert row["planned_saving_krw"] is None
            assert row["budget_state"] == "not_registered"
            assert row["budget_comparison"]["diagnosis"] == "indeterminate_missing_budget"
            assert row["budget_comparison"]["causal_attribution_established"] is False
