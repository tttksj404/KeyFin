"""Bounded Korean period recognition; unsupported or conflicting periods never become seven days."""

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
    resolve_period,
)
from coaching_service.schemas import JsonDocument

_PERIOD: Final = re.compile(
    r"(?P<date>\d{4}-\d{2}-\d{2})\s*(?:마감\s*)?까지"
    r"|(?P<month>이번\s*달(?:\s*말(?:까지|에)?|에)?|이달(?:\s*말(?:까지|에)?|에)?|월말(?:까지|에)?)"
    r"|(?P<next_month>다음\s*달(?:\s*말(?:까지|에)?|에)?)"
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


def question_period(question: str, *, explicit: bool) -> PeriodSpec | None:  # noqa: C901 - 지원 기간 표현이 하나씩 늘며 분기가 누적된 단일 파서; 분해보다 한 곳 유지가 안전하다.
    """지원하는 명확한 한국어 기간 하나만 해석한다.

    여러 기간·음력·영업일은 422로 재확인을 요구한다. 그 밖의 모호한 표현은
    명시적 구조화 기간이 있을 때만 맡기며 임의로 기본 7일로 바꾸지 않는다.
    """
    if _UNSUPPORTED_CALENDAR.search(question):
        raise ServiceError("period_unsupported_calendar")
    matches = list(_PERIOD.finditer(question))
    if len(matches) > 1:
        raise ServiceError("period_clarification_required")
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


def turn_period(
    reference: date, question: str, explicit: PeriodSpec | None, analysis: JsonDocument | None
) -> ResolvedPeriod:
    """명시적 기간→질문→추가 분석 순으로 선택하되 서로 다른 종료일은 거부한다.

    7일은 기간 정보가 전혀 없을 때의 기본 정책이다. 출처를 응답에 남기며,
    분석 horizon_days까지 같은 미래 구간을 가리켜야 계산을 시작한다.
    """
    recognized = question_period(question, explicit=explicit is not None)
    source: PeriodSource = "default"
    spec: PeriodSpec = RollingDays(days=7)
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
    resolved = resolve_period(reference, spec, source)
    if explicit is not None and recognized is not None:
        parsed = resolve_period(reference, recognized, "question")
        if parsed.forecast_end != resolved.forecast_end:
            raise ServiceError("period_conflict")
    if (
        analysis is not None
        and "horizon_days" in analysis.root
        and analysis.root["horizon_days"] != resolved.forecast_days
    ):
        raise ServiceError("period_conflict")
    return resolved
