"""Server receipt stamps committed atomically with each accepted Twin revision."""

import time

import anyio
from pydantic import Field

from coaching_service.errors import ServiceError
from coaching_service.repository import Repository, write
from coaching_service.schemas import Frozen, TwinIdentity
from coaching_service.store import Write


class IngestionStamp(Frozen):
    identity: TwinIdentity
    received_at: float = Field(allow_inf_nan=False, gt=0)
    request_digest: str = Field(pattern=r"^[a-f0-9]{64}$")


def ingestion_key(revision: int, input_digest: str | None = None) -> str:
    """Return an immutable receipt key for one Twin identity.

    ``input_digest`` is part of the key because bootstrap is a full replacement
    and therefore legitimately starts again at revision zero.  The one-argument
    form remains the legacy key so existing stored receipts can be read during
    the transition; new writes always use the identity-bound form.
    """
    if input_digest is None:
        return f"forecast-ingestion/revision-{revision}"
    return f"forecast-ingestion/revision-{revision}/digest-{input_digest}"


def ingestion_lookup_keys(identity: TwinIdentity) -> tuple[str, ...]:
    """Prefer the identity-bound receipt and then fall back to the legacy key."""
    return (ingestion_key(identity.revision, identity.input_digest), ingestion_key(identity.revision))


async def stored_ingestion_stamp(
    repository: Repository, owner: str, identity: TwinIdentity
) -> IngestionStamp | None:
    """Load the receipt for the current identity without treating an absent stamp as an error."""
    for key in ingestion_lookup_keys(identity):
        raw = await anyio.to_thread.run_sync(repository.store.load, owner, key)
        if raw is not None:
            return IngestionStamp.model_validate_json(raw)
    return None


async def ingestion_writes(
    repository: Repository, owner: str, identity: TwinIdentity, request_digest: str
) -> tuple[Write, ...]:
    """Preserve the first server receipt for this Twin identity.

    A bootstrap is a full replacement and can legitimately restart at revision
    zero.  The identity-bound key keeps that new epoch separate; replaying the
    same identity remains a no-op and cannot move its receipt clock.

    Call inside the same owner-scoped mutation that writes the Twin. This proves
    server receipt time only, not banking-provider truth or consent provenance.
    """
    key = ingestion_key(identity.revision, identity.input_digest)
    existing = await anyio.to_thread.run_sync(repository.store.load, owner, key)
    if existing is not None:
        if IngestionStamp.model_validate_json(existing).identity != identity:
            raise ServiceError("ingestion_revision_conflict", 409)
        return ()
    return (
        write(key, IngestionStamp(identity=identity, received_at=time.time(), request_digest=request_digest)),
    )
