"""Inference measurements have no access to financial or transport payloads."""

# ruff: noqa: INP001

from __future__ import annotations

from dataclasses import fields

import anyio
import pytest

from coaching_service import inference_metrics as metrics


class ManualClock:
    def __init__(self) -> None:
        self.now: float = 0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def test_phase_and_total_times_use_injected_monotonic_clock() -> None:
    # Given a request-scoped collector and an independently controlled clock.
    clock = ManualClock()
    # When an inference waits, checks its input and receives a generated response.
    with (
        metrics.capture_inference_metrics() as collector,
        metrics.measure_inference("write", clock=clock) as trace,
    ):
        with trace.phase("limiter_wait"):
            clock.advance(0.125)
        with trace.phase("token_preflight"):
            clock.advance(0.25)
        with trace.phase("generation_http"):
            clock.advance(0.5)
        clock.advance(0.125)
    # Then measurements contain elapsed milliseconds, not wall-clock timestamps.
    measurement, = collector.snapshot()
    assert measurement.limiter_wait_ms == 125
    assert measurement.token_preflight_ms == 250
    assert measurement.generation_http_ms == 500
    assert measurement.total_ms == 1000
    assert measurement.outcome == "success"


def test_disabled_observation_does_not_call_clock() -> None:
    # Given a clock which must not be used without an enabled collector.
    def unused_clock() -> float:
        pytest.fail("Disabled inference observation called its clock")

    # When normal work enters the same instrumentation scopes.
    with metrics.measure_inference("route", clock=unused_clock) as trace, trace.phase("limiter_wait"):
        trace.set_outcome("failure")
    # Then no observations or clock work are performed; the scope exits normally.


def test_measurement_schema_only_has_safe_identifiers_and_numbers() -> None:
    # Given the public measurement data type.
    # When its serializable fields are inspected.
    names = {field.name for field in fields(metrics.InferenceMeasurement)}
    # Then arbitrary payloads, URLs, messages and exception text cannot be stored.
    assert names == {
        "request_id", "operation", "limiter_wait_ms", "token_preflight_ms",
        "generation_http_ms", "total_ms", "outcome",
    }


def test_unentered_phases_are_distinguishable_from_zero_duration() -> None:
    # Given an enabled collector and a clock which does not advance.
    clock = ManualClock()
    # When input validation rejects before generation starts.
    with (
        metrics.capture_inference_metrics() as collector,
        metrics.measure_inference("route", clock=clock) as trace,
        trace.phase("token_preflight"),
    ):
        trace.set_outcome("rejected")
    # Then a measured zero differs from phases which never ran.
    measurement, = collector.snapshot()
    assert measurement.token_preflight_ms == 0
    assert measurement.limiter_wait_ms is None
    assert measurement.generation_http_ms is None
    assert measurement.outcome == "rejected"


@pytest.mark.parametrize("failure", [ValueError, KeyboardInterrupt, SystemExit, GeneratorExit])
def test_failure_propagates_and_is_not_misreported_as_cancellation(
    failure: type[BaseException],
) -> None:
    # Given one operation and a non-cancellation exception.
    collector = metrics.InferenceMetricsCollector()
    clock = ManualClock()

    def failing_work() -> None:
        clock.advance(0.25)
        raise failure("private payload must not be retained")

    # When the operation fails.
    with (
        pytest.raises(failure),
        metrics.measure_inference("write", observer=collector, clock=clock),
    ):
        failing_work()
    # Then the exception reaches its caller and the metric contains only its class of outcome.
    measurement, = collector.snapshot()
    assert measurement.outcome == "failure"
    assert measurement.total_ms == 250


def test_explicit_outcome_is_preserved_when_exception_propagates() -> None:
    # Given a caller which has classified a downstream timeout precisely.
    collector = metrics.InferenceMetricsCollector()

    def failing_work(trace: metrics.InferenceTrace) -> None:
        trace.set_outcome("timeout")
        raise ValueError("no details recorded")

    # When a non-TimeoutError transport exception leaves its operation.
    with (
        pytest.raises(ValueError, match="no details recorded"),
        metrics.measure_inference("write", observer=collector) as trace,
    ):
        failing_work(trace)
    # Then generic exception handling must not overwrite the caller's classification.
    measurement, = collector.snapshot()
    assert measurement.outcome == "timeout"


