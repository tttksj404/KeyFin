"""Leakage, aggregation and prediction-grid contracts for actual-bank evaluation."""

import json
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pytest
from pydantic import TypeAdapter, ValidationError

from benchmarks.forecast import public_bank
from benchmarks.forecast.public_bank.baselines import BASELINES, predict
from benchmarks.forecast.public_bank.contracts import Case, Inputs, TrainingSeries, Truth
from benchmarks.forecast.public_bank.data import history, sha256
from benchmarks.forecast.public_bank.evaluate import evaluate, select
from benchmarks.forecast.public_bank.metrics import Sample, confidence, metrics

from .test_public_bank_fixtures import final_targets, prepared_fixture


def test_future_window_when_cutoff_has_payment() -> None:
    # Given: the cutoff itself has a debit, and future debits span the boundary.
    ledger = {date(1998, 1, 31): 99900, date(1998, 2, 1): 1200, date(1998, 2, 7): 3400}
    # When: the independent target sums seven days after the cutoff.
    result = public_bank.ledger_total(ledger, date(1998, 1, 31), 7)
    # Then: cutoff debit is excluded and all seven future days are included.
    assert result == 46.0


def test_prediction_grid_when_case_is_missing() -> None:
    # Given: a required two-case grid and only one prediction.
    rows = [{"case_id": "a", "model": "mean", "point": 12.0}]
    # When / Then: an incomplete model cannot receive a metric.
    with pytest.raises(ValueError, match="prediction grid"):
        public_bank.validate_predictions(rows, {"a", "b"})


@pytest.mark.parametrize("point", [float("nan"), float("inf"), -1.0])
def test_prediction_when_value_is_not_a_finite_nonnegative_amount(point: float) -> None:
    # Given: an invalid model output.
    rows = [{"case_id": "a", "model": "mean", "point": point}]
    # When / Then: invalid arithmetic never becomes a reported score.
    with pytest.raises(ValidationError):
        public_bank.validate_predictions(rows, {"a"})


def test_prediction_when_case_is_duplicated() -> None:
    # Given: two outputs for the same required case.
    rows = [{"case_id": "a", "model": "mean", "point": 1.0}] * 2
    # When / Then: duplicates cannot increase the denominator.
    with pytest.raises(ValueError, match="prediction grid"):
        public_bank.validate_predictions(rows, {"a"})


def test_history_when_future_transaction_is_present() -> None:
    # Given: a massive later debit alongside the last observed debit.
    cutoff = date(1998, 1, 31)
    ledger = {cutoff: 500, cutoff + timedelta(days=1): 999999900}
    # When: history is materialized independently of target aggregation.
    observed = history(ledger, cutoff)
    # Then: future magnitude cannot affect any input slot.
    assert len(observed) == 365
    assert sum(observed) == 5.0
    assert observed[-1] == 5.0


def case(split: str = "development", horizon: int = 7) -> Case:
    cutoff = date(1998, 1, 31) if split == "development" else date(1998, 7, 31)
    return Case.model_validate({"case_id": f"{split}:{horizon}", "account": split, "split": split,
                                "cutoff": cutoff, "first_date": cutoff - timedelta(days=364),
                                "end_date": cutoff + timedelta(days=horizon), "horizon": horizon,
                                "history": (10.0,) * 365})


def test_case_when_history_date_extends_past_cutoff() -> None:
    # Given: a 365-value sequence labelled as starting one day too late.
    raw = case().model_dump()
    raw["first_date"] = date(1997, 2, 2)
    # When / Then: the shifted future-bearing window is rejected.
    with pytest.raises(ValidationError, match="History must end"):
        Case.model_validate(raw)


def test_bundle_when_training_account_is_reused_for_development() -> None:
    # Given: an account assigned to both learning and development.
    training = TrainingSeries(account="development", daily=(10.0,) * 365)
    # When / Then: account-level leakage fails before a worker can consume input.
    with pytest.raises(ValidationError, match="Account leakage"):
        Inputs(protocol_sha256="test", training=(training,), cases=(case(),))


def test_baselines_when_every_historical_day_has_same_outflow() -> None:
    # Given: constant 10 CZK daily outflows through a month boundary.
    observed = case(horizon=30)
    # When: every fixed baseline predicts the next 30 days.
    rows = predict(observed)
    # Then: calendar/weekday matching preserves a constant process exactly.
    assert {row.model for row in rows} == set(BASELINES)
    assert {row.point for row in rows} == {300.0}


def test_metrics_when_overprediction_and_underprediction_coexist() -> None:
    # Given: errors +2 and -5 CZK.
    actual = np.asarray([10.0, 20.0])
    predicted = np.asarray([12.0, 15.0])
    # When: absolute and signed errors are summarized.
    result = metrics(actual, predicted)
    # Then: cancellation affects bias only, not MAE/WAPE.
    assert result.mae_czk == 3.5
    assert result.mean_bias_czk == -1.5
    assert result.wape == pytest.approx(7 / 30)


