"""Optional joint routing and fact selection without changing existing model adapters."""

from typing import Annotated, Literal, Protocol, Self, runtime_checkable

from pydantic import Field, model_validator
from pydantic_core import PydanticCustomError

from coaching_service.finance_knowledge import FinanceSelection, MissingInformation
from coaching_service.llm_contract import (
    CoachModel,
    EvidenceInput,
    FinanceWording,
    FrozenContract,
    Routing,
    RoutingDraft,
)


class DialogueFinanceSelection(FrozenContract):
    """Restrict the generation schema too, while reusing all existing fact validation."""

    status: Literal["answered", "needs_source"]
    fact_ids: Annotated[tuple[str, ...], Field(max_length=3)]
    missing: Annotated[tuple[MissingInformation, ...], Field(max_length=3)] = ()

    @model_validator(mode="after")
    def approved_facts(self) -> Self:
        _ = FinanceSelection.model_validate_json(self.model_dump_json())
        return self


class DialogueSelection(RoutingDraft):
    """Finance facts belong only to a finance route; all other routes defer to their tools."""

    finance: DialogueFinanceSelection | None

    @model_validator(mode="after")
    def matching_route(self) -> Self:
        if (self.mode == "finance") != (self.finance is not None):
            raise PydanticCustomError("inconsistent_dialogue", "Finance selection must match the route")
        return self


class DialogueDecision(FrozenContract):
    routing: Routing
    finance: FinanceWording | None = None


@runtime_checkable
class DialogueDecisionModel(Protocol):
    async def decide(self, routing: EvidenceInput, finance: EvidenceInput) -> DialogueDecision: ...


async def decide_dialogue(
    model: CoachModel, routing: EvidenceInput, finance: EvidenceInput,
) -> DialogueDecision:
    """Keep older injected adapters on their established route-then-write contract."""
    if isinstance(model, DialogueDecisionModel):
        return await model.decide(routing, finance)
    return DialogueDecision(routing=await model.route(routing))
