from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from test_api import OTHER, TOKEN, TestModel, setup
from test_engine import fixture

from coaching_service.api import create_app
from coaching_service.settings import Client, Settings


def chart_request(*, start: str = "2026-09-01", as_of: str = "2026-09-09") -> dict:
    data = fixture().model_dump(mode="json")
    data["as_of"] = as_of
    data["snapshot"]["as_of"] = as_of
    row = data["transactions"][0]
    data["transactions"] = [row, {**row, "transaction_id": "current", "transaction_date": as_of}]
    return {"data": data, "period_start": start, "question": "예산 기간의 예상 소비를 보여줘"}


def headers(key: str, token: str = TOKEN) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Idempotency-Key": key}


@pytest.mark.parametrize("direction", ["INCOME", "TRANSFER", "EXPENSE", " EXPENSE "])
def test_incoming_transfer_cannot_be_counted_as_a_purchase(tmp_path: Path, direction: str) -> None:
    body = chart_request(start="2026-09-01", as_of="2026-09-30")
    for row in body["data"]["transactions"]:
        row["transaction_type"] = "TRANSFER_IN"
        row["direction"] = direction
    with TestClient(setup(tmp_path / "incoming.sqlite", TestModel())) as client:
        response = client.post("/v1/charts/budget-forecast", json=body, headers=headers("incoming"))
    if direction.strip() == "EXPENSE":
        assert response.status_code == 422, response.text
        assert response.json()["error"] == "inconsistent_transfer_direction"
    else:
        assert response.status_code == 200, response.text
        assert response.json()["chart"]["totalCurrent"] == 0


def test_chart_request_calls_model_and_returns_chart_contract(tmp_path: Path) -> None:
    # Given a real FDT input and a replaceable language-model boundary.
    model = TestModel()
    with TestClient(setup(tmp_path / "chart.sqlite", model)) as client:
        # When data arrives at the chart endpoint.
        response = client.post("/v1/charts/budget-forecast", json=chart_request(), headers=headers("first"))
        # Then the client receives the fixed renderer contract with source evidence.
        assert response.status_code == 200, response.text
        result = response.json()
        chart = result["chart"]
        assert chart["schema_version"] == "2.0"
        assert chart["meta"]["horizon_end"] == "2026-09-30"
        assert chart["totalCurrent"] == 10000
        assert (
            chart["totalForecast"]
            == 10000 + result["receipt"]["numeric_result"]["metrics"]["total_expense_p50_krw"]["value"]
        )
        assert chart["forecastAggregation"] == "joint_p50"
        assert chart["balance"]["forecast"][0]["p50_krw"] == 10000
        assert chart["balance"]["forecast"][-1]["p50_krw"] == chart["totalForecast"]
        assert result["wording"]["source"] == "llm"
        assert model.writes == 1
        assert model.seen[0].purpose == "chart"


def test_chart_contains_every_future_day_and_preserves_observed_consumption(tmp_path: Path) -> None:
    # Given a real ledger with repeatable purchases and an unfinished budget period.
    with TestClient(setup(tmp_path / "daily.sqlite", TestModel())) as client:
        # When the real chart endpoint is called.
        response = client.post("/v1/charts/budget-forecast", json=chart_request(), headers=headers("daily"))
        assert response.status_code == 200, response.text
        result = response.json()
        chart = result["chart"]
        daily = chart["balance"]["daily"]
        future = [row for row in daily if row["date"] > chart["meta"]["as_of"]]
        # Then every forecast date has computed category values, including genuine zero days.
        assert [row["date"] for row in future] == [
            (date(2026, 9, 10) + timedelta(days=i)).isoformat() for i in range(21)
        ]
        assert all(len(row["amounts_krw"]) == 7 for row in future)
        assert sum(sum(row["amounts_krw"]) for row in future) > 0
        assert sum(sum(row["amounts_krw"]) for row in daily if row not in future) == 10000
        assert chart["meta"]["daily_forecast_statistic"] == "empirical_path_mean"
        assert result["receipt"]["daily_forecast"]["points"] == future


@pytest.mark.parametrize(
    ("start", "as_of", "end"),
    [
        ("2028-01-31", "2028-02-20", "2028-02-28"),
        ("2028-02-01", "2028-02-20", "2028-02-29"),
        ("2026-12-16", "2026-12-20", "2027-01-15"),
    ],
)
def test_chart_calendar_matches_renderer(tmp_path: Path, start: str, as_of: str, end: str) -> None:
    # Given an anchored monthly period crossing a calendar boundary.
    with TestClient(setup(tmp_path / "chart.sqlite", TestModel())) as client:
        # When the chart is requested.
        response = client.post(
            "/v1/charts/budget-forecast",
            json=chart_request(start=start, as_of=as_of),
            headers=headers("period"),
        )
        # Then the inclusive end agrees with the chart calendar, not a fixed 30 days.
        assert response.status_code == 200, response.text
        assert response.json()["chart"]["meta"]["horizon_end"] == end
        assert (
            response.json()["receipt"]["numeric_request"]["horizon_days"]
            == (date.fromisoformat(end) - date.fromisoformat(as_of)).days
        )


