"""FDT 분류 함수를 호출하지 않고 원거래에서 7봉투 평가 정답을 합산한다."""

import json
from datetime import date
from hashlib import sha256
from typing import Final

from coaching_service.errors import ServiceError
from coaching_service.forecast_validation_month_contracts import EnvelopeObservation
from coaching_service.forecast_validation_observations import RawTransaction, consumption_amount
from coaching_service.forecast_validation_values import ENVELOPES, EnvelopeName

__all__ = ["ENVELOPES", "consumption_amount", "envelope_for", "observed_envelopes", "window_digest"]

# 원천 CSV 라벨의 명시적 평가 규약이다. 정답 계산은 vendor.mapping/normalize를 가져오지 않는다.
SUBCATEGORIES: Final[dict[EnvelopeName, frozenset[str]]] = {
    "외식": frozenset({
        "점심", "저녁/외식", "가족 외식", "고객 미팅", "빵·간식", "간식", "반찬", "모임",
        "카페", "배달", "주점",
    }),
    "교통비": frozenset({"대중교통", "기차", "택시", "대리운전", "주차", "주유"}),
    "의료·건강": frozenset({"병원", "약국", "한의원", "안경", "건강식품", "헬스장", "수영"}),
    "취미·여가": frozenset({
        "영화/공연", "전시", "관람", "스포츠 관람", "게임", "노래방", "숙박", "놀이공원",
        "키즈카페", "문화센터",
    }),
    "쇼핑": frozenset({"의류", "선물", "미용", "뷰티·건강", "장난감"}),
    "편의점·마트·잡화": frozenset({"편의점", "장보기", "생활용품", "학용품"}),
    "기타": frozenset({
        "도서", "온라인 강의", "스터디카페", "시험 응시료", "등록금", "자녀 캠프", "자녀 학원", "해외 결제",
        "경조사", "회비", "가족 생활비", "가족 용돈", "연금", "종교", "기부", "세차",
    }),
}
CATEGORIES: Final[dict[str, EnvelopeName]] = {
    "식비": "외식", "교통": "교통비", "건강": "의료·건강", "여가·문화": "취미·여가",
    "쇼핑": "쇼핑", "생활서비스": "쇼핑", "교육": "기타", "사회·경조": "기타",
    "주거·통신": "기타", "세금·공과": "기타", "보험": "기타", "업무": "기타",
}


def envelope_for(row: RawTransaction) -> EnvelopeName:
    for envelope, labels in SUBCATEGORIES.items():
        if row.subcategory in labels:
            return envelope
    return CATEGORIES.get(row.category, "기타")


def observed_envelopes(
    rows: tuple[RawTransaction, ...], start: date, end: date,
) -> tuple[EnvelopeObservation, ...]:
    totals: dict[EnvelopeName, list[int]] = {name: [0, 0, 0, 0] for name in ENVELOPES}
    for row in rows:
        if not start <= row.transaction_date <= end:
            continue
        amount = consumption_amount(row)
        if amount is None:
            raise ServiceError("validation_unresolved_transactions", 409)
        if amount == 0:
            continue
        values = totals[envelope_for(row)]
        values[0] += amount
        values[1] += 1
        # 소비 예측의 정답에는 포함되지만 봉투 예산에서 제외되는 소비를 구분한다.
        if row.exclude_tag == "NONE":
            values[2] += amount
            values[3] += 1
    return tuple(
        EnvelopeObservation(
            envelope=name, consumption_krw=values[0], consumption_count=values[1],
            budget_used_krw=values[2], budget_transaction_count=values[3],
            budget_excluded_consumption_krw=values[0] - values[2],
        )
        for name, values in totals.items()
    )


def window_digest(rows: tuple[RawTransaction, ...], start: date, end: date) -> str:
    """동일 합계의 재분류·취소·교체도 감지하며 평가 월 이후 거래는 제외한다."""
    selected = sorted(
        (row for row in rows if start <= row.transaction_date <= end),
        key=lambda row: row.transaction_id,
    )
    raw = json.dumps([row.model_dump(mode="json") for row in selected], ensure_ascii=False, sort_keys=True)
    return sha256(raw.encode()).hexdigest()
