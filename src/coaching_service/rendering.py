"""Render amounts and causal claims only from the immutable decision receipt."""

from datetime import date
from typing import Final

from coaching_service.numeric_rendering import numeric_text, purchase_envelope, purchase_verdict_text
from coaching_service.periods import period_text
from coaching_service.schemas import Envelope, JsonDocument, Receipt, Tone


def authoritative_text(receipt: Receipt) -> str:
    pieces = historical_text(receipt)
    if receipt.period is not None:
        observed_on = date.fromisoformat(receipt.identity.as_of)
        # A balance check (table turn without a purchase) shows what is left now; the
        # forecast window header belongs to forecast/risk answers. A stale-data notice
        # still shows because it changes how the balances should be read.
        if not _is_balance_check(receipt) or observed_on != receipt.period.reference_date:
            pieces.append(period_text(receipt.period, observed_on))
    pieces.extend(numeric_text(receipt))
    facts = receipt.payment
    if facts is not None:
        pieces.append(
            f"{facts.envelope} 결제액 {facts.amount_krw:,}원, "
            f"차감 전 봉투 잔액 {facts.balance_before_krw:,}원, "
            f"차감 후 {facts.balance_after_krw:,}원입니다."
        )
        if facts.remaining_percent is not None:
            pieces.append(
                f"직전 잔액 대비 남은 비율은 {facts.remaining_percent}%, "
                f"해당 주 같은 봉투의 확인된 결제는 {facts.weekly_count}회입니다."
            )
        if receipt.trigger == "p0_half_balance":
            pieces.append("결제액이 차감 전 봉투 잔액의 50% 이상이어서 코칭이 생성됐습니다.")
        elif receipt.trigger == "p1_context_concern":
            pieces.append("애매 상황에 대한 모델의 보조 판단으로 추가 점검을 제안합니다.")
    # A session-bound historical follow-up must never label the old FDT result as
    # a new result for the current Twin revision. It still renders the preserved
    # historical cause so the user can see why the original coaching existed.
    result = (
        receipt.historical.engine_result
        if receipt.trigger == "historical_coaching_followup" and receipt.historical is not None
        else receipt.result
    )
    action = result.root.get("next_action")
    # "keep_and_review" only says no new cut is advised plus a safety disclaimer;
    # actionable next steps (payment account, earmark, cap, ...) are still shown.
    if isinstance(action, dict) and action.get("kind") not in _SILENT_ACTIONS:
        title, detail = action.get("title"), action.get("detail")
        if isinstance(title, str) and isinstance(detail, str):
            pieces.append(title + ". " + detail)
    pieces.extend(user_warnings(result))
    if not pieces:
        pieces.append("현재 자료로 확인할 수 있는 코칭 근거가 부족합니다. 거래·잔액 정보를 확인해 주세요.")
    return "\n".join(pieces)


_BALANCE_TABLE_NOTE: Final = (
    "**봉투별 남은 잔액은 아래 표에 정리했어요.** 지금까지 들어온 결제를 반영한 장부 잔액이에요."
)


def is_purchase_review(receipt: Receipt) -> bool:
    changes = receipt.request.root.get("changes")
    return isinstance(changes, list) and bool(changes)


BALANCE_TABLE_NOTE: Final = _BALANCE_TABLE_NOTE


def _is_balance_check(receipt: Receipt) -> bool:
    changes = receipt.request.root.get("changes")
    return bool(envelope_balance_table(receipt)) and not (isinstance(changes, list) and changes)


_HANGUL_FIRST: Final = 0xAC00
_HANGUL_LAST: Final = 0xD7A3
_JONG_COUNT: Final = 28
_JONG_RIEUL: Final = 8


def _with_ro(word: str) -> str:
    """Attach 로/으로 by the last syllable: 외식으로, 쇼핑으로, 기타로, 교통비로, 취미·여가로."""
    last = ord(word[-1]) if word else 0
    if _HANGUL_FIRST <= last <= _HANGUL_LAST:
        final = (last - _HANGUL_FIRST) % _JONG_COUNT
        return word + ("로" if final in {0, _JONG_RIEUL} else "으로")
    return word + "(으)로"


