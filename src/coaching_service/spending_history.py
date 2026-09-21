"""연결된 확정 거래의 봉투 소비를 날짜와 함께 직접 합산한다."""

import re
from datetime import date, timedelta
from enum import StrEnum
from typing import Final, Literal, assert_never

from coaching_service.chart_projection import ENVELOPES
from coaching_service.schemas import Frozen, TransactionView

_ENVELOPE_PATTERN: Final = "|".join(re.escape(name) for name in (*ENVELOPES, "외식비"))
# 부분 키워드 일치는 가맹점·현금·제외 조건을 지워 전체 합계로 바꿀 수 있다.
# 지원하는 문장 전체가 맞아야 집계하며, 나머지는 명확한 조건을 다시 요청한다.
_QUERY: Final = re.compile(
    r"(?:내가|제가|나의|저의|내)?"
    r"(?P<period>지난달|이번달|이달|오늘|어제|현재까지|지금까지|현재)"
    r"(?:동안|까지|의|에)?"
    r"(?:나의|저의|내)?"
    rf"(?P<envelope>{_ENVELOPE_PATTERN})?(?:봉투)?(?:에서|으로|에|의|는|은)?"
    r"(?:(?:전체|총|누적)?(?:소비|지출|사용|결제)(?:액|금액|내역)?|쓴돈|쓴금액)?"
    r"(?:이|가|은|는|을|를)?(?:다시)?"
    r"(?:얼마(?:나)?(?:썼(?:어|나요|지|니)|사용했(?:어|나요)|나왔(?:어|나요))?"
    r"|얼마(?:야|인가요|예요|지)|알려(?:줘|주세요)|보여(?:줘|주세요)|확인해(?:줘|주세요))"
    r"[?!.\uff1f\u3002]*"
)
_COVERAGE: Final = (
    "연결된 거래에서 확인된 7봉투 소비만 집계했습니다. "
    "고정비·본인계좌 이체·카드 대금 정산·현금 인출·대출 상환과 취소·미확정·제외 거래는 포함하지 않습니다. "
    "자료의 수집 시작일과 누락 여부를 알 수 없어 월 전체 또는 모든 계좌의 소비 합계로 확정할 수 없습니다. "
    "거래가 없는 날짜를 0원으로 채우지 않았습니다."
)


class SpendingRow(Frozen):
    envelope: str
    total_krw: int
    count: int


class SpendingSummary(Frozen):
    status: Literal["answered", "needs_clarification", "needs_data"]
    text: str
    reference: date
    start: date | None = None
    end: date | None = None
    total_krw: int | None = None
    count: int = 0
    rows: tuple[SpendingRow, ...] = ()
    coverage: Literal["unknown"] = "unknown"
    coverage_caveat: str = _COVERAGE
    basis: Literal["confirmed_envelope_budget_amount"] = "confirmed_envelope_budget_amount"


class _Period(StrEnum):
    LAST_MONTH = "지난달"
    THIS_MONTH = "이번달"
    MONTH = "이달"
    TODAY = "오늘"
    YESTERDAY = "어제"
    THROUGH_NOW = "현재까지"
    UNTIL_NOW = "지금까지"
    CURRENT = "현재"


def supports_spending_question(question: str) -> bool:
    """Return whether the existing exact aggregate grammar can answer this turn.

    The dialogue router uses this same predicate only to skip an LLM intent call.
    It deliberately does not broaden the supported language: ``spending_answer``
    remains the single parser that decides the calculation scope and can still
    return ``needs_data`` when the connected ledger cannot prove an amount.
    """
    return _QUERY.fullmatch(re.sub(r"\s+", "", question)) is not None


