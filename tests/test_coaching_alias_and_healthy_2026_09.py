# ruff: noqa: INP001
"""Two coaching-quality improvements, guards unchanged.

#1 Counseling-shaped questions now match EXISTING approved concepts (via added
   aliases only) and reach the model finance-selection path (source=llm), instead
   of falling through to review->template. The volatile/decision carve-out block
   is unchanged: live-rate and purchase-decision questions still never reach it.
#2 A lowest-precedence healthy/surplus branch in ``deterministic_advice`` fires
   only on the engine's own high ``remaining_percent`` fact, is digit-free, and
   never disturbs the over-budget > near-limit > shortfall precedence.
"""

from __future__ import annotations

import pytest

from coaching_service.finance_knowledge import (
    deterministic_finance_status,
    deterministic_finance_wording,
    finance_evidence,
    model_selected_finance_evidence,
)
from coaching_service.knowledge_retrieval import retrieve_facts
from coaching_service.rendering import deterministic_advice
from coaching_service.schemas import Receipt

# ---------------------------------------------------------------------------
# #1 alias-driven counseling questions reach the model finance-selection path
# ---------------------------------------------------------------------------

_ALIAS_QUESTIONS = [
    ("지출 줄이기", "budget"),
    ("소비 습관 점검", "budget"),
    ("예산 세우기", "budget"),
    ("저축 늘리기", "budget"),
    ("빚 갚는 순서", "debt_repayment_methods"),
    ("목돈 모으기", "deposits"),
    ("비상금 모으기", "emergency_fund"),
]


@pytest.mark.parametrize(("question", "concept"), _ALIAS_QUESTIONS)
def test_counseling_question_reaches_model_finance_selection(question: str, concept: str) -> None:
    # The added alias makes the question retrieve the intended approved concept.
    assert concept in {fact.id for fact in retrieve_facts(question)}
    evidence = finance_evidence(question)
    # It is not an exact catalog definition, so no deterministic template answer,
    # and it is not a live-rate/tax status question either.
    assert deterministic_finance_wording(evidence) is None
    assert deterministic_finance_status(evidence) is None
    # It therefore reaches the bounded model finance-selection path (source=llm),
    # not the review->template fallback.
    assert model_selected_finance_evidence(evidence) is not None


@pytest.mark.parametrize(
    "question",
    [
        "지금 예금 금리 얼마야?",
        "대출을 받을까 말까?",
        "오늘 가장 높은 적금 금리 추천해줘",
    ],
)
def test_alias_expansion_does_not_open_the_volatile_block(question: str) -> None:
    # Aliases must never let a volatile/decision question bypass the block: it
    # stays out of both the deterministic template and the model finance path.
    evidence = finance_evidence(question)
    assert deterministic_finance_wording(evidence) is None
    assert model_selected_finance_evidence(evidence) is None


# The seven conversational example phrasings that must all reach finance
# selection (deterministic catalog template OR bounded model fact-selection),
# never the review->template fallback. "지출 줄이는 법 알려줘" and "저축 늘리려면"
# are the two the added "지출 줄이"/"저축 늘리" stem aliases rescue.
_REACHES_FINANCE = [
    "지출 줄이는 법 알려줘",
    "소비 습관 어떻게 고쳐",
    "예산 어떻게 세워",
    "저축 늘리려면",
    "빚 갚는 순서",
    "비상금 모으기",
    "목돈 모으기",
]


@pytest.mark.parametrize("question", _REACHES_FINANCE)
def test_example_counseling_phrasing_reaches_finance(question: str) -> None:
    evidence = finance_evidence(question)
    # "reaches finance" = any of the three finance selection paths accepts it:
    # a deterministic catalog answer, a deterministic data/source boundary, or
    # the bounded model fact-selection input. None of these is the review route.
    reaches = (
        deterministic_finance_wording(evidence) is not None
        or deterministic_finance_status(evidence) is not None
        or model_selected_finance_evidence(evidence) is not None
    )
    assert reaches


