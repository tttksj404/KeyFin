"""The service adapter reuses immutable Twin and deterministic numeric work."""

# ruff: noqa: INP001
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date
from threading import Event, Lock
from typing import TYPE_CHECKING

from fdt import Twin
from fdt.coaching import Coach

from coaching_service import engine as engine_module
from coaching_service.engine import EngineAdapter
from coaching_service.schemas import JsonDocument, ReviewRequest
from tests.test_engine import fixture

if TYPE_CHECKING:
    import pytest
    from pydantic import JsonValue


def forecast_request(*, seed: int = 42) -> JsonDocument:
    return JsonDocument({"mode": "forecast", "horizon_days": 7, "paths": 20, "seed": seed})


def review_request(*, seed: int = 42) -> JsonDocument:
    return JsonDocument.model_validate_json(
        ReviewRequest(
            on_date=date(2026, 9, 10), through_date=date(2026, 9, 16), paths=20, seed=seed
        ).model_dump_json(exclude_none=True)
    )


def test_same_serialized_twin_is_fitted_once_for_identity_and_numeric(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A stored Twin must not be reconstructed for every service-layer operation."""
    source = EngineAdapter()
    document = source.create(fixture("demo"), "demo")
    adapter = EngineAdapter()
    original = engine_module.Twin.from_dict
    calls = 0

    def counted(_cls: type[engine_module.Twin], value: dict[str, JsonValue]) -> engine_module.Twin:
        nonlocal calls
        calls += 1
        return original(value)

    monkeypatch.setattr(engine_module.Twin, "from_dict", classmethod(counted))

    _ = adapter.identity(document)
    _ = adapter.numeric(document, forecast_request())
    _ = adapter.transactions(document)

    assert calls == 1


def test_concurrent_same_serialized_twin_shares_one_inflight_fit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Concurrent requests must not rebuild one immutable Twin in parallel."""
    source = EngineAdapter()
    document = source.create(fixture("demo"), "demo")
    adapter = EngineAdapter()
    original = engine_module.Twin.from_dict
    entered, release, lock = Event(), Event(), Lock()
    calls = 0

    def blocked(
        _cls: type[engine_module.Twin], value: dict[str, JsonValue]
    ) -> engine_module.Twin:
        nonlocal calls
        with lock:
            calls += 1
        entered.set()
        assert release.wait(timeout=1), "test_release_missing"
        return original(value)

    monkeypatch.setattr(engine_module.Twin, "from_dict", classmethod(blocked))

    with ThreadPoolExecutor(max_workers=4) as executor:
        leader = executor.submit(adapter.identity, document)
        assert entered.wait(timeout=1), "test_fit_never_started"
        followers = [executor.submit(adapter.identity, document) for _ in range(3)]
        release.set()
        identities = [leader.result(), *(future.result() for future in followers)]

    assert all(identity == identities[0] for identity in identities)
    assert calls == 1


def test_same_numeric_request_is_calculated_once_and_returned_losslessly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The fixed seed makes an exact request safe to cache within its Twin revision."""
    adapter = EngineAdapter()
    document = adapter.create(fixture("demo"), "demo")
    original = engine_module.Engine.run
    calls = 0

    def counted(
        self: engine_module.Engine, request: dict[str, JsonValue]
    ) -> dict[str, JsonValue]:
        nonlocal calls
        calls += 1
        return original(self, request)

    monkeypatch.setattr(engine_module.Engine, "run", counted)

    first = adapter.numeric(document, forecast_request())
    second = adapter.numeric(document, forecast_request())
    changed_seed = adapter.numeric(document, forecast_request(seed=43))

    assert first == second
    assert first != changed_seed
    assert calls == 2


def test_cached_numeric_result_matches_the_direct_pinned_engine_result() -> None:
    """Caching must not change a deterministic FDT value, interval, or provenance field."""
    adapter = EngineAdapter()
    document = adapter.create(fixture("demo"), "demo")
    request = forecast_request()
    expected = JsonDocument.model_validate(
        engine_module.Engine(engine_module.Twin.from_dict(document.root)).run(request.root)
    )

    first = adapter.numeric(document, request)
    repeated = adapter.numeric(document, request)

    assert first == expected
    assert repeated == expected


def test_concurrent_identical_numeric_requests_share_one_inflight_calculation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Concurrent chat retries must join one deterministic FDT calculation."""
    adapter = EngineAdapter()
    document = adapter.create(fixture("demo"), "demo")
    original = engine_module.Engine.run
    entered, release = Event(), Event()
    calls = 0

    def slow_counted(
        self: engine_module.Engine, request: dict[str, JsonValue]
    ) -> dict[str, JsonValue]:
        nonlocal calls
        calls += 1
        entered.set()
        assert release.wait(timeout=1), "test_release_missing"
        return original(self, request)

    monkeypatch.setattr(engine_module.Engine, "run", slow_counted)
    request = forecast_request()

    with ThreadPoolExecutor(max_workers=4) as executor:
        leader = executor.submit(adapter.numeric, document, request)
        assert entered.wait(timeout=1), "test_numeric_run_never_started"
        followers = [executor.submit(adapter.numeric, document, request) for _ in range(3)]
        release.set()
        results = [leader.result(), *(future.result() for future in followers)]

    assert all(result == results[0] for result in results)
    assert calls == 1


def test_same_review_request_is_calculated_once_and_matches_the_pinned_engine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A complete review has deterministic paths/seed and is safe to reuse by Twin digest."""
    adapter = EngineAdapter()
    document = adapter.create(fixture("demo"), "demo")
    request = review_request()
    original = Coach.review
    calls = 0

    def counted(self: Coach, value: dict[str, JsonValue]) -> dict[str, JsonValue]:
        nonlocal calls
        calls += 1
        return original(self, value)

    monkeypatch.setattr(Coach, "review", counted)

    expected = JsonDocument.model_validate(
        Coach(Twin.from_dict(document.root)).review(request.root)
    )
    first = adapter.review(document, request)
    repeated = adapter.review(document, request)

    assert first == expected
    assert repeated == expected
    assert calls == 2


def test_concurrent_identical_reviews_share_one_inflight_calculation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A retried review must not occupy each simulation worker with the same work."""
    adapter = EngineAdapter()
    document = adapter.create(fixture("demo"), "demo")
    request = review_request()
    original = Coach.review
    entered, release = Event(), Event()
    calls = 0

    def slow_counted(self: Coach, value: dict[str, JsonValue]) -> dict[str, JsonValue]:
        nonlocal calls
        calls += 1
        entered.set()
        assert release.wait(timeout=1), "test_release_missing"
        return original(self, value)

    monkeypatch.setattr(Coach, "review", slow_counted)

    with ThreadPoolExecutor(max_workers=4) as executor:
        leader = executor.submit(adapter.review, document, request)
        assert entered.wait(timeout=1), "test_review_never_started"
        followers = [executor.submit(adapter.review, document, request) for _ in range(3)]
        release.set()
        results = [leader.result(), *(future.result() for future in followers)]

    assert all(result == results[0] for result in results)
    assert calls == 1
