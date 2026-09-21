"""Carry calculation limits into charts without inventing missing observations."""

from datetime import date
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field

from coaching_service.chart_contract import BudgetPeriod, ChartMoney, ChartQuality
from coaching_service.schemas import JsonDocument


class Fields(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore", frozen=True)


class WarningCode(Fields):
    code: str


class ModelHistory(Fields):
    historical_days: int | None = Field(default=None, ge=0)


class PendingMetric(Fields):
    value: ChartMoney | None = Field(default=None, ge=0)


class QualityMetrics(Fields):
    pending_expense_p50_krw: PendingMetric = PendingMetric()


class QualitySource(Fields):
    warnings: tuple[WarningCode, ...] = ()
    model: ModelHistory = ModelHistory()
    metrics: QualityMetrics = QualityMetrics()


_NOTICES = {
    "PENDING_CLASSIFICATION": "입력에 분류가 확정되지 않은 소비가 있습니다.",
    "PENDING_SHARE_HIGH": "입력의 미분류 소비 비중이 5%를 넘어 항목별 예측 해석에 주의가 필요합니다.",
    "SHORT_HISTORY_FALLBACK": "과거 7일 묶음이 부족해 요일별 거래 표본으로 대체 계산했습니다.",
    "MAPPING_FALLBACK": "일부 거래는 세부분류 대신 상위 카테고리를 기준으로 분류했습니다.",
    "ABSOLUTE_STATE_UNAVAILABLE": (
        "잔액·정산 정보가 부족해 계좌 잔액은 예측하지 않습니다. 이 차트는 소비 금액입니다."
    ),
    "CASH_WITHDRAWAL_UNOBSERVED": "ATM에서 인출한 뒤 사용한 현금 소비는 입력 자료에서 확인되지 않습니다.",
    "REIMBURSEMENT_UNMATCHED": "원거래와 연결되지 않은 정산 입금은 소비에서 임의로 차감하지 않았습니다.",
    "DEBT_SPLIT_UNKNOWN": "대출 납부액의 원금·이자 구분이 확인되지 않았습니다.",
    "FIXED_UNSCHEDULED": "일부 고정지출에 반복 일정이 없으며, 고정비는 이 소비 차트에서 제외됩니다.",
    "IGNORED_LABEL_COLUMNS": "입력의 보조 라벨 대신 원본 거래 분류를 사용했습니다.",
    "UNCALIBRATED_MODEL": "실제 사용자 대상 예측 정확도는 아직 검증되지 않았습니다.",
}


def chart_quality(
    evidence: JsonDocument | None,
    unallocated_current: ChartMoney,
    period: BudgetPeriod,
    observation_start: date,
    known_budget_count: int,
) -> ChartQuality:
    """입력 이력·미분류·예산 누락·FDT 경고를 표시 문구로 전달한다.

    수치를 보정하거나 미관측 기간을 채우지 않는다. 모르는 경고 코드도 일반 안내와
    원본 코드로 남겨 새 엔진 경고가 화면에서 조용히 사라지지 않게 한다.
    """
    source = QualitySource.model_validate(evidence.root) if evidence is not None else QualitySource()
    codes = tuple(warning.code for warning in source.warnings)
    pending_forecast = source.metrics.pending_expense_p50_krw.value
    notices: list[str] = []
    summary: list[str] = []
    if observation_start > period.period_start:
        notice = (
            f"입력 이력은 {observation_start}부터입니다. "
            "그 이전 예산 기간은 미관측이며, 누적 금액은 입력에서 확인된 소비만 포함합니다."
        )
        notices.append(notice)
        summary.append("입력 전 기간은 미관측입니다.")
    if unallocated_current:
        notice = (
            f"현재 미분류 소비 {unallocated_current:,}원은 전체 금액에 포함되며, "
            "7개 카테고리와 일별 막대에서 제외됩니다."
        )
        notices.append(notice)
        summary.append(f"미분류 소비 {unallocated_current:,}원은 전체에 포함됩니다.")
    if "SHORT_HISTORY" in codes:
        history = source.model.historical_days
        notice = (
            f"과거 이력 {history}일로 예측을 계산해 추정이 불안정할 수 있습니다."
            if history is not None
            else "과거 이력이 60일 미만으로 예측이 불안정할 수 있습니다."
        )
        notices.append(notice)
        summary.append(
            f"과거 이력 {history}일로 추정이 불안정합니다."
            if history is not None
            else "과거 이력이 짧아 추정이 불안정합니다."
        )
    if pending_forecast:
        notice = (
            f"미래 미분류 소비만의 P50은 {pending_forecast:,}원이며 항목별 막대에서 제외됩니다. "
            "이 값은 전체 P50과 카테고리 P50 합의 차이로 계산한 값이 아닙니다."
        )
        notices.append(notice)
        summary.append("미래에도 미분류 소비가 포함됩니다.")
    notices.extend(
        _NOTICES.get(code, "계산에 추가 제한 사항이 있습니다. 원본 계산 근거를 확인해 주세요.")
        for code in dict.fromkeys(codes)
        if code != "SHORT_HISTORY"
    )
    if period.as_of < period.horizon_end:
        # The service never promotes a conditional model result to verified accuracy.
        unverified = _NOTICES["UNCALIBRATED_MODEL"]
        if unverified not in notices:
            notices.append(unverified)
        summary.append("예측 정확도는 미검증입니다.")
    if "REIMBURSEMENT_UNMATCHED" in codes:
        summary.append("정산 입금은 소비에서 차감하지 않았습니다.")
    if 0 < known_budget_count < 7:
        notices.append(
            f"7개 중 {known_budget_count}개 항목만 예산이 입력되어 "
            "전체 예산 합계와 전체 사용률은 계산하지 않습니다."
        )
    return ChartQuality(
        historical_days=source.model.historical_days,
        warning_codes=codes,
        pending_forecast_p50_krw=pending_forecast,
        notices=tuple(notices),
        summary=" ".join(summary),
    )
