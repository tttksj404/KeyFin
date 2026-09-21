"""Reject overlapping accounts, invalid periods, and nonfinite aggregate predictions."""

from datetime import date, timedelta
from typing import Literal, Self

from pydantic import Field, model_validator

from benchmarks.forecast.public_bank.contracts import Frozen, TrainingSeries

Split = Literal["development", "calibration", "evaluation"]


class Case(Frozen):
    """Same observed-only 365-day calendar contract, with a separate calibration tier."""

    case_id: str
    account: str
    split: Split
    cutoff: date
    first_date: date
    end_date: date
    horizon: Literal[7, 30]
    history: tuple[float, ...] = Field(min_length=365, max_length=365)

    @model_validator(mode="after")
    def calendar(self) -> Self:
        if self.first_date != self.cutoff - timedelta(days=364):
            raise ValueError("History must contain 365 days through the cutoff")
        if self.end_date != self.cutoff + timedelta(days=self.horizon):
            raise ValueError("Future period must begin after the cutoff")
        if any(value < 0 for value in self.history):
            raise ValueError("Negative observed outflow")
        return self


class Inputs(Frozen):
    protocol_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    training_start: date = date(1997, 1, 1)
    training_end: date = date(1997, 12, 31)
    training: tuple[TrainingSeries, ...]
    cases: tuple[Case, ...]

    @model_validator(mode="after")
    def independent_partitions(self) -> Self:
        if (self.training_start, self.training_end) != (date(1997, 1, 1), date(1997, 12, 31)):
            raise ValueError("Training period differs from the frozen protocol")
        ids = [row.case_id for row in self.cases]
        if not ids or len(set(ids)) != len(ids):
            raise ValueError("Cases must be nonempty and unique")
        training = {row.account for row in self.training}
        if len(training) != len(self.training) or not training:
            raise ValueError("Training accounts must be nonempty and unique")
        if any(value < 0 for row in self.training for value in row.daily):
            raise ValueError("Negative training outflow")
        owners = dict.fromkeys(training, "training")
        for row in self.cases:
            if row.cutoff <= self.training_end:
                raise ValueError("Forecast precedes training completion")
            if row.account in owners and owners[row.account] != row.split:
                raise ValueError("Account leakage between partitions")
            owners[row.account] = row.split
        return self


class Prediction(Frozen):
    case_id: str
    model: str
    point: float = Field(ge=0)
    lower: float = Field(ge=0)
    upper: float = Field(ge=0)

    @model_validator(mode="after")
    def ordered(self) -> Self:
        if not self.lower <= self.point <= self.upper:
            raise ValueError("Aggregate interval must contain its point")
        return self
