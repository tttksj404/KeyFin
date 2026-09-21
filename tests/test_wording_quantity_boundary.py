# ruff: noqa: INP001
import pytest

from coaching_service.llm_prompt import wording_problem


@pytest.mark.parametrize(
    "wording",
    [
        "다음 주에 예정된 반복 지출 항목과 결제 채널별 정산 조건을 확인해 주세요.",
        "결제 조건을 확인해 주세요.",
        "정산 조건이 정해졌는지 확인해 주세요.",
        "조건 확인에 필요한 내용을 알려 주세요.",
        "조건, 확인에 필요한 내용을 알려 주세요.",
    ],
)
def test_condition_noun_is_not_a_trillion_items_claim(wording: str) -> None:
    # Given: the observed GPU answer and ordinary noun/particle forms make no quantity claim.
    # When/Then: the complete wording guard accepts the information request.
    assert wording_problem(wording) is None


@pytest.mark.parametrize(
    "wording",
    [
        "이전 정보와 현재 상태의 차이를 구분하기 위해 최근 상황을 알려 주세요.",
        "결제 채널을 구분하기 위해 정산 조건을 확인해 주세요.",
        "항목을 구분하기 전에 내용을 확인해 주세요.",
        "취소된 구매가 포함된 이전 점검과 현재 상태의 차이를 구분해 확인해 주세요.",
        "이전 점검과 현재 상태를 구분해서 확인해 주세요.",
        "항목을 구분하고 결제 조건을 확인해 주세요.",
        "이전 점검과 현재 상태를 구분하여 확인해 주세요.",
        "항목을 구분하는 데 필요한 내용을 알려 주세요.",
        "항목을 구분하도록 관련 내용을 알려 주세요.",
    ],
)
def test_distinguishing_verb_is_not_a_nine_minute_claim(wording: str) -> None:
    # Given: the observed verb inflection requests information without stating a duration.
    # When/Then: accepting that complete word must also preserve the condition noun exception.
    assert wording_problem(wording) is None


@pytest.mark.parametrize("prefix", ["조건을 살피고 ", "항목을 구분하기 위해 "])
@pytest.mark.parametrize(
    "quantity",
    [
        "일조 건",
        "조 건",
        "일조건",
        "일조원",
        "일 조 건",
        "일 조건",
        "십조건",
        "백조건",
        "천조건",
        "만조건",
        "억조건",
        "일조건이",
        "일조건을",
        "조  건",
        "조\t건",
        "조\n건",
        "조\u00a0건",
        "일\u200b조 건",
        "일조\u200b건",
        "이백만원",
        "일 조 원",
        "오 퍼센트",
        "두 배",
        "세 번",
        "절반",
        "반값",
        "one",
        "TWO",
        "hundred",
        "million",
        "half",
        "twice",
        "1,000원",
        "１０００원",
        "₩",
        "$",
        "€",
        "£",
        "%",
    ],
)
def test_condition_exception_preserves_numeric_and_amount_rejection(quantity: str, prefix: str) -> None:
    # Given: a genuine quantity may follow an accepted ordinary noun or verb.
    wording = prefix + quantity + " 내용도 확인해 주세요."

    # When/Then: the exception cannot suppress another numeric or currency claim in the sentence.
    assert wording_problem(wording) == "numeric_output"


@pytest.mark.parametrize("quantity", ["일조건", "일조 건", "일 조 건", "조 건", "일조원"])
def test_condition_inside_numeric_word_is_not_exempted(quantity: str) -> None:
    # Given: the noun-shaped suffix is part of a larger Korean quantity or separated number/unit.
    # When/Then: reject it without relying on another occurrence of the word for the guard to fire.
    assert wording_problem(quantity + " 내용도 확인해 주세요.") == "numeric_output"


@pytest.mark.parametrize(
    "duration",
    [
        "구 분",
        "구분 동안",
        "구분 걸려",
        "구분 걸렸는지",
        "구\t분",
        "구\n분",
        "구\u00a0분",
        "구\u200b 분",
        "구\u200b분 동안",
        "십구분",
        "구십구분",
        "구 분하기",
        "구분 하기로",
    ],
)
def test_distinguishing_exception_preserves_duration_rejection(duration: str) -> None:
    # Given: nine-minute quantities and separated words must not inherit the complete verb exception.
    wording = "상황을 구분하기 위해 " + duration + " 관련 내용을 확인해 주세요."

    # When/Then: a valid verb earlier in the sentence cannot hide a later duration.
    assert wording_problem(wording) == "numeric_output"


@pytest.mark.parametrize(
    "wording",
    [
        "구분해 일조원 내용을 확인해 주세요.",
        "구분해서 one 항목을 확인해 주세요.",
        "구분하여 1,000원 내용을 확인해 주세요.",
        "구분해삼천원 내용을 확인해 주세요.",
    ],
)
def test_distinguishing_inflections_cannot_hide_amounts(wording: str) -> None:
    # Given: a valid conjugation may precede a quantity, or be joined to a Korean amount without a boundary.
    # When/Then: neither a full sentence nor an arbitrary continuation of the verb stem is exempted.
    assert wording_problem(wording) == "numeric_output"
