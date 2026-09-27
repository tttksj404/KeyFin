"""V2 archives preserve original JSON bytes so the recorded file hashes remain verifiable."""

import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import JsonValue, TypeAdapter

from .contracts import Frozen


class RemoteArchive(Frozen):
    """v2의 sha256은 raw_files 원문을 UTF-8로 인코딩한 바이트의 해시이다."""

    schema_version: Literal[2]
    files: dict[str, JsonValue]
    raw_files: dict[str, str]
    sha256: dict[str, str]
    upload_manifest: dict[str, str]
    finished: bool


def canonical(value: JsonValue) -> str:
    """키 순서는 무시하되 Python의 True == 1 비교로 다른 JSON 타입이 통과하지 않게 한다."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def load_archive(remote_path: Path, input_path: Path) -> RemoteArchive:
    """원문 해시·파일 집합·파싱 값을 확인한 원문만 평가 입력으로 반환한다.

    v1은 원문을 버렸으므로 같은 해시 의미로 재검증할 수 없다. 기존 결과를 묵인하거나
    재직렬화한 바이트를 원문으로 간주하지 않고, 보존된 worker 파일에서 재export하도록 거절한다.
    """
    payload = TypeAdapter(dict[str, JsonValue]).validate_json(remote_path.read_bytes())
    if payload.get("schema_version") != 2:
        raise ValueError(
            "Legacy or unsupported forecast archive; re-export from the original worker result files "
            "with benchmarks.forecast.bundle"
        )
    remote = RemoteArchive.model_validate(payload)
    if not remote.finished:
        raise ValueError("Remote execution is incomplete")
    if set(remote.files) != set(remote.raw_files) or set(remote.files) != set(remote.sha256):
        raise ValueError("Archive files, raw_files and sha256 keys disagree")
    verified: dict[str, JsonValue] = {}
    for name, raw in remote.raw_files.items():
        if hashlib.sha256(raw.encode("utf-8")).hexdigest() != remote.sha256[name]:
            raise ValueError("Archived raw file SHA-256 mismatch")
        value = TypeAdapter(JsonValue).validate_json(raw)
        if canonical(value) != canonical(remote.files[name]):
            raise ValueError("Archived parsed data differs from its verified raw content")
        verified[name] = value
    runtime = verified.get("runtime.json")
    if not isinstance(runtime, dict) or runtime.get("input_sha256") != hashlib.sha256(
        input_path.read_bytes(),
    ).hexdigest():
        raise ValueError("Worker inputs differ from the evaluation inputs")
    return remote.model_copy(update={"files": verified})
