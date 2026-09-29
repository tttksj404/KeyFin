"""연결된 확정 거래의 봉투 소비를 날짜와 함께 직접 합산한다."""

import re
from datetime import date, timedelta
from enum import StrEnum
from typing import Final, Literal, assert_never

from coaching_service.chart_projection import ENVELOPES
from coaching_service.schemas import Frozen, TransactionView
from coaching_service.word_segments import WordSegments

# 엔진 mapping.py 는 일상어 "외식비"·"식비"를 모두 "외식" 봉투로 접는다.
_ENVELOPE_PATTERN: Final = "|".join(re.escape(name) for name in (*ENVELOPES, "외식비", "식비"))
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
    r"(?:얼마(?:나)?(?:썼(?:어|나요|지|니)|사용했(?:어|나요)|나왔(?:어|나요)"
    r"|나갔(?:어|나요|지|니)|지출했(?:어|나요))?"
    r"|얼마(?:야|인가요|예요|지)|알려(?:줘|주세요)|보여(?:줘|주세요)|확인해(?:줘|주세요))"
    r"[?!.\uff1f\u3002]*"
)
# "교통비 이번달 얼마 썼어"처럼 봉투가 기간보다 먼저 오면 기간을 앞으로 옮겨 같은 문법에 태운다.
_ENVELOPE_FIRST: Final = re.compile(
    rf"(?P<envelope>{_ENVELOPE_PATTERN})(?P<box>봉투)?(?:은|는|의)?"
    r"(?P<period>지난달|이번달|이달|오늘|어제|현재까지|지금까지|현재)(?P<rest>.*)"
)


# Emoticon jamo and decorative marks ("ㅠㅠ", "ㅋㅋ", "~", "^^") carry no query meaning;
# the exact grammar below must not fail on them ("이번달 외식 얼마 썼어 ㅠㅠ").
_DECORATION: Final = re.compile(r"\s+|[\u3131-\u318e~^;…♡♥]+")


# 정확한 문법이 못 받는 일상 표현("어제 쓴 돈 총 얼마야?", "이번 달 외식비로 나간 돈 합계
# 보여줘", "지난달 총 소비 얼마였지?")은 기간 하나와 봉투 하나(또는 전체)만 뽑아 같은 문법의
# 표준 문장으로 바꾼다. 가맹점·결제수단·비교·예측 조건이 섞이면 바꾸지 않는다.
_LENIENT_PERIODS: Final[tuple[tuple[str, str], ...]] = (
    ("지난달", "지난달"), ("저번달", "지난달"), ("이번달", "이번달"), ("이달", "이번달"), ("오늘", "오늘"),
    ("어제", "어제"), ("지금까지", "지금까지"), ("현재까지", "현재까지"),
)
_LENIENT_ENVELOPES: Final[tuple[tuple[str, str], ...]] = (
    ("편의점·마트·잡화", "편의점·마트·잡화"), ("편의점마트잡화", "편의점·마트·잡화"),
    ("의료·건강", "의료·건강"),
    ("의료건강", "의료·건강"), ("취미·여가", "취미·여가"), ("취미여가", "취미·여가"), ("외식비", "외식"),
    ("식비", "외식"), ("외식", "외식"), ("교통비", "교통비"), ("교통", "교통비"), ("의료", "의료·건강"),
    ("취미", "취미·여가"), ("쇼핑", "쇼핑"), ("편의점", "편의점·마트·잡화"), ("마트", "편의점·마트·잡화"),
    ("잡화", "편의점·마트·잡화"), ("기타", "기타"), ("편의점비", "편의점·마트·잡화"),
    ("마트비", "편의점·마트·잡화"),
    ("쇼핑비", "쇼핑"), ("의료비", "의료·건강"), ("병원비", "의료·건강"), ("취미비", "취미·여가"),
    ("여가비", "취미·여가"),
)
_LENIENT_SPEND: Final = re.compile(
    r"썼|쓴|나간|나갔|나왔|지출|소비|사용했|사용한|사용내역|내역|결제했|결제한|했더라|찍혔|찍힌"
    # "지난달 편의점비 얼마였어": an envelope's cost word names the spending itself.
    r"|(?:외식|교통|편의점|마트|쇼핑|의료|병원|취미|여가)비(?:는|가|이|로)?(?:총|전체)?얼마|식비(?:는|가|로)?(?:총)?얼마"
    r"|기록|spending|지출액|소비액|샀|들었|들어갔|씀|결제한거"
)
_LENIENT_ASK: Final = re.compile(
    r"얼마|총액|합계|금액|알려|보여|궁금|확인|어떻게|내역|봐|볼래|뭐|몇|기록|(?:지출|소비)(?:액)?(?:은|는)[?!.]*$"
)
_LENIENT_BLOCK: Final = re.compile(
    r"것같|거같|될까|나올까|나올지|예측|예상|전망|위험|리스크|수준|쓸까|쓰게|갈것|남을|남았|남은|예산"
    r"|이번주|지난주|저번주|주말|올해|작년"
    r"|[0-9]+월|[0-9]+일|분기|비교|차이|가맹점|카드|현금|계좌|통장|제외|말고|빼고|평균|매달|매일|몇번|몇건|건수"
    r"|기록해|기록하|기록할|어떻게해"
)


