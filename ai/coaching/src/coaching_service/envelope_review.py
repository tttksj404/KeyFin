"""One envelope's budget-alert evaluation for the backend's 50·20·5%·over alerts.

Every amount comes from the backend's own ledger (``Bootstrap.envelopes`` →
``ledger``) and the approved envelope budget in the Twin snapshot, and the period
is the configured budget cycle (``budget_start_day``). This deliberately does not
reuse the risk answer's ``budget_risk`` rows, which mix calendar-month simulation
and transfers, so the alert's number and the coach's sentence always agree.

The text is a deterministic template: no model call, so it is fast, never drifts
from the ledger, and never fails because the GPU is busy. It is plain text (no
``**`` bold marks) because the alert is shown where markdown is not rendered.
"""

from __future__ import annotations

import time
from datetime import date
from typing import Annotated, Literal
from uuid import uuid4

import anyio
from pydantic import Field

from coaching_service.chart_projection import ENVELOPES
from coaching_service.errors import ServiceError
from coaching_service.payments import Ledger
from coaching_service.periods import DateOnly, budget_cycle
from coaching_service.repository import Mutation, Repository, write
from coaching_service.schemas import BUDGET_CONFIG_KEY, BudgetConfig, Frozen, JsonDocument

EnvelopeTier = Literal["50", "20", "5", "over"]
_STRONG_PERCENT = 10.0


class EnvelopeReviewRequest(Frozen):
    envelope: Annotated[str, Field(min_length=1, max_length=40)]
    tier: EnvelopeTier
    # 생략하면 현재 Twin 기준일(백엔드가 방금 push 한 오늘)을 쓴다.
    on_date: DateOnly | None = None


class EnvelopeReview(Frozen):
    id: str
    envelope: str
    tier: EnvelopeTier
    text: str
    budget_krw: int
    remaining_krw: int
    used_krw: int
    remaining_percent: float
    as_of: date
    period_start: date
    period_end: date
    days_left: int
    daily_allowance_krw: int | None
    wording_source: Literal["template"] = "template"
    created_at: float


def _won(value: int) -> str:
    return f"{value:,}원"


def _percent(value: float) -> str:
    # 0%라고 쓰면 남은 금액과 어긋나므로 1% 미만은 따로 표기한다.
    return "1% 미만" if 0 < value < 1 else f"{round(value)}%"


def _text(review: EnvelopeReview) -> str:
    """Wording follows the ledger numbers; the tier only picks the advice sentence."""
    env, end = review.envelope, f"{review.period_end.month}월 {review.period_end.day}일"
    days, remaining, budget = review.days_left, review.remaining_krw, review.budget_krw
    if remaining <= 0:
        head = (
            f"{env} 예산을 {_won(-remaining)} 넘었어요(예산 {_won(budget)})."
            if remaining < 0
            else f"{env} 예산을 모두 썼어요(예산 {_won(budget)})."
        )
        return (
            f"{head} {end}까지 {days}일 남았으니 이번 주기에는 {env} 지출을 멈추는 편이 좋아요. "
            "다른 봉투에 여유가 있으면 옮겨 쓰는 방법도 있어요."
        )
    if remaining > budget:
        extra = _won(remaining - budget)
        head = f"{env} 예산 {_won(budget)}보다 {extra} 많은 {_won(remaining)}이 남아 있어요."
    else:
        head = (
            f"{env} 예산이 {_percent(review.remaining_percent)} 남았어요. "
            f"예산 {_won(budget)} 중 {_won(remaining)}이 남았어요."
        )
    daily = review.daily_allowance_krw
    pace = (
        f" {end}까지 {days}일 동안 하루 {_won(daily)} 안에서 쓰면 이번 주기를 지킬 수 있어요."
        if daily
        else ""
    )
    careful = f" 남은 기간에는 꼭 필요한 {env} 지출 위주로 조절해 보세요."
    strong = f" 거의 다 썼으니 {end}까지는 {env} 지출을 최대한 미루는 편이 좋아요."
    # 5%·초과 알림이어도 장부 잔액이 넉넉하면(장부 갱신 시차) "거의 다 썼다"고 하지 않는다.
    advice = {
        "50": "",
        "20": careful,
        "5": strong if review.remaining_percent <= _STRONG_PERCENT else careful,
        "over": strong if review.remaining_percent <= _STRONG_PERCENT else careful,
    }[review.tier]
    return head + pace + advice


async def evaluate_envelope(
    repository: Repository, owner: str, twin: JsonDocument, request: EnvelopeReviewRequest
) -> Mutation:
    if request.envelope not in ENVELOPES:
        raise ServiceError("envelope_unknown", 422)
    ledger = Ledger.model_validate_json(await repository.load(owner, "ledger"))
    balance = next((row.balance_krw for row in ledger.envelopes if row.envelope == request.envelope), None)
    if balance is None:
        raise ServiceError("envelope_not_in_ledger", 422)
    snapshot = twin.root.get("snapshot")
    budgets = snapshot.get("budgets") if isinstance(snapshot, dict) else None
    budget = budgets.get(request.envelope) if isinstance(budgets, dict) else None
    if isinstance(budget, float) and budget.is_integer():
        budget = int(budget)  # push 스키마가 300000.0을 정수로 받아 주므로 여기서도 같게 본다
    if isinstance(budget, bool) or not isinstance(budget, int) or budget <= 0:
        raise ServiceError("envelope_budget_missing", 422)
    raw_as_of = twin.root.get("as_of") or (snapshot.get("as_of") if isinstance(snapshot, dict) else None)
    as_of = raw_as_of if isinstance(raw_as_of, str) else None
    if request.on_date is None and as_of is None:
        raise ServiceError("envelope_reference_missing", 422)
    reference = request.on_date or date.fromisoformat(str(as_of))
    stored = await anyio.to_thread.run_sync(repository.store.load, owner, BUDGET_CONFIG_KEY)
    start_day = BudgetConfig.model_validate_json(stored).start_day if stored is not None else 1
    period_start, period_end = budget_cycle(reference, start_day)
    if as_of is not None and budget_cycle(date.fromisoformat(as_of), start_day) != (period_start, period_end):
        # 장부 잔액은 push 시점 주기의 값이라 다른 주기의 날짜에 붙이면 숫자가 어긋난다.
        raise ServiceError("envelope_on_date_out_of_cycle", 422)
    days_left = (period_end - reference).days + 1  # 오늘 포함
    draft = EnvelopeReview(
        id=uuid4().hex,
        envelope=request.envelope,
        tier=request.tier,
        text="",
        budget_krw=budget,
        remaining_krw=balance,
        used_krw=max(budget - balance, 0),
        remaining_percent=round(balance / budget * 100, 1) + 0.0,  # -0.0 방지
        as_of=reference,
        period_start=period_start,
        period_end=period_end,
        days_left=days_left,
        daily_allowance_krw=((balance // days_left) or None) if balance > 0 else None,
        created_at=time.time(),
    )
    review = draft.model_copy(update={"text": _text(draft)})
    return Mutation(
        result=JsonDocument.model_validate_json(review.model_dump_json()),
        writes=(write("envelope-review/" + review.id, review),),
    )
