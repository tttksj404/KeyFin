# /// script
# requires-python = ">=3.11"
# dependencies = ["pydantic", "numpy", "jsonschema"]
# ///
# How to run: from the service directory, python -m benchmarks.forecast.prepare
# ruff: noqa: T201
"""Freeze model-only inputs, independent outcomes and current FDT baselines."""

import hashlib
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Final

from pydantic import TypeAdapter

from benchmarks.forecast.ledger_adapter.engine_path import Request, execute
from benchmarks.forecast.ledger_adapter.ledger import read_ledger

from .baselines import predict
from .contracts import Forecast, ForecastCase, InputBundle, Series, Truth
from .data import TRAINING_END, build_cases, observed_series

if TYPE_CHECKING:
    from benchmarks.forecast.ledger_adapter.contracts import EngineOutput

HERE: Final = Path(__file__).resolve().parent


def main() -> None:
    data_directory, out = (Path(value).resolve() for value in sys.argv[1:3])
    out.mkdir(exist_ok=False)
    raw_dir = out / "fdt_raw"
    raw_dir.mkdir()
    cases: list[ForecastCase] = []
    outcomes: list[Truth] = []
    training: list[Series] = []
    forecasts: list[Forecast] = []
    hashes: dict[str, str] = {}
    for index in range(1, 5):
        source = data_directory / f"consumer_{index:03}.csv"
        hashes[source.name] = hashlib.sha256(source.read_bytes()).hexdigest()
        rows = read_ledger(source)
        training.extend(observed_series(rows, TRAINING_END))
        cache: dict[str, EngineOutput] = {}
        for split in ("development", "evaluation"):
            tasks, actuals = build_cases(rows, split)
            cases.extend(tasks)
            outcomes.extend(actuals)
            for case in tasks:
                key = f"{index}_{case.cutoff}_{case.horizon}"
                if key not in cache:
                    observed = tuple(row for row in rows if row.transaction_date <= case.cutoff)
                    result = execute(observed, Request(case.cutoff, case.horizon))
                    cache[key] = result.output
                    _ = (raw_dir / f"{key}.result.json").write_text(
                        result.raw.model_dump_json(), encoding="utf-8",
                    )
                    _ = (raw_dir / f"{key}.input.json").write_text(
                        result.bootstrap.model_dump_json(), encoding="utf-8",
                    )
                    _ = (raw_dir / f"{key}.request.json").write_text(
                        result.request.model_dump_json(), encoding="utf-8",
                    )
                envelope = next(row for row in cache[key].datasets.envelopes if row.envelope == case.envelope)
                forecasts.extend(predict(case))
                forecasts.append(Forecast(case_id=case.case_id, model="fdt", point=envelope.p50_krw,
                                          lower=envelope.p10_krw, upper=envelope.p90_krw))
    bundle = InputBundle(training_end=TRAINING_END, training=tuple(training), cases=tuple(cases))
    _ = (out / "model_inputs.json").write_text(bundle.model_dump_json(), encoding="utf-8")
    _ = (out / "truth.json").write_bytes(TypeAdapter(list[Truth]).dump_json(outcomes))
    _ = (out / "baselines.json").write_bytes(TypeAdapter(list[Forecast]).dump_json(forecasts))
    manifest = {
        "protocol_sha256": hashlib.sha256((HERE / "README.md").read_bytes()).hexdigest(),
        "target_definition": "future_total_variable_consumption/v1",
        "outcome_calculator": "separate_spec_implementation_not_human_oracle/v1",
        "source_csv_sha256": hashes, "cases": len(cases), "users": len({case.user for case in cases}),
        "training_series": len(training), "training_end": str(TRAINING_END),
        "input_sha256": hashlib.sha256((out / "model_inputs.json").read_bytes()).hexdigest(),
        "truth_sha256": hashlib.sha256((out / "truth.json").read_bytes()).hexdigest(),
        "files": {path.relative_to(out).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                  for path in sorted(out.rglob("*.json"))},
    }
    _ = (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"cases": len(cases), "users": manifest["users"], "training_series": len(training)}))
    print("R7_INPUTS_FROZEN")


if __name__ == "__main__":
    main()