def _balance_summary(envelopes: tuple[Envelope, ...], focus: str | None = None) -> str:
    total = sum(envelope.balance_krw for envelope in envelopes)
    lowest = min(envelopes, key=lambda envelope: envelope.balance_krw)
    head = f"봉투 잔액 합계는 {total:,}원이에요."
    named = next((envelope for envelope in envelopes if envelope.envelope == focus), None)
    if named is not None:
        # "외식 예산 얼마 남았어" is answered about 외식 first, then the whole table.
        own = (
            f"{named.envelope} 봉투는 예산을 {-named.balance_krw:,}원 넘었어요."
            if named.balance_krw < 0
            else f"{named.envelope} 봉투는 {named.balance_krw:,}원 남았어요."
        )
        return own + " " + head
    if lowest.balance_krw < 0:
        return head  # 초과 봉투는 가장 크게 넘은 순서로 조언 문장이 짚는다
    return head + f" 가장 적게 남은 봉투는 {_with_ro(lowest.envelope)} {lowest.balance_krw:,}원이 남았어요."


def envelope_balance_table(receipt: Receipt) -> tuple[Envelope, ...]:
    """Envelopes to send as a table row each instead of one sentence per envelope.

    Only a dialogue turn listing several envelopes qualifies. A payment-event
    coaching can also become push-notification text that carries no table, and a
    follow-up about a stored coaching answers one specific balance, so both keep
    their sentences.
    """
    if receipt.payment is not None or receipt.historical is not None:
        return ()
    # A numeric turn's text never lists balances (nor explains a table), and its
    # per-envelope figures already ship in ``numeric_rows``; no balance table there.
    if receipt.numeric_result is not None:
        return ()
    if len(receipt.current_envelopes) < 2:
        return ()
    return receipt.current_envelopes


def historical_text(receipt: Receipt) -> list[str]:
    pieces: list[str] = []
    past = receipt.historical
    if past is not None and past.payment is not None:
        facts = past.payment
        pieces.append(
            f"이전 코칭 생성 당시의 기록: 결제액 {facts.amount_krw:,}원, "
            f"당시 차감 전 {facts.balance_before_krw:,}원, "
            f"당시 차감 후 {facts.balance_after_krw:,}원이었습니다."
        )
        if past.transaction_status == "canceled":
            pieces.append(
                "그 코칭의 원 거래는 현재 취소 상태입니다. 당시 잔액을 현재 잔액으로 사용하지 않습니다."
            )
        elif past.transaction_status == "not_found":
            pieces.append("현재 자료에서 원 거래를 찾을 수 없어 거래 상태를 확인할 수 없습니다.")
    # A fresh numeric turn (what-if/risk/forecast/goal/optimize) answers its own
    # question from ``numeric_result`` and ships per-envelope figures separately in
    # ``numeric_rows``. Prepending every envelope's ledger balance there only buries
    # the actual answer under unrelated lines, so the balance list is kept for the
    # contexts where current balance *is* the point: payment/lookup turns and
    # follow-ups about a stored coaching (``historical``).
    if receipt.numeric_result is not None and past is None:
        return pieces
    if envelope_balance_table(receipt):
        if is_purchase_review(receipt):
            # A purchase answer leads with its verdict; ``compose`` places the table
            # note after it instead of opening with every envelope's balance.
            return pieces
        # The per-envelope balances ship as the structured ``envelope_balances`` table
        # the app renders below the answer; the text only explains that table.
        pieces.append(_BALANCE_TABLE_NOTE)
        focus = receipt.request.root.get("envelope")
        pieces.append(_balance_summary(receipt.current_envelopes, focus if isinstance(focus, str) else None))
        return pieces
    pieces.extend(
        f"현재 수신 이벤트까지 반영한 {envelope.envelope} 봉투 장부 잔액은 {envelope.balance_krw:,}원입니다."
        for envelope in receipt.current_envelopes
    )
    return pieces


