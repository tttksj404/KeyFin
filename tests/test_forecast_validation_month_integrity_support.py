# ruff: noqa: INP001
"""기존 저장 문서의 순서 변경·구버전·손상을 명시적으로 만드는 시험 보조 함수."""

import json
import sqlite3
from contextlib import closing
from pathlib import Path


def stored(path: Path, key: str) -> dict:
    with closing(sqlite3.connect(path)) as connection:
        row = connection.execute("SELECT payload FROM items WHERE owner='demo' AND key=?", (key,)).fetchone()
    assert row is not None
    return json.loads(row[0])


def replace(path: Path, key: str, payload: dict) -> None:
    with closing(sqlite3.connect(path)) as connection, connection:
        changed = connection.execute(
            "UPDATE items SET payload=? WHERE owner='demo' AND key=?", (json.dumps(payload), key),
        )
    assert changed.rowcount == 1
