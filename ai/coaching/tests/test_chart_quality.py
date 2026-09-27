import json
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from test_api import TOKEN, TestModel, setup
from test_chart_api import chart_request, headers

from coaching_service.api import create_app
from coaching_service.settings import Client, Settings


def test_short_history_reaches_chart_and_required_model_fact(tmp_path: Path) -> None:
    # Given just one observed day, not an independently verified complete history.
    body = chart_request()
    body["data"]["transactions"] = body["data"]["transactions"][-1:]
    model = TestModel()
    with TestClient(setup(tmp_path / "short.sqlite", model)) as client:
        result = client.post("/v1/charts/budget-forecast", json=body, headers=headers("short")).json()
    # Then the upstream warning and its actual day count survive every explanation boundary.
    raw = result["receipt"]["numeric_result"]
    assert "SHORT_HISTORY" in [row["code"] for row in raw["warnings"]]
    quality = result["chart"]["meta"]["quality"]
    assert quality["historical_days"] == raw["model"]["historical_days"] == 1
    assert quality["warning_codes"] == [row["code"] for row in raw["warnings"]]
    assert "과거 이력 1일" in " ".join(quality["notices"])
    facts = json.loads(model.seen[0].facts_json)
    assert "과거 이력 1일" in next(row["text"] for row in facts["facts"] if row["id"] == "total")


def test_days_before_first_input_are_missing_observations_not_zero_spending(tmp_path: Path) -> None:
    # Given a budget starting on September 1 but inputs beginning September 9.
    body = chart_request()
    body["data"]["transactions"] = body["data"]["transactions"][-1:]
    model = TestModel()
    with TestClient(setup(tmp_path / "coverage.sqlite", model)) as client:
        response = client.post("/v1/charts/budget-forecast", json=body, headers=headers("coverage"))
    assert response.status_code == 200
    chart = response.json()["chart"]
    # Then the chart must not turn eight unobserved dates into actual zero-won records.
    assert chart["balance"]["history"] == [{"date": "2026-09-09", "value_krw": 10000}]
    assert chart["balance"]["daily"][0]["date"] == "2026-09-09"
    assert chart["meta"]["observation_start"] == "2026-09-09"
    assert "미관측" in " ".join(chart["meta"]["quality"]["notices"])


def test_unallocated_amount_is_explained_instead_of_disappearing_from_categories(tmp_path: Path) -> None:
    # Given a 10,000-won pending expense and no classified current expenses.
    body = chart_request()
    for row in body["data"]["transactions"]:
        row["confirm_status"] = "PENDING"
    model = TestModel()
    with TestClient(setup(tmp_path / "pending.sqlite", model)) as client:
        result = client.post("/v1/charts/budget-forecast", json=body, headers=headers("pending")).json()
    chart = result["chart"]
    assert chart["totalCurrent"] == chart["unallocatedCurrent"] == 10000
    assert sum(row["current"] for row in chart["categories"]) == 0
    notice = " ".join(chart["meta"]["quality"]["notices"])
    assert "미분류 소비 10,000원" in notice
    assert "전체 금액에 포함" in notice
    assert "일별 막대에서 제외" in notice
    facts = json.loads(model.seen[0].facts_json)
    assert "미분류 소비 10,000원" in next(row["text"] for row in facts["facts"] if row["id"] == "total")


def test_completed_period_keeps_unallocated_notice_without_calling_model(tmp_path: Path) -> None:
    body = chart_request(as_of="2026-09-30")
    body["data"]["transactions"][-1]["confirm_status"] = "PENDING"
    model = TestModel()
    with TestClient(setup(tmp_path / "closed.sqlite", model)) as client:
        result = client.post("/v1/charts/budget-forecast", json=body, headers=headers("closed")).json()
    assert model.writes == 0
    assert result["receipt"]["numeric_result"] is None
    assert "미분류 소비 10,000원" in " ".join(result["chart"]["meta"]["quality"]["notices"])
    assert "미분류 소비 10,000원" in result["wording"]["text"]


def test_completed_period_preserves_model_audit_for_unscheduled_fixed_cost(tmp_path: Path) -> None:
    body = chart_request(as_of="2026-09-30")
    body["data"]["transactions"].append(
        {
            **body["data"]["transactions"][-1],
            "transaction_id": "unscheduled-rent",
            "subcategory": "월세",
            "amount_krw": 70000,
        }
    )
    model = TestModel()
    with TestClient(setup(tmp_path / "fixed.sqlite", model)) as client:
        response = client.post("/v1/charts/budget-forecast", json=body, headers=headers("fixed"))
    assert response.status_code == 200
    result = response.json()
    assert model.writes == 0
    assert result["chart"]["totalCurrent"] == 10000
    assert "FIXED_UNSCHEDULED" in [row["code"] for row in result["receipt"]["observation_audit"]["warnings"]]
    assert "FIXED_UNSCHEDULED" in result["chart"]["meta"]["quality"]["warning_codes"]
    assert "고정비는 이 소비 차트에서 제외" in " ".join(result["chart"]["meta"]["quality"]["notices"])


