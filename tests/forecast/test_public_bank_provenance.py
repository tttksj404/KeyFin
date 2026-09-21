"""Provenance checks must inspect source and arithmetic, not assertion flags."""

import json
from pathlib import Path

import pytest

from benchmarks.forecast.public_bank.data import sha256
from benchmarks.forecast.public_bank.evaluate import select

from .test_public_bank_fixtures import prepared_fixture


def test_selection_when_contract_source_changes_despite_claimed_equality(tmp_path: Path) -> None:
    # Given: preserved source with a weaker history validator and an untrusted equality claim.
    prepared, neural = prepared_fixture(tmp_path)
    source = neural / "source_snapshot/benchmarks/forecast/public_bank/contracts.py"
    changed = source.read_text(encoding="utf-8").replace(
        "Field(min_length=365, max_length=365)", "Field(min_length=1, max_length=365)", 1)
    source.write_text(changed, encoding="utf-8")
    runtime_path = neural / "runtime.json"
    runtime = json.loads(runtime_path.read_text(encoding="utf-8"))
    runtime["source_sha256"]["contracts.py"] = sha256(source)
    runtime_path.write_text(json.dumps(runtime), encoding="utf-8")
    hashes_path = neural / "file_hashes.json"
    hashes = json.loads(hashes_path.read_text(encoding="utf-8"))
    hashes["runtime.json"] = sha256(runtime_path)
    hashes_path.write_text(json.dumps(hashes), encoding="utf-8")
    (prepared / "worker_source_comparison.json").write_text(
        '{"ast_equal":{"contracts":true}}', encoding="utf-8")
    # When / Then: actual AST comparison rejects the changed dependency before opening final truth.
    with pytest.raises(ValueError, match="Worker contract dependency"):
        select(prepared, neural)


def test_selection_when_baseline_prediction_is_rewritten(tmp_path: Path) -> None:
    # Given: a complete baseline file whose numbers no longer follow the frozen algorithm.
    prepared, neural = prepared_fixture(tmp_path)
    path = prepared / "predictions/recent90.predictions.json"
    rows = json.loads(path.read_text(encoding="utf-8"))
    rows[0]["point"] = 1000
    path.write_text(json.dumps(rows), encoding="utf-8")
    # When / Then: recomputation catches the changed comparator instead of selecting against it.
    with pytest.raises(ValueError, match="Stored baseline"):
        select(prepared, neural)
