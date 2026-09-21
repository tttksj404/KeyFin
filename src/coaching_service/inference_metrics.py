"""Opt-in, payload-free timings for individual model operations."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from time import perf_counter
from typing import TYPE_CHECKING, Final, Literal, Self, assert_never
from uuid import UUID, uuid4

import anyio

if TYPE_CHECKING:
    from collections.abc import Callable, Generator
    from types import TracebackType

    from coaching_service.llm_contract import Operation

MetricPhase = Literal["limiter_wait", "token_preflight", "generation_http"]
MetricOutcome = Literal["success", "rejected", "failure", "timeout", "cancelled"]


@dataclass(frozen=True, slots=True)
class InferenceMeasurement:
    """Only generated correlation IDs, operation labels and elapsed times leave a trace."""

    request_id: UUID
    operation: Operation
    limiter_wait_ms: float | None
    token_preflight_ms: float | None
    generation_http_ms: float | None
    total_ms: float
    outcome: MetricOutcome


class InferenceMetricsCollector:
    """Mutable in-memory request accumulator; exporters consume immutable snapshots.

    This deliberately is not an arbitrary callback: instrumentation never performs
    I/O, invokes external logging code, or gains access to request/response payloads.
    Create one collector per request, never on a shared application singleton.
    """

    def __init__(self) -> None:
        self.request_id: UUID = uuid4()
        self._measurements: list[InferenceMeasurement] = []

    def record(self, measurement: InferenceMeasurement) -> None:
        self._measurements.append(measurement)

    def snapshot(self) -> tuple[InferenceMeasurement, ...]:
        return tuple(self._measurements)


_CURRENT_COLLECTOR: Final[ContextVar[InferenceMetricsCollector | None]] = ContextVar(
    "inference_metrics_collector", default=None,
)


@contextmanager
def capture_inference_metrics() -> Generator[InferenceMetricsCollector, None, None]:
    """Bind one fresh request collector, restoring any outer scope on every exit."""
    collector = InferenceMetricsCollector()
    token = _CURRENT_COLLECTOR.set(collector)
    try:
        yield collector
    finally:
        _CURRENT_COLLECTOR.reset(token)


class InferenceTrace:
    """Mutable operation-local stopwatch; no global clock or shared timing state.

    A phase is measured through completion or interruption, including repeated
    attempts. HTTP time includes transport and response reading, not GPU compute
    alone. Unentered phases are None. The total also includes local work outside
    phases and therefore must not be reconstructed by summing the phase fields.
    """

    def __init__(
        self, operation: Operation, observer: InferenceMetricsCollector | None,
        clock: Callable[[], float],
    ) -> None:
        self._operation: Operation = operation
        self._observer: InferenceMetricsCollector | None = observer
        self._clock: Callable[[], float] = clock
        self._started: float = 0
        self._durations: dict[MetricPhase, float | None] = {
            "limiter_wait": None, "token_preflight": None, "generation_http": None,
        }
        self._outcome: MetricOutcome | None = None

    def __enter__(self) -> Self:
        """Start timing only when a collector is enabled."""
        if self._observer is not None:
            self._started = self._clock()
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> Literal[False]:
        """Record one outcome while preserving every exception and cancellation."""
        # Do not catch, suppress or serialize exceptions, including cancellation.
        if self._observer is not None:
            total_ms = (self._clock() - self._started) * 1000
            outcome = self._outcome
            # A received response is not an operational success if cleanup still raises.
            # Keep precise handled failure classifications such as transport timeouts.
            if outcome is None or (outcome == "success" and exc is not None):
                outcome = _exception_outcome(exc)
            self._observer.record(InferenceMeasurement(
                request_id=self._observer.request_id,
                operation=self._operation,
                limiter_wait_ms=self._durations["limiter_wait"],
                token_preflight_ms=self._durations["token_preflight"],
                generation_http_ms=self._durations["generation_http"],
                total_ms=total_ms,
                outcome=outcome,
            ))
        return False

    def set_outcome(self, outcome: MetricOutcome) -> None:
        """Mark handled failures, whose exceptions do not reach the context exit."""
        self._outcome = outcome

    @contextmanager
    def phase(self, phase: MetricPhase) -> Generator[None, None, None]:
        """Measure one named phase without adding an async cancellation checkpoint."""
        if self._observer is None:
            yield
            return
        started = self._clock()
        try:
            yield
        finally:
            self._durations[phase] = (self._durations[phase] or 0) + (self._clock() - started) * 1000


def _exception_outcome(exc: BaseException | None) -> MetricOutcome:
    match exc:
        case None:
            return "success"
        case TimeoutError():
            return "timeout"
        case BaseException():
            try:
                cancelled_type = anyio.get_cancelled_exc_class()
            except RuntimeError:
                # AnyIO raises NoEventLoopError when these sync helpers run outside
                # an async backend. Such exceptions cannot be AnyIO cancellation.
                return "failure"
            return "cancelled" if isinstance(exc, cancelled_type) else "failure"
        case unreachable:
            assert_never(unreachable)


def measure_inference(
    operation: Operation, *, observer: InferenceMetricsCollector | None = None,
    clock: Callable[[], float] = perf_counter,
) -> InferenceTrace:
    """Measure one operation using an explicit collector or the current request.

    With no collector configured the context managers are inert: they do not read
    the clock or generate IDs. The injected clock must be monotonic and return
    seconds, matching ``time.perf_counter``.
    """
    collector = observer if observer is not None else _CURRENT_COLLECTOR.get()
    return InferenceTrace(operation, collector, clock)
