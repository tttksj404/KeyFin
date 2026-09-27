# ruff: noqa: INP001
"""Future-tense buy phrasings are purchases, so their date words never trigger a period re-ask.

"내일 … 사려는데" used to miss the purchase verbs, fall through to the period parser, and get
"언제 기준인지 알려주세요" even though "내일" already named the date.
"""

import pytest

from coaching_service.fast_routes import NaturalPurchase, natural_purchase


@pytest.mark.parametrize(
    "question",
    [
        "나 내일 70만원 닌텐도 스위치 현금으로 사려는데 괜찮을까? 차트도 보여줘",
        "내일 70만원 스위치 현금으로 사려해",
        "내일 스위치 70만원짜리 현금으로 살건데 괜찮아?",
        "내일 70만원 스위치 현금으로 살거야",
        "내일 70만원 스위치 현금으로 구매하려는데 괜찮아?",
        "내일 70만원 스위치 현금으로 구입하려고 해",
        "쿠팡에서 내일 70만원 스위치 현금으로 사려는데",
    ],
)
def test_future_tense_purchase_is_admitted(question: str) -> None:
    parsed = natural_purchase(question)
    assert isinstance(parsed, NaturalPurchase), parsed
    assert (parsed.amount_krw, parsed.date_token, parsed.payment_hint) == (700_000, "tomorrow", "cash")


@pytest.mark.parametrize(
    "question",
    [
        # 목표 저축 질문
        "노트북 사려는데 이번달에 200만원 모을 수 있을까",
        "아이폰 살건데 이번달에 150만원 모을 수 있을까",
        "차 사려는데 3000만원 모으려면",
        "100만원 모아서 사려는데",
        # 금융상품 질문
        "주식 사려는데 뭐가 좋아",
        "적금 사려는데",
        "코인 지르려는데 괜찮아",
        # 금액·품목이 없는 일반 문장
        "사려는 사람 많아?",
        "사려는데 돈이 없어",
        "어제 150만원 아이폰 사려는거 봤는데 비싸더라",
        # 거주 뜻의 살다
        "서울에 살건데 집값 어때",
        "부산에 살건데 월세 50만원 괜찮아?",
        "서울에서 살건데 한달 생활비 200만원이면 돼?",
        "혼자 살예정인데 식비 30만원 적당해?",
        "1년 동안 100만원으로 살거야",
        "이 동네에서 오래 살거야, 월 관리비 20만원",
        "자취방에서 살생각인데 옷 사는데 얼마 써?",
        "살생각 없어 그냥 저축할래 50만원",
    ],
)
def test_goal_finance_and_living_phrases_stay_out_of_purchase(question: str) -> None:
    assert natural_purchase(question) is None
