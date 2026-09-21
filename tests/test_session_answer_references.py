# ruff: noqa: INP001
"""재접속 시 본문을 해석하지 않고 저장된 원본 답변의 출처와 기간을 복원한다."""

import json
import time
from pathlib import Path
from typing import Literal

import httpx2
import pytest
from pydantic import ValidationError
from test_api import OTHER, TOKEN, TestModel, setup
from test_engine import fixture
from test_general_chat_api import ConceptModel

from coaching_service.schemas import AnswerReference, Message
from coaching_service.store import Store


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
@pytest.mark.parametrize("kind", ["chat", "coaching"])
async def test_exact_answer_reference_survives_reload_retry_and_owner_checks(
    tmp_path: Path, kind: Literal["chat", "coaching"]
) -> None:
    # Given: 일반 금융 답변과 FDT 답변은 각각 서로 다른 원본 조회 경로를 사용한다.
    database = tmp_path / "references.sqlite3"
    model = ConceptModel() if kind == "chat" else TestModel()
    body = {"question": "예금과 적금의 차이는?" if kind == "chat" else "앞으로 7일 위험을 알려줘"}
    headers = {"Idempotency-Key": "turn"}
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=setup(database, model)), base_url="http://test",
        headers={"Authorization": "Bearer " + TOKEN},
    ) as client:
        if kind == "coaching":
            created = await client.post(
                "/v1/twin", json=fixture().model_dump(mode="json"), headers={"Idempotency-Key": "twin"}
            )
            assert created.status_code == 200, created.text
        session = await client.post("/v1/sessions", json={}, headers={"Idempotency-Key": "session"})
        assert session.status_code == 200, session.text
        session_path = "/v1/sessions/" + session.json()["id"]
        response = await client.post(session_path + "/messages", json=body, headers=headers)
        assert response.status_code == 200, response.text
        answer = response.json()
        answer_path = ("/v1/answers/" if kind == "chat" else "/v1/coaching/") + answer["id"]
        # When: 동일 요청을 재전송하고 세션의 원본 참조를 읽는다.
        assert (await client.post(session_path + "/messages", json=body, headers=headers)).json() == answer
        saved = (await client.get(session_path)).json()
        assert saved["messages"] == [
            {"role": "user", "content": body["question"], "response": None},
            {"role": "assistant", "content": answer["text"], "response": {"kind": kind, "id": answer["id"]}},
        ]
        assert (await client.get(answer_path)).json() == answer
        if kind == "chat":
            assert answer["evidence"]["references"]
        else:
            assert answer["receipt"]["period"]["forecast_start"] == "2026-09-10"
            assert answer["receipt"]["period"]["forecast_end"] == "2026-09-16"
        conflict = await client.post(
            session_path + "/messages", json={"question": "다른 질문"}, headers=headers
        )
        assert conflict.status_code == 409
        assert (await client.get(session_path)).json() == saved
    # Then: 메모리를 공유하지 않는 새 저장소/앱에서도 같은 원본과 멱등 응답을 읽는다.
    restarted_model = TestModel()
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=setup(database, restarted_model)), base_url="http://test",
        headers={"Authorization": "Bearer " + TOKEN},
    ) as restarted:
        assert (await restarted.get(session_path)).json() == saved
        assert (await restarted.get(answer_path)).json() == answer
        assert (
            await restarted.post(session_path + "/messages", json=body, headers=headers)
        ).json() == answer
        for path in (session_path, answer_path):
            denied = await restarted.get(path, headers={"Authorization": "Bearer " + OTHER})
            assert denied.status_code == 404
        injected = await restarted.post(
            session_path + "/messages", headers={"Idempotency-Key": "forged-reference"},
            json={**body, "response": {"kind": kind, "id": answer["id"]}},
        )
        assert injected.status_code == 422
        assert (await restarted.get(session_path)).json() == saved
        assert (await restarted.delete("/v1/me/data")).status_code == 200
        assert (await restarted.get(session_path)).status_code == 404
        assert (await restarted.get(answer_path)).status_code == 404
    # Clear personal FDT wording now selects its validated numeric mode without a separate route call.
    assert model.routes == (0 if kind == "coaching" else 1)
    assert model.writes == (0 if kind == "coaching" else 1)
    assert restarted_model.routes == restarted_model.writes == 0


