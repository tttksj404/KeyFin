# ruff: noqa: INP001
"""Five SAFE coaching improvements: deterministic advice, tone, multi-item personal
query, emergency-fund concept enrichment, and a tighter numeric-free write prompt.

None of these tests touch ``wording_problem`` directly; they only exercise
deterministic templates and routing that never pass through the LLM guard.
A separate assertion below pins ``wording_problem`` behavior unchanged.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest

from coaching_service.finance_knowledge import deterministic_finance_wording, finance_evidence
from coaching_service.knowledge_catalog import load_catalog
from coaching_service.llm_prompt import _WRITE, wording_problem
from coaching_service.payments import Ledger
from coaching_service.personal_query import select_personal_topic, select_personal_topics
from coaching_service.personal_service import personal_summary
from coaching_service.rendering import deterministic_advice
from coaching_service.repository import Repository
from coaching_service.schemas import Envelope, Receipt
from coaching_service.store import Store

if TYPE_CHECKING:
    from pathlib import Path

# ---------------------------------------------------------------------------
# HARD CONSTRAINT regression pin: wording_problem() must keep every guard.
# ---------------------------------------------------------------------------


def test_wording_problem_guards_are_unchanged() -> None:
    assert wording_problem("금액은 5만원입니다.") == "numeric_output"
    assert wording_problem("절반으로 줄여보세요.") == "numeric_output"
    assert wording_problem("이번 달 외식비가 예산을 초과했습니다.") == "unsupported_claim"
    assert wording_problem("결제를 완료했어요.") == "unsupported_action"
    assert wording_problem('그는 "괜찮다"고 말했다.') == "unsupported_quote"
    assert wording_problem("앞으로 지출 계획에서 신경 쓰이는 부분을 알려 주세요.") is None


def test_write_prompt_still_forbids_every_numeric_form() -> None:
    # #2 prompt elaboration was reverted (real-model A/B showed it increased
    # numeric_output fallbacks); the write prompt keeps its baseline no-numbers
    # constraint and the guard (tested above) is what actually rejects quantities.
    assert "숫자" in _WRITE
    assert "수량" in _WRITE
    assert "실행 완료" in _WRITE


# ---------------------------------------------------------------------------
# #1 deterministic advice + #4 tone
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


def _over_budget_receipt() -> Receipt:
    return _base_receipt(
        payment={
            "transaction_id": "t1",
            "envelope": "외식",
            "amount_krw": 10000,
            "balance_before_krw": 5000,
            "balance_after_krw": -5000,
            "remaining_percent": "0",
            "weekly_count": 3,
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


def _healthy_receipt() -> Receipt:
    return _base_receipt(current_envelopes=(Envelope(envelope="외식", balance_krw=30000),))


def test_over_budget_envelope_triggers_named_advice_via_remaining_percent() -> None:
    advice = deterministic_advice(_over_budget_receipt())
    assert advice is not None
    assert "외식" in advice
    assert not any(char.isdigit() for char in advice)


def test_over_budget_envelope_triggers_named_advice_via_negative_ledger_balance() -> None:
    receipt = _base_receipt(current_envelopes=(Envelope(envelope="쇼핑", balance_krw=-1500),))
    advice = deterministic_advice(receipt)
    assert advice is not None
    assert "쇼핑" in advice


def test_forecast_shortfall_triggers_generic_advice() -> None:
    advice = deterministic_advice(_shortfall_receipt())
    assert advice is not None
    assert "부족" in advice
    assert not any(char.isdigit() for char in advice)


def test_healthy_receipt_has_no_advice() -> None:
    assert deterministic_advice(_healthy_receipt()) is None
    assert deterministic_advice(_base_receipt()) is None


def test_tone_selects_direct_or_encouraging_wording_without_changing_trigger() -> None:
    receipt = _over_budget_receipt()
    encouraging = deterministic_advice(receipt, tone="encouraging")
    direct = deterministic_advice(receipt, tone="direct")
    default = deterministic_advice(receipt)
    assert encouraging != direct
    assert default == encouraging
    assert "외식" in direct
    assert "외식" in encouraging
    for text in (encouraging, direct):
        assert not any(char.isdigit() for char in text)

    shortfall = _shortfall_receipt()
    assert deterministic_advice(shortfall, tone="direct") != deterministic_advice(
        shortfall, tone="encouraging"
    )


# ---------------------------------------------------------------------------
# #3a multi-item personal query
# ---------------------------------------------------------------------------


def test_compound_question_resolves_both_recognized_topics() -> None:
    topics = select_personal_topics("계좌 잔액이랑 자산 알려줘")
    assert topics == ("accounts", "assets")


def test_compound_question_with_one_unsupported_fragment_still_resolves_known_topic() -> None:
    # "남은 예산" is now a supported topic ("budget"), so this compound question
    # resolves both fragments instead of dropping the budget half.
    topics = select_personal_topics("지금 계좌 잔액이랑 남은 예산 알려줘")
    assert topics == ("accounts", "budget")


def test_compound_question_with_a_genuinely_unsupported_fragment_still_drops_it() -> None:
    topics = select_personal_topics("계좌 잔액이랑 국민은행 알려줘")
    assert topics == ("accounts",)


def test_single_topic_question_is_untouched_by_the_multi_parser() -> None:
    # select_personal_topic still owns single-topic questions; the multi-topic
    # helper must defer instead of double-answering.
    assert select_personal_topic("내 계좌 잔액 알려줘") == "accounts"
    assert select_personal_topics("내 계좌 잔액 알려줘") == ()


def test_comparison_language_still_falls_back_like_the_existing_single_topic_guard() -> None:
    # Mirrors test_personal_summary.test_unsupported_filter_is_not_silently_dropped:
    # "내 자산과 부채 비교해줘" must not become a silent side-by-side answer either.
    assert select_personal_topic("내 자산과 부채 비교해줘") is None
    assert select_personal_topics("내 자산과 부채 비교해줘") == ()


# ---------------------------------------------------------------------------
# #3b emergency_fund concept enrichment (no fabricated numbers)
# ---------------------------------------------------------------------------


def test_emergency_fund_amount_question_now_resolves_without_a_model() -> None:
    evidence = finance_evidence("비상금은 얼마가 적당해?")
    wording = deterministic_finance_wording(evidence)
    assert wording is not None
    assert wording.answer_status == "answered"
    assert wording.reference_ids == ("emergency_fund",)
    assert "소득" in wording.text
    assert "고정지출" in wording.text
    # No fabricated figures anywhere in the catalog-derived answer.
    assert not re.search(r"\d", wording.text)


def test_emergency_fund_answer_still_has_no_digits_in_source_text() -> None:
    fact = next(fact for fact in load_catalog().facts if fact.id == "emergency_fund")
    assert not re.search(r"\d", fact.text)


def test_other_volatile_or_decision_requests_are_still_blocked() -> None:
    # The narrow emergency-fund carve-out must not loosen the general guard:
    # a live-rate or purchase-decision question still needs the model/FDT path.
    evidence = finance_evidence("지금 예금 금리 얼마야?")
    assert deterministic_finance_wording(evidence) is None
    evidence = finance_evidence("대출을 받을까 말까?")
    assert deterministic_finance_wording(evidence) is None


# ---------------------------------------------------------------------------
# #6 "budget" (봉투 예산 잔액) topic added to the personal-query path
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "question",
    [
        "이번 달 예산 얼마 남았어?",
        "남은 예산 알려줘",
        "봉투 예산 알려줘",
        "봉투 잔액 알려줘",
    ],
)
def test_budget_single_topic_question_is_recognized(question: str) -> None:
    assert select_personal_topic(question) == "budget"


def test_existing_single_topic_grammar_is_unaffected_by_the_budget_alias() -> None:
    # Regression pin: unrelated single-topic questions still resolve exactly as before.
    assert select_personal_topic("내 계좌 잔액 알려줘") == "accounts"
    assert select_personal_topic("내 자산 알려줘") == "assets"
    assert select_personal_topic("내 월 소득이 얼마야") == "income"
    assert select_personal_topic("내 보험료는?") == "insurance"
    assert select_personal_topic("예정 결제 알려주세요") == "payments"
    assert select_personal_topic("내 자산과 부채 비교해줘") is None


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _ledger_json() -> str:
    return Ledger(
        envelopes=(Envelope(envelope="식비", balance_krw=15000), Envelope(envelope="교통", balance_krw=5000))
    ).model_dump_json()


def _twin_json() -> str:
    return (
        '{"as_of": "2026-09-03", "snapshot": {"as_of": "2026-09-03", "source": "USER_ASSUMPTION", '
        '"accounts": [{"account_id": "cash", "balance_krw": 1000000}], "cards": []}}'
    )


def _seeded_repository(tmp_path: Path, *, ledger: str | None, twin: str | None) -> Repository:
    store = Store(tmp_path / "personal.sqlite3")
    with store.connection() as connection:
        if ledger is not None:
            _ = connection.execute(
                "INSERT INTO items VALUES(?,?,?)", ("owner", "ledger", ledger)
            )
        if twin is not None:
            _ = connection.execute("INSERT INTO items VALUES(?,?,?)", ("owner", "twin", twin))
    return Repository(store)


@pytest.mark.anyio
async def test_budget_single_topic_answers_with_envelope_rows_and_total(tmp_path: Path) -> None:
    repository = _seeded_repository(tmp_path, ledger=_ledger_json(), twin=None)
    summary = await personal_summary(repository, "owner", "남은 예산 알려줘")
    assert summary.status == "answered"
    assert summary.total_krw == 20000
    assert {row.label: row.amount_krw for row in summary.rows} == {"식비": 15000, "교통": 5000}
    # No fabricated digits: every number in the text traces back to the ledger rows.
    assert "20,000" in summary.text
    assert "15,000" in summary.text
    assert "5,000" in summary.text


@pytest.mark.anyio
async def test_budget_topic_missing_ledger_is_graceful(tmp_path: Path) -> None:
    repository = _seeded_repository(tmp_path, ledger=None, twin=None)
    summary = await personal_summary(repository, "owner", "남은 예산 알려줘")
    assert summary.status == "needs_data"
    assert summary.rows == ()


@pytest.mark.anyio
async def test_compound_accounts_and_budget_question_answers_both(tmp_path: Path) -> None:
    repository = _seeded_repository(tmp_path, ledger=_ledger_json(), twin=_twin_json())
    summary = await personal_summary(repository, "owner", "계좌 잔액이랑 남은 예산 알려줘")
    assert summary.status == "answered"
    # Accounts half: the FDT-reported cash balance shows up.
    assert "1,000,000" in summary.text
    # Budget half: the envelope balances and total show up.
    assert "식비" in summary.text
    assert "20,000" in summary.text
    # The old "미지원/코칭 리뷰에서 확인" redirect must not fire now that budget is supported.
    assert "코칭 리뷰" not in summary.text
    assert "지원" not in summary.text


@pytest.mark.anyio
async def test_compound_question_with_a_genuinely_unknown_fragment_still_gets_the_note(
    tmp_path: Path,
) -> None:
    repository = _seeded_repository(tmp_path, ledger=_ledger_json(), twin=_twin_json())
    summary = await personal_summary(repository, "owner", "계좌 잔액이랑 국민은행 알려줘")
    assert summary.status == "answered"
    assert "1,000,000" in summary.text
    assert "이 조회로는 답하지 않습니다" in summary.text
