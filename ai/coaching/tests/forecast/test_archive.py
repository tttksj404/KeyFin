"""An old worker run cannot silently score a different set of inputs."""

import hashlib
import json
from pathlib import Path

import pytest

from benchmarks.forecast.bundle import export
from benchmarks.forecast.evaluate import load_archive


def exported_archive(tmp_path: Path) -> tuple[Path, Path, bytes]:
    inputs = tmp_path / "inputs.json"
    _ = inputs.write_bytes(b"observed-inputs")
    worker = tmp_path / "worker"
    worker.mkdir()
    runtime = json.dumps({"input_sha256": hashlib.sha256(inputs.read_bytes()).hexdigest(),
                          "enabled": True}, indent=2).replace("\n", "\r\n").encode("utf-8")
    _ = (worker / "runtime.json").write_bytes(runtime)
    _ = (worker / "sample.predictions.json").write_bytes(b'[{"case_id":"sample","point":100}]')
    _ = (worker / "completed.json").write_text('{"completed":true}', encoding="utf-8")
    bundle = tmp_path / "bundle.json"
    export(worker, bundle)
    return bundle, inputs, runtime


@pytest.mark.parametrize("finished", [False, True])
def test_incomplete_or_mismatched_worker_archive_is_rejected(tmp_path: Path, *, finished: bool) -> None:
    bundle, inputs, _ = exported_archive(tmp_path)
    _ = inputs.write_bytes(b"new-observed-inputs")
    payload = json.loads(bundle.read_bytes())
    payload["finished"] = finished
    _ = bundle.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match=r"inputs|incomplete"):
        load_archive(bundle, inputs)


def test_export_preserves_raw_utf8_bytes_with_explicit_v2_contract(tmp_path: Path) -> None:
    # Given original CRLF bytes, which cannot be recovered from a parsed JSON object.
    bundle, inputs, runtime = exported_archive(tmp_path)
    # When exporting and loading the archive.
    payload = json.loads(bundle.read_bytes())
    # Then the raw-byte SHA contract survives without newline normalization.
    assert payload["schema_version"] == 2
    assert payload["raw_files"]["runtime.json"].encode("utf-8") == runtime
    assert payload["sha256"]["runtime.json"] == hashlib.sha256(runtime).hexdigest()
    assert load_archive(bundle, inputs).finished is True


@pytest.mark.parametrize("corruption", ["digest", "value", "raw", "keys", "raw_keys", "json_type"])
def test_archive_rejects_digest_content_and_key_set_mismatches(tmp_path: Path, corruption: str) -> None:
    # Given an exported archive whose input identifier still matches.
    bundle, inputs, _ = exported_archive(tmp_path)
    payload = json.loads(bundle.read_bytes())
    if corruption == "digest":
        payload["sha256"]["runtime.json"] = "0" * 64
    elif corruption == "value":
        payload["files"]["sample.predictions.json"][0]["point"] = 0
    elif corruption == "raw":
        payload["raw_files"]["sample.predictions.json"] = "[]"
    elif corruption == "keys":
        del payload["sha256"]["sample.predictions.json"]
    elif corruption == "raw_keys":
        del payload["raw_files"]["sample.predictions.json"]
    else:
        payload["files"]["runtime.json"]["enabled"] = 1
    _ = bundle.write_text(json.dumps(payload), encoding="utf-8")
    # When a hash, parsed value, key set or JSON type changes.
    # Then input identity alone cannot admit the corrupted result.
    with pytest.raises(ValueError, match=r"hash|SHA|content|keys|data"):
        load_archive(bundle, inputs)


def test_legacy_archive_requires_reexport_from_original_results(tmp_path: Path) -> None:
    # Given a legacy archive with no recoverable raw JSON bytes.
    bundle, inputs, _ = exported_archive(tmp_path)
    payload = json.loads(bundle.read_bytes())
    payload.pop("schema_version", None)
    payload.pop("raw_files", None)
    _ = bundle.write_text(json.dumps(payload), encoding="utf-8")
    # When evaluating it.
    # Then the old hash meaning is preserved by requiring an explicit re-export.
    with pytest.raises(ValueError, match="re-export"):
        load_archive(bundle, inputs)
