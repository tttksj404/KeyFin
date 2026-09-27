"""Aggregate endpoints and observed optimizer updates are required evidence."""

import numpy as np
import pytest

from benchmarks.forecast.aggregate import worker_support


def test_terminal_quantile_is_the_horizon_total_instead_of_a_sum_of_quantiles() -> None:
    # Given: intermediate rolling totals overlap; only the last row covers the future horizon.
    quantiles = np.asarray([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0], [7.0, 8.0, 9.0]])
    # When: the horizon endpoint becomes an aggregate prediction.
    row = worker_support.terminal_prediction("case", "model", quantiles, 3)
    # Then: the overlapping path is not summed into an invalid aggregate distribution.
    assert (row.lower, row.point, row.upper) == (7, 8, 9)


def test_nonnegative_clipping_preserves_the_interval_order() -> None:
    # Given: a positive-outflow model emits a small negative lower endpoint.
    quantiles = np.asarray([[-10.0, 0.0, 12.0]])
    # When: the endpoint is restricted to the known nonnegative target domain.
    row = worker_support.terminal_prediction("case", "model", quantiles, 1)
    # Then: no negative expense is invented and the interval remains ordered.
    assert (row.lower, row.point, row.upper) == (0, 0, 12)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ([5.0, 4.0, 12.0], (4, 4, 12)),
        ([1.0, 8.0, 5.0], (1, 8, 8)),
        ([8.4954833984375, -1.4544677734375, 2766.785400390625], (0, 0, 2766.785400390625)),
    ],
)
def test_crossed_quantiles_widen_without_changing_the_clipped_median(
    raw: list[float],
    expected: tuple[float, float, float],
) -> None:
    # Given: independently generated quantiles cross at either endpoint, including the GPU regression.
    audit = worker_support.QuantileAudit()
    row = worker_support.terminal_prediction("case", "model", np.asarray([raw]), 1, audit)
    # Then: the original nonnegative median is retained and every repair remains visible.
    assert (row.lower, row.point, row.upper) == expected
    assert audit.values() == {
        "quantile_crossings_raw": 1,
        "quantile_crossings_after_clip": 1,
        "quantile_intervals_widened": 1,
    }


def test_negative_crossing_removed_by_domain_clip_is_counted_separately() -> None:
    audit = worker_support.QuantileAudit()
    row = worker_support.terminal_prediction("case", "model", np.asarray([[-1.0, -2.0, -3.0]]), 1, audit)
    assert (row.lower, row.point, row.upper) == (0, 0, 0)
    assert (audit.quantile_crossings_raw, audit.quantile_intervals_widened) == (1, 0)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_quantiles_are_rejected_before_widening(value: float) -> None:
    with pytest.raises(ValueError, match="finite"):
        _ = worker_support.terminal_prediction("case", "model", np.asarray([[0.0, value, 2.0]]), 1)


def test_transposed_output_is_not_silently_reshaped() -> None:
    with pytest.raises(ValueError, match="shape"):
        _ = worker_support.terminal_prediction("case", "model", np.asarray([[0.0], [1.0], [2.0]]), 1)


def test_requested_updates_are_not_sufficient_without_optimizer_callbacks() -> None:
    # Given: trainer state claims two steps without any observed optimizer events.
    audit = worker_support.UpdateAudit()
    audit.step_end(1)
    audit.step_end(2)
    # When / Then: recording the requested step count cannot pass the training gate.
    with pytest.raises(ValueError, match="optimizer"):
        _ = audit.finish(2)


def test_skipped_optimizer_step_cannot_be_reported_as_a_weight_update() -> None:
    # Given: one optimizer event was skipped even though global_step advanced.
    audit = worker_support.UpdateAudit()
    audit.optimizer_step(skipped=False)
    audit.step_end(1)
    audit.optimizer_step(skipped=True)
    audit.step_end(2)
    # When / Then: the run cannot claim two actual updates.
    with pytest.raises(ValueError, match="optimizer"):
        _ = audit.finish(2)


def test_audit_accepts_exactly_observed_fresh_training_updates() -> None:
    # Given: three optimizer updates and their completed trainer steps were observed.
    audit = worker_support.UpdateAudit()
    for step in range(1, 4):
        audit.optimizer_step(skipped=False)
        audit.step_end(step)
    # When: the observed result is checked against the frozen protocol.
    result = audit.finish(3)
    # Then: the record separately carries observed events, updates and trainer state.
    assert result.optimizer_step_events == result.optimizer_updates == result.global_step == 3
    assert result.skipped_updates == 0
    assert result.observed_global_steps == (1, 2, 3)