# Everything else a lenient spending question may contain. Anything left over (a merchant,
# an amount condition, another person, "고정비 포함") keeps the exact grammar's refusal.
_LENIENT_WORDS: Final = tuple(sorted({
    "얼마나갔어", "얼마나갔", "얼마나왔어", "얼마나왔", "얼마나썼어", "썼는지", "썼어", "썼나",
    "썼지", "썼", "쓴돈", "쓴", "나간돈", "나간", "나갔는지", "나갔어", "나갔", "나왔어", "나왔",
    "지출", "소비한", "소비", "사용했", "사용한", "결제했", "결제한", "했더라", "했어", "찍혔어",
    "찍혔", "찍힌", "얼마나", "얼마인지", "얼마", "총액", "합계", "금액", "알려주실래요",
    "알려줄래", "알려주세요", "알려줘", "알려", "보여주세요", "보여줘", "보여", "궁금해", "궁금",
    "확인해줘", "확인", "알아", "알수있어", "혹시", "좀", "총", "전부", "모두", "전체", "합쳐서",
    "하루", "돈", "쪽으로", "쪽", "에서", "으로", "로", "에", "은", "는", "이", "가", "을", "를",
    "의", "였는지", "였어", "였지", "였더라", "이었어", "인지", "는지", "있어", "야", "요", "줘",
    "지", "어", "해", "한", "?", "!", ".", ",",
    # "오늘 썼던 거 알려줄래", "지난달 교통비 지출 보여줄래", "지난달 기타 사용내역 봐", "뭐 썼냐"
    "썼던거", "썼던", "쓴거", "거", "보여줄래요", "보여줄래", "보여줄수있을까요", "보여줄수있어",
    "알려줄수있을까요", "어떻게", "사용내역", "내역", "봐줘", "볼래", "봐", "자세히", "뭐", "썼냐",
    "였어요", "였나요", "기록", "항목", "spending", "됐어", "예요", "이에요",
    "지출액", "소비액", "지출한", "다", "있어요", "지출은", "소비는",
    # Degree, grouping and time fillers name no merchant or condition ("어제 가장 많이 쓴 항목이
    # 뭐고 얼마였어요?", "이번 달 쇼핑 항목별 지출이 몇인가요?", "오늘 하루 동안 지출한 내역").
    "가장", "제일", "많이", "몇", "대략", "대충", "항목별", "봉투별", "동안", "뭐고", "인가요",
    "있나요", "있었어", "몇인가요", "정도",
    # "지난달 외식 지출 정리해줘", "지난달 외식 히스토리?", "취미·여가 사용액은 몇 원입니까?"
    "정리해줘", "정리해", "정리", "히스토리", "사용액", "사용", "몇원입니까", "입니까", "궁금해요", "봐줄래",
    "알려줄수있어", "총액은", "얼마였는지",
    "샀어", "샀지", "샀는지", "샀", "들었어", "들어갔어", "씀", "결제한거", "결제한것",
}, key=len, reverse=True))

