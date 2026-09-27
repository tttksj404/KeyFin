# ruff: noqa: INP001
"""backend 입력의 위조·오래된 revision·재시도 충돌을 검증한다."""

from pathlib import Path

import httpx2
import pytest
from test_api import TOKEN, TestModel, setup
from test_personal_summary import context_input


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("user_id", "other"),
        ("received_at", "2026-09-03T00:00:00Z"),
        ("currency", "USD"),
        ("as_of", "2026-09-03T00:00:00Z"),
        ("as_of", "2099-01-01"),
        ("expected_revision", True),
    ],
)
async def test_context_rejects_body_identity_currency_time_and_coercion(
    tmp_path: Path, field: str, value: str | bool
) -> None:
    # Given: 신뢰된 backend 토큰이어도 body는 입력 검증을 거친다.
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=setup(tmp_path / "invalid.sqlite3", TestModel())),
        base_url="http://test",
        headers={"Authorization": "Bearer " + TOKEN},
    ) as client:
        # When: owner/서버시각 위조 또는 KRW/date/revision 계약 위반 입력을 보낸다.
        result = await client.post(
            "/v1/personal/context",
            json=context_input().root | {field: value},
            headers={"Idempotency-Key": "bad"},
        )
    # Then: 저장하지 않는다.
    assert result.status_code == 422


@pytest.mark.anyio
async def test_retries_and_updates_enforce_original_body_and_monotonic_revision(tmp_path: Path) -> None:
    # Given: 첫 번째 snapshot이 저장되었다.
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=setup(tmp_path / "revision.sqlite3", TestModel())),
        base_url="http://test",
        headers={"Authorization": "Bearer " + TOKEN},
    ) as client:
        body = context_input().root
        first = await client.post("/v1/personal/context", json=body, headers={"Idempotency-Key": "source"})
        assert first.status_code == 200
        # When: 동일 재전송/변경된 재전송/낡은 revision/낡은 기준일을 보낸다.
        retry = await client.post("/v1/personal/context", json=body, headers={"Idempotency-Key": "source"})
        conflict = await client.post(
            "/v1/personal/context",
            json=body | {"source_record_id": "changed"},
            headers={"Idempotency-Key": "source"},
        )
        revision = await client.post("/v1/personal/context", json=body, headers={"Idempotency-Key": "stale"})
        old = await client.post(
            "/v1/personal/context",
            json=body | {"expected_revision": 1, "as_of": "2026-09-02"},
            headers={"Idempotency-Key": "old"},
        )
        next_snapshot = await client.post(
            "/v1/personal/context",
            json=body | {"expected_revision": 1, "source_record_id": "source-v2"},
            headers={"Idempotency-Key": "new"},
        )
    # Then: 같은 요청만 재사용하고 새 snapshot은 실제 현재 revision 다음으로 저장한다.
    assert retry.json() == first.json()
    assert conflict.status_code == revision.status_code == old.status_code == 409
    assert next_snapshot.status_code == 200
    assert next_snapshot.json()["revision"] == 2
