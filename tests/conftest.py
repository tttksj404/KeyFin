# ruff: noqa: INP001
"""Shared test configuration."""

import pytest


@pytest.fixture(autouse=True)
def _plain_persona(monkeypatch: pytest.MonkeyPatch) -> None:
    # Production speaks in the cat voice by default. Existing tests compare the neutral
    # stored sentences, so they run with the plain persona; persona tests opt back in.
    monkeypatch.setenv("COACHING_PERSONA", "plain")
