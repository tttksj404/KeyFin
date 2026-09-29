"""Bounded Korean period recognition; unsupported or conflicting periods never become seven days."""

import calendar
import re
from datetime import date
from typing import Final

from pydantic import ValidationError

from coaching_service.admission import RequestCost
from coaching_service.errors import ServiceError
from coaching_service.periods import (
    MonthEnd,
    NextMonthEnd,
    PeriodSource,
    PeriodSpec,
    ResolvedPeriod,
    RollingDays,
    ThroughDate,
    budget_cycle,
    resolve_period,
)
from coaching_service.schemas import JsonDocument

_PERIOD: Final = re.compile(
    r"(?P<date>\d{4}-\d{2}-\d{2})\s*(?:마감\s*)?(?:까지|에(?!서))"
    # "이번 달까지", "이번 달 안에", "월말 전에", "다음달까지" name the same month end.
    r"|(?P<month>(?:이번\s*달|이달)(?:\s*말)?(?:\s*(?:까지|에|안에|내에|중에))?"
    r"|월말(?:\s*전(?:에|까지)?)?(?:\s*(?:까지|에))?)"
    r"|(?P<next_month>다음\s*달(?:\s*말)?(?:\s*(?:까지|에|안에|내에|중에))?)"
    r"|(?P<inclusive>기준일\s*(?:부터|포함))\s*(?P<included_days>\d{1,3})\s*일"
    r"|(?<![\d./-])(?P<ahead>앞으로\s*)?(?P<days>\d{1,3})\s*일"
    r"(?P<suffix>\s*(?:뒤|후|동안|간))?(?![\d])"
)
_UNRESOLVED: Final = re.compile(
    r"\d\s*[-./]\s*\d|\d\s*(?:개월|달|월|년|주|일)|한\s*달|한\s*개월|석\s*달|세\s*달"
    r"|다음\s*(?:달|주|해|월)|내년|내일|모레|오늘|금일|주말|월초|월말|월중"
    r"|목표일까지|윤달|음력|영업일|공휴일"
    r"|이틀|사흘|나흘|닷새|엿새|이레|열흘|보름|일주일|반년|올해|연말|분기|상반기|하반기"
)
_MODIFIED: Final = re.compile(
    r"^\s*(?:부터|까지|이내|미만|이상|이전|이후|말고|아니라"
    r"|전(?:[\s,.?!]|$|에|의)|초(?:순|[\s,.?!]|$|에|의)|중(?:순|[\s,.?!]|$|에|의))"
)
_UNSUPPORTED_CALENDAR: Final = re.compile(r"윤달|음력|영업일|공휴일")
# "주말에 뭐하지?" / "오늘 뭐 먹지?" ask what to do, not a period.
_ACTIVITY_TIME: Final = re.compile(
    r"(?:주말|오늘|내일|이번\s*주말)\s*(?:에|에는)?\s*뭐\s*(?:하지|할까|해|하니|먹지|먹을까)(?![가-힣])"
)
# "이번 달 중순을 지났는데 …" says where in the month today is; the period asked is still this month.
_MONTH_POSITION: Final = re.compile(
    r"(?<=달)\s*(?:도\s*)?(?:중순|초순|하순|초|중반|후반)(?:을|이|쯤|은)?\s*"
    r"(?:지났는데|지나서|넘었는데|넘어서|인데|이라서|이니까|이라|지나고)"
)
# "다음 주부터 매일 택시 타면 이번 달 적자야?": the start of a habit, not the period asked about.
_HABIT_START: Final = re.compile(
    r"(?:오늘|내일|모레|다음\s*주|이번\s*주|주말)\s*부터(?!\s*\d{1,3}\s*일)"
    r"(?=.{0,20}?(?:타면|시키면|먹으면|가면|쓰면|하면|사면|내면|다니면|마시면))"
)


# "9월 말에 얼마 남을까?" names the month by number; relative to the reference date it is this
# month or the next one. "9월 30일까지" names a day. Other months stay unresolved.
_NAMED_DAY: Final = re.compile(
    r"(?<![\d./-])(?P<month>\d{1,2})\s*월\s*(?P<day>\d{1,2})\s*일(?=\s*(?:마감\s*)?(?:까지|에))"
)
_NAMED_MONTH: Final = re.compile(r"(?<![\d./-])(?P<month>\d{1,2})\s*월(?!\s*\d)(?P<end>\s*말)?")


