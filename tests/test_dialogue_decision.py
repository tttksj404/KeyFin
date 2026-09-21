# ruff: noqa: INP001
"""A single model decision must retain route and exact approved finance wording."""

import json
from pathlib import Path
from typing import Final

import httpx2
import pytest
from pydantic import JsonValue, SecretStr, ValidationError

from coaching_service.api import create_app
from coaching_service.dialogue_decision import DialogueFinanceSelection, DialogueSelection, decide_dialogue
from coaching_service.finance_knowledge import finance_evidence, selected_finance_wording
from coaching_service.llm import OpenAICompatibleCoachModel
from coaching_service.llm_contract import EvidenceInput, Mode, ModelConfig
from coaching_service.schemas import JsonDocument, Session
from coaching_service.settings import Client, Settings

TOKEN: Final = "test-only-dialogue-token-0000000000000000"
OTHER: Final = "test-only-other-dialogue-token-0000000000"


def object_at(document: JsonDocument, *keys: str) -> JsonDocument:
    """Parse each nested JSON object instead of erasing wire data types."""
    current = document
    for key in keys:
        current = JsonDocument.model_validate(current.root[key])
    return current


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.parametrize("value", [
    {"mode": "finance", "finance": None},
    {"mode": "personal", "finance": {"status": "answered", "fact_ids": ["dsr"]}},
    {"mode": "finance", "finance": {"status": "answered", "fact_ids": ["invented"]}},
    {"mode": "finance", "finance": {"status": "answered", "fact_ids": ["dsr"], "amount": 1}},
    {"mode": "finance", "finance": {"status": "out_of_scope", "fact_ids": []}},
    {"mode": "finance", "finance": {"status": "needs_data", "fact_ids": []}},
])
def test_cross_intent_or_unapproved_selection_is_rejected(value: JsonValue) -> None:
    with pytest.raises(ValidationError):
        _ = DialogueSelection.model_validate_json(json.dumps(value))


def test_generation_schema_exposes_only_supported_finance_statuses() -> None:
    # Given the schema actually supplied to constrained generation.
    schema = JsonDocument.model_validate(DialogueFinanceSelection.model_json_schema())
    # When the status vocabulary is read from the nested finance schema.
    status = object_at(schema, "properties", "status")
    # Then local validation and generated choices share the same restricted states.
    assert status.root["enum"] == ["answered", "needs_source"]
    joint = JsonDocument.model_validate(DialogueSelection.model_json_schema())
    assert object_at(joint, "$defs", "DialogueFinanceSelection", "properties", "status") == status


@pytest.mark.parametrize("mode", ["other", "personal", "history", "forecast", "risk", "review"])
def test_nonfinance_routes_allow_only_null_finance_payload(mode: Mode) -> None:
    # Given one supported route whose downstream tools own its answer.
    finance = DialogueFinanceSelection(status="answered", fact_ids=("dsr",))
    # When the route carries no premature finance answer.
    selection = DialogueSelection(mode=mode, finance=None)
    # Then it remains valid, while attaching a finance answer is rejected.
    assert selection.mode == mode
    assert selection.finance is None
    with pytest.raises(ValidationError):
        _ = DialogueSelection(mode=mode, finance=finance)


@pytest.mark.anyio
@pytest.mark.parametrize("combined", [False, True])
async def test_combined_choice_reuses_exact_finance_renderer(combined: bool) -> None:
    calls: list[JsonDocument] = []
    finance = {"status": "answered", "fact_ids": ["dsr"], "missing": []}

    def respond(request: httpx2.Request) -> httpx2.Response:
        payload = JsonDocument.model_validate_json(request.content)
        calls.append(payload)
        choice = {"mode": "finance", "finance": finance} if combined else {"mode": "finance"}
        return httpx2.Response(200, json={"choices": [{
            "message": {"content": json.dumps(choice)}, "finish_reason": "stop",
        }]})

    evidence = finance_evidence("DSR이 뭐야?")
    async with httpx2.AsyncClient(transport=httpx2.MockTransport(respond)) as client:
        model = OpenAICompatibleCoachModel(ModelConfig(
            endpoint_url="http://localhost/v1", token_preflight=False, combined_dialogue=combined,
        ), client=client)
        answer = await decide_dialogue(model, EvidenceInput(question=evidence.question, facts_json="{}"),
                                       evidence)
    assert len(calls) == 1
    assert answer.routing.mode == "finance"
    assert answer.routing.source == "llm"
    if combined:
        assert answer.finance == selected_finance_wording(
            json.dumps(finance), "coaching-model", evidence=evidence,
        )
        assert object_at(calls[0], "response_format", "json_schema", "schema", "properties").root["finance"]
    else:
        assert answer.finance is None