@pytest.mark.anyio
async def test_legacy_message_load_keeps_null_reference_without_body_inference(tmp_path: Path) -> None:
    # Given: 같은 본문에 ID처럼 보이는 문자열이 있어도 과거 저장 레코드에는 원본 참조가 없다.
    database = tmp_path / "legacy.sqlite3"
    store = Store(database)
    old = {
        "id": "legacy", "created_at": time.time(), "expires_at": time.time() + 1000,
        "messages": [
            {"role": "user", "content": "이전 질문"},
            {"role": "assistant", "content": "answer-looking-id 답변 출처와 2026-09-30 예측"},
        ],
    }
    raw = json.dumps(old, ensure_ascii=False)
    with store.connection() as connection:
        _ = connection.execute("INSERT INTO items VALUES(?,?,?)", ("demo", "session/legacy", raw))
    # When: 새 계약의 GET을 호출한다.
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=setup(database, ConceptModel())), base_url="http://test",
        headers={"Authorization": "Bearer " + TOKEN},
    ) as client:
        response = await client.get("/v1/sessions/legacy")
    # Then: 옛 본문은 그대로 보존하고 참조를 생성하거나 DB를 암묵적으로 이관하지 않는다.
    assert response.status_code == 200, response.text
    assert response.json()["messages"] == [{**row, "response": None} for row in old["messages"]]
    assert store.load("demo", "session/legacy") == raw


@pytest.mark.anyio
async def test_failed_answer_write_rolls_back_session_reference_and_allows_retry(tmp_path: Path) -> None:
    # Given: 원본 답변 저장만 DB 트리거로 실패시켜 부분 저장을 재현한다.
    database = tmp_path / "atomic.sqlite3"
    app = setup(database, ConceptModel())
    store = Store(database)
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test",
        headers={"Authorization": "Bearer " + TOKEN},
    ) as client:
        session = await client.post("/v1/sessions", json={}, headers={"Idempotency-Key": "session"})
        path = "/v1/sessions/" + session.json()["id"]
        with store.connection() as connection:
            _ = connection.execute(
                "CREATE TRIGGER reject_answer BEFORE INSERT ON items "
                "WHEN NEW.key LIKE 'answer/%' BEGIN SELECT RAISE(ABORT,'injected_failure'); END"
            )
        body, headers = {"question": "예금과 적금 차이는?"}, {"Idempotency-Key": "turn"}
        # When: 세션 변경 뒤 원본 저장이 실패한다.
        failed = await client.post(path + "/messages", json=body, headers=headers)
        assert failed.status_code == 500
        # Then: 빈 세션과 원본 부재가 유지되며 실패 응답은 멱등 성공으로 저장하지 않는다.
        assert (await client.get(path)).json() == session.json()
        assert store.list_items("demo", "answer/") == ()
        with store.connection() as connection:
            _ = connection.execute("DROP TRIGGER reject_answer")
        retried = await client.post(path + "/messages", json=body, headers=headers)
        assert retried.status_code == 200, retried.text
        answer = retried.json()
        assert (await client.get(path)).json()["messages"][-1]["response"] == {
            "kind": "chat", "id": answer["id"],
        }
        assert (await client.get("/v1/answers/" + answer["id"])).json() == answer


def test_user_message_cannot_claim_a_server_answer_reference() -> None:
    reference = AnswerReference(kind="chat", id="valid-answer")
    with pytest.raises(ValidationError, match="user_message_cannot_reference_answer"):
        Message(role="user", content="사용자 본문", response=reference)


@pytest.mark.parametrize(
    "raw", [
        {"kind": "other", "id": "valid"}, {"kind": "chat", "id": "../other"},
        {"kind": "coaching", "id": ""}, {"kind": "chat", "id": "a" * 121},
    ],
)
def test_answer_reference_rejects_unsupported_kind_or_unsafe_id(raw: dict[str, str]) -> None:
    with pytest.raises(ValidationError):
        AnswerReference.model_validate(raw)
