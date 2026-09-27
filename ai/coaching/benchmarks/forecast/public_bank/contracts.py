"""Strict boundaries separate observed arrays, targets and model predictions."""

from datetime import date, timedelta
from typing import ClassVar, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

Split = Literal["development", "evaluation"]


class Frozen(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)


class Case(Frozen):
    case_id: str
    account: str
    split: Split
    cutoff: date
    first_date: date
    end_date: date
    horizon: Literal[7, 30]
    history: tuple[float, ...] = Field(min_length=365, max_length=365)

    @model_validator(mode="after")
    def ordered_dates(self) -> Self:
        if self.first_date != self.cutoff - timedelta(days=364):
            raise ValueError("History must end at the cutoff and contain exactly 365 days")
        if self.end_date != self.cutoff + timedelta(days=self.horizon):
            raise ValueError("Target must begin after cutoff and end at cutoff plus horizon")
        if any(value < 0 for value in self.history):
            raise ValueError("Negative outflow history")
        return self


class TrainingSeries(Frozen):
    account: str
    daily: tuple[float, ...] = Field(min_length=365, max_length=365)


class Inputs(Frozen):
    protocol_sha256: str
    training_start: date = date(1997, 1, 1)
    training_end: date = date(1997, 12, 31)
    training: tuple[TrainingSeries, ...]
    cases: tuple[Case, ...]

    @model_validator(mode="after")
    def separate_accounts(self) -> Self:
        if (self.training_start, self.training_end) != (date(1997, 1, 1), date(1997, 12, 31)):
            raise ValueError("Training date range differs from frozen protocol")
        ids = [row.case_id for row in self.cases]
        if len(set(ids)) != len(ids):
            raise ValueError("Duplicate case ID")
        train = [row.account for row in self.training]
        if len(set(train)) != len(train):
            raise ValueError("Duplicate training account")
        dev = {row.account for row in self.cases if row.split == "development"}
        test = {row.account for row in self.cases if row.split == "evaluation"}
        if set(train) & (dev | test) or dev & test:
            raise ValueError("Account leakage between splits")
        if any(row.cutoff <= self.training_end for row in self.cases):
            raise ValueError("Forecast precedes the training cutoff")
        if any(value < 0 for row in self.training for value in row.daily):
            raise ValueError("Negative training outflow")
        return self


class Truth(Frozen):
    case_id: str
    actual: float = Field(ge=0)


class Prediction(Frozen):
    case_id: str
    model: str
    point: float = Field(ge=0)


class Choice(Frozen):
    model_a: str
    model_b: str
    weight_a: Literal[0.5, 1.0]
    scale: Literal[1.0]
    development_mae: float
    baseline: str


class Selection(Frozen):
    protocol_sha256: str
    input_sha256: str
    prepared_manifest_sha256: str
    evaluation_truth_sha256: str
    neural_run_manifest_sha256: str
    development_truth_sha256: str
    prediction_sha256: dict[str, str]
    choices: dict[int, Choice]

    @model_validator(mode="after")
    def complete_horizons(self) -> Self:
        if set(self.choices) != {7, 30}:
            raise ValueError("Selection must cover exactly 7 and 30 days")
        return self
