# ruff: noqa: INP001
"""출처 누락과 조회 자료가 예측 상태를 바꾸는 회귀를 막는다."""

from datetime import date
from pathlib import Path

import httpx2
import pytest
from pydantic import ValidationError
from test_api import TOKEN, TestModel, setup
from test_engine import fixture
from test_personal_summary import context_input, snapshot_input

from coaching_service.engine import EngineAdapter
from coaching_service.personal_contract import PersonalInput
from coaching_service.personal_snapshot import Snapshot, snapshot_summary
from coaching_service.schemas import JsonDocument


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def test_duplicate_monthly_items_are_rejected_before_sum() -> None:
    # Given: 한 소득원을 ID까지 동일하게 두 번 보고했다.
    item = {"id": "salary", "label": "급여", "monthly_amount_krw": 100}
    raw = context_input().root | {"income": {"coverage": "complete", "items": [item, item]}}
    # When/Then: 두 번 합산하지 않고 입력을 거부한다.
    with pytest.raises(ValidationError, match="duplicate_item_id"):
        PersonalInput.model_validate(raw)


def test_unknown_coverage_cannot_carry_reported_items() -> None:
    # Given: 모른다고 표시하면서 금액을 보내는 모순된 입력이다.
    raw = context_input().root | {
        "income": {
            "coverage": "unknown",
            "items": [{"id": "salary", "label": "급여", "monthly_amount_krw": 100}],
        }
    }
    # When/Then: 알려진 일부 자료라면 partial을 명시하도록 거부한다.
    with pytest.raises(ValidationError, match="unknown_section_has_items"):
        PersonalInput.model_validate(raw)


def test_credit_payable_cannot_be_defaulted_to_zero() -> None:
    # Given: 신용카드 존재만 있고 미결제 원금이 없다.
    raw = snapshot_input().root["snapshot"]
    assert isinstance(raw, dict)
    # When/Then: 누락된 카드 미결제액을 0원으로 바꾸지 않는다.
    with pytest.raises(ValidationError, match="credit_payable_missing"):
        Snapshot.model_validate(raw | {"cards": [{"card_id": "credit", "kind": "CREDIT"}]})


def test_snapshot_keeps_its_own_as_of_when_transactions_are_newer() -> None:
    # Given: 새 거래를 수집해 Twin 기준일만 변경됐고 원래 snapshot은 9월 3일이다.
    raw = JsonDocument.model_validate(snapshot_input().root | {"as_of": "2026-09-08"})
    # When: 계좌 잔액을 조회한다.
    result = snapshot_summary(raw, "accounts")
    # Then: 잔액 기준일을 최신 거래 날짜로 바꿔서 포장하지 않는다.
    assert result.as_of is not None
    assert result.as_of.isoformat() == "2026-09-03"
    assert result.total_krw == 950000
    assert result.source_record_id is not None
    assert result.source_record_id.startswith("sha256:")


def test_payment_oracle_fixture_is_accepted_by_the_original_engine_contract() -> None:
    # Given: 9월 3일 기준, 다음날 2만 원과 9월 8일 5만 원의 청구서를 등록했다.
    snapshot = snapshot_input().root["snapshot"]
    assert isinstance(snapshot, dict)
    request = fixture().model_copy(update={"as_of": date(2026, 9, 3), "snapshot": JsonDocument(snapshot)})
    # When: 원본 FDT로 계약을 검증한 후 개인 조회가 원본을 읽는다.
    twin = EngineAdapter().create(request, "demo")
    result = snapshot_summary(twin, "payments")
    # Then: 원본 엔진이 접수 가능한 입력에서도 독립 산술값 7만 원이 나온다.
    assert result.total_krw == 70000
    assert [row.due_date for row in result.rows] == [date(2026, 9, 4), date(2026, 9, 8)]


@pytest.mark.anyio
async def test_personal_update_does_not_write_into_fdt_or_preserve_omitted_sections(tmp_path: Path) -> None:
    # Given: FDT와 개인 현황이 각각 자기 출처에서 연결됐다.
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=setup(tmp_path / "sources.sqlite3", TestModel())),
        base_url="http://test",
        headers={"Authorization": "Bearer " + TOKEN},
    ) as client:
        assert (
            await client.post(
                "/v1/twin",
                json=fixture().model_dump(mode="json"),
                headers={"Idempotency-Key": "fdt"},
            )
        ).status_code == 200
        before = (await client.get("/v1/twin")).json()
        assert (
            await client.post(
                "/v1/personal/context",
                json=context_input().root,
                headers={"Idempotency-Key": "personal"},
            )
        ).status_code == 200
        # When: 전체 교체 snapshot에서 소득/보험/목표를 보내지 않는다.
        result = await client.post(
            "/v1/personal/context",
            json={
                "expected_revision": 1,
                "as_of": "2026-09-03",
                "source_system": "backend",
                "source_record_id": "empty-v2",
                "provenance": "synthetic",
            },
            headers={"Idempotency-Key": "replace"},
        )
        after = (await client.get("/v1/twin")).json()
        question = await client.post(
            "/v1/personal/questions",
            json={"question": "내 소득 얼마야"},
            headers={"Idempotency-Key": "ask"},
        )
    # Then: 누락된 옛 값을 최신으로 남겨두지 않으며 예측 엔진 상태도 바꾸지 않는다.
    assert result.status_code == 200
    assert result.json()["income"]["coverage"] == "unknown"
    assert question.json()["status"] == "needs_data"
    assert before == after
