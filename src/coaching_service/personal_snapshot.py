"""이미 검증·저장된 팀 FDT snapshot을 조회용으로만 투영한다."""

import hashlib
import json
from typing import ClassVar, Literal, Self, assert_never

from pydantic import ConfigDict, Field, model_validator
from pydantic_core import PydanticCustomError

from coaching_service.periods import DateOnly
from coaching_service.personal_contract import NonnegativeMoney, PersonalRow, PersonalSummary, PersonalTopic
from coaching_service.personal_summary import LABELS, finish, missing
from coaching_service.schemas import Frozen, JsonDocument, Money


class Account(Frozen):
    account_id: str
    balance_krw: Money


class Asset(Frozen):
    asset_id: str
    kind: str
    value_krw: NonnegativeMoney


class Debt(Frozen):
    liability_id: str
    principal_krw: NonnegativeMoney


class Bill(Frozen):
    bill_id: str
    card_id: str
    due_date: DateOnly
    amount_krw: NonnegativeMoney


class Card(Frozen):
    # 원본 FDT가 카드 유형별 필수값을 검증한다. 조회에 필요 없는 필드는 복제하지 않는다.
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="ignore")
    card_id: str
    kind: Literal["DEBIT", "CREDIT"]
    opening_payable_krw: NonnegativeMoney | None = None

    @model_validator(mode="after")
    def credit_payable_is_known(self) -> Self:
        if self.kind == "CREDIT" and self.opening_payable_krw is None:
            raise PydanticCustomError("credit_payable_missing", "Credit card opening payable is required")
        return self


class SnapshotCoverage(Frozen):
    all_assets_reported: bool = Field(default=False, strict=True)
    all_liabilities_reported: bool = Field(default=False, strict=True)


class Snapshot(Frozen):
    """무수정 엔진의 schedules/budgets 등을 남겨두고 필요한 필드만 읽는 투영이다."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="ignore")
    as_of: DateOnly
    source: Literal["USER_ASSUMPTION", "LIVE"]
    accounts: tuple[Account, ...] = Field(max_length=30)
    assets: tuple[Asset, ...] | None = Field(default=None, max_length=100)
    liabilities: tuple[Debt, ...] | None = Field(default=None, max_length=100)
    known_bills: tuple[Bill, ...] | None = Field(default=None, max_length=100)
    cards: tuple[Card, ...] = Field(default=(), max_length=30)
    coverage: SnapshotCoverage = SnapshotCoverage()

    @model_validator(mode="after")
    def unique_ids(self) -> Self:
        groups = (
            tuple(r.account_id for r in self.accounts),
            tuple(r.asset_id for r in self.assets or ()),
            tuple(r.liability_id for r in self.liabilities or ()),
            tuple(r.bill_id for r in self.known_bills or ()),
            tuple(r.card_id for r in self.cards),
        )
        if any(len(set(group)) != len(group) for group in groups):
            raise PydanticCustomError(
                "duplicate_snapshot_id", "Snapshot IDs must be unique within their group"
            )
        return self


def snapshot_summary(twin: JsonDocument, topic: PersonalTopic) -> PersonalSummary:
    """현재 Twin의 예측 cash를 재사용하지 않고 보고된 원본 기준일 잔액만 반환한다."""
    raw_snapshot = twin.root.get("snapshot")
    if raw_snapshot is None:
        return missing(topic)
    snapshot = Snapshot.model_validate(raw_snapshot)
    source_digest = hashlib.sha256(
        json.dumps(raw_snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    required = {"assets": snapshot.assets, "debts": snapshot.liabilities, "payments": snapshot.known_bills}
    if topic in required and required[topic] is None:
        return missing(topic)
    accounts = tuple(
        PersonalRow(
            id="account/" + r.account_id,
            label=r.account_id,
            amount_krw=r.balance_krw,
        )
        for r in snapshot.accounts
    )
    complete = False
    label = LABELS[topic]
    warnings = ["FDT에 보고된 snapshot 값이며 실시간 계좌 재조회 결과가 아닙니다."]
    match topic:
        case "accounts":
            rows = accounts
            warnings.append("보고되지 않은 계좌가 있을 수 있습니다. 음수 잔액도 그대로 합산합니다.")
        case "assets":
            rows = accounts + tuple(
                PersonalRow(
                    id="asset/" + r.asset_id,
                    label=r.asset_id,
                    amount_krw=r.value_krw,
                )
                for r in snapshot.assets or ()
            )
            complete = snapshot.coverage.all_assets_reported
            label = "보고된 계좌 순잔액과 비계좌 자산가액"
            warnings.append(
                "부채를 차감한 순자산이 아닙니다. backend는 계좌를 비계좌 자산에 중복 등록하면 안 됩니다."
            )
        case "debts":
            rows = tuple(
                PersonalRow(
                    id="debt/" + r.liability_id,
                    label=r.liability_id,
                    amount_krw=r.principal_krw,
                )
                for r in snapshot.liabilities or ()
            ) + tuple(
                PersonalRow(
                    id="card/" + r.card_id,
                    label=r.card_id,
                    amount_krw=r.opening_payable_krw,
                )
                for r in snapshot.cards
                if r.kind == "CREDIT" and r.opening_payable_krw is not None
            )
            complete = snapshot.coverage.all_liabilities_reported
            label = "보고된 대출 원금과 카드 미결제액"
            warnings.append(
                "카드 청구서는 미결제액과 중복될 수 있어 다시 더하지 않습니다. 미래 이자는 포함하지 않습니다."
            )
        case "payments":
            rows = tuple(
                PersonalRow(
                    id=r.bill_id,
                    label=r.card_id,
                    amount_krw=r.amount_krw,
                    due_date=r.due_date,
                )
                for r in snapshot.known_bills or ()
                if r.due_date > snapshot.as_of
            )
            warnings.append(
                "기준일 다음날부터의 등록 카드 청구서만 조회하며 미래 소비나 전체 자동이체 예측은 아닙니다."
            )
        case "income" | "fixed_costs" | "insurance" | "goals" | "budget":
            return missing(topic)
        case unreachable:
            assert_never(unreachable)
    if not rows and not complete:
        return missing(topic)
    if twin.root.get("as_of") != snapshot.as_of.isoformat():
        warnings.append(
            "snapshot 기준일과 Twin 거래 기준일이 다릅니다. 최신 거래 반영 잔액으로 해석하지 마세요."
        )
    return finish(
        PersonalSummary(
            topic=topic,
            status="answered",
            text="",
            coverage="complete" if complete else "partial",
            as_of=snapshot.as_of,
            total_krw=sum(r.amount_krw for r in rows),
            total_label=label,
            rows=rows,
            source_system="fdt_snapshot",
            source_record_id="sha256:" + source_digest,
            provenance=snapshot.source,
            warnings=tuple(warnings),
        )
    )
