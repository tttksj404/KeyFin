"""Convert engine amounts once; neither language models nor renderers invent numbers."""

from datetime import date, timedelta
from itertools import pairwise
from typing import ClassVar, Final

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

from coaching_service.chart_contract import (
    Balance,
    BudgetPeriod,
    Category,
    ChartMeta,
    ChartMoney,
    ChartResult,
    DailyForecast,
    DailyPoint,
    ForecastPoint,
    HistoricalPoint,
    PurchaseChange,
    Quantile,
)
from coaching_service.chart_quality import chart_quality
from coaching_service.errors import ServiceError
from coaching_service.schemas import JsonDocument, TransactionView

ENVELOPES: Final = ("외식", "교통비", "의료·건강", "취미·여가", "쇼핑", "편의점·마트·잡화", "기타")
# 엔진의 봉투 순서와 KeyFin 표시 이름을 연결하는 계약이며 사용자별 예측값이 아니다.
LABELS: Final = ("외식", "교통", "의료·건강", "취미·여가", "쇼핑", "마트·편의점", "기타")
_MONEY: Final = TypeAdapter[int](ChartMoney)


def checked_money(value: int) -> int:
    """중간 합계도 차트의 안전한 정수 범위로 검사한다. 초과분을 잘라내지 않는다.

    각각 유효한 관측액·예측액도 합치면 범위를 넘을 수 있으므로 저장 전에 422다.
    """
    try:
        return _MONEY.validate_python(value)
    except ValidationError as exc:
        raise ServiceError("chart_money_range_limit") from exc


