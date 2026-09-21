"""Archive and restore bounded E2E evidence without runtime environments or credentials."""

import argparse
import hashlib
import json
import re
import stat
from pathlib import Path, PurePosixPath
from typing import Final, Literal
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from benchmarks.coaching.e2e.e2e import ROOT
from benchmarks.coaching.e2e.e2e_bundle import BundleEntry, BundleManifest
from benchmarks.coaching.e2e.e2e_contracts import Report
from coaching_service.schemas import Frozen, JsonDocument

_MAX_BYTES: Final = 32 * 1024 * 1024
_WINDOWS_RESERVED: Final = frozenset(
    ("con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)), *(f"lpt{i}" for i in range(1, 10)))
)


class Options(Frozen):
    command: Literal["build", "verify", "restore"]
    archive: Path = ROOT / "evidence" / "r5_e2e_evidence.zip"
    output: Path | None = None
    source: Path | None = None


def safe_path(name: str) -> PurePosixPath:
    path = PurePosixPath(name)
    if (
        not name
        or not path.parts
        or path.is_absolute()
        or name != path.as_posix()
        or ".." in path.parts
        or "\\" in name
        or ":" in name
        or any(
            part.endswith((" ", ".")) or part.split(".")[0].casefold() in _WINDOWS_RESERVED
            for part in path.parts
        )
        or any(
            part.casefold() in {".venv", "venv", "site-packages", "__pycache__", ".git"}
            for part in path.parts
        )
        or re.search(r"(?:^|/)(?:\.env(?:\..*)?|worker\.token|token)$", name, re.IGNORECASE)
        or re.search(
            r"\.(?:sqlite3?|db)(?:-(?:wal|shm|journal))?$|\.(?:token|key|pem|p12)$", name, re.IGNORECASE
        )
    ):
        raise ValueError("Unsafe or excluded evidence archive path")
    return path


def write_archive(payloads: dict[str, bytes], output: Path) -> BundleManifest:
    """검증한 payload와 실제 Report.cases 수를 묶어 재검증 가능한 증거를 작성한다."""
    sidecar = output.with_suffix(".manifest.json")
    if output.exists() or sidecar.exists():
        raise FileExistsError("Evidence archive outputs must be new")
    entries = tuple(
        BundleEntry(path=safe_path(name).as_posix(), bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
        for name, data in sorted(payloads.items())
    )
    validate_entries(entries)
    case_count = report_case_count(payloads)
    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output, "x", compression=ZIP_DEFLATED, compresslevel=6) as archive:
        for entry in entries:
            info = ZipInfo(entry.path, date_time=(2026, 9, 9, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, payloads[entry.path])
    manifest = BundleManifest(
        archive_sha256=hashlib.sha256(output.read_bytes()).hexdigest(), case_count=case_count, entries=entries
    )
    _ = sidecar.write_bytes(manifest.model_dump_json(indent=2).encode("utf-8"))
    return manifest


def report_case_count(payloads: dict[str, bytes]) -> int:
    """실제 Report.cases 길이를 기록하고 검증한다. 보고서가 없는 일반 증거는 사례 수 0이다."""
    report = payloads.get("report.json")
    return len(Report.model_validate_json(report).cases) if report is not None else 0


def validate_entries(entries: tuple[BundleEntry, ...]) -> None:
    names = [safe_path(entry.path).as_posix().casefold() for entry in entries]
    if not entries or len(names) != len(set(names)):
        raise ValueError("Archive entries must be nonempty and unique on all supported filesystems")
    if any(entry.bytes < 0 or not re.fullmatch(r"[0-9a-f]{64}", entry.sha256) for entry in entries):
        raise ValueError("Invalid archive entry length or hash")
    if len(entries) > 256 or sum(entry.bytes for entry in entries) > _MAX_BYTES:
        raise ValueError("Evidence archive exceeds its entry or byte limit")


def verified_payloads(path: Path) -> tuple[BundleManifest, dict[str, bytes]]:
    """파일 해시와 보고서의 실제 사례 수까지 대조해 manifest의 완료 분모를 검증한다."""
    sidecar = path.with_suffix(".manifest.json")
    if path.stat().st_size > _MAX_BYTES or sidecar.stat().st_size > 128 * 1024:
        raise ValueError("Archive or manifest exceeds its byte limit")
    manifest = BundleManifest.model_validate_json(sidecar.read_bytes())
    validate_entries(manifest.entries)
    if hashlib.sha256(path.read_bytes()).hexdigest() != manifest.archive_sha256:
        raise ValueError("Archive SHA-256 mismatch")
    payloads: dict[str, bytes] = {}
    with ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or set(names) != {entry.path for entry in manifest.entries}:
            raise ValueError("Archive contents differ from the manifest")
        for entry in manifest.entries:
            info = archive.getinfo(entry.path)
            if info.file_size != entry.bytes or stat.S_ISLNK(info.external_attr >> 16):
                raise ValueError("Archive contains an unexpected length or symlink")
            data = archive.read(info)
            if hashlib.sha256(data).hexdigest() != entry.sha256:
                raise ValueError("Archived file SHA-256 mismatch")
            payloads[entry.path] = data
    if manifest.case_count != report_case_count(payloads):
        raise ValueError("Evidence manifest case count differs from the report")
    return manifest, payloads


def restore_archive(path: Path, output: Path) -> BundleManifest:
    manifest, payloads = verified_payloads(path)
    target = output.resolve()
    if target.exists():
        raise FileExistsError("Restore directory must be new")
    for name in payloads:
        if not (target / safe_path(name)).resolve().is_relative_to(target):
            raise ValueError("Archive target escapes the restore directory")
    target.mkdir(parents=True)
    for name, data in payloads.items():
        destination = target / safe_path(name)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("xb") as stream:
            _ = stream.write(data)
    return manifest


def build_evidence(source: Path, output: Path) -> BundleManifest:
    """Package one explicit R5 run; never ingest historical R4 reports or log identifiers."""
    payloads = {
        name: (source / name).read_bytes() for name in ("report.json", "freeze.json", "verification.json")
    }
    report = Report.model_validate_json(payloads["report.json"])
    freeze = JsonDocument.model_validate_json(payloads["freeze.json"])
    verification = JsonDocument.model_validate_json(payloads["verification.json"])
    if freeze.root.get("experiment") != report.experiment:
        raise ValueError("Evidence must identify the current R5 experiment")
    if (
        verification.root.get("source_hashes_unchanged") is not True
        or verification.root.get("report_sha256") != hashlib.sha256(payloads["report.json"]).hexdigest()
    ):
        raise ValueError("Evidence source stability and report SHA-256 must verify")
    return write_archive(payloads, output)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument("command", choices=("build", "verify", "restore"))
    _ = parser.add_argument("--archive", type=Path, default=ROOT / "evidence" / "r5_e2e_evidence.zip")
    _ = parser.add_argument("--output", type=Path)
    _ = parser.add_argument("--source", type=Path)
    options = Options.model_validate(vars(parser.parse_args()))
    if options.command == "build":
        if options.source is None:
            raise ValueError("Build requires an explicit R5 run source directory")
        manifest = build_evidence(options.source, options.archive)
    elif options.command == "restore":
        if options.output is None:
            raise ValueError("Restore requires a new output directory")
        manifest = restore_archive(options.archive, options.output)
    else:
        manifest, _ = verified_payloads(options.archive)
    print(  # noqa: T201 - CLI reports only verified archive hashes and counts.
        json.dumps(
            {"archive_sha256": manifest.archive_sha256, "files": len(manifest.entries), "model_calls": 0}
        )
    )


if __name__ == "__main__":
    main()
