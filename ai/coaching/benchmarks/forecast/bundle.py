# /// script
# requires-python = ">=3.11"
# dependencies = ["pydantic"]
# ///
# How to run: python -m benchmarks.forecast.bundle /private/results /private/result-bundle.json
"""Export completed forecast results without configuration, checkpoints or process logs."""

import hashlib
import sys
from pathlib import Path

from pydantic import JsonValue, TypeAdapter

from .archive import RemoteArchive


def export(directory: Path, output: Path) -> None:
    """완료 표식이 있는 worker JSON 원문을 UTF-8 바이트 그대로 v2에 보존한다.

    완료 표식은 계산 결과의 완전성을 대신하지 않는다. 모델·fold·case별 필수 예측 집합은
    평가 runner가 점수를 쓰기 전에 별도로 검사한다.
    """
    if output.exists():
        raise FileExistsError("Use a new result bundle path")
    if (directory / "completed.json").read_text(encoding="utf-8") != '{"completed":true}':
        raise ValueError("The worker has not completed")
    paths = [*directory.glob("*.predictions.json"), *directory.glob("*.training.json"),
             *directory.glob("*.inference.json"), directory / "runtime.json"]
    raw = {path.name: path.read_bytes() for path in sorted(paths)}
    bundle = RemoteArchive(
        schema_version=2,
        files={name: TypeAdapter(JsonValue).validate_json(data) for name, data in raw.items()},
        raw_files={name: data.decode("utf-8") for name, data in raw.items()},
        sha256={name: hashlib.sha256(data).hexdigest() for name, data in raw.items()},
        upload_manifest={}, finished=True,
    )
    _ = output.write_text(bundle.model_dump_json(), encoding="utf-8")


if __name__ == "__main__":
    export(Path(sys.argv[1]), Path(sys.argv[2]))
