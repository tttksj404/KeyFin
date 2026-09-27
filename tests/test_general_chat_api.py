# ruff: noqa: INP001
"""General concepts do not depend on a forecast, Twin, or an earlier notification."""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx2
import pytest
from test_api import OTHER, TOKEN, TestModel, setup

from coaching_service.finance_knowledge import selected_finance_wording
from coaching_service.llm_contract import EvidenceInput, Mode, Routing, Wording
from coaching_service.schemas import Session

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class ConceptModel(TestModel):
    async def route(self, evidence: EvidenceInput) -> Routing:
        self.routes += 1
        return Routing(mode="finance", source="llm")

    async def write(self, evidence: EvidenceInput) -> Wording:
        self.writes += 1
        assert evidence.purpose == "finance"
        assert "numeric_result" not in evidence.facts_json
        return selected_finance_wording(
            '{"status":"answered","fact_ids":["deposits"]}', "injected-test-model"
        )


@pytest.mark.anyio
async def test_concept_without_twin_persists_and_retries_without_regeneration(tmp_path: Path) -> None:
    model = ConceptModel()
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=setup(tmp_path / "concept.sqlite3", model)),
        base_url="http://test",
        headers={"Authorization": "Bearer " + TOKEN},
    ) as client:
        body = {"question": "1년 만기 예금과 적금의 차이가 뭐야?"}
        request_headers = {"Idempotency-Key": "concept"}
        result = await client.post("/v1/finance/questions", json=body, headers=request_headers)
        assert result.status_code == 200, result.text
        answer = result.json()
        assert answer["answer_type"] == "finance_education"
        assert answer["status"] == "answered"
        assert "정기예금" in answer["text"]
        assert "정기적금" in answer["text"]
        assert "receipt" not in answer
        assert (await client.get("/v1/answers/" + answer["id"])).json() == answer
        assert (
            await client.post("/v1/finance/questions", json=body, headers=request_headers)
        ).json() == answer
        assert model.writes == 1
        assert model.routes == 0
        conflict = await client.post(
            "/v1/finance/questions", json={"question": "복리는?"}, headers=request_headers
        )
        assert conflict.status_code == 409
        isolated = await client.get(
            "/v1/answers/" + answer["id"], headers={"Authorization": "Bearer " + OTHER}
        )
        assert isolated.status_code == 404


@pytest.mark.anyio
async def test_empty_session_avoids_maturity_as_forecast_and_survives_restart(tmp_path: Path) -> None:
    database = tmp_path / "chat.sqlite3"
    model = ConceptModel()
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=setup(database, model)),
        base_url="http://test",
        headers={"Authorization": "Bearer " + TOKEN},
    ) as client:
        session = await client.post("/v1/sessions", json={}, headers={"Idempotency-Key": "session"})
        assert session.status_code == 200, session.text
        path = "/v1/sessions/" + session.json()["id"]
        result = await client.post(
            path + "/messages",
            json={"question": "1년 만기 예금과 적금 차이가 뭐야?"},
            headers={"Idempotency-Key": "turn"},
        )
        assert result.status_code == 200, result.text
        answer = result.json()
        assert answer["status"] == "answered"
        history = (await client.get(path)).json()
        assert len(history["messages"]) == 2
        assert history["messages"][-1]["content"] == answer["text"]
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=setup(database, model)),
        base_url="http://test",
        headers={"Authorization": "Bearer " + TOKEN},
    ) as restarted:
        assert (await restarted.get(path)).json() == history
        assert (await restarted.get("/v1/answers/" + answer["id"])).json() == answer
    assert model.routes == 1
    assert model.writes == 1


