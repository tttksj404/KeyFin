# ruff: noqa: INP001
"""개인 금융 조회의 HTTP 경계와 기존 FDT 재사용을 검증한다."""

from pathlib import Path

import httpx2
import pytest
from pydantic import SecretStr
from test_api import OTHER, TOKEN, TestModel, setup
from test_engine import fixture
from test_personal_summary import context_input

from coaching_service.api import create_app
from coaching_service.settings import Client, Settings


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_personal_query_requires_data_when_no_source_is_connected(tmp_path: Path) -> None:
    # Given: 거래와 개인 현황이 모두 없는, 인증된 소유자다.
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=setup(tmp_path / "personal.sqlite3", TestModel())),
        base_url="http://test",
        headers={"Authorization": "Bearer " + TOKEN},
    ) as client:
        # When: 개인 자산을 묻는다.
        response = await client.post(
            "/v1/personal/questions",
            json={"question": "내 자산 얼마야?"},
            headers={"Idempotency-Key": "assets"},
        )
    # Then: 누락을 0원으로 만들지 않고 명시적으로 자료가 필요하다고 응답한다.
    assert response.status_code == 200
    assert response.json()["status"] == "needs_data"
    assert response.json()["evidence"]["total_krw"] is None


@pytest.mark.anyio
async def test_context_answer_is_owner_scoped_idempotent_and_survives_restart(tmp_path: Path) -> None:
    # Given: backend가 보험 현황을 등록했고 응답 생성은 실제 Repository를 사용한다.
    database = tmp_path / "personal.sqlite3"
    model = TestModel()
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=setup(database, model)),
        base_url="http://test",
        headers={"Authorization": "Bearer " + TOKEN},
    ) as client:
        stored = await client.post(
            "/v1/personal/context", json=context_input().root, headers={"Idempotency-Key": "source"}
        )
        assert stored.status_code == 200, stored.text
        assert stored.json()["revision"] == 1
        first = await client.post(
            "/v1/personal/questions", json={"question": "내 보험료는?"}, headers={"Idempotency-Key": "ask"}
        )
        assert first.status_code == 200, first.text
        answer = first.json()
        assert answer["evidence"]["total_krw"] == 50000
        assert (
            await client.post(
                "/v1/personal/questions",
                json={"question": "내 보험료는?"},
                headers={"Idempotency-Key": "ask"},
            )
        ).json() == answer
        isolated = await client.get(
            "/v1/answers/" + answer["id"], headers={"Authorization": "Bearer " + OTHER}
        )
        assert isolated.status_code == 404
        assert (
            await client.get("/v1/personal/context", headers={"Authorization": "Bearer " + OTHER})
        ).status_code == 404
        assert model.writes == model.routes == 0
    # When: 별도 앱 인스턴스로 DB를 다시 연다.
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=setup(database, TestModel())),
        base_url="http://test",
        headers={"Authorization": "Bearer " + TOKEN},
    ) as restarted:
        readback = await restarted.get("/v1/answers/" + answer["id"])
        context = await restarted.get("/v1/personal/context")
    # Then: 서버 수신 시각과 숫자 근거를 포함한 원래 응답이 그대로 남아 있다.
    assert readback.json() == answer
    assert context.json() == stored.json()


@pytest.mark.anyio
async def test_delete_removes_context_answer_and_completed_request_cache(tmp_path: Path) -> None:
    # Given: 개인 현황과 멱등 응답을 저장했다.
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=setup(tmp_path / "delete.sqlite3", TestModel())),
        base_url="http://test",
        headers={"Authorization": "Bearer " + TOKEN},
    ) as client:
        assert (
            await client.post(
                "/v1/personal/context", json=context_input().root, headers={"Idempotency-Key": "source"}
            )
        ).status_code == 200
        answer = await client.post(
            "/v1/personal/questions", json={"question": "내 소득 얼마야"}, headers={"Idempotency-Key": "ask"}
        )
        assert answer.status_code == 200
        # When: 서비스의 기존 전체 삭제 API를 호출한다.
        assert (await client.delete("/v1/me/data")).status_code == 200
        # Then: 새 저장소도 함께 지워져 이전 멱등 응답이 데이터를 되살리지 않는다.
        assert (await client.get("/v1/personal/context")).status_code == 404
        assert (await client.get("/v1/answers/" + answer.json()["id"])).status_code == 404
        retry = await client.post(
            "/v1/personal/questions", json={"question": "내 소득 얼마야"}, headers={"Idempotency-Key": "ask"}
        )
        assert retry.json()["status"] == "needs_data"


@pytest.mark.anyio
async def test_snapshot_query_reuses_fdt_without_modifying_engine_state(tmp_path: Path) -> None:
    # Given: 기존 원본 FDT API로만 계좌 잔액을 등록했다.
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=setup(tmp_path / "fdt.sqlite3", TestModel())),
        base_url="http://test",
        headers={"Authorization": "Bearer " + TOKEN},
    ) as client:
        assert (
            await client.post(
                "/v1/twin", json=fixture().model_dump(mode="json"), headers={"Idempotency-Key": "twin"}
            )
        ).status_code == 200
        before = await client.get("/v1/twin")
        # When: 개인 조회 API로 계좌를 질문한다.
        result = await client.post(
            "/v1/personal/questions",
            json={"question": "내 계좌 잔액 알려줘"},
            headers={"Idempotency-Key": "cash"},
        )
        after = await client.get("/v1/twin")
    # Then: FDT 원본은 변하지 않으며 독립적으로 지정한 100만 원을 읽는다.
    assert result.status_code == 200, result.text
    assert result.json()["evidence"]["total_krw"] == 1000000
    assert result.json()["evidence"]["source_system"] == "fdt_snapshot"
    assert before.json() == after.json()


@pytest.mark.anyio
async def test_backend_context_rejects_user_role_and_missing_authentication(tmp_path: Path) -> None:
    # Given: 실제 인증 의존성에 user 역할만 가진 토큰을 등록했다.
    app = create_app(
        Settings(
            database=tmp_path / "roles.sqlite3",
            clients=(Client(user_id="demo", token=SecretStr(TOKEN), role="user"),),
        ),
        TestModel(),
    )
    async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app), base_url="http://test") as client:
        # When: backend 전용 입력을 두 종류의 잘못된 인증 상태로 시도한다.
        missing_auth = await client.post(
            "/v1/personal/context", json=context_input().root, headers={"Idempotency-Key": "a"}
        )
        user_role = await client.post(
            "/v1/personal/context",
            json=context_input().root,
            headers={"Idempotency-Key": "b", "Authorization": "Bearer " + TOKEN},
        )
    # Then: 자료를 쓰기 전에 인증/역할 단계에서 차단한다.
    assert missing_auth.status_code == 401
    assert user_role.status_code == 403