@pytest.mark.parametrize(("failure", "outcome"), [(RuntimeError, "failure"), (TimeoutError, "timeout")])
def test_cleanup_error_cannot_retain_an_earlier_success(
    failure: type[Exception], outcome: metrics.MetricOutcome,
) -> None:
    collector = metrics.InferenceMetricsCollector()
    # A response can finish before its connection cleanup raises an exception.
    def completed_response_then_cleanup_error(trace: metrics.InferenceTrace) -> None:
        trace.set_outcome("success")
        raise failure("cleanup details must not enter the measurement")

    with (
        pytest.raises(failure),
        metrics.measure_inference("write", observer=collector) as trace,
    ):
        completed_response_then_cleanup_error(trace)
    measurement, = collector.snapshot()
    assert measurement.outcome == outcome


def test_native_timeout_is_recorded_without_swallowing_it() -> None:
    # Given a collector for one operation.
    collector = metrics.InferenceMetricsCollector()
    # When the caller's deadline raises TimeoutError.
    with pytest.raises(TimeoutError), metrics.measure_inference("write", observer=collector):
        raise TimeoutError
    # Then the operation is classified as a timeout while the caller receives it.
    measurement, = collector.snapshot()
    assert measurement.outcome == "timeout"


def test_repeated_phases_accumulate_and_snapshot_does_not_change() -> None:
    # Given a collector whose earlier snapshot was exported.
    collector = metrics.InferenceMetricsCollector()
    earlier_snapshot = collector.snapshot()
    clock = ManualClock()
    # When one operation executes two generation attempts.
    with metrics.measure_inference("write", observer=collector, clock=clock) as trace:
        for _ in range(2):
            with trace.phase("generation_http"):
                clock.advance(0.125)
    # Then both attempts contribute to this measurement without changing old snapshots.
    measurement, = collector.snapshot()
    assert measurement.generation_http_ms == 250
    assert earlier_snapshot == ()


def test_nested_scope_restores_outer_collector_after_failure() -> None:
    # Given a request which starts a nested observation scope.
    with metrics.capture_inference_metrics() as outer:
        with metrics.measure_inference("route"):
            pass
        # When the nested scope fails.
        with (
            pytest.raises(ValueError, match="nested"),
            metrics.capture_inference_metrics() as inner,
            metrics.measure_inference("judge"),
        ):
            raise ValueError("nested")
        with metrics.measure_inference("write"):
            pass
    # Then subsequent work returns to the original request's collector.
    assert [measurement.operation for measurement in outer.snapshot()] == ["route", "write"]
    assert [measurement.operation for measurement in inner.snapshot()] == ["judge"]
    assert inner.request_id != outer.request_id
    assert all(measurement.request_id == outer.request_id for measurement in outer.snapshot())


@pytest.mark.anyio
async def test_concurrent_requests_have_isolated_correlation_and_phase_times() -> None:
    # Given two operations deliberately suspended across each other's timing windows.
    ready = [anyio.Event(), anyio.Event()]
    collectors: list[metrics.InferenceMetricsCollector] = []

    async def worker(index: int) -> None:
        clock = ManualClock()
        with (
            metrics.capture_inference_metrics() as collector,
            metrics.measure_inference("write", clock=clock) as trace,
            trace.phase("generation_http"),
        ):
            collectors.append(collector)
            clock.advance(index + 1)
            ready[index].set()
            await ready[1 - index].wait()

    # When both request scopes run concurrently, without wall-clock sleeps.
    async with anyio.create_task_group() as group:
        _ = group.start_soon(worker, 0)
        _ = group.start_soon(worker, 1)
    # Then each request contains only its own elapsed time and request ID.
    measurements = [collector.snapshot()[0] for collector in collectors]
    assert {measurement.generation_http_ms for measurement in measurements} == {1000, 2000}
    assert len({measurement.request_id for measurement in measurements}) == 2
    assert all(len(collector.snapshot()) == 1 for collector in collectors)


@pytest.mark.anyio
@pytest.mark.parametrize("response_received", [False, True])
async def test_cancelled_request_records_elapsed_phase_and_preserves_cancellation(
    response_received: bool,
) -> None:
    # Given an operation running inside the caller's cancellation scope.
    clock = ManualClock()
    reached_after_checkpoint = False
    # When cancellation interrupts a generation checkpoint.
    with (
        metrics.capture_inference_metrics() as collector,
        anyio.CancelScope() as cancellation,
        metrics.measure_inference("write", clock=clock) as trace,
        trace.phase("generation_http"),
    ):
        clock.advance(0.5)
        if response_received:
            trace.set_outcome("success")
        cancellation.cancel()
        await anyio.lowlevel.checkpoint()
        reached_after_checkpoint = True
    # Then the caller's scope catches cancellation and the elapsed phase is retained.
    measurement, = collector.snapshot()
    assert measurement.outcome == "cancelled"
    assert measurement.generation_http_ms == 500
    assert cancellation.cancelled_caught
    assert not reached_after_checkpoint