@pytest.mark.parametrize("as_of", ["2026-09-09", "2026-09-30"])
def test_observed_reimbursement_warning_reaches_open_and_completed_charts(tmp_path: Path, as_of: str) -> None:
    body = chart_request(as_of=as_of)
    body["data"]["transactions"].append(
        {
            **body["data"]["transactions"][-1],
            "transaction_id": "reimbursement",
            "transaction_type": "DEPOSIT",
            "subcategory": "모임 정산",
        }
    )
    model = TestModel()
    with TestClient(setup(tmp_path / "reimbursement.sqlite", model)) as client:
        response = client.post("/v1/charts/budget-forecast", json=body, headers=headers("reimbursement"))
    assert response.status_code == 200
    result = response.json()
    assert result["chart"]["totalCurrent"] == 10000
    assert "REIMBURSEMENT_UNMATCHED" in result["chart"]["meta"]["quality"]["warning_codes"]
    if as_of == "2026-09-30":
        assert model.writes == 0
        assert "정산 입금" in result["wording"]["text"]
        assert "차감하지" in result["wording"]["text"]
        assert result["receipt"]["observation_audit"] is not None
    else:
        facts = json.loads(model.seen[0].facts_json)
        assert "정산 입금" in next(row["text"] for row in facts["facts"] if row["id"] == "total")
        assert facts["context_notes"] == result["chart"]["meta"]["quality"]["notices"]


def test_old_stored_chart_json_and_retry_do_not_gain_fabricated_quality_fields(tmp_path: Path) -> None:
    # Given the prior stored contract, with no quality or observation-start fields.
    database = tmp_path / "legacy.sqlite"
    model = TestModel()
    with TestClient(setup(database, model)) as client:
        body = chart_request()
        result = client.post("/v1/charts/budget-forecast", json=body, headers=headers("legacy")).json()
        result["chart"]["meta"].pop("quality", None)
        result["chart"]["meta"].pop("observation_start", None)
        result["receipt"].pop("observation_audit", None)
        payload = json.dumps(result, ensure_ascii=False, separators=(",", ":"))
        with sqlite3.connect(database) as conn:
            conn.execute("UPDATE items SET payload=? WHERE key=?", (payload, "chart/" + result["id"]))
            conn.execute("UPDATE requests SET result=? WHERE key=?", (payload, "legacy"))
        # When read or retried, then the saved JSON remains exactly the saved version.
        saved = client.get("/v1/charts/" + result["id"], headers=headers("read"))
        retry = client.post("/v1/charts/budget-forecast", json=body, headers=headers("legacy"))
        assert saved.content == payload.encode()
        assert retry.content == payload.encode()
        assert model.writes == 1


@pytest.mark.parametrize("amount", [10000, 10**12])
def test_combined_limits_keep_a_bounded_fallback_and_preserve_future_pending_amount(
    tmp_path: Path, amount: int
) -> None:
    # Given simultaneous incomplete history, pending-only consumption and sparse coverage.
    body = chart_request()
    body["data"]["transactions"] = body["data"]["transactions"][-1:]
    body["data"]["transactions"][0]["confirm_status"] = "PENDING"
    body["data"]["transactions"][0]["amount_krw"] = amount
    settings = Settings(
        database=tmp_path / "combined.sqlite",
        clients=(Client(user_id="demo", token=SecretStr(TOKEN)),),
    )
    with TestClient(create_app(settings), raise_server_exceptions=False) as client:
        result = client.post("/v1/charts/budget-forecast", json=body, headers=headers("combined"))
    assert result.status_code == 200, result.text
    data = result.json()
    quality = data["chart"]["meta"]["quality"]
    # All paths repeat the only observed pending amount across the 21 future days.
    assert quality["pending_forecast_p50_krw"] == 21 * amount
    assert data["chart"]["totalForecast"] == 22 * amount
    assert sum(row["forecast"] for row in data["chart"]["categories"]) == 0
    assert f"{21 * amount:,}원" in " ".join(quality["notices"])
    assert "차이로 계산한 값이 아닙니다" in " ".join(quality["notices"])
    assert "P50" not in " ".join(quality["notices"])
    assert data["wording"]["source"] == "template"
    assert len(data["wording"]["text"]) <= 400
