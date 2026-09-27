"""The FDT worker limit is a bounded service setting, separate from model concurrency."""

# ruff: noqa: INP001
from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest
from pydantic import SecretStr, ValidationError

from coaching_service.coaching import CoachingCore
from coaching_service.repository import Repository
from coaching_service.settings import Client, Settings
from coaching_service.store import Store

if TYPE_CHECKING:
    from pathlib import Path

    from coaching_service.coaching import LanguageModel


def settings(*, fdt_max_concurrency: int = 2) -> Settings:
    return Settings(
        clients=(Client(user_id="demo", token=SecretStr("a" * 32)),),
        fdt_max_concurrency=fdt_max_concurrency,
    )


def test_fdt_concurrency_default_is_two_and_environment_setting_is_bounded() -> None:
    """The measured default stays conservative without silently accepting invalid limits."""
    assert settings().fdt_max_concurrency == 2
    assert settings(fdt_max_concurrency=1).fdt_max_concurrency == 1
    assert settings(fdt_max_concurrency=8).fdt_max_concurrency == 8
    with pytest.raises(ValidationError, match="greater than or equal to 1"):
        _ = settings(fdt_max_concurrency=0)
    with pytest.raises(ValidationError, match="less than or equal to 8"):
        _ = settings(fdt_max_concurrency=9)


def test_fdt_concurrency_can_be_overridden_by_the_scoped_service_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A deployment can tune the FDT queue without changing model settings or source code."""
    monkeypatch.setenv("COACHING_FDT_MAX_CONCURRENCY", "1")
    configured = Settings(clients=(Client(user_id="demo", token=SecretStr("a" * 32)),))
    assert configured.fdt_max_concurrency == 1


def test_core_uses_the_explicit_fdt_limit_and_rejects_unbounded_direct_construction(tmp_path: Path) -> None:
    """Direct construction cannot accidentally bypass the settings admission boundary."""
    core = CoachingCore(
        Repository(Store(tmp_path / "coaching.sqlite3")),
        cast("LanguageModel", object()),
        fdt_max_concurrency=1,
    )
    assert core.engine_limit.total_tokens == 1
    with pytest.raises(ValueError, match="fdt_max_concurrency_out_of_range"):
        _ = CoachingCore(
            Repository(Store(tmp_path / "invalid.sqlite3")),
            cast("LanguageModel", object()),
            fdt_max_concurrency=9,
        )
