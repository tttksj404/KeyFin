"""The persona backtest must retain no raw source identifiers in its result."""

from __future__ import annotations

import csv
from typing import TYPE_CHECKING

from benchmarks.forecast.persona_backtest import read_persona_csv, report

if TYPE_CHECKING:
    from pathlib import Path


def write_source(path: Path) -> None:
    """Create a tiny KeyFin-shaped ledger spanning the predeclared screen dates."""
    fields = (
        "id", "tx_type", "amount", "tx_date", "tx_time", "subcategory_id", "confirm_status", "exclude_tag",
        "status",
    )
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for index in range(92):
            day = f"2026-{6 + (index // 30):02d}-{1 + (index % 30):02d}"
            writer.writerow({
                "id": f"secret-id-{index}", "tx_type": "CARD", "amount": "1000", "tx_date": day,
                "tx_time": "12:00", "subcategory_id": "101", "confirm_status": "CONFIRMED",
                "exclude_tag": "NONE", "status": "NORMAL",
            })


def test_persona_backtest_v2_has_decidable_evaluation_size(tmp_path: Path) -> None:
    source = tmp_path / "persona.csv"
    write_source(source)

    result = report(source)
    scores = result["scores_by_paths"]["100"]

    assert scores["evaluation"]["fdt"]["interval_cases"] == 42
    assert scores["development"]["fdt"]["cases"] == 84
    assert result["schema"] == "keyfin-persona-forecast-backtest/2"


def test_conformal_calibration_reaches_development_target(tmp_path: Path) -> None:
    source = tmp_path / "persona.csv"
    write_source(source)

    result = report(source)

    for paths_key, scores in result["scores_by_paths"].items():
        development = scores["development"]
        assert development["fdt_conformal"]["coverage80"] >= 0.8, paths_key
        assert development["fdt_conformal"]["wape"] == development["fdt"]["wape"], paths_key


def test_gate_reports_decidability_and_never_adopts(tmp_path: Path) -> None:
    source = tmp_path / "persona.csv"
    write_source(source)

    result = report(source)
    gate = result["scores_by_paths"]["100"]["evaluation_promotion_gate"]

    assert gate["decidable"] is True
    assert gate["minimum_evaluation_interval_cases"] == 40
    assert gate["production_adopted"] is False
    assert result["interval_calibration"]["production_interval_change_adopted"] is False


def test_persona_backtest_is_aggregate_only(tmp_path: Path) -> None:
    source = tmp_path / "persona.csv"
    write_source(source)

    parsed = read_persona_csv(source)
    result = report(source)
    serialized = str(result)
    scores = result["scores_by_paths"]["400"]

    assert len(parsed) == 92
    assert result["scope"]["customer_data_included"] is False
    assert result["scope"]["closing_balance_accuracy_measured"] is False
    assert result["source"]["card_rows_converted"] == 92
    assert result["interval_calibration"]["selected_factor"] >= 1
    assert result["interval_calibration"]["production_interval_change_adopted"] is False
    assert "fdt_calibrated" in scores["evaluation"]
    assert scores["evaluation_promotion_gate"]["production_adopted"] is False
    assert "secret-id" not in serialized
    assert "redacted" not in serialized
