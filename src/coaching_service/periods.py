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


def resolve_period(reference: date, spec: PeriodSpec, source: PeriodSource) -> ResolvedPeriod:
    """기준일은 관측 마감값이며 시뮬레이션은 다음 날부터 종료일 포함이다.

    요청 구간에 기준일을 포함해도 그 날을 다시 예측하지 않는다. 미래 0일·과거·
    90일 초과·날짜 범위 초과는 422로 거부하고, 윤년은 양력 달력으로 계산한다.
    """
    month_start = reference.replace(day=1)
    month_end = reference.replace(day=calendar.monthrange(reference.year, reference.month)[1])
    try:
        tomorrow = reference + timedelta(days=1)
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
