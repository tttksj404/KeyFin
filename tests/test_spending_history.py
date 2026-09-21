# ruff: noqa: INP001
"""원본 거래에서 확정한 소비 합계와 달력 경계를 검증한다."""

from datetime import date

import pytest

from coaching_service.engine import EngineAdapter
from coaching_service.schemas import JsonDocument, TransactionView
from coaching_service.spending_history import spending_answer
from tests.test_engine import fixture


def raw_transactions() -> tuple[JsonDocument, ...]:
    """카드 구매 12,000 + 교통 5,000 + 제삼자 회비 3,000 = 20,000원."""
    base = fixture().transactions[0].root
    changes = (
        {
            "transaction_id": "card",
            "transaction_type": "CARD",
            "card_id": "c",
            "category": "식비",
            "subcategory": "점심",
            "amount_krw": 12000,
            "transaction_date": "2028-02-01",
        },
        {
            "transaction_id": "transport",
            "category": "교통",
            "subcategory": "택시",
            "amount_krw": 5000,
            "transaction_date": "2028-02-29",
        },
        {
            "transaction_id": "dues",
            "transaction_type": "TRANSFER_OUT",
            "category": "사회·경조",
            "subcategory": "회비",
            "amount_krw": 3000,
        },
        {"transaction_id": "settlement", "transaction_type": "CARD_SETTLEMENT", "amount_krw": 12000},
        {"transaction_id": "self", "transaction_type": "TRANSFER", "amount_krw": 100000},
        {"transaction_id": "income", "transaction_type": "DEPOSIT", "amount_krw": 1000000},
        {"transaction_id": "cash", "subcategory": "ATM 출금", "amount_krw": 9999},
        {"transaction_id": "debt", "subcategory": "대출 상환", "amount_krw": 40000},
        {"transaction_id": "rent", "subcategory": "월세", "amount_krw": 500000},
        {"transaction_id": "pending", "confirm_status": "PENDING", "amount_krw": 8000},
        {"transaction_id": "canceled", "status": "CANCELED", "amount_krw": 7000},
        {"transaction_id": "dutch", "exclude_tag": "DUTCH", "amount_krw": 2000},
        {"transaction_id": "jan", "transaction_date": "2028-01-31", "amount_krw": 99},
        {"transaction_id": "march", "transaction_date": "2028-03-01", "amount_krw": 6000},
        {"transaction_id": "future", "transaction_date": "2028-03-15", "amount_krw": 33000},
    )
    return tuple(
        JsonDocument.model_validate({**base, "transaction_date": "2028-02-15", **row}) for row in changes
    )


def transactions() -> tuple[TransactionView, ...]:
    engine = EngineAdapter()
    request = fixture().model_copy(
        update={"as_of": date(2028, 3, 15), "transactions": raw_transactions(), "snapshot": None}
    )
    return engine.transactions(engine.create(request, "demo"))


def test_last_month_matches_independent_raw_ledger_arithmetic() -> None:
    # Given: 카드 정산 및 이체가 섞인 실제 정규화 입력, 윤년 2월의 양쪽 경계 거래.
    rows = transactions()
    # When: 기준일이 3월일 때 지난달 소비를 요청한다.
    answer = spending_answer(date(2028, 3, 14), rows, "지난달 총 소비 얼마 썼어?")
    # Then: 정산 이중 합산 없이 원본에서 직접 확정한 세 소비만 집계된다.
    assert answer.status == "answered"
    assert (answer.start, answer.end) == (date(2028, 2, 1), date(2028, 2, 29))
    assert (answer.total_krw, answer.count) == (20000, 3)
    assert {row.envelope: (row.total_krw, row.count) for row in answer.rows} == {
        "외식": (12000, 1),
        "교통비": (5000, 1),
        "기타": (3000, 1),
    }
    assert answer.coverage == "unknown"
    assert answer.coverage_caveat


@pytest.mark.parametrize(
    ("question", "envelope", "total"),
    [
        ("지난달 외식비 얼마 썼어?", "외식", 12000),
        ("지난달 외식 소비를 다시 확인해줘.", "외식", 12000),
        ("내 지난달 교통비 알려줘", "교통비", 5000),
        ("지난달 기타 봉투 소비 알려주세요", "기타", 3000),
    ],
)
def test_exact_envelope_filter(question: str, envelope: str, total: int) -> None:
    # Given / When: 원장에 존재하는 정확한 봉투 한 개를 지정한다.
    answer = spending_answer(date(2028, 3, 14), transactions(), question)
    # Then: 다른 봉투 금액은 포함되지 않는다.
    assert answer.status == "answered"
    assert answer.total_krw == total
    assert tuple(row.envelope for row in answer.rows) == (envelope,)


