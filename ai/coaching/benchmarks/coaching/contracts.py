"""Separate model-visible inputs, evaluator labels and immutable call evidence."""

from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field

from coaching_service.llm_contract import EvidenceInput, Mode, Operation
from coaching_service.schemas import Receipt

Split = Literal["development", "holdout"]
Stratum = Literal["complete", "missing", "adversarial"]
Profile = Literal["base8", "base27"]
Phase = Literal["development", "holdout", "warmup", "repeat", "load"]


class Frozen(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")


class CaseInput(Frozen):
    case_id: str
    evidence: EvidenceInput


class CaseLabel(Frozen):
    case_id: str
    family_id: str
    split: Split
    domain: str
    stratum: Stratum
    receipt_archetype_id: str
    attack_template_id: str | None = None
    expected_route: Mode
    expected_judgment: Literal["needs_data"] | None = None
    rationale: str


class ReceiptRecord(Frozen):
    case_id: str
    receipt: Receipt


class CaseBundle(Frozen):
    inputs: tuple[CaseInput, ...]
    labels: tuple[CaseLabel, ...]
    receipts: tuple[ReceiptRecord, ...]


class CallRecord(Frozen):
    """One attempted operation; failures keep their original denominator and raw text."""

    call_id: str
    case_id: str
    operation: Operation
    profile: Profile
    phase: Phase
    repeat_index: int = Field(default=0, ge=0)
    started_at: str
    elapsed_seconds: float | None = Field(default=None, ge=0)
    http_status: int | None = None
    response_body: str | None = None
    raw_text: str = ""
    result_json: str | None = None
    error_code: str | None = None
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)


class Interval(Frozen):
    low: float
    high: float


class Rate(Frozen):
    successes: int
    attempts: int
    fraction: float | None
    wilson95: Interval | None


class ScoredCall(Frozen):
    call_id: str
    case_id: str
    family_id: str
    receipt_archetype_id: str
    split: Split
    stratum: Stratum
    expected_route: Mode
    profile: Profile
    operation: Operation
    http_ok: bool
    model_accepted: bool
    route_correct: bool | None = None
    effective_route_correct: bool | None = None
    needs_data_expected: bool = False
    needs_data_returned: bool | None = None
    judge_policy_model_correct: bool | None = None
    judge_policy_effective_correct: bool | None = None
    raw_policy_flags: tuple[str, ...] = ()
    delivered_policy_flags: tuple[str, ...] = ()
    elapsed_seconds: float | None


class SemanticProbe(Frozen):
    probe_id: str
    family_id: str
    expected_allowed: bool
    text: str
    rationale: str
