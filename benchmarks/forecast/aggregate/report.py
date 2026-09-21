"""Expose paired improvement, uncertainty and deterioration without reselecting on test."""

from bisect import bisect_right
from collections.abc import Mapping
from typing import TypedDict

from .contracts import Case, Prediction
from .scoring import Confidence, Metrics, expand, paired_confidence, percentile, score
from .selection import Bank, Choice


class SliceReport(TypedDict):
    selected: Metrics
    baseline: Metrics
    relative_mae_reduction: float | None


class HorizonReport(TypedDict):
    selected_model: str
    baseline_model: str
    selected: Metrics
    baseline: Metrics
    selected_uncalibrated: Metrics
    baseline_uncalibrated: Metrics
    relative_mae_reduction: float | None
    confidence: Confidence
    per_origin: dict[str, SliceReport]
    per_observed_spend_quartile: dict[str, SliceReport]
    individual_candidates_diagnostic_only: dict[str, Metrics]
    gates: dict[str, bool]
    research_gate_passed: bool


def reduction(candidate: Metrics, reference: Metrics) -> float | None:
    return 1 - candidate["mae_czk"] / reference["mae_czk"] if reference["mae_czk"] else None


def horizon_report(
    cases: tuple[Case, ...], truth: Mapping[str, float], bank: Bank,
    choice: Choice, radii: Mapping[str, float],
) -> HorizonReport:
    """Apply the frozen choice and calibration to every aligned evaluation outcome."""
    actual = tuple(truth[row.case_id] for row in cases)
    selected_raw = tuple(bank.rows[choice.selected][row.case_id] for row in cases)
    baseline_raw = tuple(bank.rows[choice.baseline][row.case_id] for row in cases)

    def calibrated(rows: tuple[Prediction, ...], name: str) -> tuple[Prediction, ...]:
        return tuple(expand(row, bank.rows["recent90"][row.case_id].point, radii[name]) for row in rows)

    selected, baseline = calibrated(selected_raw, choice.selected), calibrated(baseline_raw, choice.baseline)
    selected_scores, baseline_scores = score(actual, selected), score(actual, baseline)

    def slice_report(indices: tuple[int, ...]) -> SliceReport:
        values = tuple(actual[i] for i in indices)
        candidate = score(values, tuple(selected[i] for i in indices))
        reference = score(values, tuple(baseline[i] for i in indices))
        return SliceReport(selected=candidate, baseline=reference,
                           relative_mae_reduction=reduction(candidate, reference))

    per_origin = {str(cutoff): slice_report(tuple(i for i, row in enumerate(cases) if row.cutoff == cutoff))
                  for cutoff in sorted({row.cutoff for row in cases})}
    observed = tuple(sum(row.history) for row in cases)
    quartiles = tuple(percentile(observed, probability) for probability in (0.25, 0.5, 0.75))
    groups = tuple(bisect_right(quartiles, value) for value in observed)
    per_group = {str(group + 1): slice_report(tuple(i for i, value in enumerate(groups) if value == group))
                 for group in range(4) if group in groups}
    confidence = paired_confidence(tuple(row.account for row in cases), actual,
                                   tuple(row.point for row in selected), tuple(row.point for row in baseline))
    improvement = reduction(selected_scores, baseline_scores)
    paired = confidence["paired_wape_difference_95"]
    gates = {
        # Compare error amounts: 1 - 90/100 rounds just below 0.1 in binary floats.
        "mae_reduction_at_least_10_percent": (
            baseline_scores["mae_czk"] > 0
            and selected_scores["mae_czk"] <= baseline_scores["mae_czk"] * 0.9
        ),
        "paired_wape_ci_upper_below_zero": paired is not None and paired[1] < 0,
        "calibrated_wis_no_worse": selected_scores["wis80"] <= baseline_scores["wis80"],
        "each_origin_mae_no_more_than_5_percent_worse": all(
            part["selected"]["mae_czk"] <= part["baseline"]["mae_czk"] * 1.05
            for part in per_origin.values()),
    }
    return HorizonReport(
        selected_model=choice.selected, baseline_model=choice.baseline,
        selected=selected_scores, baseline=baseline_scores,
        selected_uncalibrated=score(actual, selected_raw), baseline_uncalibrated=score(actual, baseline_raw),
        relative_mae_reduction=improvement, confidence=confidence, per_origin=per_origin,
        per_observed_spend_quartile=per_group,
        individual_candidates_diagnostic_only={name: score(actual, tuple(rows[row.case_id] for row in cases))
                                              for name, rows in bank.rows.items()},
        gates=gates, research_gate_passed=all(gates.values()),
    )
