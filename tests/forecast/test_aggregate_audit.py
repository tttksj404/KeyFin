"""Adversarial evidence and admission tests use invented observations, never study truth."""

from datetime import date, timedelta

import pytest

from benchmarks.forecast.aggregate.contracts import Inputs, Prediction
from benchmarks.forecast.aggregate.protocol_boundary import (
    REQUIRED,
    Manifest,
    validate_inputs,
    validate_manifest,
)
from benchmarks.forecast.aggregate.provenance import validate_updates
from benchmarks.forecast.aggregate.report import horizon_report
from benchmarks.forecast.aggregate.selection import Bank, Choice
from benchmarks.forecast.aggregate.worker_support import UpdateEvidence
from benchmarks.forecast.public_bank.contracts import TrainingSeries
from benchmarks.forecast.public_bank.data import EXPECTED

from .test_aggregate import case


def manifest() -> Manifest:
    return Manifest(
        protocol_sha256="a" * 64, training_accounts=1,
        accounts_by_split={"development": 200, "calibration": 200, "evaluation": 400},
        cases_by_split={"development": 1200, "calibration": 400, "evaluation": 2400},
        previous_eval_dev_accounts_excluded=300, evaluation_future_used_in_r12=False,
        old_training_history_overlap=True, source_files=EXPECTED,
        files=dict.fromkeys(REQUIRED, "b" * 64),
    )


def test_omitted_unopened_test_hash_blocks_manifest_admission() -> None:
    # Given: a manifest intentionally omits the outcome that must remain frozen.
    record = manifest()
    changed = record.model_copy(update={"files": {key: value for key, value in record.files.items()
                                                  if key != "evaluation_truth.json"}})
    # When/Then: an apparently unchanged subset is insufficient evidence.
    with pytest.raises(ValueError, match="incomplete"):
        validate_manifest(changed)


def test_different_original_ledger_hash_is_not_the_frozen_study() -> None:
    record = manifest().model_copy(update={"source_files": {"account.asc": "0" * 64}})
    with pytest.raises(ValueError, match="source"):
        validate_manifest(record)


def test_evaluation_date_relabeled_development_is_rejected() -> None:
    # Given: all dates are internally consistent, but a test origin is labeled development.
    end = date(1998, 11, 30)
    row = case().model_copy(update={"cutoff": end, "first_date": end - timedelta(days=364),
                                   "end_date": end + timedelta(days=30)})
    inputs = Inputs(protocol_sha256="a" * 64, cases=(row,),
                    training=(TrainingSeries(account="train", daily=(0.0,) * 365),))
    with pytest.raises(ValueError, match="partition"):
        validate_inputs(inputs, manifest())


def test_requested_training_steps_cannot_hide_skipped_optimizer_updates() -> None:
    observed = UpdateEvidence(requested_updates=128, optimizer_step_events=128,
                              optimizer_updates=127, skipped_updates=1, global_step=128,
                              observed_global_steps=tuple(range(1, 129)))
    with pytest.raises(ValueError, match="optimizer"):
        validate_updates(observed, 128)


@pytest.mark.parametrize(("point", "expected"), [(10.0, True), (9.999, False)])
def test_exact_ten_percent_gate_uses_error_amounts(point: float, expected: bool) -> None:
    # Given: actual=100, baseline=0: its MAE is exactly 100.
    row = case(split="evaluation")
    forecasts = {name: {row.case_id: Prediction(case_id=row.case_id, model=name,
                                               point=value, lower=value, upper=value)}
                 for name, value in (("candidate", point), ("recent90", 0.0))}
    choice = Choice(selected="candidate", baseline="recent90", development_mae={})
    # When: the frozen candidate predicts 10 (exactly 10% less error) or just below it.
    report = horizon_report((row,), {row.case_id: 100.0}, Bank(forecasts), choice,
                            {"candidate": 0.0, "recent90": 0.0})
    # Then: display rounding must neither reject the boundary nor admit a smaller gain.
    assert report["gates"]["mae_reduction_at_least_10_percent"] is expected
