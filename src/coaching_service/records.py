"""Readback, notification delivery acknowledgments and user deletion."""

import anyio

from coaching_service.repository import Mutation, Repository, document, write
from coaching_service.schemas import DeleteResult, JsonDocument, Notification, NotificationList
from coaching_service.store import Operation, Write


class Records:
    def __init__(self, repository: Repository) -> None:
        self.repository: Repository = repository

    async def notifications(self, owner: str) -> NotificationList:
        values = await anyio.to_thread.run_sync(self.repository.store.list_items, owner, "outbox/")
        return NotificationList(items=tuple(Notification.model_validate_json(value) for value in values))

    async def acknowledge(self, op: Operation, event_id: str) -> JsonDocument:
        async def action() -> Mutation:
            acknowledged = await anyio.to_thread.run_sync(
                self.repository.store.load, op.owner, "ack/" + event_id
            )
            if acknowledged is not None:
                return Mutation(result=JsonDocument.model_validate_json(acknowledged))
            value = await self.repository.load(op.owner, "outbox/" + event_id)
            notification = Notification.model_validate_json(value).model_copy(update={"acknowledged": True})
            return Mutation(
                result=document(notification),
                writes=(
                    Write(key="outbox/" + event_id, payload=None),
                    write("ack/" + event_id, notification),
                ),
            )

        return await self.repository.mutate(op, action)

    async def erase(self, owner: str) -> DeleteResult:
        await anyio.to_thread.run_sync(self.repository.store.erase, owner)
        return DeleteResult(deleted=True)