@pytest.mark.parametrize(
    "question",
    [
        "지난달 스타벅스 지출 알려줘",
        "지난달 현금 소비 알려줘",
        "지난달 카드 사용액 알려줘",
        "지난달 외식 중 1만원 이상 지출 알려줘",
        "지난달 외식비와 교통비 비교해줘",
        "작년 지출 알려줘",
        "최근 30일 소비 알려줘",
        "지난달 주말 소비 알려줘",
        "지난달 고정비 포함 총지출 알려줘",
        "지난달 외식 빼고 소비 알려줘",
        "이번달 외식 빼고 소비를 다시 확인해줘",
        "앞으로 7일 지출 예측해줘",
        "지난달 커피값 알려줘",
        "소비 알려줘",
        "이번달 다른 사람 지출은 얼마야?",
        "이번달 너의 지출은 얼마야?",
    ],
)
def test_unsupported_period_or_filter_never_becomes_total(question: str) -> None:
    # Given / When: 지원하지 않는 기간, 가맹점, 결제수단, 비교 조건 또는 기간 누락.
    answer = spending_answer(date(2028, 3, 14), transactions(), question)
    # Then: 전체 합계나 미래 7일로 바꾸지 않는다.
    assert answer.status == "needs_clarification"
    assert answer.total_krw is None
    assert answer.rows == ()


@pytest.mark.parametrize(
    ("question", "start", "end", "total"),
    [
        ("이번달 소비 알려줘", date(2028, 3, 1), date(2028, 3, 14), 6000),
        ("오늘 소비 알려줘", date(2028, 3, 1), date(2028, 3, 1), 6000),
        ("어제 소비 알려줘", date(2028, 2, 29), date(2028, 2, 29), 5000),
        ("현재까지 총소비 알려줘", date(2028, 1, 31), date(2028, 3, 14), 26099),
    ],
)
def test_resolved_period_uses_reference_and_does_not_include_future(
    question: str,
    start: date,
    end: date,
    total: int,
) -> None:
    # Given: 오늘/어제는 3월 1일, 월간/누적 조회는 3월 14일을 기준으로 한다.
    reference = date(2028, 3, 1) if question.startswith(("오늘", "어제")) else date(2028, 3, 14)
    # When: 명시적인 달력 기간으로 조회한다.
    answer = spending_answer(reference, transactions(), question)
    # Then: 윤일 및 기준일 포함 경계를 그대로 사용한다.
    assert answer.status == "answered"
    assert (answer.start, answer.end, answer.total_krw) == (start, end, total)


def test_missing_month_is_not_zero_spending() -> None:
    # Given / When: 기록이 없는 2027년 12월을 조회한다.
    answer = spending_answer(date(2028, 1, 5), transactions(), "지난달 소비 알려줘")
    # Then: 미관측 기록을 0원으로 채우지 않는다.
    assert answer.status == "needs_data"
    assert answer.total_krw is None
    assert (answer.start, answer.end) == (date(2027, 12, 1), date(2027, 12, 31))


def test_duplicate_source_identity_does_not_double_spending() -> None:
    # Given: 같은 원장 거래가 두 번 전달된다.
    rows = transactions()
    # When: 중복 입력으로 월별 합계를 요청한다.
    answer = spending_answer(date(2028, 3, 14), (*rows, rows[0]), "지난달 소비 알려줘")
    # Then: 두 번 합산한 수치 대신 자료 확인을 요청한다.
    assert answer.status == "needs_data"
    assert answer.total_krw is None


@pytest.mark.parametrize(
    "question",
    [
        "이번 달 소비 내역을 알려줘",
        "이번달 소비 알려줘?",
        "이번달 소비 알려줘\uff1f",
        "이번 달 내 지출은 얼마야?",
        "이번 달 나의 지출은 얼마야?",
        "이번 달 저의 지출은 얼마야?",
    ],
)
def test_supported_sentence_variants_keep_same_scope(question: str) -> None:
    # Given / When: 조사와 문장부호만 다른 같은 소비 조회.
    answer = spending_answer(date(2028, 3, 14), transactions(), question)
    # Then: 기준일 이후의 33,000원은 모든 표현에서 제외된다.
    assert (answer.status, answer.total_krw, answer.count) == ("answered", 6000, 1)


@pytest.mark.parametrize("question", ["이번달 소비 알려줘", "현재까지 소비 알려줘"])
def test_no_observed_transactions_does_not_imply_zero(question: str) -> None:
    # Given / When: 수집 범위를 알 수 없고 연결된 거래가 전혀 없다.
    answer = spending_answer(date(2028, 3, 14), (), question)
    # Then: 미관측 소비를 0원으로 생성하지 않는다.
    assert (answer.status, answer.total_krw, answer.coverage) == ("needs_data", None, "unknown")


def test_inconsistent_budget_amount_requires_source_verification() -> None:
    # Given: 카드 정산을 소비 반영값 12,000원으로 손상시킨 입력.
    source = next(row for row in transactions() if row.id == "settlement")
    invalid = source.model_copy(update={"budget_amount_krw": 12000})
    # When: helper에 불일치 자료를 전달한다.
    answer = spending_answer(date(2028, 3, 14), (invalid,), "지난달 소비 알려줘")
    # Then: 합산하거나 조용히 누락하지 않고 자료 확인을 요청한다.
    assert (answer.status, answer.total_krw) == ("needs_data", None)


def test_invalid_record_date_is_not_an_unhandled_error() -> None:
    # Given: typed adapter 경계가 아닌 곳에서 손상된 날짜가 들어온다.
    invalid = transactions()[0].model_copy(update={"date": "2028-02-30"})
    # When: 해당 원장의 합계를 요청한다.
    answer = spending_answer(date(2028, 3, 14), (invalid,), "지난달 소비 알려줘")
    # Then: 잘못된 날짜로 금융 수치를 산출하지 않는다.
    assert (answer.status, answer.total_krw) == ("needs_data", None)
