import sqlite3
from pathlib import Path

import pytest

from coaching_service.errors import ServiceError
from coaching_service.schemas import JsonDocument
from coaching_service.store import Operation, Store, Write


def op(key: str = "key", owner: str = "owner", digest: str = "digest") -> Operation:
    return Operation(owner=owner, scope="pay", key=key, digest=digest)


def test_cross_instance_lock_and_fencing(tmp_path: Path) -> None:
    path = tmp_path / "state.sqlite3"
    one, two = Store(path), Store(path)
    lease = one.reserve(op()).lease
    assert lease is not None
    with pytest.raises(ServiceError, match="owner_operation_in_progress"):
        two.reserve(op("other"))
    # Simulate a crashed/expired worker, then demonstrate that its stale commit is rejected.
    with sqlite3.connect(path) as conn:
        conn.execute("UPDATE leases SET expires=0")
    fresh = two.reserve(op("fresh")).lease
    assert fresh is not None
    with pytest.raises(ServiceError, match="request_lease_expired"):
        one.commit(lease, (Write(key="ledger", payload="old"),), JsonDocument.model_validate({"ok": True}))
    two.commit(fresh, (Write(key="ledger", payload="new"),), JsonDocument.model_validate({"ok": True}))
    assert one.load("owner", "ledger") == "new"
    assert one.reserve(op("fresh")).cached == JsonDocument.model_validate({"ok": True})
    with pytest.raises(ServiceError, match="idempotency_key_conflict"):
        two.reserve(op("fresh", digest="different"))


def test_commit_failure_rolls_back_all_records(tmp_path: Path) -> None:
    store = Store(tmp_path / "atomic.sqlite3")
    first = store.reserve(op()).lease
    assert first is not None
    store.commit(first, (Write(key="ledger", payload="original"),), JsonDocument.model_validate({"ok": True}))
    lease = store.reserve(op("next")).lease
    assert lease is not None
    # Force the request uniqueness conflict after writes; the transaction must roll back those writes.
    conflict = lease.model_copy(update={"operation": op()})
    with pytest.raises(sqlite3.IntegrityError):
        store.commit(
            conflict,
            (Write(key="ledger", payload="corrupt"), Write(key="outbox/x", payload="bad")),
            JsonDocument.model_validate({"ok": True}),
        )
    assert store.load("owner", "ledger") == "original"
    assert store.load("owner", "outbox/x") is None
