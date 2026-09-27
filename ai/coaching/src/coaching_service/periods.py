"""Date-only periods over an observed day-close state; the vendor engine stays unchanged."""

import calendar
from datetime import date, datetime, timedelta
from typing import Annotated, ClassVar, Literal, assert_never

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, JsonValue
from pydantic_core import PydanticCustomError

from coaching_service.errors import ServiceError


def date_only(value: JsonValue | date) -> date:
    """날짜를 담은 date 객체 또는 YYYY-MM-DD 문자열만 받으며 datetime의 시각을 버리지 않는다."""
    match value:
        case datetime():
            raise PydanticCustomError("date_only", "Use a YYYY-MM-DD date, not a timestamp")
        case date():
            return value
        case str():
            if len(value) != 10:
                raise PydanticCustomError("date_only", "Use a YYYY-MM-DD date")
            try:
                parsed = date.fromisoformat(value)
            except ValueError:
                raise PydanticCustomError("date_only", "Use a valid YYYY-MM-DD date") from None
            if parsed.isoformat() == value:
                return parsed
        case int() | float() | list() | dict() | None:
            raise PydanticCustomError("date_only", "Use a YYYY-MM-DD date")
        case unreachable:
            assert_never(unreachable)
    raise PydanticCustomError("date_only", "Use a YYYY-MM-DD date")


DateOnly = Annotated[date, BeforeValidator(date_only)]


class PeriodContract(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")


class RollingDays(PeriodContract):
    kind: Literal["rolling_days"] = "rolling_days"
    days: int = Field(strict=True, ge=1, le=90)
    include_reference_date: bool = Field(default=False, strict=True)


class MonthEnd(PeriodContract):
    kind: Literal["month_end"] = "month_end"


class NextMonthEnd(PeriodContract):
    """The requested display window is the next Gregorian calendar month."""

    kind: Literal["next_month_end"] = "next_month_end"


class ThroughDate(PeriodContract):
    kind: Literal["through_date"] = "through_date"
    end_date: DateOnly


PeriodSpec = Annotated[RollingDays | MonthEnd | NextMonthEnd | ThroughDate, Field(discriminator="kind")]
PeriodSource = Literal["request", "question", "analysis", "default", "review"]


class ResolvedPeriod(PeriodContract):
    contract_version: Literal["coaching-period/1"] = "coaching-period/1"
    kind: Literal["rolling_days", "month_end", "next_month_end", "through_date"]
    source: PeriodSource
    reference_date: date
    reference_state: Literal["day_close_observed"] = "day_close_observed"
    window_start: date
    window_end: date
    window_calendar_days: int
    forecast_start: date
    forecast_end: date
    forecast_days: int
    reference_in_window: bool
    budget_month_start: date
    budget_month_end: date
    budget_forecast_end: date
    budget_future_coverage_complete: bool
    calendar: Literal["gregorian"] = "gregorian"
    time_zone: Literal["Asia/Seoul"] = "Asia/Seoul"
    holiday_adjustment: Literal["none"] = "none"
    lunar_calendar_supported: Literal[False] = False


def budget_cycle(reference: date, budget_start_day: int = 1) -> tuple[date, date]:
    """설정한 예산 시작일 기준으로 기준일이 속한 주기의 시작·종료일을 계산한다.

    주기 시작일은 기준일 당일 또는 그 이전의 가장 최근 해당 일자이고, 종료일은 다음
    주기 시작 전날이다. ``budget_start_day=1`` 이면 기준월 1일~말일과 정확히 같아
    기존 동작을 그대로 유지한다. 시작일은 1~28만 허용하므로 모든 달에 존재해 말일
    없는 달(2월 등) 보정이 필요 없다. 기준일이 바뀌면 주기도 함께 이동한다.
    """
    start_day = min(max(budget_start_day, 1), 28)
    anchor = reference.replace(day=start_day)
    if anchor <= reference:
        start = anchor
    elif reference.month == 1:
        start = date(reference.year - 1, 12, start_day)
    else:
        start = date(reference.year, reference.month - 1, start_day)
    following = (
        date(start.year + 1, 1, start_day)
        if start.month == 12
        else date(start.year, start.month + 1, start_day)
    )
    return start, following - timedelta(days=1)


def resolve_period(
    reference: date, spec: PeriodSpec, source: PeriodSource, budget_start_day: int = 1
) -> ResolvedPeriod:
    """기준일은 관측 마감값이며 시뮬레이션은 다음 날부터 종료일 포함이다.

    요청 구간에 기준일을 포함해도 그 날을 다시 예측하지 않는다. 미래 0일·과거·
    90일 초과·날짜 범위 초과는 422로 거부하고, 윤년은 양력 달력으로 계산한다.
    예산 주기는 ``budget_start_day`` (없으면 1일)로 정하며 기준일 이동을 따라간다.
    """
    try:
        tomorrow = reference + timedelta(days=1)
        month_start, month_end = budget_cycle(reference, budget_start_day)
        match spec:
            case RollingDays():
                window_start = reference if spec.include_reference_date else tomorrow
                end = window_start + timedelta(days=spec.days - 1)
            case MonthEnd():
                window_start, end = month_start, month_end
            case NextMonthEnd():
                next_year, next_month = (
                    (reference.year + 1, 1)
                    if reference.month == 12
                    else (reference.year, reference.month + 1)
                )
                window_start = date(next_year, next_month, 1)
                end = date(next_year, next_month, calendar.monthrange(next_year, next_month)[1])
            case ThroughDate():
                window_start, end = tomorrow, spec.end_date
            case unreachable:
                assert_never(unreachable)
    except (OverflowError, ValueError):
        raise ServiceError("period_date_out_of_range") from None
    horizon = (end - reference).days
    if horizon < 0:
        raise ServiceError("period_ends_before_reference")
    if horizon == 0:
        raise ServiceError("period_has_no_future_days")
    if horizon > 90:
        raise ServiceError("period_exceeds_90_future_days")
    return ResolvedPeriod(
        kind=spec.kind,
        source=source,
        reference_date=reference,
        window_start=window_start,
        window_end=end,
        window_calendar_days=(end - window_start).days + 1,
        forecast_start=tomorrow,
        forecast_end=end,
        forecast_days=horizon,
        reference_in_window=window_start <= reference <= end,
        budget_month_start=month_start,
        budget_month_end=month_end,
        budget_forecast_end=min(end, month_end),
        budget_future_coverage_complete=end >= month_end,
    )


def period_text(period: ResolvedPeriod, observed_on: date) -> str:
    """검증된 날짜를 직접 표시한다. LLM이 기간을 바꾸거나 오래된 자료를 숨기지 않는다."""
    if observed_on != period.reference_date:
        return (
            f"자료 기준일은 {observed_on.isoformat()} 마감입니다. "
            f"요청 기준일 {period.reference_date.isoformat()}과 일치하지 않아 "
            f"{period.forecast_end.isoformat()}까지의 코칭 예측은 자료 갱신 후 확인해야 합니다."
        )
    return (
        f"자료 기준일은 {period.reference_date.isoformat()} 마감입니다. "
        f"예측 구간은 {period.forecast_start.isoformat()}부터 "
        f"{period.forecast_end.isoformat()} 마감까지 {period.forecast_days}일입니다. "
        f"요청 구간은 {period.window_start.isoformat()}부터 {period.window_end.isoformat()}까지이며, "
        "기준일까지의 관측값과 이후 예측값을 구분합니다."
    )