def test_stem_aliased_conjugations_reach_the_model_finance_path() -> None:
    # The two previously-failing conjugations now retrieve budget via the stem
    # aliases and, being neither an exact definition nor a live-rate/tax status,
    # reach the bounded model fact-selection path (source=llm).
    for question in ("저축 늘리려면", "저축 늘리는", "저축 늘리기"):
        assert "budget" in {fact.id for fact in retrieve_facts(question)}
    savings = finance_evidence("저축 늘리려면")
    assert model_selected_finance_evidence(savings) is not None


# Regression pin: genuine personal-ledger lookups must NOT be answered by the
# general-concept finance shortcut. ``_PERSONAL_DATA_LOOKUP`` was deliberately
# left UNCHANGED (not narrowed), so these still decline the finance shortcut and
# fall to the personal/FDT route as before.
@pytest.mark.parametrize(
    "question",
    [
        "내 지출 얼마야",
        "이번 달 지출 알려줘",
        "계좌 잔액 알려줘",
        "남은 예산 얼마야",
    ],
)
def test_personal_ledger_lookups_still_decline_the_finance_shortcut(question: str) -> None:
    evidence = finance_evidence(question)
    assert model_selected_finance_evidence(evidence) is None
    assert deterministic_finance_wording(evidence) is None


# ---------------------------------------------------------------------------
# #2 lowest-precedence healthy/surplus advice branch (fact-gated, digit-free)
# ---------------------------------------------------------------------------


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
            "amount_krw": 1000,
            "balance_before_krw": 50000,
            "balance_after_krw": 49000,
            "remaining_percent": remaining_percent,
            "weekly_count": 1,
        }
    )


def _shortfall_receipt() -> Receipt:
    return _base_receipt(
        request={
            "on_date": "2026-09-21",
            "through_date": "2026-09-28",
            "changes": [{"kind": "expense", "envelope": "쇼핑", "amount_krw": 200000}],
        },
        result={
            "comparison": {
                "baseline": {"cash": {"period_account_shortfall": {"fraction": 0}}},
                "planned": {
                    "cash": {
                        "period_account_shortfall": {"fraction": 0.3},
                        "terminal_balance": {"p50_krw": 50000},
                    }
                },
            }
        },
    )


def test_healthy_surplus_branch_fires_only_on_the_surplus_fact() -> None:
    advice = deterministic_advice(_payment_receipt("90"))
    assert advice is not None
    assert "외식" in advice
    assert not any(char.isdigit() for char in advice)


def test_healthy_branch_requires_the_surplus_fact_to_be_present() -> None:
    # No payment fact at all -> no surplus signal -> no advice (not every account).
    assert deterministic_advice(_base_receipt()) is None


def test_healthy_band_lower_boundary_is_inclusive_and_moderate_is_silent() -> None:
    assert deterministic_advice(_payment_receipt("80")) is not None
    assert deterministic_advice(_payment_receipt("79")) is None
    assert deterministic_advice(_payment_receipt("50")) is None


def test_healthy_branch_never_overrides_over_budget_near_limit_or_shortfall() -> None:
    over_budget = deterministic_advice(_payment_receipt("0"))
    near_limit = deterministic_advice(_payment_receipt("8"))
    healthy = deterministic_advice(_payment_receipt("90"))
    assert over_budget is not None
    assert near_limit is not None
    assert healthy is not None
    assert len({over_budget, near_limit, healthy}) == 3
    # Shortfall still wins over the healthy branch when both could be read.
    assert deterministic_advice(_shortfall_receipt()) == deterministic_advice(
        _shortfall_receipt(), tone="encouraging"
    )
    assert "부족" in deterministic_advice(_shortfall_receipt())


def test_healthy_branch_tone_variants_are_distinct_and_digit_free() -> None:
    encouraging = deterministic_advice(_payment_receipt("90"), tone="encouraging")
    direct = deterministic_advice(_payment_receipt("90"), tone="direct")
    default = deterministic_advice(_payment_receipt("90"))
    assert encouraging is not None
    assert direct is not None
    assert encouraging != direct
    assert default == encouraging
    for text in (encouraging, direct):
        assert "외식" in text
        assert not any(char.isdigit() for char in text)


