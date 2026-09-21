"""Owner-bound sessions with engine tools and durable, idempotent turns."""

import time
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING, assert_never
from uuid import uuid4
from zoneinfo import ZoneInfo

import anyio

from coaching_service.chat_answers import (
    ChatAnswer,
    FinanceQuestion,
    knowledge_answer,
    missing_twin_answer,
    out_of_scope_answer,
)
from coaching_service.coaching import CoachingCore, coaching_writes, evidence_for
from coaching_service.dialogue_decision import decide_dialogue
from coaching_service.errors import ServiceError
from coaching_service.evidence import LIMITED_CONTEXT, bounded_evidence, context_limited
from coaching_service.fast_routes import (
    NaturalGoal,
    NaturalPurchase,
    NaturalWhatIf,
    deterministic_analysis_route,
    deterministic_lookup_route,
    natural_goal,
    natural_purchase,
    natural_what_if,
    stored_coaching_followup,
)
from coaching_service.finance_knowledge import (
    deterministic_finance_status,
    deterministic_finance_wording,
    finance_evidence,
    model_selected_finance_evidence,
    selected_finance_wording,
)
from coaching_service.history import historical_context
from coaching_service.knowledge_retrieval import is_followup
from coaching_service.llm_contract import ChatMessage, EvidenceInput, FinanceWording, Routing
from coaching_service.payments import Ledger
from coaching_service.period_request import turn_period
from coaching_service.personal_contract import PersonalContext
from coaching_service.personal_service import CONTEXT_KEY, personal_answer
from coaching_service.repository import Mutation, document, write
from coaching_service.schemas import (
    AnswerReference,
    Coaching,
    JsonDocument,
    Message,
    ReviewRequest,
    Session,
    SessionRequest,
    Tone,
    TurnRequest,
)
from coaching_service.spending_history import spending_answer
from coaching_service.store import Operation

if TYPE_CHECKING:
    from pydantic import JsonValue


def turn_numeric_request(
    analysis: JsonDocument | None,
    parsed_goal: NaturalGoal | None,
    parsed_what_if: NaturalWhatIf | None,
    route: Routing,
    horizon_days: int,
) -> JsonDocument | None:
    """Build a typed FDT request without allowing natural language to invent inputs.

    API-supplied analysis remains authoritative. Natural shortcuts can add only
    one explicitly parsed target or variable-expense branch; the calendar resolver
    provides the horizon after independently checking the user's period expression.
    """
    if analysis is not None:
        return JsonDocument({**analysis.root, "horizon_days": horizon_days})
    if parsed_goal is not None:
        return JsonDocument.model_validate({
            "mode": "goal",
            "horizon_days": horizon_days,
            "paths": 400,
            "seed": 42,
            "goal": {"target_krw": parsed_goal.target_krw},
        })
    if parsed_what_if is not None:
        return JsonDocument.model_validate({
            "mode": "what_if",
            "horizon_days": horizon_days,
            "paths": 400,
            "seed": 42,
            "scenario": parsed_what_if.scenario(),
        })
    if route.mode in {"risk", "forecast"}:
        return JsonDocument.model_validate(
            {"mode": route.mode, "horizon_days": horizon_days, "paths": 100, "seed": 42}
        )
    return None


