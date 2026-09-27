# ruff: noqa: INP001
"""정답 금액을 독립된 작은 산술 사례로 고정한다."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from coaching_service.personal_contract import PersonalContext, PersonalInput, PersonalTopic
from coaching_service.personal_query import select_personal_topic
from coaching_service.personal_snapshot import Snapshot, snapshot_summary
from coaching_service.personal_summary import context_summary
from coaching_service.schemas import JsonDocument


def context_input() -> JsonDocument:
    return JsonDocument.model_validate(
        {
            "expected_revision": 0,
            "as_of": "2026-09-03",
            "source_system": "test-fixture",
            "source_record_id": "synthetic-only",
            "provenance": "synthetic",
            "income": {
                "coverage": "complete",
                "items": [
                    {"id": "salary", "label": "급여", "monthly_amount_krw": 3100000},
                    {"id": "side", "label": "부수입", "monthly_amount_krw": 200000},
                ],
            },
            "fixed_costs": {
                "coverage": "partial",
                "items": [
                    {"id": "rent", "label": "월세", "monthly_amount_krw": 450000},
                    {"id": "phone", "label": "통신비", "monthly_amount_krw": 55000},
                ],
            },
            "insurance": {
                "coverage": "complete",
                "items": [
                    {
                        "id": "life",
                        "label": "생명보험",
                        "monthly_premium_krw": 20000,
                        "coverage_amount_krw": 100000000,
                    },
                    {
                        "id": "health",
                        "label": "건강보험",
                        "monthly_premium_krw": 30000,
                        "coverage_amount_krw": 50000000,
                    },
                ],
            },
            "goals": {
                "coverage": "complete",
                "items": [
                    {"id": "car", "label": "자동차", "target_krw": 1000000, "saved_krw": 120000},
                    {"id": "travel", "label": "여행", "target_krw": 200000, "saved_krw": 80000},
                ],
            },
        }
    )


def snapshot_input() -> JsonDocument:
    return JsonDocument.model_validate(
        {
            "as_of": "2026-09-03",
            "snapshot": {
                "as_of": "2026-09-03",
                "source": "USER_ASSUMPTION",
                "accounts": [
                    {"account_id": "cash", "balance_krw": 1000000},
                    {"account_id": "overdraft", "balance_krw": -50000},
                ],
                "assets": [{"asset_id": "stock", "kind": "investment", "value_krw": 300000}],
                "liabilities": [{"liability_id": "loan", "principal_krw": 200000}],
                "cards": [
                    {
                        "card_id": "credit",
                        "kind": "CREDIT",
                        "opening_payable_krw": 70000,
                        "settlement_account_id": "cash",
                        "payment_delay_days": 2,
                    }
                ],
                "known_bills": [
                    {
                        "bill_id": "tomorrow",
                        "card_id": "credit",
                        "due_date": "2026-09-04",
                        "amount_krw": 20000,
                    },
                    {"bill_id": "next", "card_id": "credit", "due_date": "2026-09-08", "amount_krw": 50000},
                ],
                "coverage": {"all_assets_reported": True, "all_liabilities_reported": True},
            },
        }
    )


@pytest.mark.parametrize(
    ("topic", "expected"),
    [
        ("income", 3300000),
        ("fixed_costs", 505000),
        ("insurance", 50000),
        ("goals", None),
    ],
)
def test_context_amounts_have_explicit_units_when_sections_are_reported(
    topic: PersonalTopic, expected: int | None
) -> None:
    # Given: 월 금액과 목표별 적립액을 독립적으로 지정한 입력이다.
    context = PersonalContext.model_validate(
        context_input().root | {"revision": 1, "received_at": datetime.now(UTC)}
    )
    # When: 해당 항목을 조회한다.
    result = context_summary(context, topic)
    # Then: 월보험료만 합산하며 서로 다른 목표의 적립액은 합치지 않는다.
    assert result.total_krw == expected
    assert result.status == "answered"


@pytest.mark.parametrize(
    ("topic", "expected"), [("accounts", 950000), ("assets", 1250000), ("debts", 270000), ("payments", 70000)]
)
def test_fdt_values_are_read_without_duplicate_cash_or_bill_counting(
    topic: PersonalTopic, expected: int
) -> None:
    # Given: 현금 100만, 마이너스잔액 -5만, 비계좌자산 30만, 대출 20만, 카드미결제 7만이다.
    raw = snapshot_input()
    # When: 미래 시뮬레이션을 호출하지 않고 원본 snapshot만 읽는다.
    result = snapshot_summary(raw, topic)
    # Then: 부채에 카드 청구 7만을 다시 더하지 않고 다음날부터의 청구서를 합산한다.
    assert result.total_krw == expected


@pytest.mark.parametrize("coverage", ["unknown", "partial"])
def test_empty_noncomplete_section_is_unknown_instead_of_zero(coverage: str) -> None:
    # Given: 전체 수집을 확인하지 못한 빈 소득 자료다.
    raw = context_input().root | {
        "income": {"coverage": coverage, "items": []},
        "revision": 1,
        "received_at": "2026-09-03T12:00:00+09:00",
    }
    # When: 소득을 조회한다.
    result = context_summary(PersonalContext.model_validate(raw), "income")
    # Then: 부분 수집/미수집과 명시적인 0원을 구분한다.
    assert result.status == "needs_data"
    assert result.total_krw is None


def test_explicit_complete_empty_section_can_report_zero() -> None:
    # Given: backend가 소득 항목이 없다는 것을 확인한 자료다.
    raw = context_input().root | {
        "income": {"coverage": "complete", "items": []},
        "revision": 1,
        "received_at": "2026-09-03T12:00:00+09:00",
    }
    # When: 소득을 조회한다.
    result = context_summary(PersonalContext.model_validate(raw), "income")
    # Then: 명시적으로 확인한 빈 집합만 0원이다.
    assert result.status == "answered"
    assert result.total_krw == 0


@pytest.mark.parametrize("amount", [-1, True, 1.5, "100", 1000000000001])
def test_monthly_money_rejects_invalid_values(amount: float | str) -> None:
    # Given: 한 소득 항목에 정수 원 금액이 아닌 값 또는 범위 밖 금액을 넣었다.
    raw = context_input().root | {
        "income": {
            "coverage": "complete",
            "items": [{"id": "salary", "label": "급여", "monthly_amount_krw": amount}],
        }
    }
    # When/Then: 입력 경계에서 거부한다.
    with pytest.raises(ValidationError):
        PersonalInput.model_validate(raw)


def test_duplicate_account_id_is_rejected() -> None:
    # Given: 같은 계좌를 두 번 보냈다.
    raw = snapshot_input().root["snapshot"]
    assert isinstance(raw, dict)
    duplicate = raw | {
        "accounts": [{"account_id": "a", "balance_krw": 1}, {"account_id": "a", "balance_krw": 2}]
    }
    # When/Then: 중복 합산 전에 거부한다.
    with pytest.raises(ValidationError, match="duplicate_snapshot_id"):
        Snapshot.model_validate(duplicate)


@pytest.mark.parametrize(
    "question",
    [
        "내 자산에서 자동차 빼고 알려줘",
        "작년 내 소득 얼마야",
        "국민은행 잔액 알려줘",
        "내 자산과 부채 비교해줘",
    ],
)
def test_unsupported_filter_is_not_silently_dropped(question: str) -> None:
    # Given/When: 미지원 필터가 붙은 실제 질문이다.
    result = select_personal_topic(question)
    # Then: 전체 합계로 바꿔 답하지 않는다.
    assert result is None


@pytest.mark.parametrize(
    ("question", "topic"),
    [
        ("내 계좌 잔액 알려줘", "accounts"),
        ("내 계좌 잔액은 지금 얼마야?", "accounts"),
        ("내 부채는 현재 얼마인가요?", "debts"),
        ("지금 나의 부채는 얼마야?", "debts"),
        ("내 월 소득이 얼마야", "income"),
        ("내 보험료는?", "insurance"),
        ("예정 결제 알려주세요", "payments"),
    ],
)
def test_supported_question_selects_one_topic(question: str, topic: str) -> None:
    # Given/When: 한 항목의 범위를 명확히 묻는다.
    result = select_personal_topic(question)
    # Then: 날짜나 금융 숫자를 LLM에서 얻지 않고 조회 항목만 결정한다.
    assert result == topic
