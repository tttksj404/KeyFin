"""Separate commands lock development selection and calibration before opening test truth."""

import json
import sys
from pathlib import Path

from benchmarks.forecast.public_bank.data import sha256

from .artifacts import CalibrationLock, Prepared, SelectionLock, freeze, truth_for, verify_lock, write_new
from .report import horizon_report
from .scoring import calibration_radius
from .selection import choose


def select(prepared: Path, gpu: Path, output: Path) -> None:
    """Commit all candidate choices before calibration/evaluation outcomes can be used."""
    bundle = freeze(prepared, gpu)
    truth = truth_for(prepared, bundle.inputs, "development")
    cases = tuple(row for row in bundle.inputs.cases if row.split == "development")
    choices = choose(cases, truth, bundle.bank)
    output.mkdir(parents=True, exist_ok=False)
    write_new(output / "selection.json", SelectionLock(hashes=dict(bundle.hashes), choices=choices))
    _ = sys.stdout.write(json.dumps({str(key): {"selected": value.selected, "baseline": value.baseline,
                                           "development_mae": value.development_mae[value.selected]}
                                for key, value in choices.items()}) + "\nAGGREGATE_SELECTION_LOCKED\n")


def calculate_radii(
    prepared: Path, bundle: Prepared, selection: SelectionLock,
) -> dict[int, dict[str, float]]:
    """Reproducible calibration prevents hand-edited interval widths from passing a lock."""
    truth = {row.case_id: row.actual for row in truth_for(prepared, bundle.inputs, "calibration")}
    radii: dict[int, dict[str, float]] = {}
    for horizon, choice in selection.choices.items():
        cases = tuple(row for row in bundle.inputs.cases
                      if row.split == "calibration" and row.horizon == horizon)
        radii[horizon] = {}
        for name in {choice.selected, choice.baseline}:
            scores: list[float] = []
            for case in cases:
                row = bundle.bank.rows[name][case.case_id]
                scale = max(row.point, bundle.bank.rows["recent90"][case.case_id].point, 1.0)
                actual = truth[case.case_id]
                scores.append(max(row.lower - actual, actual - row.upper, 0) / scale)
            radii[horizon][name] = calibration_radius(tuple(scores))
    return radii


def calibrate(prepared: Path, gpu: Path, output: Path) -> None:
    """Use only separate calibration accounts to set interval widths."""
    bundle = freeze(prepared, gpu)
    selection = SelectionLock.model_validate_json((output / "selection.json").read_bytes())
    verify_lock(selection, bundle)
    radii = calculate_radii(prepared, bundle, selection)
    write_new(output / "calibration.json", CalibrationLock(
        selection_sha256=sha256(output / "selection.json"),
        calibration_truth_sha256=sha256(prepared / "calibration_truth.json"), radii=radii))
    _ = sys.stdout.write("AGGREGATE_CALIBRATION_LOCKED\n")


def evaluate(prepared: Path, gpu: Path, output: Path) -> None:
    """Open unseen evaluation observations only after verifying both previous locks."""
    if (output / "report.json").exists():
        raise FileExistsError("Evaluation report already exists")
    bundle = freeze(prepared, gpu)
    selection = SelectionLock.model_validate_json((output / "selection.json").read_bytes())
    calibration = CalibrationLock.model_validate_json((output / "calibration.json").read_bytes())
    verify_lock(selection, bundle)
    if calibration.selection_sha256 != sha256(output / "selection.json"):
        raise ValueError("Selection changed after calibration")
    if calibration.calibration_truth_sha256 != sha256(prepared / "calibration_truth.json"):
        raise ValueError("Calibration targets changed")
    # Independently recompute selection from development to reject a hand-edited lock.
    choices = choose(tuple(row for row in bundle.inputs.cases if row.split == "development"),
                     truth_for(prepared, bundle.inputs, "development"), bundle.bank)
    if choices != selection.choices:
        raise ValueError("Selection no longer matches the development-only procedure")
    if calibration.radii != calculate_radii(prepared, bundle, selection):
        raise ValueError("Interval widths no longer match the calibration-only procedure")
    truth = {row.case_id: row.actual for row in truth_for(prepared, bundle.inputs, "evaluation")}
    horizons = {str(horizon): horizon_report(
        tuple(row for row in bundle.inputs.cases if row.split == "evaluation" and row.horizon == horizon),
        truth, bundle.bank, choice, calibration.radii[horizon])
        for horizon, choice in selection.choices.items()}
    report = {
        "protocol_sha256": bundle.inputs.protocol_sha256,
        "selection_sha256": sha256(output / "selection.json"),
        "calibration_sha256": sha256(output / "calibration.json"),
        "currency": "CZK", "target": "gross_account_outflow",
        "current_korean_customer_accuracy_validated": False,
        "independent_human_oracle": False, "horizons": horizons,
    }
    with (output / "report.json").open("x", encoding="utf-8") as stream:
        _ = json.dump(report, stream, indent=2, allow_nan=False)
    _ = sys.stdout.write(json.dumps({key: {"selected": value["selected_model"],
                                      "mae_reduction": value["relative_mae_reduction"],
                                      "gate": value["research_gate_passed"]}
                                for key, value in horizons.items()}) + "\nAGGREGATE_EVALUATED\n")


if __name__ == "__main__":
    commands = {"select": select, "calibrate": calibrate, "evaluate": evaluate}
    commands[sys.argv[1]](Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4]))
