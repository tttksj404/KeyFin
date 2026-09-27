"""Evaluation-adapter controls must remain inside the service contract."""

from __future__ import annotations

from datetime import date

import pytest

from benchmarks.forecast.ledger_adapter.engine_path import Request


def test_replay_request_keeps_the_frozen_four_hundred_path_default() -> None:
    """Existing replay artifacts still mean the documented 400-path request."""
    assert Request(date(2026, 8, 1), 30).paths == 400


@pytest.mark.parametrize("paths", [19, 401])
def test_replay_request_rejects_paths_outside_the_service_admission_range(paths: int) -> None:
    """An experiment cannot obtain a more permissive simulation budget than production."""
    with pytest.raises(ValueError, match="forecast_paths_out_of_range"):
        _ = Request(date(2026, 8, 1), 30, paths=paths)
