"""A separate future-outcome calculator for forecast evaluation.

This module deliberately does not import the FDT normalizer, simulator, or the
forecast input classifier.  It keeps the settled-outcome definition readable
and independently testable: a normal confirmed variable purchase remains
consumption even when its budget tag excludes it from an envelope balance.
It is a second implementation of the product specification, not a human
approved oracle.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from benchmarks.forecast.ledger_adapter.contracts import LedgerRow

FIXED_SUBCATEGORIES: Final = frozenset((
    "월세", "관리비", "전기요금", "가스요금", "수도요금", "통신", "인터넷", "실손보험",
    "사회보험", "자동차세", "구독", "코워킹",
))
SUBCATEGORY_ENVELOPES: Final = {
    "음식점": "외식", "카페": "외식", "배달": "외식", "주점": "외식",
    "대중교통": "교통비", "택시": "교통비", "주유": "교통비",
    "병원·약국": "의료·건강", "운동·헬스": "의료·건강",
    "영화·공연·전시": "취미·여가", "스포츠 관람": "취미·여가",
    "게임·콘텐츠": "취미·여가", "여행·숙박": "취미·여가",
    "패션·잡화": "쇼핑", "뷰티": "쇼핑", "온라인 쇼핑": "쇼핑",
    "편의점": "편의점·마트·잡화", "마트": "편의점·마트·잡화", "생활용품": "편의점·마트·잡화",
    "교육": "기타", "해외 결제": "기타", "경조사·기타": "기타",
    "점심": "외식", "저녁/외식": "외식", "가족 외식": "외식", "고객 미팅": "외식",
    "빵·간식": "외식", "간식": "외식", "반찬": "외식", "모임": "외식",
    "기차": "교통비", "대리운전": "교통비", "주차": "교통비",
    "병원": "의료·건강", "약국": "의료·건강", "한의원": "의료·건강", "안경": "의료·건강",
    "건강식품": "의료·건강", "헬스장": "의료·건강", "수영": "의료·건강",
    "영화/공연": "취미·여가", "전시": "취미·여가", "관람": "취미·여가",
    "노래방": "취미·여가", "숙박": "취미·여가", "놀이공원": "취미·여가",
    "키즈카페": "취미·여가", "문화센터": "취미·여가",
    "의류": "쇼핑", "선물": "쇼핑", "미용": "쇼핑", "뷰티·건강": "쇼핑", "장난감": "쇼핑",
    "장보기": "편의점·마트·잡화", "학용품": "편의점·마트·잡화",
    "도서": "기타", "온라인 강의": "기타", "스터디카페": "기타", "시험 응시료": "기타",
    "등록금": "기타", "자녀 캠프": "기타", "자녀 학원": "기타", "경조사": "기타",
    "회비": "기타", "가족 생활비": "기타", "가족 용돈": "기타", "연금": "기타",
    "종교": "기타", "기부": "기타", "세차": "기타",
}
CATEGORY_ENVELOPES: Final = {
    "식비": "외식", "교통": "교통비", "건강": "의료·건강", "여가·문화": "취미·여가",
    "쇼핑": "쇼핑", "생활서비스": "쇼핑",
}


def settled_consumption_envelope(row: LedgerRow) -> str | None:
    """Return the settled variable-consumption envelope under the frozen target.

    ``DUTCH``, ``EMERGENCY``, and ``CARRYOVER`` purchases are intentionally
    retained.  They differ from the monthly budget-use target but belong in the
    FDT's total variable-consumption forecast and its future truth.
    """
    if (
        row.status != "NORMAL"
        or row.confirm_status == "PENDING"
        or row.direction != "EXPENSE"
        or row.transaction_type in {"CARD_BILL", "CARD_SETTLEMENT"}
        or row.subcategory in FIXED_SUBCATEGORIES | {"ATM 출금", "대출 상환"}
        or row.exclude_tag in {"INTERNAL_TRANSFER", "SELF_TRANSFER"}
        or (row.transaction_type in {"TRANSFER", "TRANSFER_OUT"} and row.category == "저축·투자")
    ):
        return None
    return SUBCATEGORY_ENVELOPES.get(row.subcategory, CATEGORY_ENVELOPES.get(row.category, "기타"))
