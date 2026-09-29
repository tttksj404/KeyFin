# ruff: noqa: INP001
"""Styles and follow-ups the 2026-09-28 sweep found answered against their intent.

A new corpus of about 2,200 questions (casual speech, typos, polite long sentences,
hedged conditionals, varied amount and date forms, very short and English-mixed
questions) and 62 multi-turn flows ran under 9 conversation contexts and 8 router
answers. Short follow-ups ("외식은?", "위험은 어때?", "150만원이면?") had no subject of
their own and fell to the router; everyday forms ("사려는데 괜찮을까?", "사는 건?",
"지금", "쇼핑 봉투는 얼마야?", "외식 20% 줄이면?", "적자 날 수 있어?", "보여줄래")
missed the grammar; and the catalog shortcut answered "예산 상태 체크해줄래?" or
"아니다 됐어" with a concept card. The router here answers "other" or "review" on
purpose, so each answer must come from the grammar itself.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from test_intent_routing_2026_09_26 import _conversation, _family, _Mode

from coaching_service.dialogue import _own_state_question
from coaching_service.fast_routes import (
    NaturalPurchase,
    balance_check_question,
    canonical_question,
    contextual_followup,
    deterministic_analysis_route,
    natural_goal,
    natural_purchase,
    natural_what_if,
    with_bare_won,
    with_won_units,
)
from coaching_service.spending_history import supports_spending_question

if TYPE_CHECKING:
    from pathlib import Path

_VERDICT = "300만원 노트북 오늘 현금으로 사도 돼?"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
@pytest.mark.parametrize(("mode", "turns", "family"), [
    # a pending purchase is completed by bare answers, a restated verb included
    ("other", ("노트북 사려는데 괜찮아?", "150만원", "현금으로 오늘"), "purchase"),
    ("review", ("노트북 사려는데 괜찮아?", "150만원이고 현금으로 오늘 살 거야"), "purchase"),
    ("other", ("치킨 시켜도 돼?", "2만원", "지금 체크카드로"), "purchase"),
    # short follow-ups lean on the previous question
    ("other", ("봉투 잔액 보여줘", "외식은?"), "balance"),
    ("review", ("이번 달 교통비 얼마 썼어?", "외식은?"), "history"),
    ("other", ("월말 잔액 얼마 남을까", "위험은 어때?"), "numeric:risk"),
    ("other", (_VERDICT, "150만원이면?"), "purchase"),
    ("other", (_VERDICT, "그럼 150만원짜리는?"), "purchase"),
    ("other", ("지난달 쇼핑 얼마 썼어?", "그럼 이번달은"), "history"),
    ("other", ("복리가 뭐야?", "적금은?"), "concept"),
    # an unsupported period is asked for, and the bare answer completes it
    ("other", ("다음주까지 예산 괜찮아?",), "period_review"),
    ("other", ("다음주까지 예산 괜찮아?", "이번 달"), "balance"),
    # a question of its own is never rewritten from the previous one
    ("other", ("봉투 잔액 보여줘", "복리가 뭐야?"), "concept"),
    ("other", ("복리가 뭐야?", "예산 잔액 좀 보여줘"), "balance"),
    ("other", ("복리가 뭐야?", "쇼핑 예산 얼마나 남았어?"), "balance"),
    ("other", ("노트북 사려는데 괜찮아?", "내일 비 와?"), "out_of_scope"),
    ("review", (_VERDICT, "운동화 10만원 오늘 현금으로 사는 건?"), "purchase"),
])
async def test_follow_ups_keep_the_conversation(
    tmp_path: Path, mode: str, turns: tuple[str, ...], family: str,
) -> None:
    answers = await _conversation(tmp_path, turns, one_session=True, router=_Mode(mode))
    assert _family(answers[-1]) == family, answers[-1].get("text")


@pytest.mark.anyio
async def test_a_changed_amount_is_judged_at_that_amount(tmp_path: Path) -> None:
    answers = await _conversation(
        tmp_path, (_VERDICT, "150만원이면?"), one_session=True, router=_Mode("other"),
    )
    assert answers[-1]["receipt"]["request"]["changes"][0]["amount_krw"] == 1_500_000


@pytest.mark.anyio
async def test_an_envelope_follow_up_names_that_envelope_first(tmp_path: Path) -> None:
    answers = await _conversation(
        tmp_path, ("봉투 잔액 보여줘", "외식은?"), one_session=True, router=_Mode("other"),
    )
    assert "외식 봉투는" in answers[-1]["text"].split("\n")[1]


@pytest.mark.anyio
@pytest.mark.parametrize(("mode", "question", "family"), [
    ("other", "노트북 사려는데 괜찮아?", "purchase_clarify"),
    ("review", "의류를 구매하려는데 가능할까요?", "purchase_clarify"),
    ("other", "운동화 10만원 오늘 현금으로 사는 건?", "purchase"),
    ("other", "지금 계좌이체로 피자 8000원 사도 될까?", "purchase"),
    ("other", "이따 체크카드로 커피 2만5천짜리 사도 될까", "purchase"),
    ("other", "쇼핑 봉투는 얼마야?", "balance"),
    ("other", "기타 얼마 남았어~", "balance"),
    ("other", "모든 봉투 현황이 궁금해", "balance"),
    ("other", "외식 20% 줄이면?", "numeric:what_if"),
    ("finance", "편의점·마트·잡화 10% 줄이면 어떻게 돼?", "numeric:what_if"),
    ("other", "교통비 30% 절감하면?", "numeric:what_if"),
    ("other", "외식 줄이면 될까?", "period_review"),
    ("other", "적자 날 수 있어?", "numeric:risk"),
    ("other", "이번 달 예산 초과 가능성 체크", "numeric:risk"),
    ("other", "예산이 모자랄 확률이 얼마나 돼?", "numeric:risk"),
    ("other", "다음 달 이 때쯤 100만원이 모여 있을까요?", "numeric:goal"),
    ("other", "이번 달 30만원 세이브 가능해?", "numeric:goal"),
    ("other", "10만원 모을까?", "period_review"),
    ("other", "이번 달 예산 진단 좀 해줘", "review"),
    ("other", "월말 남은 거 대략 얼마?", "numeric:forecast"),
    ("review", "이더리움 투자 해볼만 해?", "fin_out_of_scope"),
    ("review", "국채 지금 사도 될까", "fin_out_of_scope"),
    ("review", "오늘 코스닥 지수 알려줘", "fin_needs_source"),
    ("review", "달러 환율 지금 어떻게 되냐", "fin_needs_source"),
    ("other", "지난달 교통비 지출 보여줄래", "history"),
    ("other", "지난달 편의점비 얼마였어", "history"),
    ("other", "오늘 썼던 거 알려줄래", "history"),
    ("other", "대출금 알려줄래", "personal"),
    ("other", "은행 잔고 알려줘", "personal"),
    ("review", "아니다 됐어", "out_of_scope"),
    ("review", "직장은 어떤 곳이에요?", "out_of_scope"),
    ("review", "개발자가 되려면 뭘 공부해야 할까요?", "out_of_scope"),
])
async def test_everyday_forms_keep_their_intent(
    tmp_path: Path, mode: str, question: str, family: str,
) -> None:
    answers = await _conversation(tmp_path, (question,), one_session=True, router=_Mode(mode))
    assert _family(answers[-1]) == family, answers[-1].get("text")


@pytest.mark.anyio
@pytest.mark.parametrize(
    "question", ["요즘 예산 상태 체크해줄래?", "외식 30% 아끼면 어떻게 되~", "아니다 됐어"],
)
async def test_own_state_is_never_a_concept_card(tmp_path: Path, question: str) -> None:
    answers = await _conversation(tmp_path, (question,), one_session=True, router=_Mode("review"))
    assert _family(answers[-1]) != "concept", answers[-1].get("text")


@pytest.mark.parametrize(("previous", "question"), [
    ("봉투 잔액 보여줘", "복리가 뭐야?"),
    ("봉투 잔액 보여줘", "왜?"),
    (_VERDICT, "왜?"),
    (_VERDICT, "운동화 10만원 오늘 현금으로 사는 건?"),
    (_VERDICT, "30만원 모을 수 있을까?"),
    ("복리가 뭐야?", "외식은?"),
    ("월말 잔액 얼마 남을까", "외식 20% 줄이면?"),
])
def test_a_question_of_its_own_is_not_rebuilt(previous: str, question: str) -> None:
    assert contextual_followup(previous, question) is None


@pytest.mark.parametrize("question", [
    "책 사는 게 취미야", "운동화 사는 게 취미야", "옷 사는 게 나을까", "커피 사는 게 지출이 커",
    "옷 사는 게 지금 힘들어", "신발 사는 게 얼마나 드는지 알아", "핸드폰 사는 게 뭐가 필요한지 모르겠어",
    "신발 사는 게 뭔지 몰라", "노트북 사는 게 맞는지 몰라",
])
def test_a_buy_noun_in_a_statement_is_not_a_purchase(question: str) -> None:
    assert natural_purchase(question) is None


@pytest.mark.parametrize("question", [
    "이번달 저금한 돈으로 오늘 30만원짜리 패딩 현금으로 사도 될까?",
    "이번달 돈이 좀 모여서 오늘 40만원짜리 자전거 현금으로 사도 될까?",
    "이번달 용돈 모아서 30만원짜리 신발 사고 싶어",
    "이번달 30만원 모으고 싶은데 뭐부터 줄여야 해?",
    "월말까지 100만원 모으려면 뭘 줄여야 해?",
    "다음달 여행비 50만원 마련하고 싶은데 적금이 나을까 예금이 나을까?",
    "이번달 하루 5천원씩 모으면 가능할까?",
    "다음달 월급 삼백만원 들어오면 저금 가능할까?",
    "다음달 월급 300만원 들어오면 저금 가능할까?",
])
def test_a_purchase_advice_or_income_is_not_a_saving_goal(question: str) -> None:
    assert natural_goal(question) is None


@pytest.mark.parametrize(("question", "target"), [
    ("다음 달 50만원 모으면 될까?", 500_000),
    ("다음 달 월급 받으면 90만원 모을 수 있을까?", 900_000),
    ("다음 달 이 때쯤 100만원이 모여 있을까요?", 1_000_000),
    ("이번 달 말까지 50만원 저축?", 500_000),
])
def test_everyday_goal_forms_read_their_target(question: str, target: int) -> None:
    goal = natural_goal(question)
    assert goal is not None
    assert goal.target_krw == target


@pytest.mark.parametrize("question", [
    "외식비 20% 줄이려면 어떻게 해야 돼?",
    "지난달 외식 20% 줄였더니 얼마나 아꼈어?",
    "지난달 외식 20% 줄였으면 얼마 남았을까?",
    "월급이 20% 삭감되면 지출 어떻게 해야 돼?",
    "외식 예산의 20%밖에 안 남았는데 줄이면 어떻게 돼?",
    "쇼핑 20% 세일하면 얼마 절약돼?",
    "외식 20% 줄이는 게 건강에 도움 될까?",
    "두 달 동안 외식 20% 줄이면 어떻게 돼?",
])
def test_a_how_to_past_or_foreign_rate_is_not_a_what_if(question: str) -> None:
    assert natural_what_if(question) is None


@pytest.mark.parametrize("question", [
    "앞으로 30일 동안 쇼핑 10% 줄이면 얼마 남아?",
    "쇼핑비를 절반으로 줄이면?",
    "의료·건강에 10% 적게 쓸 수 있으면 도움이 될까요?",
    "외식 20퍼 줄이면?",
    "배달 20% 줄이면?",
])
def test_everyday_what_if_forms_are_read(question: str) -> None:
    assert natural_what_if(question) is not None


@pytest.mark.parametrize("question", [
    "외식 잔액이 마이너스로 나와",
    "돈 모자랄 때 리볼빙 써도 돼?",
    "금리가 마이너스 되면 예금 어떻게 돼?",
    "우리 회사 적자 날까?",
    "적자가 나면 어떻게 해야 해?",
    "자전거 타이어 펑크 나면 수리비 얼마야?",
    "외식비 다 쓰고 부족해서 카드 썼어",
    "지난달에 예산 다 쓰고 얼마 남았었지?",
    "요즘 소비 분석 앱 추천해줘",
    "지금 소비 체크카드로 하는데 신용카드로 바꿀까?",
    "이번달 예산 진단이 뭐야?",
])
def test_other_topics_are_not_this_budgets_analysis(question: str) -> None:
    assert deterministic_analysis_route(question) is None


def test_a_present_guess_is_a_balance_check_and_a_spending_check_is_not() -> None:
    assert balance_check_question("교통비 얼마 남은 것 같아?")
    assert not balance_check_question("이번달 지출 확인해줘")
    assert not balance_check_question("오늘 외식 지출 상태 알려줘")


def test_a_request_to_record_is_not_a_spending_lookup() -> None:
    assert not supports_spending_question("오늘 지출 기록해줘")


@pytest.mark.parametrize("question", ["신용점수 떨어질 가능성 있어?", "비상금은 월말에 얼마 있어야 돼?"])
def test_a_product_question_is_not_own_state(question: str) -> None:
    assert not _own_state_question(question)


def test_only_prices_before_jjari_gain_a_won_unit() -> None:
    assert with_won_units("커피 2만5천짜리") == "커피 2만5천원짜리"
    assert with_won_units("5천 어치") == "5천원 어치"
    assert with_won_units("300만원짜리 노트북") == "300만원짜리 노트북"
    assert with_won_units("2만 명이 쓰는 앱") == "2만 명이 쓰는 앱"


def test_slang_next_month_is_next_month() -> None:
    assert canonical_question("담달까지 50만원 모을 수 있을까?") == "다음 달까지 50만원 모을 수 있을까?"
    assert canonical_question("내달 외식 20% 줄이면?") == "다음 달 외식 20% 줄이면?"
    assert canonical_question("차가 내달리다 멈췄어") == "차가 내달리다 멈췄어"


# The router names the intent; the values still come only from the user's words. A value the
# text does not state is asked for, and a wrongly named intent never answers small talk.
@pytest.mark.anyio
@pytest.mark.parametrize(("mode", "question", "family"), [
    ("purchase", "오늘 옷 5만 현금으로 가능할까", "purchase"),
    ("purchase", "내일 모자 25000 통장에서 가능할까", "purchase"),
    ("purchase", "비디오카드 사려는데 괜찮을까?", "purchase_clarify"),
    ("purchase", "RTX 4090 오늘 현금으로 사도 돼?", "purchase_clarify"),
    ("goal", "월말까지 백만원 모으려면?", "numeric:goal"),
    ("goal", "다음 달까지 15만원?", "numeric:goal"),
    ("goal", "월말까지 50만 모을 수 있어?", "numeric:goal"),
    ("goal", "여행 가려고 돈 모으고 싶어", "period_review"),
    ("goal", "3년 안에 1억 모을 수 있어?", "period_review"),
    ("what_if", "외식비 반으로 줄이면?", "numeric:what_if"),
    ("what_if", "외식 좀 줄이면 어때?", "period_review"),
    ("balance", "budget 얼마 남았어", "balance"),
    ("balance", "이번 달 남은 돈 얼마", "balance"),
    ("purchase", "오늘 날씨 어때?", "out_of_scope"),
    ("goal", "안녕", "out_of_scope"),
    ("what_if", "고마워", "out_of_scope"),
    ("balance", "심심해", "out_of_scope"),
    ("purchase", "ETF가 뭐야?", "concept"),
])
async def test_a_router_named_intent_reads_its_values_from_the_text(
    tmp_path: Path, mode: str, question: str, family: str,
) -> None:
    answers = await _conversation(tmp_path, (question,), one_session=True, router=_Mode(mode))
    assert _family(answers[-1]) == family, answers[-1].get("text")


@pytest.mark.anyio
async def test_a_router_named_purchase_is_judged_at_the_stated_amount(tmp_path: Path) -> None:
    answers = await _conversation(
        tmp_path, ("오늘 옷 5만 현금으로 가능할까",), one_session=True, router=_Mode("purchase"),
    )
    assert answers[-1]["receipt"]["request"]["changes"][0]["amount_krw"] == 50_000


def test_a_bare_amount_gains_its_won_unit_only_as_an_amount() -> None:
    assert with_bare_won("옷 5만 현금으로") == "옷 5만원 현금으로"
    assert with_bare_won("모자 25,000 통장에서") == "모자 25,000원 통장에서"
    assert with_bare_won("커피 2만5천 오늘") == "커피 2만5천원 오늘"
    assert with_bare_won("노트북 150만원 오늘") == "노트북 150만원 오늘"
    assert with_bare_won("RTX 4090 사도 돼?") == "RTX 4090 사도 돼?"
    assert with_bare_won("콘서트 5만 명") == "콘서트 5만 명"
    assert with_bare_won("2026년 10월 3일") == "2026년 10월 3일"


# A question about the user's own budget skips the concept shortcut, so the router's intent
# decides it; a general finance question still takes the shortcut before any route call.
@pytest.mark.anyio
@pytest.mark.parametrize(("mode", "question", "family"), [
    ("what_if", "편의점 비용을 40% 줄면?", "numeric:what_if"),
    ("what_if", "지출을 15% 줄일 수 있을까?", "numeric:what_if"),
    ("what_if", "취미·여가에 절반만 쓰면 이번 달이 안정적일까요?", "numeric:what_if"),
    ("what_if", "편의점·마트·잡화를 한 달간 최소한으로만 쓰면 어떨까요?", "period_review"),
    ("balance", "헬스를 등록해야 하는데 의료·건강 봉투가 충분할까요?", "balance"),
    ("finance", "잔액이 부족하면 카드 결제 안 돼?", "fin_unavailable"),
])
async def test_an_own_budget_question_is_the_routers_to_name(
    tmp_path: Path, mode: str, question: str, family: str,
) -> None:
    answers = await _conversation(tmp_path, (question,), one_session=True, router=_Mode(mode))
    assert _family(answers[-1]) == family, answers[-1].get("text")


@pytest.mark.parametrize(("question", "amount"), [
    ("오늘 현금으로 커피 40000짜리 사도 될까", 40_000),
    ("낼 현금으로 향수 85,116원 사도 될까?", 85_116),
    ("치킨 4만인데 이따 체크카드로 사도 돼", 40_000),
    ("헬스비 60000인데 지금 통장에서 사도 돼", 60_000),
])
def test_a_purchase_reads_a_bare_price_and_opening_nael(question: str, amount: int) -> None:
    outcome = natural_purchase(canonical_question(question))
    assert isinstance(outcome, NaturalPurchase)
    assert outcome.amount_krw == amount


def test_mid_sentence_nael_is_the_verb() -> None:
    assert canonical_question("회비 낼 수 있을까?") == "회비 낼 수 있을까?"