_OVER_BUDGET_ENCOURAGING: Final = (
    "{env} 지출이 예산을 넘고 있어요. **이번 기간 {env} 소비를 조금 줄여보면 좋아요.**"
)
_OVER_BUDGET_DIRECT: Final = "{env} 예산을 초과했어요. **{env} 소비를 줄이세요.**"
_OVER_BUDGET_MANY_ENCOURAGING: Final = (
    "{env} 지출이 예산을 가장 많이 넘었고, {others}도 예산을 넘었어요. "
    "**이번 기간 {env} 소비부터 줄여보면 좋아요.**"
)
_OVER_BUDGET_MANY_DIRECT: Final = (
    "{env} 예산을 가장 크게 초과했고, {others}도 초과했어요. **{env} 소비부터 줄이세요.**"
)
_NEAR_LIMIT_ENCOURAGING: Final = "{env} 예산이 거의 다 찼어요. **남은 기간 지출을 조절해 보세요.**"
_NEAR_LIMIT_DIRECT: Final = "{env} 예산이 얼마 남지 않았어요. **{env} 지출을 줄이세요.**"
_SHORTFALL_ENCOURAGING: Final = "이번 기간 현금이 부족할 수 있어요. **큰 지출은 미루는 편이 좋아요.**"
_SHORTFALL_DIRECT: Final = "이번 기간 현금이 부족할 수 있어요. **큰 지출은 미루세요.**"
_SHORTFALL_MARKER: Final = "부족 예측 있음."
_NEAR_LIMIT_MAX_PERCENT: Final = 10
_PURCHASE_OVER_ENCOURAGING: Final = "**이 구매는 미루거나 다른 봉투에서 예산을 옮겨 보면 좋아요.**"
_PURCHASE_OVER_DIRECT: Final = "**구매를 미루거나 다른 봉투 예산을 옮기세요.**"
_HEALTHY_ENCOURAGING: Final = (
    "{env} 예산에 여유가 있어요. **남는 만큼은 저축이나 비상금으로 옮겨 두면 좋아요.**"
)
_HEALTHY_DIRECT: Final = "{env} 예산에 여유가 있어요. **남는 만큼은 저축으로 옮겨 두세요.**"
_HEALTHY_MIN_PERCENT: Final = 80
_OBSERVED_BUDGET_BASIS: Final = "approved_snapshot_budget_minus_observed_budgeted_spending"


def _observed_budget_bands(receipt: Receipt) -> tuple[tuple[str, float], ...]:
    """Read the review engine's own per-envelope remaining fact as ``(envelope, remaining_percent)``.

    A ``requested_review`` receipt never carries ``PaymentFacts``, so its
    ``deterministic_advice`` had no ``remaining_percent`` signal at all. The
    pinned review result (``vendor/fdt/coaching.py`` ``observed_budgets``) already
    computes each envelope's ``budget_krw`` and ``observed_remaining_krw`` from the
    approved snapshot budget minus observed budgeted spending, bound to the same
    Twin revision as the rest of the receipt. This helper only reads that existing
    fact and converts it to a percentage for the identical bands the payment path
    uses; it invents no number and returns ``()`` whenever the fact is absent,
    malformed, or explicitly flagged unreliable.

    It is deliberately confined to receipts without ``PaymentFacts`` so a
    payment-event receipt keeps its established single-envelope advice unchanged.
    """
    if receipt.payment is not None:
        return ()
    result = receipt.result.root
    # Only a fully ready review is trustworthy. A ``needs_data`` review (stale or
    # dirty snapshot, missing cash inputs) still lists observed budgets, but the
    # engine is asking for a data refresh first, so its remaining is not a basis
    # for a spending nudge. Treat anything but ``ready`` as an absent fact.
    if result.get("status") != "ready":
        return ()
    warnings = result.get("warnings")
    if isinstance(warnings, list) and any(
        # The engine itself says remaining budget is not trustworthy for advice
        # when its input is incomplete; treat that as an absent fact, not a nudge.
        isinstance(warning, dict) and warning.get("code") == "BUDGET_INPUT_INCOMPLETE"
        for warning in warnings
    ):
        return ()
    rows = result.get("observed_budgets")
    if not isinstance(rows, list):
        return ()
    bands: list[tuple[str, float]] = []
    for row in rows:
        if not isinstance(row, dict):
            return ()
        if row.get("basis") != _OBSERVED_BUDGET_BASIS:
            continue
        envelope = row.get("envelope")
        budget = row.get("budget_krw")
        remaining = row.get("observed_remaining_krw")
        if (
            not isinstance(envelope, str)
            or not envelope
            or isinstance(budget, bool)
            or not isinstance(budget, (int, float))
            or isinstance(remaining, bool)
            or not isinstance(remaining, (int, float))
            or budget <= 0
        ):
            continue
        bands.append((envelope, remaining / budget * 100))
    return tuple(bands)


