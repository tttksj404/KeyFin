"""Typed boundaries for the isolated, CPU-only forecast diagnosis."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field


class Frozen(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="ignore")


class LedgerRow(Frozen):
    user_id: str
    transaction_id: str
    source: Literal["SEED", "LIVE"]
    transaction_type: str
    transaction_date: date
    transaction_time: str
    category: str
    subcategory: str
    merchant: str
    merchant_id: str
    amount_krw: int = Field(ge=0, le=10**12)
    account_id: str
    card_id: str
    confirm_status: str
    status: str
    exclude_tag: str = "NONE"
    direction: str = "EXPENSE"


@dataclass(frozen=True, slots=True)
class Period:
    start: date
    end: date


class EnvelopeForecast(Frozen):
    envelope: str
    p10_krw: int
    p50_krw: int
    p90_krw: int


class BudgetForecast(Frozen):
    envelope: str
    budget_krw: int
    observed_used_krw: int
    projected_used_p50_krw: int
    p_over_budget: float
    coverage_end: date
    full_month_forecast_coverage: bool
    observation_starts_midmonth: bool


class Datasets(Frozen):
    envelopes: tuple[EnvelopeForecast, ...]
    budget_risk: tuple[BudgetForecast, ...] = ()


class WarningCode(Frozen):
    code: str


class Metric(Frozen):
    value: float | int | None
    unit: str


class EngineOutput(Frozen):
    as_of: date
    horizon_days: int
    input_digest: str
    status: str
    datasets: Datasets
    metrics: dict[str, Metric]
    warnings: tuple[WarningCode, ...]


class Comparison(Frozen):
    sample: str
    population: Literal["synthetic_seed"] = "synthetic_seed"
    month: str
    cutoff: date
    scope: Literal["month_ahead_consumption", "current_month_budget"]
    envelope: str
    actual_krw: int
    forecast_krw: int
    baseline_krw: int
    p10_krw: int | None = None
    p90_krw: int | None = None
    budget_krw: int | None = None
    budget_source: Literal["unavailable", "fixed_diagnostic_assumption"]
    forecast_error_krw: int
    forecast_minus_budget_krw: int | None = None
    actual_minus_budget_krw: int | None = None
    actual_budget_ratio: float | None = None


class MetricSummary(Frozen):
    scope: str
    sample_count: int
    actual_denominator_krw: int
    absolute_error_numerator_krw: int
    wape: float | None
    signed_bias_krw: int
    mean_absolute_error_krw: float
    baseline_wape: float | None
    interval_count: int
    interval_covered_count: int
    nominal_80_interval_coverage: float | None


class MonthlyTotals(Frozen):
    sample: str
    month: str
    fixed_actual_krw: int
    fixed_forecast_krw: int
    all_consumption_actual_krw: int
    budget_actual_krw: int
    consumption_forecast_krw: int