def _bounds(reference: date, period: _Period, observed: tuple[date, ...]) -> tuple[date | None, date]:
    """달력 월·하루·현재까지를 구분하고 기준일 이후는 읽지 않는다."""
    match period:
        case _Period.LAST_MONTH:
            end = reference.replace(day=1) - timedelta(days=1)
            return end.replace(day=1), end
        case _Period.YESTERDAY:
            day = reference - timedelta(days=1)
            return day, day
        case _Period.THIS_MONTH | _Period.MONTH:
            return reference.replace(day=1), reference
        case _Period.TODAY:
            return reference, reference
        case _Period.THROUGH_NOW | _Period.UNTIL_NOW | _Period.CURRENT:
            # 첫 거래일은 고객의 거래 개시일이나 수집 범위의 보장이 아니다.
            return min(observed) if observed else None, reference
        case unreachable:
            assert_never(unreachable)


def spending_answer(
    reference: date, transactions: tuple[TransactionView, ...], question: str
) -> SpendingSummary:
    """지원 범위를 벗어난 질문에는 수치를 생성하지 않는 과거 소비 조회.

    FDT budget_amount_krw는 확정 expense 중 소비 제외 태그가 없는 7봉투
    금액이다. 제삼자 TRANSFER_OUT 소비는 포함될 수 있으므로 거래의 원 타입을
    이체라는 이유로 일괄 제외하지 않는다. 반환값은 완전한 원장 범위를 보장하지 않는다.
    """
    query = _QUERY.fullmatch(re.sub(r"\s+", "", question))
    if query is None:
        return SpendingSummary(
            status="needs_clarification",
            reference=reference,
            text="지난달·이번 달·오늘·어제·현재까지 중 기간과 전체 소비 또는 정확한 봉투 이름을 알려주세요. "
            "가맹점·결제수단·금액 조건·제외·비교 조회는 현재 지원하지 않습니다.",
        )
    try:
        dated = tuple((date.fromisoformat(row.date), row) for row in transactions)
        observed = tuple(day for day, _ in dated if day <= reference)
        start, end = _bounds(reference, _Period(query.group("period")), observed)
    except (ValueError, OverflowError):
        return SpendingSummary(
            status="needs_data",
            reference=reference,
            text="거래 날짜와 기준일을 확인한 뒤 다시 조회해 주세요.",
        )
    if len({row.id for row in transactions}) != len(transactions) or any(
        row.budget_amount_krw < 0
        or (
            row.budget_amount_krw > 0
            and (row.kind != "expense" or not row.active or row.pending or row.envelope not in ENVELOPES)
        )
        for row in transactions
    ):
        return SpendingSummary(
            status="needs_data",
            reference=reference,
            start=start,
            end=end,
            text="중복 거래 또는 소비 반영값의 불일치가 있어 원장 확인이 필요합니다.",
        )
    envelope = query.group("envelope")
    envelope = "외식" if envelope == "외식비" else envelope
    matched = tuple(
        row
        for day, row in dated
        if start is not None
        and start <= day <= end
        and row.active
        and not row.pending
        and row.kind == "expense"
        and row.budget_amount_krw > 0
        and (envelope is None or row.envelope == envelope)
    )
    if not matched:
        return SpendingSummary(
            status="needs_data",
            reference=reference,
            start=start,
            end=end,
            text="요청 범위에 집계할 확정 봉투 소비 기록이 없습니다. "
            "기록이 없다는 이유로 실제 소비가 0원이라고 판단할 수 없어 거래 연결 범위를 확인해야 합니다.",
        )
    rows = tuple(
        SpendingRow(
            envelope=name,
            total_krw=sum(row.budget_amount_krw for row in matched if row.envelope == name),
            count=sum(row.envelope == name for row in matched),
        )
        for name in ENVELOPES
        if any(row.envelope == name for row in matched)
    )
    total = sum(row.total_krw for row in rows)
    details = ", ".join(f"{row.envelope} {row.total_krw:,}원({row.count}건)" for row in rows)
    text = (
        f"{start}부터 {end}까지 연결된 확정 봉투 소비는 {total:,}원, {len(matched)}건입니다. "
        f"봉투별 내역: {details}. {_COVERAGE}"
    )
    return SpendingSummary(
        status="answered",
        reference=reference,
        text=text,
        start=start,
        end=end,
        total_krw=total,
        count=len(matched),
        rows=rows,
    )
