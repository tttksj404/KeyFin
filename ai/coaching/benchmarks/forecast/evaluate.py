# /// script
# requires-python = ">=3.11"
# dependencies = ["pydantic", "numpy"]
# ///
# How to run: python -m benchmarks.forecast.evaluate /private/prepared /private/bundle.json /private/analysis
# ruff: noqa: T201
"""Replay saved accelerator predictions without calling a model or changing forecasts."""

import hashlib
import json
import sys
from pathlib import Path
from typing import Final

from pydantic import TypeAdapter

from .archive import load_archive
from .contracts import Calibration, Family, Forecast, Frozen, InputBundle, MetricSet, Truth
from .data import FAMILIES
from .protocol import TUNED_MODELS, validate_prediction_grid
from .scoring import expanded, summarize
from .selection import calibrate, choose

HERE: Final = Path(__file__).resolve().parent


class ModelReport(Frozen):
    raw: MetricSet
    calibrated: MetricSet
    families: dict[Family, MetricSet]
    users: dict[str, MetricSet]


class Lock(Frozen):
    selections: dict[str, str]
    calibration: tuple[Calibration, ...]
    model_input_sha256: str
    remote_bundle_sha256: str
    source_sha256: dict[str, str]


def main() -> None:
    """원문 무결성과 필수 예측 키를 검증한 뒤 동일한 개발·평가 기간 규약으로 점수를 쓴다.

    같은 값이라도 정답 키 중복은 거절한다. 마지막 행이 앞선 정답을 덮어쓰지 않도록
    결과 디렉터리를 만들기 전에 입력의 유일성을 확인한다.
    """
    prepared, remote_path, destination = (Path(value).resolve() for value in sys.argv[1:4])
    remote = load_archive(remote_path, prepared / "model_inputs.json")
    bundle = InputBundle.model_validate_json((prepared / "model_inputs.json").read_bytes())
    truths = TypeAdapter(list[Truth]).validate_json((prepared / "truth.json").read_bytes())
    truth = {row.case_id: row.actual for row in truths}
    if len(truth) != len(truths):
        raise ValueError("Duplicate truth case key")
    forecasts = TypeAdapter(list[Forecast]).validate_json((prepared / "baselines.json").read_bytes())
    for name, value in remote.files.items():
        if name.endswith(".predictions.json"):
            forecasts.extend(TypeAdapter(list[Forecast]).validate_python(value))
    cases = {case.case_id: case for case in bundle.cases}
    if len(cases) != len(bundle.cases) or set(cases) != set(truth):
        raise ValueError("Case and truth keys disagree")
    validate_prediction_grid(bundle.cases, forecasts)
    index = {(row.model, row.fold, row.case_id): row for row in forecasts}
    destination.mkdir(exist_ok=False)
    models = sorted({row.model for row in forecasts})
    users = sorted({case.user for case in bundle.cases})
    selections: dict[str, str] = {}
    calibrations: list[Calibration] = []
    raw: dict[str, list[Forecast]] = {name: [] for name in models}
    corrected: dict[str, list[Forecast]] = {name: [] for name in models}
    selected: list[Forecast] = []
    selected_raw: list[Forecast] = []
    for user in users:
        development = [case for case in bundle.cases if case.split == "development" and case.user != user]
        evaluation = [case for case in bundle.cases if case.split == "evaluation" and case.user == user]
        dev_predictions = {
            name: [index[(name, user if name in TUNED_MODELS else "common", case.case_id)]
                   for case in development] for name in models
        }
        selections[user] = choose(dev_predictions, truth)
        for name in models:
            corrections = {family: calibrate(
                user, family, [row for row in dev_predictions[name] if cases[row.case_id].family == family],
                cases, truth,
            ) for family in FAMILIES}
            calibrations.extend(corrections.values())
            for case in evaluation:
                row = index[(name, user if name in TUNED_MODELS else "common", case.case_id)]
                fixed = expanded(row, case, corrections[case.family].radius)
                raw[name].append(row)
                corrected[name].append(fixed)
                if name == selections[user]:
                    selected.append(fixed)
                    selected_raw.append(row)
    lock = Lock(selections=selections, calibration=tuple(calibrations),
                model_input_sha256=hashlib.sha256((prepared / "model_inputs.json").read_bytes()).hexdigest(),
                remote_bundle_sha256=hashlib.sha256(remote_path.read_bytes()).hexdigest(),
                source_sha256={p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                               for p in sorted(HERE.glob("*.py"))})
    _ = (destination / "selection_lock.json").write_text(lock.model_dump_json(indent=2), encoding="utf-8")
    reports = {name: ModelReport(
        raw=summarize(raw[name], truth), calibrated=summarize(corrected[name], truth),
        families={family: summarize(
            [row for row in corrected[name] if cases[row.case_id].family == family], truth,
        )
                  for family in FAMILIES},
        users={user: summarize([row for row in corrected[name] if cases[row.case_id].user == user], truth)
               for user in users},
    ) for name in models}
    reports["development_selected"] = ModelReport(
        raw=summarize(selected_raw, truth), calibrated=summarize(selected, truth),
        families={family: summarize([row for row in selected if cases[row.case_id].family == family], truth)
                  for family in FAMILIES},
        users={user: summarize([row for row in selected if cases[row.case_id].user == user], truth)
               for user in users},
    )
    _ = (destination / "scores.json").write_bytes(
        TypeAdapter(dict[str, ModelReport]).dump_json(reports, indent=2),
    )
    _ = (destination / "selected_predictions.json").write_bytes(
        TypeAdapter(list[Forecast]).dump_json(selected),
    )
    print(json.dumps({name: {"wape": result.calibrated.wape, "coverage": result.calibrated.coverage80,
                            "normalized_wis": result.calibrated.normalized_wis}
                      for name, result in reports.items()}))
    print("R7_SCORED")


if __name__ == "__main__":
    main()
