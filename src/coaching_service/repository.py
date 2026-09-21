"""Async boundary around short SQLite operations."""

from collections.abc import Awaitable, Callable

import anyio
from pydantic import BaseModel

from coaching_service.errors import ServiceError
from coaching_service.schemas import Frozen, JsonDocument
from coaching_service.store import Operation, Store, Write


class Mutation(Frozen):
    result: JsonDocument
    writes: tuple[Write, ...] = ()


def document(value: BaseModel) -> JsonDocument:
    return JsonDocument.model_validate_json(value.model_dump_json())


def write(key: str, value: BaseModel) -> Write:
    return Write(key=key, payload=value.model_dump_json())


class Repository:
    def __init__(self, store: Store) -> None:
        self.store: Store = store

    async def load(self, owner: str, key: str) -> str:
        value = await anyio.to_thread.run_sync(self.store.load, owner, key)
        if value is None:
            raise ServiceError("resource_not_found", 404)
        return value

    async def mutate(self, operation: Operation, action: Callable[[], Awaitable[Mutation]]) -> JsonDocument:
        """요청 키를 예약한 뒤 계산하고, 검증된 변경과 응답을 한 트랜잭션에 저장한다.

        같은 키의 완료 요청은 저장된 응답을 그대로 돌려준다. action 실패 시에는
        결과를 캐시하지 않아 수정 후 재시도할 수 있고, commit은 lease를 다시 검사해
        삭제·예약 만료 이후 돌아온 작업이 데이터를 되살리지 못하게 한다.
        """
        reservation = await anyio.to_thread.run_sync(self.store.reserve, operation)
        if reservation.cached is not None:
            return reservation.cached
        lease = reservation.lease
        if lease is None:
            raise ServiceError("reservation_failed", 503)
        try:
            # 작업 제한 150초는 Store 예약 180초보다 짧다. 긴 추론 중에는 DB 쓰기
            # 트랜잭션을 열어 두지 않고, commit에서만 짧게 원자적으로 반영한다.
            with anyio.fail_after(150):
                change = await action()
                await anyio.to_thread.run_sync(self.store.commit, lease, change.writes, change.result)
                return change.result
        except TimeoutError:
            raise ServiceError("operation_deadline", 503) from None
        finally:
            # 클라이언트 취소·시간 초과 중에도 예약 해제는 끝내야 다음 요청이 진행된다.
            with anyio.CancelScope(shield=True):
                await anyio.to_thread.run_sync(self.store.release, lease)
