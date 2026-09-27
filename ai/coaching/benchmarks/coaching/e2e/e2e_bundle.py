"""Create a runtime-only E2E archive with scoring labels and previous results excluded."""

import argparse
import hashlib
import json
from pathlib import Path
from typing import Final
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from pydantic import Field

from benchmarks.coaching.e2e.e2e import ROOT, load_cases
from coaching_service.schemas import Frozen, JsonDocument

_INPUT_FIELDS: Final = {
    "case_id",
    "owner",
    "envelope",
    "category",
    "subcategory",
    "amount_krw",
    "balance_krw",
    "snapshot",
    "action",
    "question",
    "analyses",
}


class BundleEntry(Frozen):
    path: str
    bytes: int
    sha256: str


class BundleManifest(Frozen):
    archive_sha256: str
    case_count: int = Field(ge=0)
    entries: tuple[BundleEntry, ...]


class BundleOptions(Frozen):
    output: Path


def build_bundle(output: Path) -> BundleManifest:
    """라벨을 제거한 실행 코드를 묶고 wheel 필수 manifest와 차트 자산도 함께 보존한다.

    원격 복원본의 pyproject가 같은 파일을 force-include하므로 차트 API를 호출하지 않는
    코칭 평가에도 이 파일들이 있어야 환경을 정상 설치할 수 있다.
    """
    sidecar = output.with_suffix(".manifest.json")
    if output.exists() or sidecar.exists():
        raise FileExistsError("Runtime bundle outputs must be new")
    service = ROOT.parents[2]
    paths = [*ROOT.glob("e2e*.py"), ROOT / "__init__.py"]
    paths = [path for path in paths if path.name not in {"e2e_bundle.py", "e2e_package.py"}]
    paths.extend((service / "src" / "coaching_service").glob("*.py"))
    paths.extend(path for path in (service / "vendor" / "fdt").rglob("*") if path.suffix in {".py", ".json"})
    paths.extend(path for path in (service / "vendor" / "keyfin_chart").rglob("*") if path.is_file())
    paths.extend(
        service / name
        for name in ("ENGINE_MANIFEST.json", "CHART_MANIFEST.json", "pyproject.toml", "uv.lock")
    )
    payloads = {path.relative_to(service).as_posix(): path.read_bytes() for path in paths}
    cases = load_cases()
    rows = [
        JsonDocument.model_validate_json(case.model_dump_json(include=_INPUT_FIELDS)).root for case in cases
    ]
    payloads["benchmarks/coaching/e2e/e2e_cases.json"] = json.dumps(
        rows,
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
    ).encode("utf-8")
    payloads["RUN_E2E.md"] = (ROOT / "README.md").read_bytes()
    entries = tuple(
        BundleEntry(path=name, bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
        for name, data in sorted(payloads.items())
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output, "x", compression=ZIP_DEFLATED, compresslevel=6) as archive:
        for entry in entries:
            info = ZipInfo(entry.path, date_time=(2026, 9, 10, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, payloads[entry.path])
    manifest = BundleManifest(
        archive_sha256=hashlib.sha256(output.read_bytes()).hexdigest(), case_count=len(cases), entries=entries
    )
    _ = sidecar.write_bytes(manifest.model_dump_json(indent=2).encode("utf-8"))
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument("--output", type=Path, required=True)
    options = BundleOptions.model_validate(vars(parser.parse_args()))
    manifest = build_bundle(options.output)
    print(  # noqa: T201 - CLI emits artifact hashes and counts only.
        json.dumps(
            {
                "archive_sha256": manifest.archive_sha256,
                "files": len(manifest.entries),
                "cases": manifest.case_count,
                "model_calls": 0,
            }
        )
    )


if __name__ == "__main__":
    main()