@pytest.mark.anyio
@pytest.mark.parametrize("content", [
    '{"mode":"finance","finance":null}',
    '{"mode":"personal","finance":{"status":"answered","fact_ids":["dsr"]}}',
    '{"mode":"finance","mode":"other","finance":null}',
    "not JSON",
])
async def test_invalid_combined_choice_fails_closed_without_retry(content: str) -> None:
    calls = 0

    def respond(_: httpx2.Request) -> httpx2.Response:
        nonlocal calls
        calls += 1
        return httpx2.Response(200, json={"choices": [{
            "message": {"content": content}, "finish_reason": "stop",
        }]})

    async with httpx2.AsyncClient(transport=httpx2.MockTransport(respond)) as client:
        model = OpenAICompatibleCoachModel(ModelConfig(
            endpoint_url="http://localhost/v1", token_preflight=False, combined_dialogue=True,
        ), client=client)
        answer = await decide_dialogue(model, EvidenceInput(question="DSR이 뭐야?", facts_json="{}"),
                                       finance_evidence("DSR이 뭐야?"))
    assert calls == 1
    assert answer.routing.source == "template"
    assert answer.routing.fallback_reason == "invalid_schema"
    assert answer.finance is None


@pytest.mark.anyio
@pytest.mark.parametrize(("combined", "expected_calls"), [(False, 2), (True, 1)])
async def test_api_single_call_retry_and_owner_contract(
    tmp_path: Path, combined: bool, expected_calls: int,
) -> None:
    calls: list[str] = []
    finance = {"status": "answered", "fact_ids": ["dsr"], "missing": []}

    def respond(request: httpx2.Request) -> httpx2.Response:
        request_document = JsonDocument.model_validate_json(request.content)
        name = object_at(request_document, "response_format", "json_schema").root["name"]
        assert isinstance(name, str)
        calls.append(name)
        selection = finance if name == "finance_facts" else {"mode": "finance"}
        if combined:
            selection = {"mode": "finance", "finance": finance}
        return httpx2.Response(200, json={"choices": [{
            "message": {"content": json.dumps(selection)}, "finish_reason": "stop",
        }]})

    # Preserve the model-backed route/call-count contract under explicit
    # opt-out. Default shortcut coverage lives in the dedicated D1 tests.
    config = ModelConfig(endpoint_url="http://localhost/v1", token_preflight=False,
                         combined_dialogue=combined, deterministic_finance_fast_path=False)
    async with httpx2.AsyncClient(transport=httpx2.MockTransport(respond)) as model_client:
        app = create_app(Settings(database=tmp_path / "dialogue.sqlite3", clients=(
            Client(user_id="demo", token=SecretStr(TOKEN)),
            Client(user_id="other", token=SecretStr(OTHER)),
        )), OpenAICompatibleCoachModel(config, client=model_client))
        async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app), base_url="http://test",
                                     headers={"Authorization": "Bearer " + TOKEN}) as client:
            session = await client.post("/v1/sessions", json={}, headers={"Idempotency-Key": "session"})
            path = "/v1/sessions/" + Session.model_validate_json(session.content).id
            body = {"question": "DSR이 뭐야?"}
            response = await client.post(path + "/messages", json=body,
                                         headers={"Idempotency-Key": "turn"})
            assert response.status_code == 200, response.text
            assert len(calls) == expected_calls
            answer_document = JsonDocument.model_validate_json(response.content)
            assert answer_document.root["text"] == selected_finance_wording(
                json.dumps(finance), "coaching-model", evidence=finance_evidence(body["question"]),
            ).text
            repeated = await client.post(path + "/messages", json=body,
                                         headers={"Idempotency-Key": "turn"})
            assert JsonDocument.model_validate_json(repeated.content) == answer_document
            assert len(calls) == expected_calls
            stored_session = Session.model_validate_json((await client.get(path)).content)
            assert len(stored_session.messages) == 2
            foreign = await client.get(path, headers={"Authorization": "Bearer " + OTHER})
            assert foreign.status_code == 404
            conflict = await client.post(path + "/messages", json={"question": "LTV도?"},
                                         headers={"Idempotency-Key": "turn"})
            assert conflict.status_code == 409
            assert len(calls) == expected_calls
