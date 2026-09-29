# ruff: noqa: INP001
"""Intents the second 2026-09-28 sweep found answered against the coaching contract.

About 3,000 new questions and 159 flows ran through the in-process API, and the real
Qwen3.8-27B router named a mode for every one of them. Its mode was then replayed through
the whole pipeline. Own-budget lookups ("교통비 예산 상황?", "자산 얼마?") got a concept
card; another person's money ("엄마 카드값 많이 나왔대") got the user's own review; a home
("이 아파트 지금 사도 될까") was asked its price; product advice and market outlooks got the
"connect your data" status; and "9월 말" or "이번 달 기타는?" were not read at all.
Each case names the router's mode, so the answer must hold whatever the model picks.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

import pytest
from test_intent_routing_2026_09_26 import _conversation, _family, _Mode

from coaching_service.fast_routes import (
    finance_advice_decision,
    is_bare_purchase_fragment,
    real_estate_trade,
    states_purchase,
    third_party_money,
)
from coaching_service.finance_knowledge import deterministic_finance_status, finance_evidence
from coaching_service.period_request import named_calendar
from coaching_service.personal_query import intent_personal_topic

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
@pytest.mark.parametrize(("mode", "question", "family"), [
    # the user's own budget or data is looked up, never answered with a concept card
    ("balance", "교통비 예산 상황?", "balance"),
    ("balance", "외식 예산 다 썼어?", "balance"),
    ("balance", "예산 관리가 잘되고 있어?", "balance"),
    ("personal", "자산 얼마?", "personal"),
    ("personal", "다음 결제일 언제인지 봐줄래?", "personal"),
    # a concept ask still takes the catalog, bare or paraphrased
    ("other", "복리가 뭐야?", "concept"),
    ("other", "ETF?", "concept"),
    ("other", "예산이 뭐야?", "concept"),
    ("finance", "금리 인상되면 채권 가격 떨어질까?", "concept"),
    # another person's money is not the user's review
    ("review", "엄마 카드값 많이 나왔대", "fin_out_of_scope"),
    ("review", "형이 적자래", "fin_out_of_scope"),
    ("history", "아빠 용돈 얼마 쓰는지 알려줄 수 있어?", "fin_out_of_scope"),
    ("review", "동생 용돈 10만원 주면 이번 달 괜찮아?", "review"),
    ("other", "친구 돈 관리 좀 봐줄 수 있어?", "fin_out_of_scope"),
    # judging or changing the user's own spending is not a concept card
    ("review", "소비 습관이 건강해?", "review"),
    ("review", "요즘 예산 관리 잘 되고 있는지 궁금해", "review"),
    ("what_if", "선택지출을 전부 삭제하면?", "period_review"),
    # a recommendation is not a purchase missing its price
    ("other", "여행 어디로 가면 좋을지 추천해줘", "out_of_scope"),
    # a purchase with its price and payment is judged, not turned into a balance
    ("purchase", "피자 할부 가능?", "purchase_clarify"),
    ("purchase", "선글라스를 온라인으로 주문해도 괜찮아?", "purchase_clarify"),
    # a home is not a purchase check; advice and outlooks are declined, tax amounts need terms
    ("purchase", "이 아파트 지금 사도 될까", "fin_out_of_scope"),
    ("finance", "집 살까?", "fin_out_of_scope"),
    ("purchase", "차를 살까?", "purchase_clarify"),
    ("finance", "비트코인 앞으로 올라갈까?", "fin_out_of_scope"),
    ("finance", "종신보험 가입해야 할까", "fin_out_of_scope"),
    ("finance", "이 코인 단타 쳐도 될까", "fin_out_of_scope"),
    ("finance", "XRP 지금 사도 될까요?", "fin_out_of_scope"),
    ("finance", "연말정산 얼마 돌려받아?", "fin_needs_source"),
    ("personal", "종합소득세 얼마 나올지 궁금해", "fin_needs_source"),
    # an envelope named with nothing bought is its balance
    ("purchase", "편의점·마트 봉투는?", "balance"),
    # a numbered month is this or the next month; a part of a month is asked again
    ("review", "9월 말에 얼마가 남을 것 같아?", "numeric:forecast"),
    ("review", "10월 말에 얼마 남을까?", "numeric:forecast"),
    ("review", "10월 초에 돈 남아?", "period_review"),
])
async def test_the_answer_keeps_the_intent_whatever_the_router_names(
    tmp_path: Path, mode: str, question: str, family: str,
) -> None:
    answers = await _conversation(tmp_path, (question,), one_session=True, router=_Mode(mode))
    assert _family(answers[-1]) == family, answers[-1].get("text")


@pytest.mark.anyio
@pytest.mark.parametrize(("mode", "turns", "family"), [
    # a question of its own is not merged into the pending purchase
    ("other", ("노트북 사려는데 괜찮아?", "영화 평점?"), "out_of_scope"),
    # an envelope name answers the envelope the purchase belongs to
    ("purchase", ("전기포트 3만원 오늘 현금으로 사도 될까?", "쇼핑이요"), "purchase"),
    # a period with an envelope continues the spending lookup
    ("review", ("이번 달 외식 얼마 썼어?", "이번 달 기타는?"), "history"),
    ("other", ("이번 달 외식 얼마 썼어?", "지난달 쇼핑은?"), "history"),
    # a lookup read in its canonical form is continued like any other
    ("history", ("지난달 외식비 총액 좀 알려줘", "이번 달 거는 어때?"), "history"),
    # another asset keeps the buy or sell decision just declined
    ("finance", ("비트코인 지금 사도 될까?", "그럼 이더리움은?"), "fin_out_of_scope"),
])
async def test_follow_ups_keep_their_intent(
    tmp_path: Path, mode: str, turns: tuple[str, ...], family: str,
) -> None:
    answers = await _conversation(tmp_path, turns, one_session=True, router=_Mode(mode))
    assert _family(answers[-1]) == family, answers[-1].get("text")


@pytest.mark.anyio
async def test_a_corrected_amount_replaces_the_pending_one(tmp_path: Path) -> None:
    answers = await _conversation(
        tmp_path, ("노트북 150만원 오늘 현금으로 사도 돼?", "150만원 말고 100만원"),
        one_session=True, router=_Mode("other"),
    )
    assert answers[-1]["receipt"]["request"]["changes"][0]["amount_krw"] == 1_000_000


@pytest.mark.anyio
async def test_a_purchase_date_outside_the_period_is_asked_again(tmp_path: Path) -> None:
    answers = await _conversation(
        tmp_path, ("노트북 150만원 2026-12-01 현금으로 사도 돼?",), one_session=True, router=_Mode("other"),
    )
    assert _family(answers[-1]) == "purchase_clarify"
    assert "기간 밖" in answers[-1]["text"]


@pytest.mark.parametrize(("question", "expected"), [
    ("엄마가 저축 안 한대 어떡하지", True),
    ("남자친구가 돈을 너무 써", True),
    ("엄마 생일 선물 5만원 사도 될까?", False),
    ("친구랑 밥 먹는데 3만원 써도 돼?", False),
    ("엄마한테 용돈 드렸어", False),
    ("딸 학원비 예산 얼마 남았어?", False),
])
def test_another_persons_money_is_told_from_the_users_own(question: str, *, expected: bool) -> None:
    assert third_party_money(question) is expected


@pytest.mark.parametrize(("question", "expected"), [
    ("땅 사도 될까?", True),
    ("집들이 선물 사도 돼?", False),
    ("아파트 인테리어 소품 사도 될까?", False),
    ("집에서 쓸 전자레인지 사도 돼?", False),
    ("주택청약이 뭐야?", False),
])
def test_a_home_trade_is_told_from_a_purchase_for_the_home(question: str, *, expected: bool) -> None:
    assert real_estate_trade(question) is expected


@pytest.mark.parametrize(("question", "expected"), [
    ("퇴직연금 어디로 옮기는 게 좋아", True),
    ("이 회사 주식 전망 어때", True),
    ("ETF 전망이 뭐야?", False),
    ("적금이랑 예금 중 뭐가 나아?", False),
    ("복리 계산 방법 알려줘", False),
])
def test_product_advice_and_outlooks_are_told_from_concepts(question: str, *, expected: bool) -> None:
    assert finance_advice_decision(question) is expected


def test_a_tax_amount_is_a_source_gap_and_own_income_is_not() -> None:
    for question in ("상속세 계산 좀 해줄래?", "주식 양도소득세 얼마나 나오는지 궁금해"):
        status = deterministic_finance_status(finance_evidence(question))
        assert status is not None
        assert status.answer_status == "needs_source"
    assert deterministic_finance_status(finance_evidence("내 소득 얼마야?")) is None


def test_a_purchase_needs_words_of_its_own() -> None:
    assert not states_purchase("외식은?")
    assert states_purchase("차를 살까?")
    assert states_purchase("노트북 150만원")
    assert not is_bare_purchase_fragment("책 소개?")
    assert is_bare_purchase_fragment("영화요")


def test_a_personal_lookup_names_its_topic() -> None:
    assert intent_personal_topic("다음 결제일 언제야?") == "payments"
    assert intent_personal_topic("자산 얼마?") == "assets"
    assert intent_personal_topic("카드 잔액 얼마야?") is None


def test_numbered_months_and_days_are_read_against_the_reference() -> None:
    reference = date(2026, 9, 10)
    assert named_calendar("9월 말에 얼마 남아?", reference) == "이번 달 말에 얼마 남아?"
    assert named_calendar("10월에 얼마 남아?", reference) == "다음 달에 얼마 남아?"
    assert named_calendar("12월 말까지", reference) == "12월 말까지"
    assert named_calendar("9월 30일까지", reference) == "2026-09-30까지"
    assert named_calendar("9월 말까지", reference, budget_start_day=25) == "2026-09-30까지"
    assert named_calendar("9월 말 잔액", reference, budget_start_day=25) == "2026-09-30까지 잔액"
    assert named_calendar("9월에", reference, budget_start_day=25) == "9월에"
