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


def ingestion_key(revision: int) -> str:
    return f"forecast-ingestion/revision-{revision}"


async def ingestion_writes(
    repository: Repository, owner: str, identity: TwinIdentity, request_digest: str
) -> tuple[Write, ...]:
    """Preserve the first server receipt; retrying a revision cannot move its clock.

    Call inside the same owner-scoped mutation that writes the Twin. This proves
    server receipt time only, not banking-provider truth or consent provenance.
    """
    key = ingestion_key(identity.revision)
    existing = await anyio.to_thread.run_sync(repository.store.load, owner, key)
    if existing is not None:
        if IngestionStamp.model_validate_json(existing).identity != identity:
            raise ServiceError("ingestion_revision_conflict", 409)
        return ()
    return (
        write(key, IngestionStamp(identity=identity, received_at=time.time(), request_digest=request_digest)),
    )
