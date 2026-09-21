"""Verify the imported team engine, including schemas, before serving requests."""

from hashlib import sha256
from importlib.resources import files
from pathlib import Path
from typing import ClassVar

from pydantic import BaseModel, ConfigDict

ENGINE_COMMIT = "307de59c9d1fde01774388257da27730754e5118"


class EngineManifest(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True)
    commit: str
    path: str
    sha256: dict[str, str]


def verify_engine() -> int:
    manifest = files("coaching_service").joinpath("engine_manifest.json")
    content = (
        manifest.read_bytes()
        if manifest.is_file()
        else (Path(__file__).resolve().parents[2] / "ENGINE_MANIFEST.json").read_bytes()
    )
    expected = EngineManifest.model_validate_json(content)
    if expected.commit != ENGINE_COMMIT or len(expected.sha256) != 21:
        raise RuntimeError("engine_manifest_mismatch")
    imported = files("fdt")
    for name, digest in expected.sha256.items():
        relative = name.removeprefix("fdt/")
        if (
            relative == name
            or ".." in relative
            or sha256(imported.joinpath(relative).read_bytes()).hexdigest() != digest
        ):
            raise RuntimeError("imported_engine_hash_mismatch")
    return len(expected.sha256)
