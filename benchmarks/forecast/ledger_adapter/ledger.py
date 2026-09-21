"""Independent raw-ledger inclusion and calendar arithmetic; imports no FDT code."""

from __future__ import annotations

import calendar
import csv
from datetime import date
from typing import TYPE_CHECKING, Final

from .contracts import LedgerRow, Period

if TYPE_CHECKING:
    from pathlib import Path

ENVELOPES: Final = ("외식", "교통비", "의료·건강", "취미·여가", "쇼핑", "편의점·마트·잡화", "기타")
FIXED_LABELS: Final = frozenset((
    "월세", "관리비", "전기요금", "가스요금", "수도요금", "통신", "인터넷", "실손보험",
    "사회보험", "자동차세", "구독", "코워킹",
))
ENVELOPE_LABELS: Final = (
    ("외식", "점심,저녁/외식,가족 외식,고객 미팅,빵·간식,간식,반찬,모임,카페,배달,주점"),
    ("교통비", "대중교통,기차,택시,대리운전,주차,주유"),
    ("의료·건강", "병원,약국,한의원,안경,건강식품,헬스장,수영"),
    ("취미·여가", "영화/공연,전시,관람,스포츠 관람,게임,노래방,숙박,놀이공원,키즈카페,문화센터"),
    ("쇼핑", "의류,선물,미용,뷰티·건강,장난감"),
    ("편의점·마트·잡화", "편의점,장보기,생활용품,학용품"),
    ("기타", (
        "도서,온라인 강의,스터디카페,시험 응시료,등록금,자녀 캠프,자녀 학원,해외 결제,"
        "경조사,회비,가족 생활비,가족 용돈,연금,종교,기부,세차"
    )),
)
CATEGORY_ENVELOPES: Final = {
    "식비": "외식", "교통": "교통비", "건강": "의료·건강", "여가·문화": "취미·여가",
    "쇼핑": "쇼핑", "생활서비스": "쇼핑",
}


def read_ledger(path: Path) -> tuple[LedgerRow, ...]:
    """Keep typed financial columns only; source persona columns never leave CSV."""
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return tuple(LedgerRow.model_validate(raw) for raw in csv.DictReader(stream))


def month_period(year: int, month: int) -> Period:
    return Period(date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1]))


def spending(row: LedgerRow) -> bool:
    """Classify purchase-time outflow from explicit raw ledger fields."""
    return (
        row.status == "NORMAL"
        and row.direction == "EXPENSE"
        and row.transaction_type not in {"CARD_BILL", "CARD_SETTLEMENT"}
        and row.subcategory not in {"ATM 출금", "대출 상환"}
        and row.exclude_tag not in {"INTERNAL_TRANSFER", "SELF_TRANSFER"}
        and not (row.transaction_type in {"TRANSFER", "TRANSFER_OUT"} and row.category == "저축·투자")
    )


def fixed(row: LedgerRow) -> bool:
    return spending(row) and row.subcategory in FIXED_LABELS and row.confirm_status != "PENDING"


def envelope(row: LedgerRow) -> str | None:
    if not spending(row) or fixed(row) or row.confirm_status == "PENDING":
        return None
    for name, labels in ENVELOPE_LABELS:
        if row.subcategory in labels.split(","):
            return name
    return CATEGORY_ENVELOPES.get(row.category, "기타")


def totals(rows: tuple[LedgerRow, ...], period: Period) -> tuple[int, int, int]:
    """Return raw consumption, confirmed budget consumption, and fixed spending."""
    selected = tuple(row for row in rows if period.start <= row.transaction_date <= period.end)
    consumption = sum(row.amount_krw for row in selected if spending(row) and not fixed(row))
    budgeted = sum(row.amount_krw for row in selected if envelope(row) and row.exclude_tag == "NONE")
    fixed_spend = sum(row.amount_krw for row in selected if fixed(row))
    return consumption, budgeted, fixed_spend


def envelope_amount(rows: tuple[LedgerRow, ...], period: Period, name: str) -> tuple[int, int]:
    selected = tuple(
        row for row in rows if period.start <= row.transaction_date <= period.end and envelope(row) == name
    )
    return sum(row.amount_krw for row in selected), sum(
        row.amount_krw for row in selected if row.exclude_tag == "NONE"
    )
