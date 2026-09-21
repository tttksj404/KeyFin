# ruff: noqa: INP001
"""The public scorer must work beyond the September 3 development fixture."""

from datetime import date

import pytest

from benchmarks.coaching.chat_response.score import expected_forecast_window


@pytest.mark.parametrize(
    ("case_id", "reference", "start", "end"),
    [
        ("forecast_month_end_balance", "2026-09-03", "2026-09-04", "2026-09-30"),
        ("forecast_month_end_balance", "2027-02-20", "2027-02-21", "2027-02-28"),
        ("risk_month", "2028-02-20", "2028-02-21", "2028-02-29"),
        ("forecast_month_end_balance", "2026-01-03", "2026-01-04", "2026-01-31"),
        ("risk_month", "2026-09-30", "2026-10-01", "2026-09-30"),
        ("forecast_7d_balance", "2026-12-28", "2026-12-29", "2027-01-04"),
    ],
)
def test_fixture_date_drives_expected_window(
    case_id: str, reference: str, start: str, end: str,
) -> None:
    # Given a fixture cutoff, only future days belong to the prediction window.
    reference_date = date.fromisoformat(reference)
    # When the benchmark independently interprets its fixed question.
    actual = expected_forecast_window(case_id, reference_date)
    # Then February, leap years, month-end and year-end have explicit expectations.
    assert actual == (date.fromisoformat(start), date.fromisoformat(end))