def resolve_purchase_change(  # noqa: C901, PLR0912 - each guard is one explicit fail-closed payment boundary.
    purchase: NaturalPurchase, twin: JsonDocument, reference: date
) -> JsonDocument:
    """Turn one text-admitted purchase into a single vendor ``expense`` change.

    The text parser never knows which account or card the change belongs to;
    it only names cash/card when the user said so. This still refuses to guess
    among several real candidates, and it still refuses a card purchase with no
    real settlement account. A resolved account/card is the last gate before
    the FDT vendor's own ``validate_change`` (``coaching_contract.py``).
    """
    snapshot = twin.root.get("snapshot")
    raw_accounts = snapshot.get("accounts") if isinstance(snapshot, dict) else None
    raw_cards = snapshot.get("cards") if isinstance(snapshot, dict) else None
    accounts = raw_accounts if isinstance(raw_accounts, list) else []
    cards = raw_cards if isinstance(raw_cards, list) else []
    match purchase.payment_hint:
        case "cash":
            use_card = False
        case "card":
            use_card = True
        case None:
            # Unspecified in the prose is only safe when exactly one real
            # payment source exists at all; two or more is genuine ambiguity.
            if len(accounts) + len(cards) != 1:
                raise ServiceError("purchase_payment_method_required")
            use_card = len(cards) == 1
    if use_card and purchase.card_payment_date is None:
        raise ServiceError("purchase_payment_method_required")
    if purchase.date_token == "today":  # noqa: S105 - a calendar token, not a credential.
        purchase_date = reference
    elif purchase.date_token == "tomorrow":  # noqa: S105 - a calendar token, not a credential.
        purchase_date = reference + timedelta(days=1)
    elif purchase.date_token == "this_week":  # noqa: S105 - a calendar token, not a credential.
        purchase_date = reference
    else:
        try:
            purchase_date = date.fromisoformat(purchase.date_token)
        except ValueError:
            raise ServiceError("purchase_date_required") from None
    change: dict[str, JsonValue] = {
        "kind": "expense",
        "date": purchase_date.isoformat(),
        "amount_krw": purchase.amount_krw,
        "envelope": purchase.envelope,
    }
    if use_card:
        if len(cards) != 1 or not isinstance(cards[0], dict):
            raise ServiceError("purchase_payment_method_required")
        card_id = cards[0].get("card_id")
        if not isinstance(card_id, str):
            raise ServiceError("purchase_payment_method_required")
        change["card_id"] = card_id
        change["payment_date"] = purchase.card_payment_date
    else:
        if len(accounts) != 1 or not isinstance(accounts[0], dict):
            raise ServiceError("purchase_payment_method_required")
        account_id = accounts[0].get("account_id")
        if not isinstance(account_id, str):
            raise ServiceError("purchase_payment_method_required")
        change["account_id"] = account_id
    return JsonDocument(change)


def chat_history(session: Session, *, include_subject: bool = False) -> tuple[ChatMessage, ...]:
    """Use recent context for intent; keep every original message intact in storage."""
    messages = session.messages[-4:]
    if include_subject:
        # Preserve one explicit topic through repeated short follow-ups without resending the full session.
        subject = next((
            row for row in reversed(session.messages) if row.role == "user" and not is_followup(row.content)
        ), None)
        if subject is not None and subject not in messages:
            messages = (subject, *messages[-2:])
    return tuple(
        ChatMessage(
            role=row.role, content=row.content[:800] + (" [이력 일부 생략]" if len(row.content) > 800 else "")
        )
        for row in messages
    )


def save_turn(session: Session, question: str, answer: Coaching | ChatAnswer) -> Mutation:
    """Commit the delivered answer and session text together, including retries."""
    match answer:
        case Coaching():
            response = AnswerReference(kind="coaching", id=answer.id)
            answer_writes = coaching_writes(answer, notify=False)
        case ChatAnswer():
            response = AnswerReference(kind="chat", id=answer.id)
            answer_writes = (write("answer/" + answer.id, answer),)
        case unreachable:
            assert_never(unreachable)
    updated = session.model_copy(
        update={
            "messages": (
                *session.messages,
                Message(role="user", content=question),
                Message(role="assistant", content=answer.text, response=response),
            )
        }
    )
    # 참조만 먼저 저장하거나 별도 호출로 재생성하지 않아 재시도에도 원문과 ID가 일치한다.
    return Mutation(result=document(answer), writes=(write("session/" + session.id, updated), *answer_writes))