# Lenient wording must split completely into allowed words, each followed only by particles
# or endings. Erasing words anywhere let a filter hide ("요가에" lost 가·에 and read as a
# total); a leftover syllable now keeps the exact grammar's refusal.
_LENIENT_PARTICLES: Final = (
    "에서", "으로", "이었어", "였는지", "였더라", "였어", "였지", "인지", "는지",
    "은", "는", "이", "가", "을", "를", "에", "로", "의", "도", "만", "요", "야", "지", "어", "해", "한",
)
_LENIENT_MAX: Final = 60


# One particle or ending per word, optionally followed by a topic marker ("외식비로는").
_LENIENT_FULL: Final = WordSegments(
    tuple(word for word, _ in _LENIENT_PERIODS)
    + tuple(word for word, _ in _LENIENT_ENVELOPES)
    + tuple(word for word in _LENIENT_WORDS if word not in _LENIENT_PARTICLES and word not in "?!.,"),
    _LENIENT_PARTICLES,
)


def _lenient(compact: str, *, intent_known: bool = False) -> str | None:  # noqa: C901, PLR0911 - one return per refusal.
    compact = compact.replace("이번달지금까지", "이번달").replace("이달지금까지", "이번달")
    compact = compact.replace("이번달현재까지", "이번달").replace("이달현재까지", "이번달")
    # Once the turn is a spending lookup, "지난달 외식?" needs neither a spending verb nor an ask.
    if not intent_known and (_LENIENT_SPEND.search(compact) is None or _LENIENT_ASK.search(compact) is None):
        return None
    periods = {canonical for word, canonical in _LENIENT_PERIODS if word in compact}
    if intent_known and periods == {"이번달", "지금까지"}:
        periods = {"이번달"}  # "이번 달 spending 지금까지 얼마야"
    if len(periods) != 1:
        return None
    rest = compact
    for word, _ in _LENIENT_PERIODS:
        rest = rest.replace(word, " ")
    if _LENIENT_BLOCK.search(rest) is not None:
        return None
    envelopes: set[str] = set()
    for word, envelope in _LENIENT_ENVELOPES:
        if word in rest:
            envelopes.add(envelope)
            rest = rest.replace(word, " ")
    if len(envelopes) > 1:
        return None
    if "하루" in compact and not periods & {"오늘", "어제"}:
        return None  # "하루에 얼마 썼어" asks a daily average, not a period total
    plain = re.sub(r"[?!.,]", "", compact)
    if len(plain) > _LENIENT_MAX or not _LENIENT_FULL.covers(plain):
        return None
    candidate = next(iter(periods)) + next(iter(envelopes), "") + "소비얼마야"
    return candidate if _QUERY.fullmatch(candidate) is not None else None


def _canonical(question: str) -> str:
    compact = _DECORATION.sub("", question)
    found = _ENVELOPE_FIRST.fullmatch(compact)
    if found is not None:
        compact = found["period"] + found["envelope"] + (found["box"] or "") + found["rest"]
    if _QUERY.fullmatch(compact) is not None:
        return compact
    return _lenient(compact) or compact


# 채팅 말풍선에 붙는 한 문장짜리 정직성 문구. 전체 근거·범위는 아래 _COVERAGE가
# coverage_caveat 구조화 필드로 그대로 보존해 앱이 작은 글씨·툴팁으로 노출할 수 있다.
_COVERAGE_SHORT: Final = "연결된 확정 거래 기준이라 월 전체·전 계좌 합계와 다를 수 있어요."
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


def history_question(question: str) -> str | None:
    """Once the turn is a spending lookup, "이번 달 지금까지 얼마?" needs no spending verb of its own.

    Only the period and the envelope are read; every other word must still be one the
    lookup can honour, so a merchant, payment or comparison is asked about, not dropped.
    """
    return _lenient(_DECORATION.sub("", question), intent_known=True)


def supports_spending_question(question: str) -> bool:
    """Return whether the existing exact aggregate grammar can answer this turn.

    The dialogue router uses this same predicate only to skip an LLM intent call.
    It deliberately does not broaden the supported language: ``spending_answer``
    remains the single parser that decides the calculation scope and can still
    return ``needs_data`` when the connected ledger cannot prove an amount.
    """
    return _QUERY.fullmatch(_canonical(question)) is not None


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
    query = _QUERY.fullmatch(_canonical(question))
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
    envelope = "외식" if envelope in ("외식비", "식비") else envelope
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
        f"봉투별 내역: {details}. {_COVERAGE_SHORT}"
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
