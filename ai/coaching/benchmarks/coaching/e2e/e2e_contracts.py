"""Synthetic scenario and trace contracts for the separately gated HTTP experiment."""

from datetime import date, timedelta
from pathlib import Path
from typing import Literal, Self
from urllib.parse import urlsplit, urlunsplit

from pydantic import Field, field_validator, model_validator

from coaching_service.llm_contract import EvidenceInput, Mode, Operation
from coaching_service.schemas import Bootstrap, Frozen, JsonDocument
from coaching_service.token_budget import TokenBudget

Action = Literal[
    "payment",
    "refresh",
    "cancel",
    "bootstrap_cancel",
    "duplicate_key",
    "duplicate_event",
    "conflict",
    "isolation",
    "ack",
    "dialogue",
    "analyses",
]
Fault = Literal["none", "write_numeric", "write_http_503", "judge_schema"]


class RunConfig(Frozen):
    output: Path
    backend: Literal["fake", "gpu"] = "fake"
    model: str = "synthetic"
    primary_completed: bool = False
    allow_gpu: bool = False
    upstream_token_file: Path | None = None
    as_of: date | None = None
    upstream_url: str = "http://127.0.0.1:18745/v1/chat/completions"

    @field_validator("upstream_url")
    @classmethod
    def loopback_worker_endpoint(cls, value: str) -> str:
        url = urlsplit(value)
        if (
            url.scheme != "http"
            or url.hostname != "127.0.0.1"
            or url.username is not None
            or url.password is not None
            or url.query
            or url.fragment
            or url.port is None
            or url.path.rstrip("/") not in {"", "/v1/chat/completions"}
        ):
            raise ValueError("Upstream must be an explicit loopback HTTP worker endpoint without credentials")
        return urlunsplit((url.scheme, url.netloc, "/v1/chat/completions", "", ""))

    @model_validator(mode="after")
    def explicit_gpu_gate(self) -> Self:
        if self.backend == "gpu" and not (self.primary_completed and self.allow_gpu):
            raise ValueError("GPU calls require explicit primary completion and allow_gpu gates")
        if self.backend == "gpu" and self.upstream_token_file is None:
            raise ValueError("GPU backend requires an upstream token file")
        return self


class E2ECase(Frozen):
    case_id: str
    owner: str
    purpose: str = ""
    envelope: str
    category: str
    subcategory: str
    amount_krw: int = Field(default=50000, ge=1, le=100000)
    balance_krw: int = 100000
    snapshot: Literal["fresh", "missing", "dirty"] = "fresh"
    action: Action = "payment"
    expected_detection: str | None = None
    question: str = "이번 지출과 관련해 확인할 자료를 같이 살펴봐 주세요."
    expected_route: Mode | None = None
    analyses: tuple[JsonDocument, ...] = ()
    fake_decision: Literal["coach", "skip", "needs_data"] = "coach"
    fake_confidence: float = 0.9
    fake_fault: Fault = "none"

    @property
    def contract_detection(self) -> str:
        """Amount policy for these fixtures, which each have one current-week payment."""
        if self.amount_krw * 2 >= self.balance_krw:
            return "p0_half_balance"
        if self.amount_krw * 5 >= self.balance_krw * 2:
            return "p1_ambiguous"
        return "below_trigger"

    def transaction(self, day: date, transaction_id: str, amount: int) -> JsonDocument:
        return JsonDocument(
            {
                "user_id": self.owner,
                "transaction_id": transaction_id,
                "source": "LIVE",
                "transaction_type": "WITHDRAW",
                "transaction_date": day.isoformat(),
                "transaction_time": "12:00",
                "category": self.category,
                "subcategory": self.subcategory,
                "merchant": "SYNTHETIC SHOP",
                "merchant_id": "synthetic",
                "amount_krw": amount,
                "account_id": "cash-account",
                "card_id": "",
                "confirm_status": "CONFIRMED",
                "status": "NORMAL",
            }
        )

    def snapshot_document(self, day: date, spent: int = 0) -> JsonDocument:
        return JsonDocument(
            {
                "as_of": day.isoformat(),
                "source": "LIVE",
                "accounts": [{"account_id": "cash-account", "balance_krw": 1500000 - spent}],
                "cards": [],
                "known_bills": [],
                "reserve_krw": 100000,
                "budgets": {self.envelope: 300000},
            }
        )

    def bootstrap(self, day: date) -> Bootstrap:
        return Bootstrap.model_validate(
            {
                "as_of": day.isoformat(),
                "transactions": [self.transaction(day - timedelta(days=75), "opening-history", 10000).root],
                "snapshot": None if self.snapshot == "missing" else self.snapshot_document(day).root,
                "envelopes": [{"envelope": self.envelope, "balance_krw": self.balance_krw}],
            }
        )

    def payment_event(self, day: date) -> JsonDocument:
        payload = JsonDocument(
            {
                "expected_revision": 0,
                "event": {
                    "type": "transaction",
                    "event_id": "payment-event",
                    "user_id": self.owner,
                    "transaction": self.transaction(day, "current-payment", self.amount_krw).root,
                },
            }
        )
        if self.snapshot == "fresh":
            payload.root["snapshot_event"] = self.snapshot_event(day, self.amount_krw).root
        return payload

    def snapshot_event(self, day: date, spent: int, event_id: str = "balance-event") -> JsonDocument:
        return JsonDocument(
            {
                "type": "snapshot",
                "event_id": event_id,
                "user_id": self.owner,
                "snapshot": self.snapshot_document(day, spent).root,
            }
        )


