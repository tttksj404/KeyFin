"""Standalone authenticated financial coaching API."""

from typing import Annotated

from fastapi import Depends, FastAPI

from coaching_service.auth import Authenticate
from coaching_service.chat_answers import ChatAnswer, FinanceQuestion
from coaching_service.coaching import CoachingCore
from coaching_service.dialogue import Dialogue
from coaching_service.events import Events
from coaching_service.http_contracts import RequestKey, operation
from coaching_service.records import Records
from coaching_service.repository import document
from coaching_service.schemas import (
    Bootstrap,
    Coaching,
    DeleteResult,
    EventRequest,
    EventResult,
    Identifier,
    JsonDocument,
    Notification,
    NotificationList,
    ReviewRequest,
    Session,
    SessionRequest,
    TurnRequest,
    TwinIdentity,
)


def register_twin(app: FastAPI, core: CoachingCore, auth: Authenticate) -> None:
    events = Events(core)

    async def bootstrap(
        body: Bootstrap, key: RequestKey, owner: Annotated[str, Depends(auth.backend)]
    ) -> TwinIdentity:
        result = await events.bootstrap(operation(owner, "bootstrap", key, document(body)), body)
        return TwinIdentity.model_validate(result.root)

    async def event(
        body: EventRequest, key: RequestKey, owner: Annotated[str, Depends(auth.backend)]
    ) -> EventResult:
        result = await events.apply(operation(owner, "event", key, document(body)), body)
        return EventResult.model_validate(result.root)

    async def twin(owner: Annotated[str, Depends(auth.backend)]) -> JsonDocument:
        return await core.twin(owner)

    app.add_api_route("/v1/twin", bootstrap, methods=["POST"], response_model=TwinIdentity)
    app.add_api_route("/v1/events", event, methods=["POST"], response_model=EventResult)
    app.add_api_route("/v1/twin", twin, methods=["GET"], response_model=JsonDocument)


def register_coaching(app: FastAPI, core: CoachingCore, auth: Authenticate) -> None:
    dialogue = Dialogue(core)

    async def review(
        body: ReviewRequest, key: RequestKey, owner: Annotated[str, Depends(auth.user)]
    ) -> Coaching:
        result = await dialogue.review(operation(owner, "review", key, document(body)), body)
        return Coaching.model_validate(result.root)

    async def coaching(coaching_id: Identifier, owner: Annotated[str, Depends(auth.user)]) -> Coaching:
        return Coaching.model_validate_json(await core.repository.load(owner, "coaching/" + coaching_id))

    async def session(
        body: SessionRequest, key: RequestKey, owner: Annotated[str, Depends(auth.user)]
    ) -> Session:
        result = await dialogue.session(operation(owner, "session", key, document(body)), body)
        return Session.model_validate(result.root)

    async def history(session_id: Identifier, owner: Annotated[str, Depends(auth.user)]) -> Session:
        return Session.model_validate_json(await core.repository.load(owner, "session/" + session_id))

    async def message(
        session_id: Identifier, body: TurnRequest, key: RequestKey, owner: Annotated[str, Depends(auth.user)]
    ) -> Coaching | ChatAnswer:
        result = await dialogue.turn(
            operation(owner, "turn/" + session_id, key, document(body)), session_id, body
        )
        return (
            ChatAnswer.model_validate(result.root)
            if "answer_type" in result.root
            else Coaching.model_validate(result.root)
        )

    async def finance(
        body: FinanceQuestion, key: RequestKey, owner: Annotated[str, Depends(auth.user)]
    ) -> ChatAnswer:
        result = await dialogue.finance(operation(owner, "finance", key, document(body)), body)
        return ChatAnswer.model_validate(result.root)

    async def answer(answer_id: Identifier, owner: Annotated[str, Depends(auth.user)]) -> ChatAnswer:
        return ChatAnswer.model_validate_json(await core.repository.load(owner, "answer/" + answer_id))

    app.add_api_route("/v1/coaching/reviews", review, methods=["POST"], response_model=Coaching)
    app.add_api_route("/v1/coaching/{coaching_id}", coaching, methods=["GET"], response_model=Coaching)
    app.add_api_route("/v1/sessions", session, methods=["POST"], response_model=Session)
    app.add_api_route("/v1/sessions/{session_id}", history, methods=["GET"], response_model=Session)
    app.add_api_route(
        "/v1/sessions/{session_id}/messages", message, methods=["POST"], response_model=Coaching | ChatAnswer
    )
    app.add_api_route("/v1/finance/questions", finance, methods=["POST"], response_model=ChatAnswer)
    app.add_api_route("/v1/answers/{answer_id}", answer, methods=["GET"], response_model=ChatAnswer)


def register_records(app: FastAPI, core: CoachingCore, auth: Authenticate) -> None:
    records = Records(core.repository)

    async def pending(owner: Annotated[str, Depends(auth.notification)]) -> NotificationList:
        return await records.notifications(owner)

    async def acknowledge(
        event_id: Identifier, key: RequestKey, owner: Annotated[str, Depends(auth.notification)]
    ) -> Notification:
        result = await records.acknowledge(
            operation(owner, "ack/" + event_id, key, JsonDocument.model_validate({})), event_id
        )
        return Notification.model_validate(result.root)

    async def erase(owner: Annotated[str, Depends(auth.user)]) -> DeleteResult:
        return await records.erase(owner)

    app.add_api_route("/v1/notifications", pending, methods=["GET"], response_model=NotificationList)
    app.add_api_route(
        "/v1/notifications/{event_id}/ack", acknowledge, methods=["POST"], response_model=Notification
    )
    app.add_api_route("/v1/me/data", erase, methods=["DELETE"], response_model=DeleteResult)
