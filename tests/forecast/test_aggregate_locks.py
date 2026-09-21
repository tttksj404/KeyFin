"""Reject a modified interval lock before the first read of final evaluation outcomes."""

from datetime import timedelta
from pathlib import Path

import pytest
from pydantic import TypeAdapter

from benchmarks.forecast.aggregate import evaluate
from benchmarks.forecast.aggregate.arithmetic import EXTRA, NEURAL
from benchmarks.forecast.aggregate.artifacts import (
    CalibrationLock,
    Prepared,
    SelectionLock,
    truth_for,
    write_new,
)
from benchmarks.forecast.aggregate.contracts import Inputs, Prediction, Split
from benchmarks.forecast.aggregate.selection import candidate_bank, choose
from benchmarks.forecast.public_bank.baselines import BASELINES
from benchmarks.forecast.public_bank.contracts import TrainingSeries, Truth

from .test_aggregate import case


def test_edited_calibration_cannot_reach_final_truth(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given: invented development/calibration examples, with no final-truth file at all.
    splits: tuple[Split, ...] = ("development", "calibration", "evaluation")
    rows = tuple(case(split=split, account=f"{split}-{index}").model_copy(update={
        "case_id": f"{split}-{index}-{horizon}", "horizon": horizon,
        "end_date": case().cutoff + timedelta(days=horizon),
    }) for split in splits for index in range(4) for horizon in (7, 30))
    inputs = Inputs(protocol_sha256="a" * 64, cases=rows,
                    training=(TrainingSeries(account="training", daily=(0.0,) * 365),))
    predictions = tuple(Prediction(case_id=row.case_id, model=name, point=10, lower=10, upper=10)
                        for row in rows for name in BASELINES + EXTRA + NEURAL)
    bundle = Prepared(inputs, candidate_bank(rows, predictions), {})
    targets = TypeAdapter(tuple[Truth, ...])
    for split in ("development", "calibration"):
        observed = tuple(Truth(case_id=row.case_id, actual=20) for row in rows if row.split == split)
        _ = (tmp_path / f"{split}_truth.json").write_bytes(targets.dump_json(observed))
    choices = choose(tuple(row for row in rows if row.split == "development"),
                     truth_for(tmp_path, inputs, "development"), bundle.bank)
    write_new(tmp_path / "selection.json", SelectionLock(hashes={}, choices=choices))

    def checked_fixture(_prepared: Path, _gpu: Path) -> Prepared:
        return bundle

    # The source verification layer has separate tests; isolate lock ordering here.
    monkeypatch.setattr(evaluate, "freeze", checked_fixture)
    evaluate.calibrate(tmp_path, tmp_path, tmp_path)
    path = tmp_path / "calibration.json"
    original = CalibrationLock.model_validate_json(path.read_bytes())
    modified = original.model_copy(update={"radii": {
        horizon: {name: value + 1 for name, value in values.items()}
        for horizon, values in original.radii.items()
    }})
    _ = path.write_text(modified.model_dump_json(), encoding="utf-8")
    # When/Then: same source hashes cannot legitimize an edited calibration parameter.
    # Reaching truth_for(evaluation) would raise FileNotFoundError instead.
    with pytest.raises(ValueError, match="calibration-only"):
        evaluate.evaluate(tmp_path, tmp_path, tmp_path)
    assert not (tmp_path / "report.json").exists()
