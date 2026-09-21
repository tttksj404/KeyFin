"""Run a privacy-minimal rolling FDT backtest over a KeyFin-shaped persona CSV.

The input remains outside the repository.  Reports contain only aggregate scores
and a source digest; they never store raw merchants, accounts, cards, transaction
IDs, questions, or per-cutoff amounts.  This is a short-history persona screen,
not a customer-forecast accuracy claim or an independent human oracle.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from statistics import mean
from typing import Final, Literal

from benchmarks.forecast.ledger_adapter.contracts import LedgerRow
from benchmarks.forecast.ledger_adapter.engine_path import Request, execute
from benchmarks.forecast.ledger_adapter.ledger import ENVELOPES

_HORIZONS: Final[tuple[int, ...]] = (7, 14, 30)
_PATHS_GRID: Final[tuple[int, ...]] = (100, 400)
_CALIBRATION_FACTORS: Final[tuple[float, ...]] = (1.0, 1.25, 1.5, 2.0, 3.0)
_TARGET_COVERAGE: Final = 0.8
_MIN_RELATIVE_WAPE_IMPROVEMENT: Final = 0.1
_MINIMUM_EVALUATION_INTERVAL_CASES: Final = 40
_CONFORMAL_MIN_SCALE_KRW: Final = 1000
_SPLIT_CUTOFFS: Final[dict[str, tuple[date, ...]]] = {
    "development": (date(2026, 6, 29), date(2026, 7, 6), date(2026, 7, 13), date(2026, 7, 20)),
    "evaluation": (date(2026, 7, 27), date(2026, 8, 1)),
}
_SUBCATEGORIES: Final[dict[str, tuple[str, str]]] = {
    "101": ("식비", "음식점"), "102": ("식비", "카페"), "103": ("식비", "배달"), "104": ("식비", "주점"),
    "201": ("교통", "대중교통"), "202": ("교통", "택시"), "203": ("교통", "주유"),
    "301": ("건강", "병원·약국"), "302": ("건강", "운동·헬스"),
    "401": ("여가·문화", "영화·공연·전시"), "402": ("여가·문화", "스포츠 관람"),
    "403": ("여가·문화", "게임·콘텐츠"), "404": ("여가·문화", "여행·숙박"),
    "501": ("쇼핑", "패션·잡화"), "502": ("쇼핑", "뷰티"), "503": ("쇼핑", "온라인 쇼핑"),
    "601": ("생활서비스", "편의점"), "602": ("생활서비스", "마트"), "603": ("생활서비스", "생활용품"),
    "701": ("기타", "교육"), "702": ("기타", "해외 결제"), "703": ("기타", "경조사·기타"),
}
_CATEGORY_TO_ENVELOPE: Final = {
    "식비": "외식", "교통": "교통비", "건강": "의료·건강", "여가·문화": "취미·여가",
    "쇼핑": "쇼핑", "생활서비스": "편의점·마트·잡화", "기타": "기타",
}
_REQUIRED_COLUMNS: Final = frozenset((
    "id", "tx_type", "amount", "tx_date", "tx_time", "subcategory_id", "confirm_status", "exclude_tag",
    "status",
))


@dataclass(frozen=True, slots=True)
class Prediction:
    """One aggregate-only comparison row retained in memory until scoring completes."""

    split: Literal["development", "evaluation"]
    model: Literal["fdt", "fdt_calibrated", "fdt_conformal", "all_mean", "recent28"]
    horizon: int
    actual: int
    point: float
    lower: int | None = None
    upper: int | None = None


def settled_variable(row: LedgerRow) -> bool:
    """Independent target rule for a settled card purchase in a known envelope.

    DUTCH remains full purchase-time consumption, matching the existing public
    FDT evaluation target.  ``adjusted_amount`` is intentionally not used: it
    is the budget-recognition amount, while this screen measures the recorded
    card outflow target.  Pending/cancelled/self-transfer values are not truth.
    """
    return (
        row.transaction_type == "CARD"
        and row.direction == "EXPENSE"
        and row.status == "NORMAL"
        and row.confirm_status == "CONFIRMED"
        and row.exclude_tag not in {"SELF_TRANSFER", "INTERNAL_TRANSFER"}
    )


def envelope_of(row: LedgerRow) -> str:
    """Use the source-contract category mapping, never merchant text or FDT output."""
    return _CATEGORY_TO_ENVELOPE[row.category]


def read_persona_csv(path: Path) -> tuple[LedgerRow, ...]:
    """Read only required fields and replace source identities before FDT input."""
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames is None or not _REQUIRED_COLUMNS.issubset(reader.fieldnames):
            raise ValueError("persona_backtest_schema_invalid")
        rows: list[LedgerRow] = []
        for source in reader:
            if source["tx_type"] != "CARD":
                continue
            category_pair = _SUBCATEGORIES.get(source["subcategory_id"])
            if category_pair is None:
                raise ValueError("persona_backtest_unknown_card_subcategory")
            category, subcategory = category_pair
            opaque_id = hashlib.sha256(("persona-backtest/" + source["id"]).encode()).hexdigest()
            rows.append(LedgerRow(
                user_id="persona-backtest",
                transaction_id=opaque_id,
                source="SEED",
                transaction_type="CARD",
                transaction_date=source["tx_date"],
                transaction_time=source["tx_time"],
                category=category,
                subcategory=subcategory,
                merchant="redacted",
                merchant_id="redacted",
                amount_krw=int(source["amount"]),
                account_id="redacted",
                card_id="redacted",
                confirm_status=source["confirm_status"],
                status=source["status"],
                exclude_tag=source["exclude_tag"],
                direction="EXPENSE",
            ))
    if not rows:
        raise ValueError("persona_backtest_no_card_rows")
    return tuple(rows)


def daily_totals(rows: tuple[LedgerRow, ...], cutoff: date, envelope: str) -> tuple[int, ...]:
    """Construct a naive observed-only baseline without importing FDT forecasting code."""
    start = min(row.transaction_date for row in rows)
    by_day: defaultdict[date, int] = defaultdict(int)
    for row in rows:
        if row.transaction_date <= cutoff and settled_variable(row) and envelope_of(row) == envelope:
            by_day[row.transaction_date] += row.amount_krw
    return tuple(by_day[start + timedelta(days=offset)] for offset in range((cutoff - start).days + 1))


def future_truth(rows: tuple[LedgerRow, ...], cutoff: date, envelope: str, horizon_days: int) -> int:
    """Calculate future settled consumption from raw rows, separate from FDT simulation."""
    end = cutoff + timedelta(days=horizon_days)
    return sum(
        row.amount_krw
        for row in rows
        if cutoff < row.transaction_date <= end and settled_variable(row) and envelope_of(row) == envelope
    )


def score(rows: tuple[Prediction, ...]) -> dict[str, int | float | None]:
    """Return aggregate accuracy and interval calibration without case-level financial values."""
    actual_sum = sum(row.actual for row in rows)
    errors = tuple(abs(row.point - row.actual) for row in rows)
    intervals = tuple(row for row in rows if row.lower is not None and row.upper is not None)
    covered = sum(
        int(row.lower is not None and row.upper is not None and row.lower <= row.actual <= row.upper)
        for row in intervals
    )
    interval_scores = tuple(
        (row.upper or 0) - (row.lower or 0)
        + 10 * max((row.lower or 0) - row.actual, 0)
        + 10 * max(row.actual - (row.upper or 0), 0)
        for row in intervals
    )
    return {
        "cases": len(rows),
        "wape": round(sum(errors) / actual_sum, 6) if actual_sum else None,
        "mae_krw": round(mean(errors), 3) if errors else None,
        "mean_bias_krw": round(mean(row.point - row.actual for row in rows), 3) if rows else None,
        "interval_cases": len(intervals),
        "coverage80": round(covered / len(intervals), 6) if intervals else None,
        "mean_interval_width_krw": round(
            mean((row.upper or 0) - (row.lower or 0) for row in intervals), 3,
        ) if intervals else None,
        "mean_interval_score80": round(mean(interval_scores), 3) if interval_scores else None,
    }


def calibrate(row: Prediction, factor: float) -> Prediction:
    """Expand an FDT interval around its unchanged median using a frozen scalar grid."""
    if row.lower is None or row.upper is None:
        raise ValueError("persona_backtest_interval_missing")
    lower = max(0, round(row.point - factor * (row.point - row.lower)))
    upper = round(row.point + factor * (row.upper - row.point))
    return Prediction(row.split, "fdt_calibrated", row.horizon, row.actual, row.point, lower, upper)


def choose_interval_factor(rows: tuple[Prediction, ...]) -> tuple[float, dict[str, int | float | None]]:
    """Choose the narrowest predeclared factor that reaches nominal development coverage."""
    candidates = tuple(
        (factor, score(tuple(calibrate(row, factor) for row in rows)))
        for factor in _CALIBRATION_FACTORS
    )
    eligible = tuple(
        candidate
        for candidate in candidates
        if candidate[1]["coverage80"] is not None and candidate[1]["coverage80"] >= _TARGET_COVERAGE
    )
    if not eligible:
        raise ValueError("persona_backtest_calibration_unmet")
    return min(eligible, key=lambda candidate: float(candidate[1]["mean_interval_width_krw"] or 0))


def _conformal_quantile(excesses: tuple[float, ...]) -> float:
    """Return the predeclared split-conformal quantile: the ceil((n+1)*0.8)-th smallest excess."""
    if not excesses:
        return 0.0
    ordered = sorted(excesses)
    n = len(ordered)
    index = math.ceil((n + 1) * _TARGET_COVERAGE) - 1
    index = min(max(index, 0), n - 1)
    return ordered[index]


def conformalize(rows: tuple[Prediction, ...]) -> tuple[Prediction, ...]:
    """Fit an asymmetric per-horizon conformal margin on development fdt rows.

    Non-conformity is scaled by ``max(point, 1000)`` so envelopes with small
    predicted totals do not receive a degenerate zero-width margin.  Only the
    lower/upper bounds move; the median point forecast is never changed.
    """
    development_fdt = tuple(row for row in rows if row.split == "development" and row.model == "fdt")
    by_horizon: defaultdict[int, list[Prediction]] = defaultdict(list)
    for row in development_fdt:
        by_horizon[row.horizon].append(row)
    quantiles: dict[int, tuple[float, float]] = {}
    for horizon, horizon_rows in by_horizon.items():
        lo_excess: list[float] = []
        up_excess: list[float] = []
        for row in horizon_rows:
            if row.lower is None or row.upper is None:
                raise ValueError("persona_backtest_interval_missing")
            scale = max(row.point, _CONFORMAL_MIN_SCALE_KRW)
            lo_excess.append(max(row.lower - row.actual, 0) / scale)
            up_excess.append(max(row.actual - row.upper, 0) / scale)
        quantiles[horizon] = (_conformal_quantile(tuple(lo_excess)), _conformal_quantile(tuple(up_excess)))
    conformal_rows: list[Prediction] = []
    for row in rows:
        if row.model != "fdt":
            continue
        if row.lower is None or row.upper is None:
            raise ValueError("persona_backtest_interval_missing")
        q_lo, q_up = quantiles.get(row.horizon, (0.0, 0.0))
        scale = max(row.point, _CONFORMAL_MIN_SCALE_KRW)
        lower2 = max(0, round(row.lower - q_lo * scale))
        upper2 = round(row.upper + q_up * scale)
        conformal_rows.append(
            Prediction(row.split, "fdt_conformal", row.horizon, row.actual, row.point, lower2, upper2),
        )
    return tuple(conformal_rows)


def promotion_gate(
    scores: dict[str, dict[str, int | float | None]],
    calibration: dict[str, int | float | None],
) -> dict[str, bool | float | None]:
    """Fail closed unless point error, raw coverage, and calibrated sharpness all improve.

    The gate is also fail-closed on the sample size itself: with an
    undecidable number of evaluation interval cases, ``production_adopted``
    can never be True regardless of any observed score.
    """
    fdt, baseline, conformal = scores["fdt"], scores["all_mean"], scores["fdt_conformal"]
    fdt_wape, baseline_wape = fdt["wape"], baseline["wape"]
    relative = None
    if isinstance(fdt_wape, float) and isinstance(baseline_wape, float) and baseline_wape > 0:
        relative = round((baseline_wape - fdt_wape) / baseline_wape, 6)
    coverage = fdt["coverage80"]
    conformal_coverage = conformal["coverage80"]
    raw_interval_score = fdt["mean_interval_score80"]
    calibrated_interval_score = calibration["mean_interval_score80"]
    conformal_interval_score = conformal["mean_interval_score80"]
    evaluation_interval_cases = fdt["interval_cases"]
    decidable = (
        isinstance(evaluation_interval_cases, int)
        and evaluation_interval_cases >= _MINIMUM_EVALUATION_INTERVAL_CASES
    )
    point_pass = relative is not None and relative >= _MIN_RELATIVE_WAPE_IMPROVEMENT
    coverage_pass = isinstance(coverage, float) and coverage >= _TARGET_COVERAGE
    conformal_coverage_pass = isinstance(conformal_coverage, float) and conformal_coverage >= _TARGET_COVERAGE
    sharpness_pass = (
        isinstance(raw_interval_score, float)
        and isinstance(calibrated_interval_score, float)
        and calibrated_interval_score <= raw_interval_score
    )
    conformal_sharpness_pass = (
        isinstance(raw_interval_score, float)
        and isinstance(conformal_interval_score, float)
        and conformal_interval_score <= raw_interval_score
    )
    production_adopted = bool(
        decidable
        and point_pass
        and (coverage_pass or conformal_coverage_pass)
        and sharpness_pass
    )
    return {
        "baseline": "all_mean",
        "minimum_relative_wape_improvement": _MIN_RELATIVE_WAPE_IMPROVEMENT,
        "minimum_evaluation_interval_cases": _MINIMUM_EVALUATION_INTERVAL_CASES,
        "evaluation_interval_cases": evaluation_interval_cases,
        "decidable": decidable,
        "relative_wape_improvement": relative,
        "raw_coverage80": coverage if isinstance(coverage, float) else None,
        "conformal_coverage80": conformal_coverage if isinstance(conformal_coverage, float) else None,
        "point_pass": point_pass,
        "coverage_pass": coverage_pass,
        "conformal_coverage_pass": conformal_coverage_pass,
        "calibrated_sharpness_pass": sharpness_pass,
        "conformal_sharpness_pass": conformal_sharpness_pass,
        "production_adopted": production_adopted,
    }


def _score_for_paths(
    rows: tuple[LedgerRow, ...],
    paths: int,
    latest: date,
) -> tuple[dict[str, dict[str, dict[str, int | float | None]]], dict[str, object], dict[str, int]]:
    """Run the full engine + scoring pipeline for one ``paths`` admission setting."""
    predictions: list[Prediction] = []
    engine_statuses: defaultdict[str, int] = defaultdict(int)
    for split, cutoffs in _SPLIT_CUTOFFS.items():
        for cutoff in cutoffs:
            observed = tuple(row for row in rows if row.transaction_date <= cutoff)
            if not observed:
                raise ValueError("persona_backtest_history_missing")
            for horizon in _HORIZONS:
                if cutoff + timedelta(days=horizon) > latest:
                    raise ValueError("persona_backtest_future_truth_missing")
                engine_output = execute(
                    observed,
                    Request(cutoff=cutoff, horizon_days=horizon, paths=paths),
                ).output
                engine_statuses[engine_output.status] += 1
                fdt = {row.envelope: row for row in engine_output.datasets.envelopes}
                if set(fdt) != set(ENVELOPES):
                    raise ValueError("persona_backtest_fdt_envelope_mismatch")
                for envelope in ENVELOPES:
                    actual = future_truth(rows, cutoff, envelope, horizon)
                    history = daily_totals(rows, cutoff, envelope)
                    if len(history) < 28:
                        raise ValueError("persona_backtest_history_too_short")
                    output = fdt[envelope]
                    predictions.extend((
                        Prediction(
                            split, "fdt", horizon, actual, output.p50_krw, output.p10_krw, output.p90_krw,
                        ),
                        Prediction(split, "all_mean", horizon, actual, mean(history) * horizon),
                        Prediction(split, "recent28", horizon, actual, mean(history[-28:]) * horizon),
                    ))
    development_fdt = tuple(row for row in predictions if row.split == "development" and row.model == "fdt")
    interval_factor, calibration_development = choose_interval_factor(development_fdt)
    predictions.extend(calibrate(row, interval_factor) for row in tuple(predictions) if row.model == "fdt")
    predictions.extend(conformalize(tuple(predictions)))
    summaries: dict[str, dict[str, dict[str, int | float | None]]] = {}
    for split in _SPLIT_CUTOFFS:
        summaries[split] = {
            model: score(tuple(row for row in predictions if row.split == split and row.model == model))
            for model in ("fdt", "fdt_calibrated", "fdt_conformal", "all_mean", "recent28")
        }
    selected = min(
        summaries["development"],
        key=lambda model: float("inf") if summaries["development"][model]["wape"] is None
        else float(summaries["development"][model]["wape"]),
    )
    evaluation_calibrated = summaries["evaluation"]["fdt_calibrated"]
    interval_calibration = {
        "target_coverage": _TARGET_COVERAGE,
        "factors": _CALIBRATION_FACTORS,
        "selected_factor": interval_factor,
        "development_score": calibration_development,
        "evaluation_score": evaluation_calibrated,
        "production_interval_change_adopted": False,
    }
    result = {
        "scores": summaries,
        "interval_calibration": interval_calibration,
        "development_selected_model": selected,
        "evaluation_selected_model_score": summaries["evaluation"][selected],
        "evaluation_promotion_gate": promotion_gate(summaries["evaluation"], evaluation_calibrated),
    }
    return summaries, result, dict(engine_statuses)


def report(path: Path, paths_grid: tuple[int, ...] = _PATHS_GRID) -> dict[str, object]:
    """Evaluate the predeclared short-history splits and retain only aggregate evidence."""
    raw_bytes = path.read_bytes()
    rows = read_persona_csv(path)
    earliest, latest = min(row.transaction_date for row in rows), max(row.transaction_date for row in rows)
    scores_by_paths: dict[str, object] = {}
    combined_engine_statuses: defaultdict[str, int] = defaultdict(int)
    for paths in paths_grid:
        _, result, engine_statuses = _score_for_paths(rows, paths, latest)
        for status, count in engine_statuses.items():
            combined_engine_statuses[status] += count
        scores_by_paths[str(paths)] = {
            **result["scores"],
            "interval_calibration": result["interval_calibration"],
            "development_selected_model": result["development_selected_model"],
            "evaluation_selected_model_score": result["evaluation_selected_model_score"],
            "evaluation_promotion_gate": result["evaluation_promotion_gate"],
        }
    return {
        "schema": "keyfin-persona-forecast-backtest/2",
        "scope": {
            "source": "user_provided_synthetic_persona_csv",
            "customer_data_included": False,
            "future_settled_card_consumption_measured": True,
            "closing_balance_accuracy_measured": False,
            "human_approved_oracle": False,
            "short_history_screen_only": True,
        },
        "source": {
            "sha256": hashlib.sha256(raw_bytes).hexdigest(),
            "card_rows_converted": len(rows),
            "calendar_days": (latest - earliest).days + 1,
            "horizons": _HORIZONS,
            "paths_grid": paths_grid,
        },
        "engine_status_counts": dict(sorted(combined_engine_statuses.items())),
        "scores_by_paths": scores_by_paths,
        "interval_calibration": scores_by_paths[str(paths_grid[0])]["interval_calibration"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument("--source", required=True, type=Path)
    _ = parser.add_argument("--output", required=True, type=Path)
    _ = parser.add_argument("--paths", type=int, action="append", default=None)
    args = parser.parse_args()
    destination = args.output.resolve()
    if destination.exists():
        raise FileExistsError(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    paths_grid = tuple(args.paths) if args.paths else _PATHS_GRID
    value = report(args.source.resolve(), paths_grid)
    destination.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({  # noqa: T201
        "schema": value["schema"],
        "scores_by_paths": {
            paths: {
                "development_selected_model": scores["development_selected_model"],
                "evaluation_selected_model_score": scores["evaluation_selected_model_score"],
                "evaluation_promotion_gate": scores["evaluation_promotion_gate"],
            }
            for paths, scores in value["scores_by_paths"].items()
        },
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
