"""Candidate routing keeps explicit periods and numeric FDT requests authoritative."""

# ruff: noqa: INP001
from pathlib import Path
from typing import Literal

import httpx2
import pytest
from pydantic import SecretStr

from coaching_service.api import create_app
from coaching_service.dialogue_decision import decide_dialogue
from coaching_service.finance_knowledge import finance_evidence
from coaching_service.llm import OpenAICompatibleCoachModel
from coaching_service.llm_contract import EvidenceInput, Mode, ModelConfig
from coaching_service.schemas import Coaching, JsonDocument, Session
from coaching_service.settings import Client, Settings
from tests.test_dialogue_decision import TOKEN, object_at
from tests.test_engine import fixture
from tests.test_llm import completion


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
@pytest.mark.parametrize("mode", ["other", "personal", "history", "forecast", "risk", "review"])
async def test_combined_nonfinance_route_does_not_create_finance_answer(mode: Mode) -> None:
    # Given a valid combined-model decision which defers to nonfinance tools.
    calls = 0

    def respond(_request: httpx2.Request) -> httpx2.Response:
        nonlocal calls
        calls += 1
        selection = JsonDocument.model_validate({"mode": mode, "finance": None})
        return httpx2.Response(200, content=completion(selection.model_dump_json()))

    config = ModelConfig(endpoint_url="http://model.test", token_preflight=False, combined_dialogue=True)
    async with httpx2.AsyncClient(transport=httpx2.MockTransport(respond)) as client:
        model = OpenAICompatibleCoachModel(config, client=client)
        # When the real adapter parses that decision.
        answer = await decide_dialogue(
            model, EvidenceInput(question="자료 확인", facts_json="{}"), finance_evidence("자료 확인"),
        )
    # Then the intended route survives with no synthesized finance payload or retry.
    assert answer.routing.mode == mode
    assert answer.routing.source == "llm"
    assert answer.finance is None
    assert calls == 1


@pytest.mark.anyio
@pytest.mark.parametrize("mode", ["finance", "forecast", "risk"])
async def test_combined_candidate_keeps_api_period_and_explicit_numeric_contracts(
    tmp_path: Path, mode: Literal["finance", "forecast", "risk"],
) -> None:
    # Given the candidate enabled, with a real FDT fixture and a wire-level model fake.
    calls: list[str] = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        document = JsonDocument.model_validate_json(request.content)
        name = (object_at(document, "response_format", "json_schema").root["name"]
                if document.root.get("response_format") is not None else "write")
        assert isinstance(name, str)
        calls.append(name)
        content = (JsonDocument.model_validate({
            "mode": "finance", "finance": {"status": "answered", "fact_ids": ["dsr"], "missing": []},
        }).model_dump_json() if name == "route" else "확인할 자료를 알려 주세요.")
        return httpx2.Response(200, content=completion(content))

    # This API case validates the model-backed combined route and its period
    # contract. Disable the separately tested catalog fast path explicitly.
    config = ModelConfig(
        endpoint_url="http://model.test",
        token_preflight=False,
        combined_dialogue=True,
        deterministic_finance_fast_path=False,
    )
    async with httpx2.AsyncClient(transport=httpx2.MockTransport(respond)) as model_client:
        app = create_app(Settings(
            database=tmp_path / "candidate.sqlite3",
            clients=(Client(user_id="demo", token=SecretStr(TOKEN)),),
        ), OpenAICompatibleCoachModel(config, client=model_client))
        async with httpx2.AsyncClient(
            transport=httpx2.ASGITransport(app=app), base_url="http://test",
            headers={"Authorization": "Bearer " + TOKEN},
        ) as client:
            assert (await client.post("/v1/twin", json=fixture().model_dump(mode="json"),
                                      headers={"Idempotency-Key": "bootstrap"})).status_code == 200
            session = await client.post("/v1/sessions", json={}, headers={"Idempotency-Key": "session"})
            saved = Session.model_validate_json(session.content)
            path = "/v1/sessions/" + saved.id
            payload = JsonDocument.model_validate(
                {"question": "DSR이 뭐야?", "period": {"kind": "rolling_days", "days": 7}}
                if mode == "finance" else {"question": "앞으로 7일 예측. 대신 DSR 설명도 알려줘.",
                    "analysis": {"mode": mode, "horizon_days": 7, "paths": 20, "seed": 42}},
            )
            # When finance receives an unsupported period or numeric intent is explicit.
            response = await client.post(path + "/messages", json=payload.root,
                                         headers={"Idempotency-Key": "turn"})
            # Then period rejection is atomic and explicit numeric requests reach FDT without routing.
            if mode == "finance":
                assert response.status_code == 422
                assert JsonDocument.model_validate_json(response.content).root["error"] == (
                    "period_not_supported_for_intent"
                )
                assert Session.model_validate_json((await client.get(path)).content) == saved
                assert calls == ["route"]
            else:
                assert response.status_code == 200, response.text
                coaching = Coaching.model_validate_json(response.content)
                receipt = coaching.receipt
                assert receipt.numeric_request is not None
                assert receipt.numeric_result is not None
                assert receipt.numeric_request.root["mode"] == mode
                assert receipt.numeric_result.root["status"] == "ok"
                assert receipt.routing == JsonDocument({"mode": mode, "source": "template",
                                                        "fallback_reason": None})
                assert coaching.wording_source == "template"
                assert coaching.model == "not_called"
                assert calls == []