def test_bootstrap_when_same_account_has_multiple_cutoffs() -> None:
    # Given: four forecasts but only two independent account clusters.
    sample = Sample(("a", "a", "b", "b"), np.asarray([10.0] * 4),
                    np.asarray([12.0] * 4), np.asarray([13.0] * 4))
    # When: paired uncertainty is estimated.
    result = confidence(sample)
    # Then: resampling retains account grouping and known constant error difference.
    assert result.accounts == 2
    assert result.mae_czk_95 == (2.0, 2.0)
    assert result.paired_wape_difference_95 == pytest.approx((-0.1, -0.1))


def test_selection_when_final_truth_does_not_exist(tmp_path: Path) -> None:
    # Given: only development truth exists, so opening final truth would fail.
    prepared, neural = prepared_fixture(tmp_path)
    # When: development selection runs through the actual module CLI.
    result = subprocess.run([sys.executable, "-m", "benchmarks.forecast.public_bank.evaluate", "select",  # noqa: S603 -- fixed Python module and isolated fixture paths.
                             str(prepared), str(neural)], capture_output=True, text=True, check=False)
    # Then: persisted selection succeeds without a final-answer dependency.
    assert result.returncode == 0, result.stderr
    assert (prepared / "selection.json").is_file()
    assert not (prepared / "evaluation_truth.json").exists()


def test_evaluation_when_prediction_changes_after_selection(tmp_path: Path) -> None:
    # Given: a frozen selection, then one changed model file.
    prepared, neural = prepared_fixture(tmp_path)
    select(prepared, neural)
    path = neural / "chronos_base_daily.predictions.json"
    rows = json.loads(path.read_text(encoding="utf-8"))
    rows[0]["point"] += 1
    path.write_text(json.dumps(rows), encoding="utf-8")
    # When / Then: mutation is caught before final truth is opened.
    with pytest.raises(ValueError, match="Neural run files"):
        evaluate(prepared, neural)


def test_evaluation_when_final_outflow_exceeds_prediction(tmp_path: Path) -> None:
    # Given: a choice frozen against development and a separately revealed later ledger.
    prepared, neural = prepared_fixture(tmp_path)
    select(prepared, neural)
    targets = final_targets(prepared)
    (prepared / "evaluation_truth.json").write_bytes(TypeAdapter(list[Truth]).dump_json(targets))
    # When: final evaluation opens the withheld truth.
    evaluate(prepared, neural)
    # Then: actual forecast error, rather than route/schema success, is reported.
    report = json.loads((prepared / "report.json").read_text(encoding="utf-8"))
    assert report["horizons"]["7"]["selected"]["mae_czk"] == 70.0
    assert report["horizons"]["30"]["selected"]["wape"] == 0.5


def test_evaluation_when_final_truth_changes_after_preparation(tmp_path: Path) -> None:
    # Given: selection knows the original final-target hash without reading its values.
    prepared, neural = prepared_fixture(tmp_path)
    select(prepared, neural)
    changed = final_targets(prepared, amount=10.0)
    (prepared / "evaluation_truth.json").write_bytes(TypeAdapter(list[Truth]).dump_json(changed))
    # When / Then: revised answers cannot improve a frozen benchmark silently.
    with pytest.raises(ValueError, match="Frozen evaluation truth"):
        evaluate(prepared, neural)


def test_evaluation_when_selected_candidate_is_changed(tmp_path: Path) -> None:
    # Given: an altered selection document but unchanged surrounding artifact hashes.
    prepared, neural = prepared_fixture(tmp_path)
    select(prepared, neural)
    path = prepared / "selection.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    document["choices"]["7"]["model_a"] = "chronos_base_daily"
    document["choices"]["7"]["model_b"] = "chronos_base_daily"
    path.write_text(json.dumps(document), encoding="utf-8")
    # When / Then: deterministic development selection detects the changed candidate.
    with pytest.raises(ValueError, match="Frozen choice"):
        evaluate(prepared, neural)


def test_selection_when_input_grid_is_shrunk(tmp_path: Path) -> None:
    # Given: a shortened input, with the manifest also rewritten to hide the byte change.
    prepared, neural = prepared_fixture(tmp_path)
    path = prepared / "model_inputs.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    document["cases"].pop()
    path.write_text(json.dumps(document), encoding="utf-8")
    manifest_path = prepared / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"]["model_inputs.json"] = sha256(path)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    # When / Then: the protocol cardinality prevents cherry-picking fewer cases.
    with pytest.raises(ValueError, match="Frozen forecast"):
        select(prepared, neural)


def test_selection_when_fine_tuning_did_not_change_weights(tmp_path: Path) -> None:
    # Given: model-named predictions with a truthful record that training changed no weights.
    prepared, neural = prepared_fixture(tmp_path)
    path = neural / "chronos_ft128_lr1e6_daily.training.json"
    record = json.loads(path.read_text(encoding="utf-8"))
    record["weights_changed"] = False
    path.write_text(json.dumps(record), encoding="utf-8")
    hashes_path = neural / "file_hashes.json"
    hashes = json.loads(hashes_path.read_text(encoding="utf-8"))
    hashes[path.name] = sha256(path)
    hashes_path.write_text(json.dumps(hashes), encoding="utf-8")
    # When / Then: a compatible prediction shape cannot establish fine-tuning provenance.
    with pytest.raises(ValueError, match="Fine-tuning provenance"):
        select(prepared, neural)