# ---------------------------------------------------------------------------
# #2b advice on a requested_review receipt (no payment fact) via the review
# engine's own observed-budget remaining, using the identical bands, digit-free.
# ---------------------------------------------------------------------------

_OBSERVED_BASIS = "approved_snapshot_budget_minus_observed_budgeted_spending"


def _observed_row(envelope: str, budget: int, remaining: int) -> dict[str, object]:
    return {
        "envelope": envelope,
        "budget_krw": budget,
        "observed_used_krw": budget - remaining,
        "observed_remaining_krw": remaining,
        "as_of": "2026-09-21",
        "basis": _OBSERVED_BASIS,
    }


def _review_receipt(
    rows: list[dict[str, object]],
    *,
    warnings: list[dict[str, object]] | None = None,
    status: str = "ready",
) -> Receipt:
    result: dict[str, object] = {"status": status, "observed_budgets": rows}
    if warnings is not None:
        result["warnings"] = warnings
    return _base_receipt(result=result)


def test_review_healthy_surplus_advice_fires_from_observed_budget_remaining() -> None:
    advice = deterministic_advice(_review_receipt([_observed_row("외식", 100000, 90000)]))
    assert advice is not None
    assert "외식" in advice
    assert not any(char.isdigit() for char in advice)


def test_review_observed_bands_match_the_payment_thresholds() -> None:
    # over-budget <= 0, near-limit 0 < x <= 10, healthy >= 80, moderate is silent.
    assert "넘고" in deterministic_advice(_review_receipt([_observed_row("외식", 100000, 0)]))
    assert "얼마 남지" in deterministic_advice(
        _review_receipt([_observed_row("외식", 100000, 10000)]), tone="direct"
    )
    assert "여유" in deterministic_advice(_review_receipt([_observed_row("외식", 100000, 80000)]))
    assert deterministic_advice(_review_receipt([_observed_row("외식", 100000, 79000)])) is None
    assert deterministic_advice(_review_receipt([_observed_row("외식", 100000, 50000)])) is None


def test_review_over_budget_outranks_a_healthy_envelope() -> None:
    advice = deterministic_advice(
        _review_receipt([_observed_row("외식", 100000, 90000), _observed_row("쇼핑", 100000, -1)])
    )
    assert advice is not None
    assert "쇼핑" in advice
    assert "외식" not in advice


def test_review_advice_is_fact_gated_and_never_fabricated() -> None:
    # No observed-budget fact at all -> no advice.
    assert deterministic_advice(_base_receipt()) is None
    # Engine flags its own budget input incomplete -> the remaining is untrusted.
    assert (
        deterministic_advice(
            _review_receipt(
                [_observed_row("외식", 100000, 90000)],
                warnings=[{"code": "BUDGET_INPUT_INCOMPLETE", "severity": "user", "detail": "x"}],
            )
        )
        is None
    )
    # A row with a foreign basis or a non-positive budget is ignored, not guessed.
    assert (
        deterministic_advice(
            _review_receipt([{"envelope": "외식", "budget_krw": 100000, "observed_remaining_krw": 90000}])
        )
        is None
    )
    assert deterministic_advice(_review_receipt([_observed_row("외식", 0, 0)])) is None
    # A review the engine still marks needs_data (stale/dirty snapshot) is not a
    # trustworthy basis for a spending nudge even though it lists observed budgets.
    assert (
        deterministic_advice(
            _review_receipt([_observed_row("외식", 100000, 90000)], status="needs_data")
        )
        is None
    )


def test_payment_receipt_advice_is_unchanged_by_the_review_path() -> None:
    # A payment-event receipt keeps its single-envelope payment path even when a
    # (production) review result with observed budgets is also present.
    receipt = _payment_receipt("50").model_copy(
        update={"result": _review_receipt([_observed_row("쇼핑", 100000, 90000)]).result}
    )
    # payment 50% is moderate -> no advice, and the observed healthy 쇼핑 envelope
    # must NOT leak into a payment receipt's advice.
    assert deterministic_advice(receipt) is None
