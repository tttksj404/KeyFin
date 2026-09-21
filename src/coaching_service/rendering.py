"""Render amounts and causal claims only from the immutable decision receipt."""

from datetime import date
from typing import Final

from coaching_service.numeric_rendering import numeric_text, purchase_verdict_text
from coaching_service.periods import period_text
from coaching_service.schemas import JsonDocument, Receipt, Tone


def authoritative_text(receipt: Receipt) -> str:
    pieces = historical_text(receipt)
    if receipt.period is not None:
        pieces.append(period_text(receipt.period, date.fromisoformat(receipt.identity.as_of)))
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
    if isinstance(action, dict):
        title, detail = action.get("title"), action.get("detail")
        if isinstance(title, str) and isinstance(detail, str):
            pieces.append(title + ". " + detail)
    pieces.extend(user_warnings(result))
    if not pieces:
        pieces.append("현재 자료로 확인할 수 있는 코칭 근거가 부족합니다. 거래·잔액 정보를 확인해 주세요.")
    return "\n".join(pieces)


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
    pieces.extend(
        f"현재 수신 이벤트까지 반영한 {envelope.envelope} 봉투 장부 잔액은 {envelope.balance_krw:,}원입니다."
        for envelope in receipt.current_envelopes
    )
    return pieces


_OVER_BUDGET_ENCOURAGING: Final = (
    "{env} 지출이 예산을 넘고 있어요. 이번 기간 {env} 소비를 조금 줄여보면 좋아요."
)
_OVER_BUDGET_DIRECT: Final = "{env} 예산을 초과했어요. {env} 소비를 줄이세요."
_NEAR_LIMIT_ENCOURAGING: Final = "{env} 예산이 거의 다 찼어요. 남은 기간 지출을 조절해 보세요."
_NEAR_LIMIT_DIRECT: Final = "{env} 예산이 얼마 남지 않았어요. {env} 지출을 줄이세요."
_SHORTFALL_ENCOURAGING: Final = "이번 기간 현금이 부족할 수 있어요. 큰 지출은 미루는 편이 좋아요."
_SHORTFALL_DIRECT: Final = "이번 기간 현금이 부족할 수 있어요. 큰 지출은 미루세요."
_SHORTFALL_MARKER: Final = "부족 예측 있음."
_NEAR_LIMIT_MAX_PERCENT: Final = 10


def _over_budget_envelope(receipt: Receipt) -> str | None:
    """Name one envelope already confirmed over budget by the engine's own facts.

    ``remaining_percent`` is the service-computed payment ledger fact
    (``PaymentFacts``); a value at or below zero means this payment already
    consumed the envelope. ``current_envelopes`` is the separately maintained
    ledger balance. Neither path invents a new threshold: both simply read an
    existing signal that the engine already produced.
    """
    payment = receipt.payment
    if payment is not None and payment.remaining_percent is not None:
        try:
            remaining = float(payment.remaining_percent)
        except ValueError:
            remaining = None
        if remaining is not None and remaining <= 0:
            return payment.envelope
    for envelope in receipt.current_envelopes:
        if envelope.balance_krw < 0:
            return envelope.envelope
    return None


def _near_limit_envelope(receipt: Receipt) -> str | None:
    """Name an envelope that is not over budget yet but is nearly exhausted.

    Reads the same already-validated ``remaining_percent`` payment fact as
    ``_over_budget_envelope`` and fires only in the strictly-between band
    ``0 < remaining_percent <= 10``. A value outside that band, missing, or
    unparseable returns ``None`` instead of guessing.
    """
    payment = receipt.payment
    if payment is None or payment.remaining_percent is None:
        return None
    try:
        remaining = float(payment.remaining_percent)
    except ValueError:
        return None
    if 0 < remaining <= _NEAR_LIMIT_MAX_PERCENT:
        return payment.envelope
    return None


def deterministic_advice(receipt: Receipt, *, tone: Tone | None = None) -> str | None:
    """Return one server-templated advice sentence, or ``None`` when no engine concern fires.

    This never calls the language model and contains no digits of its own; every
    branch is gated on an existing, already-validated engine fact (an over-budget
    or near-limit envelope's name, or the same forecast-shortfall signal already
    rendered by ``purchase_verdict_text``). Precedence per envelope is
    over-budget > near-limit > shortfall: only the single most severe sentence is
    ever returned, never more than one stacked together. A missing or healthy
    signal returns ``None`` instead of guessing a concern the engine did not report.
    """
    envelope = _over_budget_envelope(receipt)
    if envelope is not None:
        template = _OVER_BUDGET_DIRECT if tone == "direct" else _OVER_BUDGET_ENCOURAGING
        return template.format(env=envelope)
    envelope = _near_limit_envelope(receipt)
    if envelope is not None:
        template = _NEAR_LIMIT_DIRECT if tone == "direct" else _NEAR_LIMIT_ENCOURAGING
        return template.format(env=envelope)
    if _SHORTFALL_MARKER in purchase_verdict_text(receipt):
        return _SHORTFALL_DIRECT if tone == "direct" else _SHORTFALL_ENCOURAGING
    return None


def user_warnings(result: JsonDocument) -> list[str]:
    pieces: list[str] = []
    warnings = result.root.get("warnings")
    if isinstance(warnings, list):
        for warning in warnings:
            if isinstance(warning, dict) and warning.get("severity") == "user":
                detail = warning.get("detail")
                if isinstance(detail, str):
                    pieces.append(detail)
    return pieces
