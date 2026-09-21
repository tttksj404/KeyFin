# ruff: noqa: INP001
"""Graduated balance-band advice: near-limit sits strictly between healthy and over-budget.

Precedence per envelope is over-budget > near-limit > shortfall -- only one
sentence ever fires. All assertions here use ``deterministic_advice`` directly
(no model call) and confirm the near-limit sentence never contains a digit.
"""

from __future__ import annotations

from coaching_service.rendering import deterministic_advice
from coaching_service.schemas import Receipt


def _base_receipt(**overrides: object) -> Receipt:
    payload: dict[str, object] = {
        "engine_commit": "pinned-engine",
        "identity": {
            "user_id": "user",
            "twin_id": "twin",
            "revision": 1,
            "input_digest": "digest",
            "as_of": "2026-09-21",
        },
        "request": {"on_date": "2026-09-21", "through_date": "2026-09-28"},
        "result": {},
        "trigger": "requested_review",
    }
    payload.update(overrides)
    return Receipt.model_validate(payload)


def _payment_receipt(remaining_percent: str) -> Receipt:
    return _base_receipt(
        payment={
            "transaction_id": "t1",
            "envelope": "외식",
            "amount_krw": 10000,
            "balance_before_krw": 5000,
            "balance_after_krw": 1000,
            "remaining_percent": remaining_percent,
            "weekly_count": 3,
        }
    )


def test_near_limit_band_fires_at_low_positive_remaining_percent() -> None:
    advice = deterministic_advice(_payment_receipt("8"))
    assert advice is not None
    assert "외식" in advice
    assert not any(char.isdigit() for char in advice)


def test_healthy_remaining_percent_fires_nothing() -> None:
    assert deterministic_advice(_payment_receipt("60")) is None


def test_over_budget_takes_precedence_over_near_limit_at_zero() -> None:
    over_budget = deterministic_advice(_payment_receipt("0"))
    near_limit = deterministic_advice(_payment_receipt("8"))
    assert over_budget is not None
    assert over_budget != near_limit
    # Over-budget wording differs from near-limit wording for the same tone.
    assert deterministic_advice(_payment_receipt("0"), tone="direct") != deterministic_advice(
        _payment_receipt("8"), tone="direct"
    )


def test_over_budget_takes_precedence_over_near_limit_when_negative() -> None:
    advice = deterministic_advice(_payment_receipt("-5"))
    assert advice is not None
    # Negative remaining is over-budget territory, not near-limit.
    assert advice == deterministic_advice(_payment_receipt("0"))


def test_near_limit_boundary_is_inclusive_of_ten_and_exclusive_of_zero() -> None:
    assert deterministic_advice(_payment_receipt("10")) is not None
    assert deterministic_advice(_payment_receipt("11")) is None


def test_near_limit_tone_differences() -> None:
    encouraging = deterministic_advice(_payment_receipt("8"), tone="encouraging")
    direct = deterministic_advice(_payment_receipt("8"), tone="direct")
    default = deterministic_advice(_payment_receipt("8"))
    assert encouraging is not None
    assert direct is not None
    assert encouraging != direct
    assert default == encouraging
    for text in (encouraging, direct):
        assert "외식" in text
        assert not any(char.isdigit() for char in text)
