"""backend 전용 현황 입력과 사용자 조회를 동일 owner 인증 경계에 등록한다."""

from typing import Annotated

from fastapi import Depends, FastAPI

from coaching_service.auth import Authenticate
from coaching_service.chat_answers import ChatAnswer, FinanceQuestion
from coaching_service.coaching import CoachingCore
from coaching_service.http_contracts import RequestKey, operation
from coaching_service.personal_contract import PersonalContext, PersonalInput
from coaching_service.personal_service import CONTEXT_KEY, personal_answer, save_personal_context
from coaching_service.repository import Mutation, document, write


def register_personal_context(app: FastAPI, core: CoachingCore, auth: Authenticate) -> None:
    """body에는 owner/received_at이 없으며 신뢰된 토큰과 서버 시각으로만 결정한다."""

    async def update(
        body: PersonalInput,
        key: RequestKey,
        owner: Annotated[str, Depends(auth.backend)],
    ) -> PersonalContext:
        result = await save_personal_context(
            core.repository,
            operation(owner, "personal/context", key, document(body)),
            body,
        )
        return PersonalContext.model_validate(result.root)

    async def current(owner: Annotated[str, Depends(auth.user)]) -> PersonalContext:
        return PersonalContext.model_validate_json(await core.repository.load(owner, CONTEXT_KEY))

    async def question(
        body: FinanceQuestion,
        key: RequestKey,
        owner: Annotated[str, Depends(auth.user)],
    ) -> ChatAnswer:
        async def action() -> Mutation:
            answer = await personal_answer(core.repository, owner, body.question)
            return Mutation(result=document(answer), writes=(write("answer/" + answer.id, answer),))

        result = await core.repository.mutate(
            operation(owner, "personal/question", key, document(body)), action
        )
        return ChatAnswer.model_validate(result.root)

    app.add_api_route("/v1/personal/context", update, methods=["POST"], response_model=PersonalContext)
    app.add_api_route("/v1/personal/context", current, methods=["GET"], response_model=PersonalContext)
    app.add_api_route("/v1/personal/questions", question, methods=["POST"], response_model=ChatAnswer)
