"""Opt-in, payload-free request timings for live coaching latency diagnosis."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from time import perf_counter
from typing import TYPE_CHECKING, Final, Literal, TypeVar, assert_never

from starlette.datastructures import Headers

from coaching_service.inference_metrics import InferenceMeasurement, capture_inference_metrics

if TYPE_CHECKING:
    from collections.abc import Callable, Generator

    from starlette.types import ASGIApp, Message, Receive, Scope, Send

_TRACE_HEADER: Final = b"x-coaching-trace"
_TRACE_VALUE: Final = b"1"
_TIMING_HEADER: Final = b"server-timing"
TimingPhase = Literal["limiter", "tokenize", "generation"]
_PHASES: Final[tuple[TimingPhase, ...]] = ("limiter", "tokenize", "generation")
T = TypeVar("T")


@dataclass(frozen=True)
class FdtMeasurement:
    """Request-local total and worker execution times, without financial payload."""

    total_ms: float
    compute_ms: float | None


class FdtTimingCollector:
    """Request-local aggregate with no FDT request, result, or identity fields."""

    def __init__(self) -> None:
        self._milliseconds: float = 0.0
        self._measured: bool = False
        self._compute_milliseconds: float = 0.0
        self._compute_measured: bool = False

    def record(self, milliseconds_value: float) -> None:
        self._milliseconds += max(0.0, milliseconds_value)
        self._measured = True

    def record_compute(self, milliseconds_value: float) -> None:
        self._compute_milliseconds += max(0.0, milliseconds_value)
        self._compute_measured = True

    def snapshot(self) -> FdtMeasurement | None:
        return (
            FdtMeasurement(
                total_ms=self._milliseconds,
                compute_ms=self._compute_milliseconds if self._compute_measured else None,
            )
            if self._measured
            else None
        )


_CURRENT_FDT_TIMING: Final[ContextVar[FdtTimingCollector | None]] = ContextVar(
    "fdt_timing_collector", default=None,
)


@contextmanager
def capture_fdt_timing() -> Generator[FdtTimingCollector, None, None]:
    """Bind one FDT-only collector to the request currently being traced."""
    collector = FdtTimingCollector()
    token = _CURRENT_FDT_TIMING.set(collector)
    try:
        yield collector
    finally:
        _CURRENT_FDT_TIMING.reset(token)


@contextmanager
def measure_fdt() -> Generator[None, None, None]:
    """Measure an FDT operation only when the caller opted into a request trace."""
    collector = _CURRENT_FDT_TIMING.get()
    if collector is None:
        yield
        return
    started = perf_counter()
    try:
        yield
    finally:
        collector.record((perf_counter() - started) * 1000)


def run_measured_fdt(call: Callable[[], T]) -> T:
    """Execute one worker-side FDT call and record compute time when tracing is enabled.

    The outer ``measure_fdt`` span covers limiter waiting plus work. This helper runs
    inside the worker thread, so its time isolates actual cache/engine execution.
    Both values are aggregate-only and are recorded even when the engine raises.
    """
    collector = _CURRENT_FDT_TIMING.get()
    if collector is None:
        return call()
    started = perf_counter()
    try:
        return call()
    finally:
        collector.record_compute((perf_counter() - started) * 1000)


def trace_requested(scope: Scope) -> bool:
    """Enable a trace only with the exact explicit opt-in request header."""
    return Headers(scope=scope).get(_TRACE_HEADER.decode("ascii")) == _TRACE_VALUE.decode("ascii")


def milliseconds(value: float) -> bytes:
    """Emit a compact Server-Timing duration with no request metadata."""
    return f"{max(0.0, value):.3f}".encode("ascii")


def header_value(
    total_ms: float, measurements: tuple[InferenceMeasurement, ...], fdt: FdtMeasurement | None,
) -> bytes:
    """Aggregate model phases without preserving prompts, IDs, URLs, or operation labels."""
    entries = [b"api;dur=" + milliseconds(total_ms)]
    if fdt is not None:
        entries.append(b"fdt;dur=" + milliseconds(fdt.total_ms))
        if fdt.compute_ms is not None:
            entries.append(b"fdt_compute;dur=" + milliseconds(fdt.compute_ms))
            entries.append(b"fdt_wait;dur=" + milliseconds(fdt.total_ms - fdt.compute_ms))
    if not measurements:
        return b", ".join(entries)
    entries.append(b"model;dur=" + milliseconds(sum(row.total_ms for row in measurements)))
    for metric_name in _PHASES:
        measured = phase_durations(metric_name, measurements)
        if measured:
            entries.append(metric_name.encode("ascii") + b";dur=" + milliseconds(sum(measured)))
    return b", ".join(entries)


def phase_durations(
    metric_name: TimingPhase, measurements: tuple[InferenceMeasurement, ...]
) -> tuple[float, ...]:
    """Return phase durations without reflection over the immutable metric schema."""
    match metric_name:
        case "limiter":
            values = tuple(row.limiter_wait_ms for row in measurements)
        case "tokenize":
            values = tuple(row.token_preflight_ms for row in measurements)
        case "generation":
            values = tuple(row.generation_http_ms for row in measurements)
        case unreachable:
            assert_never(unreachable)
    return tuple(value for value in values if value is not None)


class RequestTiming:
    """Attach an optional response-ready timing trace to an individual HTTP request.

    Normal traffic creates no collector or clock reads. A traced response exposes only
    aggregate elapsed milliseconds: API response-ready time, all model-operation time,
    and the three bounded model phases. It deliberately omits route labels, request IDs,
    prompt text, engine evidence, endpoint addresses, and error details.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app: ASGIApp = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not trace_requested(scope):
            await self.app(scope, receive, send)
            return
        started = perf_counter()
        with capture_inference_metrics() as collector, capture_fdt_timing() as fdt_collector:
            async def send_timing(message: Message) -> None:
                if message["type"] == "http.response.start":
                    message = dict(message)
                    elapsed_ms = (perf_counter() - started) * 1000
                    message["headers"] = [
                        *message.get("headers", []),
                        (
                            _TIMING_HEADER,
                            header_value(elapsed_ms, collector.snapshot(), fdt_collector.snapshot()),
                        ),
                    ]
                await send(message)

            await self.app(scope, receive, send_timing)