@pytest.mark.anyio
async def test_personal_forecast_without_twin_returns_missing_data_not_fake_balance(tmp_path: Path) -> None:
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=setup(tmp_path / "missing.sqlite3", TestModel())),
        base_url="http://test",
        headers={"Authorization": "Bearer " + TOKEN},
    ) as client:
        session = (await client.post("/v1/sessions", json={}, headers={"Idempotency-Key": "session"})).json()
        response = await client.post(
            "/v1/sessions/" + session["id"] + "/messages",
            json={"question": "앞으로 7일 잔액 예측해줘"},
            headers={"Idempotency-Key": "turn"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "needs_data"
        assert response.json()["fallback_reason"] == "twin_not_connected"
        assert "numeric_result" not in response.text


class IntentModel(TestModel):
    def __init__(self, mode: Mode) -> None:
        super().__init__()
        self.mode: Mode = mode

    async def route(self, evidence: EvidenceInput) -> Routing:
        self.routes += 1
        return Routing(mode=self.mode, source="llm")


@pytest.mark.anyio
async def test_non_financial_question_does_not_request_a_twin(tmp_path: Path) -> None:
    model = IntentModel("other")
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=setup(tmp_path / "scope.sqlite3", model)),
        base_url="http://test",
        headers={"Authorization": "Bearer " + TOKEN},
    ) as client:
        session = (await client.post("/v1/sessions", json={}, headers={"Idempotency-Key": "session"})).json()
        path = "/v1/sessions/" + session["id"]
        response = await client.post(
            path + "/messages", json={"question": "오늘 날씨 어때?"}, headers={"Idempotency-Key": "turn"}
        )
        assert response.status_code == 200
        answer = response.json()
        assert answer["status"] == "out_of_scope"
        assert answer["answer_type"] == "scope_response"
        assert (await client.get("/v1/answers/" + answer["id"])).json() == answer
        assert (await client.get(path)).json()["messages"][-1]["content"] == answer["text"]
        assert model.writes == 0


class FailedRouteModel(TestModel):
    async def route(self, evidence: EvidenceInput) -> Routing:
        return Routing(mode="review", source="template", fallback_reason="deadline_exceeded")


@pytest.mark.anyio
async def test_failed_intent_without_twin_preserves_actual_failure(tmp_path: Path) -> None:
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=setup(tmp_path / "failure.sqlite3", FailedRouteModel())),
        base_url="http://test",
        headers={"Authorization": "Bearer " + TOKEN},
    ) as client:
        session = (await client.post("/v1/sessions", json={}, headers={"Idempotency-Key": "session"})).json()
        result = await client.post(
            "/v1/sessions/" + session["id"] + "/messages",
            json={"question": "복리가 뭐야?"},
            headers={"Idempotency-Key": "turn"},
        )
        assert result.status_code == 200
        answer = result.json()
        assert answer["status"] == "unavailable"
        assert answer["fallback_reason"] == "deadline_exceeded"
        assert answer["evidence"]["routing"]["source"] == "template"
        assert (await client.get("/v1/answers/" + answer["id"])).json() == answer


@pytest.mark.anyio
@pytest.mark.parametrize("mode", ["history", "finance", "personal", "other"])
async def test_future_period_is_not_silently_ignored_by_non_forecast_intents(
    tmp_path: Path, mode: Mode
) -> None:
    model = IntentModel(mode)
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=setup(tmp_path / "period.sqlite3", model)),
        base_url="http://test",
        headers={"Authorization": "Bearer " + TOKEN},
    ) as client:
        session = (await client.post("/v1/sessions", json={}, headers={"Idempotency-Key": "session"})).json()
        path = "/v1/sessions/" + session["id"]
        response = await client.post(
            path + "/messages",
            json={"question": "현재까지 소비 알려줘", "period": {"kind": "rolling_days", "days": 7}},
            headers={"Idempotency-Key": "turn"},
        )
        # A future period on a non-forecast intent is not silently ignored: instead of a
        # 503-inducing 4xx it now returns a 200 needs_clarification turn asking the user
        # to restate the period (a recorded turn, still without any model write).
        assert response.status_code == 200, response.text
        answer = response.json()
        assert answer["answer_type"] == "period_review"
        assert answer["status"] == "needs_clarification"
        assert answer["fallback_reason"] == "period_not_supported_for_intent"
        assert len(Session.model_validate_json((await client.get(path)).content).messages) == 2
        assert model.writes == 0


@pytest.mark.anyio
async def test_personal_question_routes_without_inventing_missing_money(tmp_path: Path) -> None:
    model = IntentModel("personal")
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=setup(tmp_path / "personal.sqlite3", model)),
        base_url="http://test", headers={"Authorization": "Bearer " + TOKEN},
    ) as client:
        session = (await client.post("/v1/sessions", json={}, headers={"Idempotency-Key": "session"})).json()
        path = "/v1/sessions/" + session["id"]
        answer = await client.post(
            path + "/messages", json={"question": "내 보험료 얼마야?"}, headers={"Idempotency-Key": "turn"},
        )
        assert answer.status_code == 200
        payload = answer.json()
        assert payload["answer_type"] == "personal_context"
        assert payload["status"] == "needs_data"
        assert payload["evidence"]["routing"]["mode"] == "personal"
        assert payload["evidence"]["routing"]["source"] == "llm"
        assert payload["evidence"]["total_krw"] is None
        assert (await client.get("/v1/answers/" + payload["id"])).json() == payload
        assert (await client.get(path)).json()["messages"][-1]["content"] == payload["text"]
        assert model.writes == 0
