"""The fixed R7 candidate grid must be complete before any scoring artifacts are written."""

import hashlib
import json
from datetime import date
from pathlib import Path

import pytest
from pydantic import TypeAdapter

from benchmarks.forecast.bundle import export
from benchmarks.forecast.contracts import Forecast, ForecastCase, InputBundle, Truth
from benchmarks.forecast.data import FAMILIES, end_for
from benchmarks.forecast.evaluate import main


def protocol_inputs(tmp_path: Path, *, missing: str | None, zero: bool) -> tuple[Path, Path, Path]:
    cases: list[ForecastCase] = []
    for user in ("one", "two"):
        for split, cutoff in (("development", date(2026, 7, 1)), ("evaluation", date(2026, 8, 1))):
            for family in FAMILIES:
                end = end_for(cutoff, family)
                cases.append(ForecastCase(case_id=f"{user}/{split}/{family}", user=user, envelope="기타",
                                          split=split, family=family, first_date=cutoff, cutoff=cutoff,
                                          end_date=end, horizon=(end-cutoff).days, history=(100.0,)))
    prepared = tmp_path / "prepared"
    prepared.mkdir()
    inputs = prepared / "model_inputs.json"
    _ = inputs.write_text(InputBundle(training_end=date(2026, 6, 30), training=(), cases=tuple(cases))
                          .model_dump_json(), encoding="utf-8")
    truths = [Truth(case_id=case.case_id, actual=0 if zero else 100) for case in cases]
    _ = (prepared / "truth.json").write_bytes(TypeAdapter(list[Truth]).dump_json(truths))
    baseline = [Forecast(case_id=case.case_id, model=name, point=100) for case in cases
                for name in ("fdt", "all_mean", "recent28", "weekday_shrink")]
    _ = (prepared / "baselines.json").write_bytes(TypeAdapter(list[Forecast]).dump_json(baseline))
    common = [Forecast(case_id=case.case_id, model=name, point=100) for case in cases for name in (
        "chronos_base_daily", "chronos_base_cumulative", "chronos_previous_daily",
        "chronos_previous_cumulative", "timesfm_cumulative",
    )]
    tuned = [Forecast(case_id=case.case_id, model=name, fold=fold, point=100)
             for name in ("chronos_ft64", "chronos_ft128") for fold in ("one", "two") for case in cases
             if (case.split == "development" and case.user != fold)
             or (case.split == "evaluation" and case.user == fold)]
    neural = common + tuned
    if missing == "all":
        neural = []
    elif missing == "fold":
        neural = [row for row in neural if not (row.model == "chronos_ft64" and row.fold == "one")]
    elif missing == "row":
        neural.pop()
    worker = tmp_path / "worker"
    worker.mkdir()
    _ = (worker / "runtime.json").write_text(json.dumps({
        "input_sha256": hashlib.sha256(inputs.read_bytes()).hexdigest(),
    }), encoding="utf-8")
    _ = (worker / "complete.predictions.json").write_bytes(TypeAdapter(list[Forecast]).dump_json(neural))
    _ = (worker / "completed.json").write_text('{"completed":true}', encoding="utf-8")
    archive = tmp_path / "bundle.json"
    export(worker, archive)
    return prepared, archive, tmp_path / "analysis"


@pytest.mark.parametrize("missing", ["all", "fold", "row"])
def test_missing_neural_candidates_or_fold_rows_stop_before_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, missing: str,
) -> None:
    # Given populated cases/truth/baselines but an incomplete neural prediction grid.
    prepared, archive, destination = protocol_inputs(tmp_path, missing=missing, zero=False)
    monkeypatch.setattr("sys.argv", ["evaluate", str(prepared), str(archive), str(destination)])
    # When the actual evaluation runner is invoked.
    # Then it reports missing protocol evidence before creating scoring output.
    with pytest.raises(ValueError, match=r"prediction.*grid|protocol"):
        main()
    assert not destination.exists()


@pytest.mark.parametrize("zero", [False, True])
def test_complete_protocol_scores_every_evaluation_case(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, zero: bool,
) -> None:
    # Given a complete common-model and held-out-user model grid.
    prepared, archive, destination = protocol_inputs(tmp_path, missing=None, zero=zero)
    monkeypatch.setattr("sys.argv", ["evaluate", str(prepared), str(archive), str(destination)])
    # When scoring positive or zero actual spending.
    main()
    # Then all eleven models and the selected candidate preserve the full evaluation denominator.
    scores = json.loads((destination / "scores.json").read_bytes())
    assert len(scores) == 12
    assert all(row["raw"]["count"] == 8 for row in scores.values())
    if zero:
        assert all(row["raw"]["wape"] is None for row in scores.values())


@pytest.mark.parametrize("duplicate_actual", [100.0, 200.0], ids=["same_value", "different_value"])
def test_duplicate_truth_is_rejected_before_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, duplicate_actual: float,
) -> None:
    # Given a complete prediction grid with a repeated evaluation truth key.
    prepared, archive, destination = protocol_inputs(tmp_path, missing=None, zero=False)
    truth_path = prepared / "truth.json"
    truths = TypeAdapter(list[Truth]).validate_json(truth_path.read_bytes())
    original = next(row for row in truths if "/evaluation/" in row.case_id)
    truths.append(original.model_copy(update={"actual": duplicate_actual}))
    _ = truth_path.write_bytes(TypeAdapter(list[Truth]).dump_json(truths))
    monkeypatch.setattr("sys.argv", ["evaluate", str(prepared), str(archive), str(destination)])
    # When scoring either equal or conflicting duplicate answers.
    # Then no answer may be silently overwritten, and no output directory is created.
    with pytest.raises(ValueError, match="Duplicate truth"):
        main()
    assert not destination.exists()