def test_chart_retries_reuse_inference_and_saved_html_is_owner_bound(tmp_path: Path) -> None:
    # Given a saved chart response.
    model = TestModel()
    with TestClient(setup(tmp_path / "chart.sqlite", model)) as client:
        first = client.post("/v1/charts/budget-forecast", json=chart_request(), headers=headers("same"))
        assert first.status_code == 200, first.text
        chart_id = first.json()["id"]
        # When the request is retried and the saved visualization is retrieved.
        retry = client.post("/v1/charts/budget-forecast", json=chart_request(), headers=headers("same"))
        html = client.get(f"/v1/charts/{chart_id}/html", headers=headers("read"))
        other = client.get(f"/v1/charts/{chart_id}", headers=headers("other", OTHER))
        # Then one inference serves both requests and other owners cannot read it.
        assert retry.json() == first.json()
        assert model.writes == 1
        assert html.status_code == 200
        assert "window.KEYFIN_CASES=" in html.text
        assert html.headers["cache-control"] == "no-store"
        assert other.status_code == 404
        conflict = client.post(
            "/v1/charts/budget-forecast", json={**chart_request(), "seed": 7}, headers=headers("same")
        )
        assert conflict.status_code == 409
        assert model.writes == 1


def test_chart_rejects_period_and_owner_mismatch(tmp_path: Path) -> None:
    # Given data outside the requested period or belonging to another principal.
    with TestClient(setup(tmp_path / "chart.sqlite", TestModel())) as client:
        # When those invalid requests are submitted.
        period = client.post(
            "/v1/charts/budget-forecast", json=chart_request(start="2026-08-01"), headers=headers("bad-date")
        )
        owner = client.post(
            "/v1/charts/budget-forecast", json=chart_request(), headers=headers("bad-owner", OTHER)
        )
        # Then no misleading chart is produced.
        assert period.status_code == 422
        assert owner.status_code == 403


def test_closed_budget_period_returns_observed_chart_without_future_invention(tmp_path: Path) -> None:
    # Given an observed closing day.
    model = TestModel()
    with TestClient(setup(tmp_path / "chart.sqlite", model)) as client:
        # When a chart is requested for that completed period.
        response = client.post(
            "/v1/charts/budget-forecast", json=chart_request(as_of="2026-09-30"), headers=headers("closed")
        )
        # Then the terminal total equals observed spending, with no model call.
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["chart"]["totalForecast"] == result["chart"]["totalCurrent"] == 10000
        assert result["receipt"]["numeric_result"] is None
        assert result["receipt"]["daily_forecast"] is None
        assert result["chart"]["meta"]["daily_forecast_statistic"] is None
        assert result["wording"]["fallback_reason"] == "period_complete"
        assert model.writes == 0


def test_inline_chart_preserves_saved_twin_and_omitted_data_uses_it(tmp_path: Path) -> None:
    # Given a saved ledger with no purchases in the requested budget period.
    with TestClient(setup(tmp_path / "chart.sqlite", TestModel())) as client:
        original = fixture().model_dump(mode="json")
        created = client.post("/v1/twin", json=original, headers=headers("bootstrap"))
        assert created.status_code == 200
        before = client.get("/v1/twin", headers=headers("before")).json()
        # When a separate inline input is charted, then that input cannot replace the saved ledger.
        inline = client.post("/v1/charts/budget-forecast", json=chart_request(), headers=headers("inline"))
        assert inline.status_code == 200, inline.text
        assert inline.json()["chart"]["totalCurrent"] == 10000
        assert client.get("/v1/twin", headers=headers("after")).json() == before
        # When data is omitted, then the same owner receives a chart of the saved ledger.
        saved = client.post(
            "/v1/charts/budget-forecast", json={"period_start": "2026-09-01"}, headers=headers("saved")
        )
        assert saved.status_code == 200, saved.text
        assert saved.json()["chart"]["totalCurrent"] == 0
        assert saved.json()["receipt"]["identity"]["input_digest"] == created.json()["input_digest"]


def test_unconfigured_model_returns_honest_template_source(tmp_path: Path) -> None:
    # Given a service without an inference endpoint.
    settings = Settings(
        database=tmp_path / "chart.sqlite", clients=(Client(user_id="demo", token=SecretStr(TOKEN)),)
    )
    with TestClient(create_app(settings)) as client:
        # When numeric forecasting succeeds, then the chart remains usable with explicit fallback provenance.
        response = client.post(
            "/v1/charts/budget-forecast", json=chart_request(), headers=headers("fallback")
        )
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["receipt"]["numeric_result"] is not None
        assert result["wording"]["source"] == "template"
        assert result["wording"]["fallback_reason"] is not None
        assert "AI 문장 미채택" in result["chart"]["meta"]["source_label"]
        assert "AI 추론 설명" not in result["chart"]["meta"]["source_label"]
