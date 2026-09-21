"""Calendar and target arithmetic are checked without a forecasting model oracle."""

from datetime import date, timedelta

import pytest
from pydantic import ValidationError

from benchmarks.forecast.aggregate import arithmetic
from benchmarks.forecast.aggregate.contracts import Case, Inputs, Prediction
from benchmarks.forecast.public_bank.contracts import TrainingSeries


def case(*, split: str = "development", account: str = "held-out") -> Case:
    return Case.model_validate({
        "case_id": f"{account}:{split}", "account": account, "split": split,
        "cutoff": "1998-01-31", "first_date": "1997-02-01", "end_date": "1998-03-02",
        "horizon": 30, "history": [1.0] * 365,
    })


def test_rolling_sum_predicts_period_target_not_sum_of_daily_quantiles() -> None:
    # Given: a five-day observed sequence and a three-day aggregation window.
    values = (1.0, 2.0, 3.0, 4.0, 5.0)
    # When: a model receives only fully observed trailing totals.
    result = arithmetic.rolling_sums(values, 3)
    # Then: no padded or future value enters the transformed series.
    assert result == (6.0, 9.0, 12.0)


def test_arithmetic_candidates_preserve_constant_flow_across_short_february() -> None:
    # Given: one currency unit spent every observed day, with future spanning February.
    row = case()
    # When: every frozen arithmetic candidate predicts thirty future days.
    rows = arithmetic.predict(row)
    # Then: missing calendar dates are not duplicated and the total stays thirty.
    assert len(rows) == 11
    assert all(item.point == pytest.approx(30.0) for item in rows)


def test_aggregate_case_rejects_inclusive_cutoff_as_future() -> None:
    # Given: an otherwise valid forecast.
    payload = case().model_dump()
    payload["end_date"] = date(1998, 1, 31) + timedelta(days=29)
    # When/Then: a 29-day future cannot be called a 30-day forecast.
    with pytest.raises(ValidationError, match="Future period"):
        Case.model_validate(payload)


def test_calibration_account_must_not_overlap_evaluation() -> None:
    # Given: distinct case IDs conceal a shared account between two partitions.
    rows = (case(split="calibration"), case(split="evaluation"))
    train = TrainingSeries(account="train", daily=(0.0,) * 365)
    # When/Then: the boundary rejects the account leakage.
    with pytest.raises(ValidationError, match="Account leakage"):
        Inputs(protocol_sha256="a" * 64, training=(train,), cases=rows)


def test_aggregate_interval_rejects_nan_and_crossed_quantiles() -> None:
    # Given/When/Then: an invalid interval cannot become an evaluation record.
    with pytest.raises(ValidationError):
        Prediction(case_id="x", model="m", point=float("nan"), lower=0, upper=1)
    with pytest.raises(ValidationError, match="interval"):
        Prediction(case_id="x", model="m", point=2, lower=0, upper=1)