class Check(Frozen):
    name: str
    passed: bool
    detail: str = ""


class HttpExchange(Frozen):
    case_id: str
    caller_user_id: str | None
    idempotency_key: str
    method: str
    path: str
    status_code: int
    elapsed_seconds: float
    request_body: JsonDocument | None
    response_body: JsonDocument


class Generation(Frozen):
    case_id: str
    operation: Operation
    backend: Literal["fake", "gpu"]
    request_body: JsonDocument
    evidence: EvidenceInput
    status_code: int
    response_body: str
    elapsed_seconds: float
    request_sha256: str
    prompt_sha256: str


class TokenPreflight(Frozen):
    case_id: str
    operation: Operation
    backend: Literal["fake", "gpu"]
    tokenizer: Literal["synthetic_utf8_bytes_standin", "upstream_serving_tokenizer"]
    evidence: EvidenceInput
    request_sha256: str
    status_code: int
    response_body: str
    budget: TokenBudget | None


class CaseOutcome(Frozen):
    case_id: str
    owner: str
    checks: tuple[Check, ...]
    wording_sources: tuple[str, ...] = ()
    judgment_sources: tuple[str, ...] = ()
    routing_sources: tuple[str, ...] = ()
    deterministic_routes: int = Field(default=0, ge=0)
    fallback_reasons: tuple[str, ...] = ()
    route_expected: Mode | None = None
    route_observed: str | None = None
    route_matches: bool | None = None
    generation_calls: int


class OperationObservation(Frozen):
    operation: Operation
    generation_attempts: int
    upstream_http_200: int
    upstream_non_200: int
    pending: int
    observed_results: int
    accepted_llm: int
    template_results: int
    other_sources: int


class ModelObservation(Frozen):
    backend: Literal["fake", "gpu"]
    generation_attempts: int
    http_status_counts: dict[str, int]
    preflight_http_status_counts: dict[str, int]
    operation_results: tuple[OperationObservation, ...]
    fallback_counts: dict[str, int]
    gpu_connection_verified: bool | None
    interpretation: str


class Report(Frozen):
    experiment: Literal["r5_20260910_e2e_compat"] = "r5_20260910_e2e_compat"
    transport: Literal["uvicorn_tcp_http"] = "uvicorn_tcp_http"
    generation_backend: Literal["fake", "gpu"]
    model: str
    as_of: date
    api_base_url: str
    gateway_base_url: str
    engine_commit: str
    gpu_calls: int
    model_observation: ModelObservation
    cases: tuple[CaseOutcome, ...]
    http: tuple[HttpExchange, ...]
    generations: tuple[Generation, ...]
    preflights: tuple[TokenPreflight, ...]
