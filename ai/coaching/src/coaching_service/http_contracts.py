"""Canonical request identity across retried JSON submissions."""

import hashlib
import json
from typing import Annotated

from fastapi import Header

from coaching_service.schemas import JsonDocument
from coaching_service.store import Operation

RequestKey = Annotated[
    str, Header(alias="Idempotency-Key", min_length=1, max_length=120, pattern=r"^[\w.-]+$")
]


def operation(owner: str, scope: str, key: str, body: JsonDocument) -> Operation:
    content = json.dumps(
        body.root, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    )
    return Operation(owner=owner, scope=scope, key=key, digest=hashlib.sha256(content.encode()).hexdigest())