def _budget_by_envelope(receipt: Receipt) -> dict[str, float]:
    rows = receipt.result.root.get("observed_budgets")
    budgets: dict[str, float] = {}
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict):
                continue
            envelope, budget = row.get("envelope"), row.get("budget_krw")
            if (
                isinstance(envelope, str)
                and isinstance(budget, (int, float))
                and not isinstance(budget, bool)
                and budget > 0
            ):
                budgets[envelope] = float(budget)
    return budgets


def _over_budget_envelopes(receipt: Receipt) -> list[str]:
    """Name every envelope already confirmed over budget, the most exceeded first.

    ``remaining_percent`` is the service-computed payment ledger fact
    (``PaymentFacts``); a value at or below zero means this payment already
    exhausted its envelope. Otherwise a negative current ledger balance, or the
    review engine's own observed-budget remaining at or below zero, confirms the
    overage. Candidates are ranked by how far past the budget they are (percent of
    budget, so a 2,000% overage is named before a 0.7% one); a ledger overage whose
    budget is unknown ranks after every known one. Nothing is invented: every
    candidate reads an existing engine or ledger signal.
    """
    payment = receipt.payment
    if payment is not None and payment.remaining_percent is not None:
        try:
            remaining = float(payment.remaining_percent)
        except ValueError:
            remaining = None
        if remaining is not None and remaining <= 0:
            return [payment.envelope]
    budgets = _budget_by_envelope(receipt)
    severity: dict[str, float] = {}
    for envelope in receipt.current_envelopes:
        if envelope.balance_krw < 0:
            budget = budgets.get(envelope.envelope)
            severity[envelope.envelope] = envelope.balance_krw / budget * 100 if budget else 0.0
    for name, remaining_percent in _observed_budget_bands(receipt):
        if remaining_percent <= 0:
            severity[name] = min(severity.get(name, remaining_percent), remaining_percent)
    return sorted(severity, key=lambda name: severity[name])


def _near_limit_envelope(receipt: Receipt) -> str | None:
    """Name an envelope that is not over budget yet but is nearly exhausted.

    Reads the same already-validated ``remaining_percent`` payment fact as
    ``_over_budget_envelopes`` and fires only in the strictly-between band
    ``0 < remaining_percent <= 10``. A value outside that band, missing, or
    unparseable returns ``None`` instead of guessing. On a review receipt with no
    payment fact, the same band is read from the engine's own observed-budget
    remaining instead.
    """
    payment = receipt.payment
    if payment is not None:
        if payment.remaining_percent is None:
            return None
        try:
            remaining = float(payment.remaining_percent)
        except ValueError:
            return None
        return payment.envelope if 0 < remaining <= _NEAR_LIMIT_MAX_PERCENT else None
    near = [band for band in _observed_budget_bands(receipt) if 0 < band[1] <= _NEAR_LIMIT_MAX_PERCENT]
    return min(near, key=lambda band: band[1])[0] if near else None


def _healthy_envelope(receipt: Receipt) -> str | None:
    """Name an envelope the engine already reports as comfortably in surplus.

    Reads the same already-validated ``remaining_percent`` payment fact as
    ``_near_limit_envelope`` and ``_over_budget_envelopes`` and fires only when it
    sits at or above ``_HEALTHY_MIN_PERCENT``. This is the lowest-precedence
    signal: a value below that band, missing, or unparseable returns ``None`` so
    no maintenance nudge is invented for an account with no clear surplus. On a
    review receipt with no payment fact, the same surplus band is read from the
    engine's own observed-budget remaining instead.
    """
    payment = receipt.payment
    if payment is not None:
        if payment.remaining_percent is None:
            return None
        try:
            remaining = float(payment.remaining_percent)
        except ValueError:
            return None
        return payment.envelope if remaining >= _HEALTHY_MIN_PERCENT else None
    healthy = [band for band in _observed_budget_bands(receipt) if band[1] >= _HEALTHY_MIN_PERCENT]
    return max(healthy, key=lambda band: band[1])[0] if healthy else None


