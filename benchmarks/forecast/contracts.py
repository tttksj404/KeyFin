"""Explicit boundaries keep future truth separate from prediction inputs."""

from datetime import date
from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field

Family = Literal["days7", "target14", "days30", "month_end"]
Split = Literal["development", "evaluation"]


class Frozen(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")


class Series(Frozen):
    user: str
    envelope: str
    first_date: date
    last_date: date
    daily: tuple[float, ...]


class ForecastCase(Frozen):
    case_id: str
    user: str
    envelope: str
    split: Split
    family: Family
    first_date: date
    cutoff: date
    end_date: date
    horizon: int = Field(ge=1, le=90)
    history: tuple[float, ...] = Field(min_length=1)


class Truth(Frozen):
    case_id: str
    actual: float = Field(ge=0)


class InputBundle(Frozen):
    training_end: date
    training: tuple[Series, ...]
    cases: tuple[ForecastCase, ...]


class Forecast(Frozen):
    case_id: str
    model: str
    fold: str = "common"
    point: float = Field(ge=0, allow_inf_nan=False)
    lower: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    upper: float | None = Field(default=None, ge=0, allow_inf_nan=False)


class MetricSet(Frozen):
    count: int
    actual_sum: float
    wape: float | None
    mae: float
    mean_bias: float
    interval_count: int
    coverage80: float | None
    mean_width: float | None
    wis: float | None
    normalized_wis: float | None


class Calibration(Frozen):
    fold: str
    model: str
    family: Family
    count: int
    radius: float
    score_case_ids: tuple[str, ...]
