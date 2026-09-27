"""Adversarial split and prediction-completeness checks for real evaluation logic."""

from datetime import timedelta

import pytest

from benchmarks.forecast.aggregate.arithmetic import EXTRA, NEURAL
from benchmarks.forecast.aggregate.contracts import Prediction
from benchmarks.forecast.aggregate.selection import candidate_bank, choose
from benchmarks.forecast.public_bank.baselines import BASELINES
from benchmarks.forecast.public_bank.contracts import Truth

from .test_aggregate import case


def test_holdout_cannot_enter_selection_even_with_its_real_target() -> None:
    # Given: complete predictions, but a case belongs to evaluation.
    row = case(split="evaluation")
    predictions = tuple(Prediction(case_id=row.case_id, model=name, point=1, lower=1, upper=1)
                        for name in BASELINES + EXTRA + NEURAL)
    bank = candidate_bank((row,), predictions)
    # When/Then: a callable selection boundary rejects test outcomes.
    with pytest.raises(ValueError, match="development"):
        choose((row,), (Truth(case_id=row.case_id, actual=1),), bank)


def test_missing_or_duplicate_neural_prediction_blocks_comparison() -> None:
    # Given: one candidate omitted, despite every reference being present.
    row = case()
    predictions = tuple(Prediction(case_id=row.case_id, model=name, point=1, lower=1, upper=1)
                        for name in BASELINES + EXTRA + NEURAL)
    # When/Then: neither partial nor duplicated evidence can win a comparison.
    with pytest.raises(ValueError, match="Incomplete"):
        candidate_bank((row,), predictions[:-1])
    with pytest.raises(ValueError, match="duplicate"):
        candidate_bank((row,), (*predictions, predictions[0]))


def test_selection_changes_only_with_development_observations() -> None:
    # Given: the two horizons favor distinct candidates on independently supplied truth.
    long = case()
    short = long.model_copy(update={"case_id": "short", "horizon": 7,
                                    "end_date": long.cutoff + timedelta(days=7)})
    rows = (short, long)
    predictions = tuple(Prediction(case_id=row.case_id, model=name,
                                   point=10 if name == "block_median" else 100,
                                   lower=0, upper=100) for row in rows for name in BASELINES + EXTRA + NEURAL)
    bank = candidate_bank(rows, predictions)
    # When: score only the development outcomes; no test outcome is an argument.
    result = choose(rows, tuple(Truth(case_id=row.case_id, actual=10) for row in rows), bank)
    # Then: the same real error calculation selects the robust model for both horizons.
    assert result[7].selected == result[30].selected == "block_median"
    assert result[7].development_mae["block_median"] == 0
