"""FDT에 없는 현황만 받는 소유자 없는 입력 계약과 명시적 자료 범위."""

from datetime import datetime
from typing import Annotated, Generic, Literal, Self, TypeVar

from pydantic import AwareDatetime, Field, model_validator
from pydantic_core import PydanticCustomError

from coaching_service.periods import DateOnly
from coaching_service.schemas import Frozen, Identifier, Money, Tone

NonnegativeMoney = Annotated[int, Field(strict=True, ge=0, le=10**12)]
Coverage = Literal["complete", "partial", "unknown"]
PersonalTopic = Literal[
    "accounts", "assets", "debts", "insurance", "income", "fixed_costs", "payments", "goals", "budget"
]


class Item(Frozen):
    id: Identifier
    label: str = Field(min_length=1, max_length=80, pattern=r"^[^\x00-\x1f<>]+$")


class MonthlyItem(Item):
    monthly_amount_krw: NonnegativeMoney


class InsuranceItem(Item):
    monthly_premium_krw: NonnegativeMoney
    coverage_amount_krw: NonnegativeMoney | None = None


class GoalItem(Item):
    target_krw: Annotated[int, Field(strict=True, gt=0, le=10**12)]
    saved_krw: NonnegativeMoney
    target_date: DateOnly | None = None


TItem = TypeVar("TItem", bound=Item)


class Section(Frozen, Generic[TItem]):
    """complete는 backend가 범위를 확인했다는 주장이다. 독립 검증 승인은 아니다."""

    coverage: Coverage = "unknown"
    items: tuple[TItem, ...] = Field(default=(), max_length=100)

    @model_validator(mode="after")
    def check_coverage_and_ids(self) -> Self:
        if self.coverage == "unknown" and self.items:
            raise PydanticCustomError("unknown_section_has_items", "Unknown sections must have no items")
        if len({item.id for item in self.items}) != len(self.items):
            raise PydanticCustomError("duplicate_item_id", "Item IDs must be unique within a section")
        return self


class PersonalInput(Frozen):
    """전체 교체 입력. accounts/assets/liabilities/known_bills는 기존 FDT만 사용한다."""

    expected_revision: int = Field(strict=True, ge=0)
    as_of: DateOnly
    currency: Literal["KRW"] = "KRW"
    source_system: Identifier
    source_record_id: Identifier
    provenance: Literal["connected_backend", "user_declared", "synthetic"]
    insurance: Section[InsuranceItem] = Section[InsuranceItem]()
    income: Section[MonthlyItem] = Section[MonthlyItem]()
    fixed_costs: Section[MonthlyItem] = Section[MonthlyItem]()
    goals: Section[GoalItem] = Section[GoalItem]()
    # Stored verbatim and reused by the turn path when a TurnRequest omits tone.
    tone: Tone | None = None


class PersonalContext(PersonalInput):
    revision: int = Field(strict=True, ge=1)
    received_at: AwareDatetime


class PersonalRow(Frozen):
    id: str
    label: str
    amount_krw: Money
    target_krw: NonnegativeMoney | None = None
    due_date: DateOnly | None = None
    coverage_amount_krw: NonnegativeMoney | None = None


class PersonalSummary(Frozen):
    topic: PersonalTopic | None
    status: Literal["answered", "needs_data", "needs_clarification"]
    text: str
    coverage: Coverage = "unknown"
    as_of: DateOnly | None = None
    total_krw: int | None = None
    total_label: str | None = None
    rows: tuple[PersonalRow, ...] = ()
    source_system: str | None = None
    source_record_id: str | None = None
    provenance: str | None = None
    received_at: datetime | None = None
    revision: int | None = None
    warnings: tuple[str, ...] = ()