class Dialogue:
    def __init__(self, core: CoachingCore) -> None:
        self.core: CoachingCore = core

    async def review(self, op: Operation, request: ReviewRequest) -> JsonDocument:
        async def action() -> Mutation:
            receipt = await self.core.receipt(await self.core.twin(op.owner), request)
            coaching = await self.core.compose(receipt, evidence_for(receipt))
            return Mutation(result=document(coaching), writes=coaching_writes(coaching, notify=False))

        return await self.core.repository.mutate(op, action)

    async def session(self, op: Operation, request: SessionRequest) -> JsonDocument:
        async def action() -> Mutation:
            if request.coaching_id is not None:
                _ = await self.core.repository.load(op.owner, "coaching/" + request.coaching_id)
            now = time.time()
            session = Session(
                id=uuid4().hex, coaching_id=request.coaching_id, created_at=now, expires_at=now + 86400
            )
            return Mutation(result=document(session), writes=(write("session/" + session.id, session),))

        return await self.core.repository.mutate(op, action)

    async def finance(self, op: Operation, request: FinanceQuestion) -> JsonDocument:
        """Allow a source-backed concept question without a Twin or initial review."""

        async def action() -> Mutation:
            evidence = finance_evidence(request.question)
            direct = deterministic_finance_wording(evidence) if self._direct_finance_enabled() else None
            answer = knowledge_answer(direct if direct is not None else await self.core.model.write(evidence))
            return Mutation(result=document(answer), writes=(write("answer/" + answer.id, answer),))

        return await self.core.repository.mutate(op, action)

    async def standalone_answer(
        self, owner: str, request: TurnRequest, route: Routing, history: tuple[ChatMessage, ...],
        finance: FinanceWording | None = None,
    ) -> ChatAnswer | None:
        """Answer concepts before loading financial data; explicit analysis takes precedence."""
        if request.analysis is not None:
            return None
        if route.mode in {"finance", "history", "personal", "other"} and request.period is not None:
            # The period object specifies a future interval, never a historical filter.
            raise ServiceError("period_not_supported_for_intent", 422)
        match route.mode:
            case "finance":
                return knowledge_answer(
                    finance if finance is not None else
                    await self.core.model.write(finance_evidence(request.question, history))
                )
            case "other":
                return out_of_scope_answer()
            case "personal":
                return await personal_answer(self.core.repository, owner, request.question)
            case "history" | "review" | "risk" | "forecast":
                return None
            case unreachable:
                assert_never(unreachable)

    async def active_session(self, owner: str, session_id: str) -> Session:
        session = Session.model_validate_json(await self.core.repository.load(owner, "session/" + session_id))
        if session.expires_at <= time.time():
            raise ServiceError("session_expired", 410)
        if len(session.messages) >= 40:
            raise ServiceError("session_turn_limit", 409)
        return session

    async def _effective_tone(self, owner: str, request: TurnRequest) -> Tone | None:
        """Resolve the tone for a turn: an explicit request tone always wins.

        Falls back to the stored personal context's tone when the request omits
        one. When neither is set this returns ``None``, which preserves the
        existing encouraging-by-default ``deterministic_advice`` wording exactly.
        """
        if request.tone is not None:
            return request.tone
        stored = await anyio.to_thread.run_sync(self.core.repository.store.load, owner, CONTEXT_KEY)
        if stored is None:
            return None
        return PersonalContext.model_validate_json(stored).tone

    async def turn(  # noqa: C901 - one durable turn orchestrates every admitted no-model shortcut in sequence.
        self, op: Operation, session_id: str, request: TurnRequest
    ) -> JsonDocument:
        async def action() -> Mutation:
            session = await self.active_session(op.owner, session_id)
            history = chat_history(session)
            # A natural goal is accepted only when the parser found one exact KRW
            # amount.  It is carried as a local typed value rather than mutating the
            # user's request, so the receipt can still distinguish API-supplied
            # analysis from an admitted natural-language shortcut.
            parsed_goal = natural_goal(request.question) if request.analysis is None else None
            parsed_what_if = natural_what_if(request.question) if request.analysis is None else None
            # A purchase clarification is raised immediately, exactly like
            # ``period_clarification_required``: a 4xx code, before any session
            # mutation, twin load, or model call, never a guessed expense.
            parsed_purchase_outcome = natural_purchase(request.question) if request.analysis is None else None
            if isinstance(parsed_purchase_outcome, str):
                raise ServiceError(parsed_purchase_outcome)
            parsed_purchase: NaturalPurchase | None = (
                parsed_purchase_outcome if isinstance(parsed_purchase_outcome, NaturalPurchase) else None
            )
            route, finance = await self._route_for_turn(
                request, session, history, parsed_goal, parsed_what_if, parsed_purchase,
            )
            standalone = await self.standalone_answer(
                op.owner, request, route,
                chat_history(session, include_subject=True) if route.mode == "finance" else history,
                finance,
            )
            if standalone is not None:
                # Keep actual router adoption separate from answer generation and HTTP success.
                standalone = standalone.model_copy(update={
                    "evidence": JsonDocument({**standalone.evidence.root, "routing": document(route).root})
                })
                return save_turn(session, request.question, standalone)
            try:
                twin = await self.core.twin(op.owner)
            except ServiceError as error:
                if error.code != "resource_not_found":
                    raise
                return save_turn(session, request.question, missing_twin_answer(route))
            original = (
                None
                if session.coaching_id is None
                else Coaching.model_validate_json(
                    await self.core.repository.load(op.owner, "coaching/" + session.coaching_id)
                )
            )
            if original is not None and stored_coaching_followup(request.question):
                # A question about an already delivered coaching cause or the current
                # envelope balance does not ask for a new future-state simulation. Keep
                # the original receipt immutable, update only the separately labelled
                # historical/current ledger facts, and avoid both model phases.
                transactions = await anyio.to_thread.run_sync(self.core.engine.transactions, twin)
                current_envelopes = Ledger.model_validate_json(
                    await self.core.repository.load(op.owner, "ledger")
                ).envelopes
                identity = await anyio.to_thread.run_sync(self.core.engine.identity, twin)
                receipt = original.receipt.model_copy(
                    update={
                        "identity": identity,
                        "request": JsonDocument(
                            {"operation": "historical_coaching_followup", "coaching_id": original.id}
                        ),
                        # The original engine result is retained only under the explicitly
                        # labelled historical field below. Presenting it as a new FDT result
                        # would incorrectly bind past numbers to the current Twin revision.
                        "result": JsonDocument(
                            {"status": "not_run", "reason": "historical_coaching_followup"}
                        ),
                        "payment": None,
                        "trigger": "historical_coaching_followup",
                        "original_coaching_id": original.id,
                        "numeric_request": None,
                        "numeric_result": None,
                        "historical": historical_context(original, transactions),
                        "current_envelopes": current_envelopes,
                        "period": None,
                        "routing": document(route),
                    }
                )
                # The answer is entirely template-rendered from the stored receipt and
                # current ledger. Do not serialize the original receipt into a model
                # prompt merely to decide that no model call is necessary.
                coaching = await self.core.compose(
                    receipt,
                    EvidenceInput(question=request.question, facts_json=LIMITED_CONTEXT),
                    tone=await self._effective_tone(op.owner, request),
                )
                return save_turn(session, request.question, coaching)
            identity = await anyio.to_thread.run_sync(self.core.engine.identity, twin)
            reference = date.fromisoformat(identity.as_of)
            if route.mode == "history" and request.analysis is None:
                summary = spending_answer(
                    reference,
                    await anyio.to_thread.run_sync(self.core.engine.transactions, twin),
                    request.question,
                )
                answer = ChatAnswer(
                    id=uuid4().hex,
                    answer_type="spending_history",
                    status=summary.status,
                    text=summary.text,
                    wording_source="engine",
                    model="not_called",
                    evidence=JsonDocument(
                        {
                            "identity": document(identity).root,
                            "routing": document(route).root,
                            "spending": summary.model_dump(mode="json"),
                        }
                    ),
                    created_at=time.time(),
                )
                return save_turn(session, request.question, answer)
            period = turn_period(reference, request.question, request.period, request.analysis)
            today = datetime.now(ZoneInfo("Asia/Seoul")).date()
            numeric_request = turn_numeric_request(
                request.analysis, parsed_goal, parsed_what_if, route, period.forecast_days,
            )
            if numeric_request is not None:
                receipt = await self.core.numeric_receipt(
                    twin, identity, numeric_request, period, replay=reference != today
                )
            else:
                changes: tuple[JsonDocument, ...] = ()
                if parsed_purchase is not None:
                    changes = (resolve_purchase_change(parsed_purchase, twin, reference),)
                receipt = await self.core.receipt(
                    twin,
                    ReviewRequest(
                        on_date=reference,
                        through_date=period.forecast_end,
                        replay=reference != today,
                        changes=changes,
                    ),
                )
            receipt = receipt.model_copy(
                update={
                    "original_coaching_id": original.id if original is not None else None,
                    "historical": historical_context(
                        original, await anyio.to_thread.run_sync(self.core.engine.transactions, twin)
                    )
                    if original is not None
                    else None,
                    "current_envelopes": Ledger.model_validate_json(
                        await self.core.repository.load(op.owner, "ledger")
                    ).envelopes,
                    "period": period,
                }
            )
            if numeric_request is None and context_limited(
                bounded_evidence(receipt, request.question, history)
            ):
                # An intent-only route is not permission to analyze incomplete financial evidence.
                route = Routing(mode="review", source="template", fallback_reason="context_limit")
            receipt = receipt.model_copy(update={"routing": document(route)})
            evidence = bounded_evidence(receipt, request.question, history)
            coaching = await self.core.compose(
                receipt, evidence, tone=await self._effective_tone(op.owner, request)
            )
            return save_turn(session, request.question, coaching)

        return await self.core.repository.mutate(op, action)

    async def _route_for_turn(  # noqa: PLR0911, PLR0913, PLR0917 - each admitted no-model shortcut is one explicit route boundary.
        self,
        request: TurnRequest,
        session: Session,
        history: tuple[ChatMessage, ...],
        parsed_goal: NaturalGoal | None,
        parsed_what_if: NaturalWhatIf | None,
        parsed_purchase: NaturalPurchase | None = None,
    ) -> tuple[Routing, FinanceWording | None]:
        """Choose a route without changing the established FDT/numeric validation path."""
        if (
            request.analysis is None
            and session.coaching_id is not None
            and stored_coaching_followup(request.question)
        ):
            # The session itself establishes which immutable coaching receipt "this"
            # denotes. A model route would add latency without improving the historical
            # cause or the current ledger values returned below.
            return Routing(mode="review", source="template"), None
        if request.analysis is not None:
            return await self._explicit_analysis_route(request, session, history)
        if parsed_goal is not None or parsed_what_if is not None:
            # A goal supplies one target and a paired branch supplies one
            # variable-expense change; the deadline remains the independently
            # validated calendar result below. ``review`` is the existing route
            # label for entering a typed numeric operation without asking a
            # model to invent an FDT parameter.
            return Routing(mode="review", source="template"), None
        lookup_route = deterministic_lookup_route(request.question)
        if lookup_route is not None:
            # Both the current-snapshot and historical-spending parsers accept
            # only their own complete grammar.  The handlers below still
            # validate availability and never turn a missing ledger into a
            # guessed amount.
            return Routing(mode=lookup_route, source="template"), None
        direct_route = deterministic_analysis_route(request.question)
        if direct_route is not None:
            # This narrow grammar chooses only an unambiguous personal FDT mode.  Calculation,
            # period validation, and final grounded wording still use the existing path below.
            return Routing(mode=direct_route, source="template"), None
        if parsed_purchase is not None:
            # A purchase change rides the same "review" route as any other
            # engine.review call; it is checked last so it can never pre-empt
            # an existing forecast/risk/personal-review/lookup grammar above.
            return Routing(mode="review", source="template"), None
        return await self._route_or_direct_finance(request, session, history)

    async def _explicit_analysis_route(
        self, request: TurnRequest, session: Session, history: tuple[ChatMessage, ...],
    ) -> tuple[Routing, FinanceWording | None]:
        """Honor typed numeric intent before the dialogue model sees its prose."""
        analysis = request.analysis
        if analysis is None:
            raise RuntimeError("structured_analysis_missing")
        match analysis.root.get("mode"):
            case "forecast" | "risk" as mode:
                # An explicit numeric request already supplies the intended mode. It does
                # not need a second model decision; downstream still validates the period
                # and all supplied numeric fields.
                return Routing(mode=mode, source="template"), None
            case "goal" | "optimize" | "what_if":
                # The structured operation is authoritative. The routing schema does not
                # represent these three FDT modes, and a model cannot safely improve the
                # supplied financial parameters.
                return Routing(mode="review", source="template", fallback_reason="structured_numeric"), None
            case _:
                return await self._route_or_direct_finance(request, session, history)

    async def _route_or_direct_finance(
        self, request: TurnRequest, session: Session, history: tuple[ChatMessage, ...],
    ) -> tuple[Routing, FinanceWording | None]:
        """Use a catalog definition only when its full question grammar is satisfied."""
        finance_input = finance_evidence(request.question, chat_history(session, include_subject=True))
        # A structured analysis may be goal/what-if/optimization even when its
        # prose resembles a general concept.  Preserve its original route and
        # numeric-operation observation instead of taking a knowledge shortcut.
        shortcut_allowed = request.analysis is None and self._direct_finance_enabled()
        direct = deterministic_finance_wording(finance_input) if shortcut_allowed else None
        if direct is not None:
            # This strict grammar cannot choose FDT routes or construct values; it
            # supplies one pinned catalog definition only.
            return Routing(mode="finance", source="template"), direct
        bounded_status = deterministic_finance_status(finance_input) if shortcut_allowed else None
        if bounded_status is not None:
            # The question explicitly requires current external material or
            # individual tax/calculation conditions. Returning that gap is
            # safer than making a model infer a catalog status from prose.
            return Routing(mode="finance", source="template"), bounded_status
        fast_selection = model_selected_finance_evidence(finance_input) if shortcut_allowed else None
        if fast_selection is not None:
            # A non-exact general concept still needs the model to choose approved facts,
            # but it does not need a preceding route call or any Twin/FDT lookup.
            wording = await self.core.model.write(fast_selection)
            if isinstance(wording, FinanceWording):
                return Routing(mode="finance", source="template"), wording
            # A model adapter must not convert its own invalid finance response into a
            # personal-data/FDT request after the deterministic scope was accepted.
            return Routing(mode="finance", source="template"), selected_finance_wording(
                None, wording.model, "invalid_finance_wording"
            )
        decision = await decide_dialogue(
            self.core.model,
            EvidenceInput(
                question=request.question,
                history=history,
                facts_json='{"operation":"dialogue"}',
            ),
            finance_input,
        )
        return decision.routing, decision.finance

    def _direct_finance_enabled(self) -> bool:
        """Keep injected legacy/test adapters on their established model-backed behavior."""
        return bool(getattr(self.core.model, "deterministic_finance_fast_path", False))