def deterministic_advice(  # noqa: PLR0911 - one return per advice precedence level.
    receipt: Receipt, *, tone: Tone | None = None,
) -> str | None:
    """Return one server-templated advice sentence, or ``None`` when no engine concern fires.

    This never calls the language model and contains no digits of its own; every
    branch is gated on an existing, already-validated engine fact (an over-budget
    or near-limit envelope's name, or the same forecast-shortfall signal already
    rendered by ``purchase_verdict_text``). Precedence per envelope is
    over-budget > near-limit > shortfall > healthy-surplus: only the single most
    severe sentence is ever returned, never more than one stacked together. The
    lowest-precedence healthy branch fires only when the engine's own
    ``remaining_percent`` surplus fact is actually present and comfortably high;
    a missing signal returns ``None`` instead of nudging every healthy account.
    A ``requested_review`` receipt carries no ``PaymentFacts``, so its envelope
    bands are instead read from the review engine's own ``observed_budgets``
    remaining (``_observed_budget_bands``) with the identical thresholds; a
    payment-event receipt keeps its established single-envelope payment path.
    """
    if is_purchase_review(receipt):
        # Advice on a purchase question is about that purchase only: other envelopes'
        # overage or a savings nudge ("교통비 예산에 여유가 있어요… 저축") right after
        # "can I buy this?" reads as a contradiction.
        if _SHORTFALL_MARKER in purchase_verdict_text(receipt):
            return _SHORTFALL_DIRECT if tone == "direct" else _SHORTFALL_ENCOURAGING
        purchase = purchase_envelope(receipt)
        if purchase is not None and purchase.over_krw:
            return _PURCHASE_OVER_DIRECT if tone == "direct" else _PURCHASE_OVER_ENCOURAGING
        return None
    over = _over_budget_envelopes(receipt)
    if len(over) > 1:
        template = _OVER_BUDGET_MANY_DIRECT if tone == "direct" else _OVER_BUDGET_MANY_ENCOURAGING
        return template.format(env=over[0], others=", ".join(over[1:]))
    if over:
        template = _OVER_BUDGET_DIRECT if tone == "direct" else _OVER_BUDGET_ENCOURAGING
        return template.format(env=over[0])
    envelope = _near_limit_envelope(receipt)
    if envelope is not None:
        template = _NEAR_LIMIT_DIRECT if tone == "direct" else _NEAR_LIMIT_ENCOURAGING
        return template.format(env=envelope)
    if _SHORTFALL_MARKER in purchase_verdict_text(receipt):
        return _SHORTFALL_DIRECT if tone == "direct" else _SHORTFALL_ENCOURAGING
    envelope = _healthy_envelope(receipt)
    if envelope is not None:
        template = _HEALTHY_DIRECT if tone == "direct" else _HEALTHY_ENCOURAGING
        return template.format(env=envelope)
    return None


# Boilerplate caveats the engine attaches regardless of the user's data; they
# repeated on each answer without telling the user anything new, so the user asked
# for them to go ("경로 수와 분위수는…", "다음 달 예산을 이번 달 예산과 같다고…").
_BOILERPLATE_WARNINGS: Final = frozenset(
    {"CONDITIONAL_MODEL", "EXISTING_CARD_SCHEDULE_APPROXIMATION", "NEXT_MONTH_BUDGET_UNCONFIRMED"}
)
_SILENT_ACTIONS: Final = frozenset({"keep_and_review"})


def user_warnings(result: JsonDocument) -> list[str]:
    pieces: list[str] = []
    warnings = result.root.get("warnings")
    if isinstance(warnings, list):
        for warning in warnings:
            if (
                isinstance(warning, dict)
                and warning.get("severity") == "user"
                and warning.get("code") not in _BOILERPLATE_WARNINGS
            ):
                detail = warning.get("detail")
                if isinstance(detail, str):
                    pieces.append(detail)
    return pieces
