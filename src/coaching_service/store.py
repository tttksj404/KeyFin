"""Atomic owner-scoped persistence and fenced request leases across processes."""

import sqlite3
import time
from collections.abc import Generator
from contextlib import closing, contextmanager
from pathlib import Path
from uuid import uuid4

from pydantic import TypeAdapter

from coaching_service.errors import ServiceError
from coaching_service.schemas import Frozen, JsonDocument


class Write(Frozen):
    key: str
    payload: str | None


class Operation(Frozen):
    owner: str
    scope: str
    key: str
    digest: str


class Lease(Frozen):
    operation: Operation
    token: str


class Reservation(Frozen):
    lease: Lease | None = None
    cached: JsonDocument | None = None


class Store:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path: Path = path
        with self.connection() as conn:
            _ = conn.execute("PRAGMA journal_mode=WAL")
            _ = conn.execute(
                "CREATE TABLE IF NOT EXISTS items(owner TEXT, key TEXT, payload TEXT NOT NULL, "
                "PRIMARY KEY(owner,key))"
            )
            _ = conn.execute(
                "CREATE TABLE IF NOT EXISTS leases(owner TEXT PRIMARY KEY, token TEXT, expires REAL NOT NULL)"
            )
            _ = conn.execute(
                "CREATE TABLE IF NOT EXISTS requests(owner TEXT, scope TEXT, key TEXT, "
                "digest TEXT NOT NULL, result TEXT NOT NULL, PRIMARY KEY(owner,scope,key))"
            )

    @contextmanager
    def connection(self) -> Generator[sqlite3.Connection]:
        with closing(sqlite3.connect(self.path, timeout=5)) as conn, conn:
            yield conn

    def reserve(self, operation: Operation) -> Reservation:
        """소유자당 진행 중 변경은 하나로 제한하고 동시 요청은 409로 거절한다.

        완료된 동일 요청은 재사용하되 본문 digest가 다르면 409다. 예약은 180초 후 만료되지만
        계산 제한은 Repository의 150초이며 완료 시에도 lease 소유권을 재검사한다.
        """
        with self.connection() as conn:
            _ = conn.execute("BEGIN IMMEDIATE")
            row = TypeAdapter[tuple[str, str] | None](tuple[str, str] | None).validate_python(
                conn.execute(
                    "SELECT digest,result FROM requests WHERE owner=? AND scope=? AND key=?",
                    (operation.owner, operation.scope, operation.key),
                ).fetchone()
            )
            if row is not None:
                saved_digest, result = TypeAdapter(tuple[str, str]).validate_python(row)
                if saved_digest != operation.digest:
                    raise ServiceError("idempotency_key_conflict", 409)
                return Reservation(cached=JsonDocument.model_validate_json(result))
            token = uuid4().hex
            _ = conn.execute(
                "DELETE FROM leases WHERE owner=? AND expires<=?", (operation.owner, time.time())
            )
            try:
                _ = conn.execute(
                    "INSERT INTO leases VALUES(?,?,?)", (operation.owner, token, time.time() + 180)
                )
            except sqlite3.IntegrityError:
                raise ServiceError("owner_operation_in_progress", 409) from None
            return Reservation(lease=Lease(operation=operation, token=token))

    def load(self, owner: str, key: str) -> str | None:
        with self.connection() as conn:
            row = TypeAdapter[tuple[str] | None](tuple[str] | None).validate_python(
                conn.execute("SELECT payload FROM items WHERE owner=? AND key=?", (owner, key)).fetchone()
            )
        return None if row is None else TypeAdapter(tuple[str]).validate_python(row)[0]

    def list_items(self, owner: str, prefix: str) -> tuple[str, ...]:
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT payload FROM items WHERE owner=? AND key LIKE ? ORDER BY key LIMIT 100",
                (owner, prefix + "%"),
            ).fetchall()
        return tuple(row[0] for row in TypeAdapter(list[tuple[str]]).validate_python(rows))

    def commit(self, lease: Lease, changes: tuple[Write, ...], result: JsonDocument) -> None:
        """유효한 예약만 상태와 완료 응답을 같은 SQLite 트랜잭션에 반영한다."""
        with self.connection() as conn:
            _ = conn.execute("BEGIN IMMEDIATE")
            row = TypeAdapter[tuple[str] | None](tuple[str] | None).validate_python(
                conn.execute(
                    "SELECT token FROM leases WHERE owner=? AND expires>?",
                    (lease.operation.owner, time.time()),
                ).fetchone()
            )
            if row is None or TypeAdapter(tuple[str]).validate_python(row)[0] != lease.token:
                raise ServiceError("request_lease_expired", 409)
            for change in changes:
                if change.payload is None:
                    _ = conn.execute(
                        "DELETE FROM items WHERE owner=? AND key=?", (lease.operation.owner, change.key)
                    )
                    continue
                _ = conn.execute(
                    "INSERT INTO items VALUES(?,?,?) ON CONFLICT(owner,key) "
                    "DO UPDATE SET payload=excluded.payload",
                    (lease.operation.owner, change.key, change.payload),
                )
            op = lease.operation
            _ = conn.execute(
                "INSERT INTO requests VALUES(?,?,?,?,?)",
                (op.owner, op.scope, op.key, op.digest, result.model_dump_json()),
            )
            _ = conn.execute("DELETE FROM leases WHERE owner=? AND token=?", (op.owner, lease.token))

    def release(self, lease: Lease) -> None:
        with self.connection() as conn:
            _ = conn.execute(
                "DELETE FROM leases WHERE owner=? AND token=?", (lease.operation.owner, lease.token)
            )

    def erase(self, owner: str) -> None:
        """상태·완료 응답·진행 예약을 함께 지워 늦은 작업의 재생성을 막는다."""
        with self.connection() as conn:
            _ = conn.execute("BEGIN IMMEDIATE")
            _ = conn.execute("DELETE FROM items WHERE owner=?", (owner,))
            _ = conn.execute("DELETE FROM requests WHERE owner=?", (owner,))
            _ = conn.execute("DELETE FROM leases WHERE owner=?", (owner,))