class EngineFields(BaseModel):
    """Parse only the numeric fields needed from a preserved upstream document."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore", frozen=True)


class Metric(EngineFields):
    value: ChartMoney


class EnvelopeForecast(EngineFields):
    envelope: str
    p50_krw: ChartMoney


class ProjectionPoint(EngineFields):
    date: date
    cumulative_expense_p50_krw: ChartMoney


class Datasets(EngineFields):
    envelopes: tuple[EnvelopeForecast, ...]
    projection: tuple[ProjectionPoint, ...]


class Metrics(EngineFields):
    total_expense_p50_krw: Metric


class NumericResult(EngineFields):
    status: str
    datasets: Datasets
    metrics: Metrics


class Budgets(EngineFields):
    budgets: dict[str, ChartMoney] = Field(default_factory=dict)


class ChartInputs(EngineFields):
    id: str
    question: str
    period: BudgetPeriod
    transactions: tuple[TransactionView, ...]
    budgets: Budgets
    paths: int
    seed: int
    observation_audit: JsonDocument | None = None


def project_chart(  # noqa: C901, PLR0912, PLR0915 - one deterministic pass over every projection contract guard.
    inputs: ChartInputs,
    raw: JsonDocument | None,
    daily_prediction: DailyForecast | None = None,
    purchase: PurchaseChange | None = None,
) -> ChartResult:
    """관측 소비와 FDT 예측을 날짜·봉투·기간말 합계 계약에 맞추어 연결한다.

    기준일 마감까지는 관측값, 다음 날부터는 예측값이다. 누적선은 P50이고
    일별 막대는 경로 평균이다. 미분류 소비는 총액에 포함하지만 봉투 막대에는 없다.
    날짜 누락이나 합계 불일치는 502로 거부하며 누락된 예측을 0원으로 채우지 않는다.

    구매 what-if(``purchase``)를 주면 두 번째 시뮬레이션 없이 결정적으로 겹쳐 그린다.
    페어드 CRN 예측은 모든 경로에 고정 금액 A를 더하므로 P50도 정확히 A만큼 이동한다.
    따라서 ``planned_cum_p50(t) = baseline_cum_p50(t) + (A if t >= 구매일 else 0)`` 이며
    기준선(구매 전 예측)은 ``balance.baseline`` 으로, 이동한 예측선은 기본 예측선으로 둔다.
    """
    period = inputs.period
    transactions = tuple(
        t
        for t in inputs.transactions
        if t.active
        and t.kind == "expense"
        and period.period_start.isoformat() <= t.date <= period.as_of.isoformat()
    )
    daily: list[DailyPoint] = []
    history: list[HistoricalPoint] = []
    cumulative = 0
    # 엔진이 받은 첫 거래일부터 관측값을 그린다. 입력 이전 날짜를 0원으로 꾸미거나
    # 거래가 없는 날짜만으로 데이터 수집이 완전하다고 판단하지 않는다.
    first_input = min((date.fromisoformat(t.date) for t in inputs.transactions), default=period.as_of)
    observation_start = max(period.period_start, first_input)
    for offset in range((period.as_of - observation_start).days + 1):
        day = observation_start + timedelta(days=offset)
        rows = tuple(t for t in transactions if t.date == day.isoformat())
        amounts = tuple(
            sum(t.amount_krw for t in rows if not t.pending and t.envelope == name) for name in ENVELOPES
        )
        daily.append(DailyPoint(date=day, amounts_krw=amounts))
        cumulative = checked_money(cumulative + sum(t.amount_krw for t in rows))
        history.append(HistoricalPoint(date=day, value_krw=cumulative))
    current = tuple(sum(row.amounts_krw[i] for row in daily) for i in range(len(ENVELOPES)))
    future: dict[str, int] = dict.fromkeys(ENVELOPES, 0)
    forecast = (ForecastPoint(date=period.as_of, p50_krw=cumulative),)
    status = "observed_period_complete"
    if raw is not None:
        result = NumericResult.model_validate(raw.root)
        if result.status not in {"ok", "partial"}:
            raise ServiceError("chart_forecast_unavailable", 422)
        future = {row.envelope: row.p50_krw for row in result.datasets.envelopes}
        if set(future) != set(ENVELOPES) or len(result.datasets.envelopes) != len(ENVELOPES):
            raise ServiceError("chart_envelope_contract_mismatch", 502)
        forecast = tuple(
            ForecastPoint(date=row.date, p50_krw=checked_money(cumulative + row.cumulative_expense_p50_krw))
            for row in result.datasets.projection
        )
        expected_dates = tuple(
            period.as_of + timedelta(days=i) for i in range((period.horizon_end - period.as_of).days + 1)
        )
        if tuple(point.date for point in forecast) != expected_dates or forecast[0].p50_krw != cumulative:
            raise ServiceError("chart_projection_contract_mismatch", 502)
        if forecast[-1].p50_krw != cumulative + result.metrics.total_expense_p50_krw.value:
            raise ServiceError("chart_terminal_contract_mismatch", 502)
        if (
            daily_prediction is None
            or tuple(point.date for point in daily_prediction.points) != expected_dates[1:]
        ):
            raise ServiceError("chart_daily_projection_mismatch", 502)
        daily.extend(daily_prediction.points)
        status = result.status
    elif daily_prediction is not None or period.as_of < period.horizon_end:
        raise ServiceError("chart_daily_projection_mismatch", 502)
    baseline_points: tuple[ForecastPoint, ...] = ()
    purchase_note: str | None = None
    if purchase is not None:
        # 종료된 기간에는 미래 예측선이 없어 겹쳐 그릴 대상이 없다.
        if raw is None:
            raise ServiceError("chart_purchase_period_closed", 422)
        if purchase.envelope not in ENVELOPES:
            raise ServiceError("chart_purchase_envelope_unknown", 422)
        # 예산 기간 안의 '미래' 구매만 허용한다. 기준일 앵커 점은 관측값이라 옮기지 않는다.
        if not period.as_of < purchase.on_date <= period.horizon_end:
            raise ServiceError("chart_purchase_out_of_period", 422)
        step = purchase.amount_krw  # ChartMoney ge=1 계약이 양수 고정 지출을 보장한다.
        baseline_points = forecast
        forecast = tuple(
            ForecastPoint(
                date=point.date,
                p50_krw=checked_money(point.p50_krw + (step if point.date >= purchase.on_date else 0)),
            )
            for point in baseline_points
        )
        # 접미 구간에 양수를 더해도 단조 비감소는 보존된다. 위반은 결정적 겹침이 깨진 것이다.
        if any(a.p50_krw > b.p50_krw for a, b in pairwise(forecast)):
            raise ServiceError("chart_projection_contract_mismatch", 502)
        future[purchase.envelope] = future[purchase.envelope] + step
        purchase_note = (
            f"계획 구매 {step:,}원({purchase.on_date})을 반영한 예상 누적 소비입니다. "
            "연한 선은 구매 전 기준 예측이며, 이 비교는 예산·소비 관점이라 "
            "계좌 잔액이나 결제 가능 여부를 보장하지 않습니다."
        )
    categories = tuple(
        Category(
            id=name,
            label=label,
            budget=inputs.budgets.budgets.get(name),
            current=used,
            forecast=checked_money(used + future[name]),
        )
        for name, label, used in zip(ENVELOPES, LABELS, current, strict=True)
    )
    total_budget = (
        checked_money(sum(inputs.budgets.budgets.values()))
        if set(inputs.budgets.budgets) == set(ENVELOPES) else None
    )
    terminal = forecast[-1].p50_krw
    return ChartResult(
        id=inputs.id,
        question=inputs.question,
        total_budget=total_budget,
        total_current=cumulative,
        unallocated_current=cumulative - sum(current),
        total_forecast=terminal,
        categories=categories,
        meta=ChartMeta(
            period_start=period.period_start,
            as_of=period.as_of,
            horizon_end=period.horizon_end,
            paths=inputs.paths,
            seed=inputs.seed,
            status=status,
            quality=chart_quality(
                raw if raw is not None else inputs.observation_audit,
                cumulative - sum(current),
                period,
                observation_start,
                sum(row.budget is not None for row in categories),
            ),
            observation_start=observation_start,
            purchase=purchase,
            purchase_note=purchase_note,
            daily_forecast_statistic=daily_prediction.statistic if daily_prediction is not None else None,
            daily_note=(
                "기준일까지는 실제 소비, 이후 연한 막대는 하루 평균 예상 소비입니다. "
                "분류된 변동소비만 포함하며 미분류 소비와 고정비는 제외합니다. "
                "누적선과 기간 말 금액은 보통 수준의 예상값이라 하루 평균 막대를 더한 값과 다를 수 있으며, "
                "각 칸은 원 단위로 반올림합니다."
                if daily_prediction is not None
                else "분류된 변동소비의 관측 기록입니다. 미분류 소비와 고정비는 제외합니다."
            ),
        ),
        balance=Balance(
            budget_krw=total_budget,
            current_krw=cumulative,
            terminal=Quantile(p50_krw=terminal),
            history=tuple(history),
            forecast=forecast,
            baseline=baseline_points,
            daily=tuple(daily),
        ),
    )