def named_calendar(question: str, reference: date, budget_start_day: int = 1) -> str:
    """Rewrite a numbered month or day into the period words the parser supports."""
    def day(found: re.Match[str]) -> str:
        month, number = int(found.group("month")), int(found.group("day"))
        year = reference.year + (month < reference.month)
        if not 1 <= month <= 12 or not 1 <= number <= calendar.monthrange(year, month)[1]:
            return found.group(0)
        return date(year, month, number).isoformat()

    def month(found: re.Match[str]) -> str:
        number = int(found.group("month"))
        following = reference.month % 12 + 1
        if number not in (reference.month, following):
            return found.group(0)
        end = found.group("end") or ""
        if budget_start_day == 1:
            return ("이번 달" if number == reference.month else "다음 달") + end
        if not end:
            # A budget month that starts mid-month is not the calendar month "9월" names.
            return found.group(0)
        year = reference.year + (number < reference.month)
        last = date(year, number, calendar.monthrange(year, number)[1]).isoformat()
        return last if re.match(r"\s*(?:까지|에(?!서))", found.string[found.end():]) else f"{last}까지"

    return _NAMED_MONTH.sub(month, _NAMED_DAY.sub(day, question))


def question_period(question: str, *, explicit: bool) -> PeriodSpec | None:  # noqa: C901 - 지원 기간 표현이 하나씩 늘며 분기가 누적된 단일 파서; 분해보다 한 곳 유지가 안전하다.
    """지원하는 명확한 한국어 기간 하나만 해석한다.

    여러 기간·음력·영업일은 422로 재확인을 요구한다. 그 밖의 모호한 표현은
    명시적 구조화 기간이 있을 때만 맡기며 임의로 기본 7일로 바꾸지 않는다.
    """
    if _UNSUPPORTED_CALENDAR.search(question):
        raise ServiceError("period_unsupported_calendar")
    question = _MONTH_POSITION.sub(" ", _ACTIVITY_TIME.sub(" ", _HABIT_START.sub(" ", question)))
    matches = list(_PERIOD.finditer(question))
    if len(matches) > 1 and not all(match.group("month") for match in matches):
        # "이번 달 … 월말 잔액" names this month end twice; different periods still conflict.
        raise ServiceError("period_clarification_required")
    if len(matches) > 1:
        matches = matches[:1]
    remaining = _PERIOD.sub("", question)
    modified = bool(matches and _MODIFIED.search(question[matches[0].end():]))
    if not explicit and (_UNRESOLVED.search(remaining) or modified):
        raise ServiceError("period_clarification_required")
    if not matches:
        return None
    found = matches[0]
    if found.group("days") and not (found.group("ahead") or found.group("suffix")):
        raise ServiceError("period_clarification_required")
    try:
        if found.group("date"):
            return ThroughDate.model_validate({"end_date": found.group("date")})
        if found.group("month"):
            return MonthEnd()
        if found.group("next_month"):
            return NextMonthEnd()
        if found.group("inclusive"):
            return RollingDays(days=int(found.group("included_days")), include_reference_date=True)
        return RollingDays(days=int(found.group("days")))
    except ValidationError:
        raise ServiceError("invalid_question_period") from None


def _default_spec(reference: date, budget_start_day: int) -> PeriodSpec:
    """Period-less turns follow the budget cycle; its last day keeps the 7-day default."""
    _, cycle_end = budget_cycle(reference, budget_start_day)
    if cycle_end > reference:
        return MonthEnd()
    return RollingDays(days=7)


def turn_period(
    reference: date,
    question: str,
    explicit: PeriodSpec | None,
    analysis: JsonDocument | None,
    budget_start_day: int = 1,
) -> ResolvedPeriod:
    """명시적 기간→질문→추가 분석 순으로 선택하되 서로 다른 종료일은 거부한다.

    기간 정보가 전혀 없으면 현재 예산 주기(기준일~주기 말)를 기본으로 해, 항상
    예산 월을 그리는 차트와 답변 기간이 어긋나지 않게 한다. 주기 마지막 날에는 남은
    미래 일이 없으므로 7일 롤링을 쓴다. 출처를 응답에 남기며, 분석 horizon_days까지
    같은 미래 구간을 가리켜야 계산을 시작한다. 예산 주기는 ``budget_start_day``
    (없으면 1일)로 정해 "이번 달" 기간이 설정 시작일을 따른다.
    """
    named = named_calendar(question, reference, budget_start_day)
    recognized = question_period(named, explicit=explicit is not None)
    source: PeriodSource = "default"
    spec: PeriodSpec = _default_spec(reference, budget_start_day)
    if analysis is not None:
        try:
            cost = RequestCost.model_validate(analysis.root)
        except ValidationError:
            raise ServiceError("invalid_numeric_request") from None
        spec, source = RollingDays(days=cost.horizon_days), "analysis"
    if recognized is not None:
        spec, source = recognized, "question"
    if explicit is not None:
        spec, source = explicit, "request"
    resolved = resolve_period(reference, spec, source, budget_start_day)
    if explicit is not None and recognized is not None:
        parsed = resolve_period(reference, recognized, "question", budget_start_day)
        if parsed.forecast_end != resolved.forecast_end:
            raise ServiceError("period_conflict")
    if (
        analysis is not None
        and "horizon_days" in analysis.root
        and analysis.root["horizon_days"] != resolved.forecast_days
    ):
        raise ServiceError("period_conflict")
    return resolved
