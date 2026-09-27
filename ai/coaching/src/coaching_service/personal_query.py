"""개인 질문은 계산 가능한 범위를 명확히 고른 뒤 서버가 그대로 집계한다."""

import re
from typing import Final

from coaching_service.personal_contract import PersonalTopic
from coaching_service.word_segments import WordSegments

_TOPICS: Final[dict[str, PersonalTopic]] = {
    "계좌잔액": "accounts",
    "통장잔액": "accounts",
    "계좌잔고": "accounts",
    "통장잔고": "accounts",
    "잔고": "accounts",
    "통장": "accounts",
    "계좌": "accounts",
    "잔액": "accounts",
    "순자산": "assets",
    "자산": "assets",
    "부채": "debts",
    "대출잔액": "debts",
    "대출금": "debts",
    "빚": "debts",
    "대출": "debts",
    "남은대출": "debts",
    "남은빚": "debts",
    "보험": "insurance",
    "보험료": "insurance",
    "소득": "income",
    "월소득": "income",
    "월급": "income",
    "고정비": "fixed_costs",
    "월고정비": "fixed_costs",
    "예정결제": "payments",
    "카드값": "payments",
    "카드대금": "payments",
    "카드청구": "payments",
    "카드청구금액": "payments",
    "청구금액": "payments",
    "예정결제금액": "payments",
    "금융목표": "goals",
    "목표": "goals",
    "예산": "budget",
    "남은예산": "budget",
    "봉투": "budget",
    "봉투잔액": "budget",
    "봉투예산": "budget",
    "예산잔액": "budget",
}
_QUERY: Final = re.compile(
    r"(?:이번달)?(?:현재|지금)?(?:내|제|나의|저의)?(?:현재|지금)?(?:총|전체)?"
    rf"(?P<topic>{'|'.join(re.escape(name) for name in _TOPICS)})"
    r"(?:현황|내역|목록|총액|합계|상태)?(?:은|는|이|가|을|를|에)?(?:현재|지금)?(?:좀)?"
    r"(?:얼마(?:나)?(?:야|인가요|예요|지|나돼|남았어|있어(?:요)?|나와(?:요)?|와(?:요)?)?|뭐(?:야|가있어)|어떻게돼|"
    r"있어(?:요)?|알려(?:줘|주세요)|보여(?:줘|주세요)|조회해(?:줘|주세요)|확인해(?:줘|주세요))?[?!.]*"
)


# 이모티콘 자모와 장식 기호("ㅠㅠ", "ㅋㅋ", "~", "^^")는 조회 조건이 아니므로 떼고 맞춘다.
_DECORATION: Final = re.compile(r"\s+|[\u3131-\u318e~^;…♡♥]+")


# 정확한 문법이 못 받는 일상 표현("내 빚 총 얼마야?", "카드값 얼마 나왔어?", "통장에 돈
# 얼마 있는지 확인해줘")은 필터 없는 단일 주제일 때만 받는다. 은행·계좌 종류·기간·비교가
# 섞이면 그 조건을 조용히 버리지 않도록 여전히 받지 않는다.
_LENIENT_TOPICS: Final[tuple[tuple[str, PersonalTopic], ...]] = (
    ("신용카드결제예정", "payments"), ("카드결제예정", "payments"), ("카드명세서", "payments"),
    ("카드값", "payments"), ("카드대금", "payments"), ("카드청구", "payments"),
    ("결제예정", "payments"), ("예정결제", "payments"), ("명세서", "payments"),
    ("순자산", "assets"), ("재산", "assets"), ("자산", "assets"),
    ("부채", "debts"), ("빚", "debts"), ("대출", "debts"),
    ("잔고", "accounts"), ("잔액", "accounts"), ("통장", "accounts"), ("계좌", "accounts"),
)
_LENIENT_FILTER: Final = re.compile(
    r"마이너스|학자금|전세|신용대출|자동차|주택|주거래|월급|청약|적금|입출금|저축|예금|보험|이자|은행|국민|신한|우리|하나"
    r"|농협|카카오뱅크|토스|케이뱅크|이번달|지난달|어제|오늘|예산|봉투|소비|지출|비교|차이|월말|앞으로|향후|예측|예상"
    r"|남을|남겠|될까|것같|거같|나올까|위험|부족|목표|고정비|소득|수입"
)
_LENIENT_ASK: Final = re.compile(
    r"얼마|알려|보여|확인|합치|합친|전부|모든|알수있|궁금|남았|남은|남아|있어|쌓였|나왔|청구"
)


# Everything else a lenient lookup may contain; any other word ("리볼빙으로", "받을 수",
# "흘러갈지", "엄마") leaves a residue and keeps the exact grammar's refusal.
_LENIENT_WORDS: Final = tuple(sorted({
    "원금", "얼마나왔어", "얼마나왔", "얼마나갔어", "얼마청구됐어", "얼마쌓였어", "얼마인지", "얼마나",
    "얼마", "알려주실래요", "알려줄래", "알려줄수있어", "알려주세요", "알려줘", "알려",
    "보여주세요", "보여줘", "보여", "확인해줘", "확인", "알수있을까", "알수있어", "궁금해",
    "합치면", "합쳐서", "합친", "전부", "모든", "모두", "한번에", "전체", "혹시", "좀", "지금",
    "현재", "이번에", "이번", "총", "다", "내", "나의", "제", "계좌별", "별", "남아있어", "남아있",
    "남았는지", "남았어", "남았지", "남은", "남아", "남았", "쌓였어", "쌓였", "나왔어", "나왔",
    "청구됐어", "청구됐", "청구된", "들어있어", "들어", "있는지", "있어", "모였어", "해줘", "줘",
    "줄래", "금액", "보유", "목록", "이랑", "랑", "하고", "돈", "의", "에", "이",
    "가", "은", "는", "을", "를", "야", "요", "지", "어", "해",
}, key=len, reverse=True))

# Lenient wording must split completely into allowed words, each followed only by particles
# or endings. Erasing words anywhere let a filter hide ("요가에" lost 가·에 and read as a
# total); a leftover syllable now keeps the exact grammar's refusal.
_LENIENT_PARTICLES: Final = (
    "에서", "으로", "이었어", "였는지", "였더라", "였어", "였지", "인지", "는지",
    "은", "는", "이", "가", "을", "를", "에", "로", "의", "도", "만", "요", "야", "지", "어", "해", "한",
)
_LENIENT_MAX: Final = 60


# One particle or ending per word, optionally followed by a topic marker ("외식비로는").
_LENIENT_FULL: Final = WordSegments(
    tuple(word for word, _ in _LENIENT_TOPICS)
    + tuple(word for word in _LENIENT_WORDS if word not in _LENIENT_PARTICLES),
    _LENIENT_PARTICLES,
)


_ACCOUNT_TOPIC: Final = re.compile(r"(?<!대출)(?<!빚)(?<!카드값)(?<!카드대금)(?:계좌|통장)(?!대출|빚)")


def _lenient_topic(compact: str) -> PersonalTopic | None:
    if _LENIENT_FILTER.search(compact) is not None or _LENIENT_ASK.search(compact) is None:
        return None
    if len(compact) > _LENIENT_MAX or not _LENIENT_FULL.covers(compact):
        return None
    found: set[PersonalTopic] = set()
    rest = compact
    for word, topic in _LENIENT_TOPICS:
        if word in rest:
            found.add(topic)
            rest = rest.replace(word, " ")
    account_named = _ACCOUNT_TOPIC.search(compact) is not None
    # "대출 잔액" is the debt balance; "카드값 잔액" the card bill. A named 계좌/통장 ("계좌
    # 잔액이랑 부채") stays a second topic, so the lookup is not narrowed to one of them.
    for owner in ("debts", "payments"):
        if owner in found and not account_named:
            found.discard("accounts")
    return next(iter(found)) if len(found) == 1 else None


# 계좌·대출 종류를 지목한 조회("월급 통장 잔액", "학자금 대출 잔액")는 종류별로 고르지
# 못하므로, 같은 주제 전체를 보여 주고 그 사실을 함께 밝힌다(personal_service가 문장을 붙인다).
_ACCOUNT_KIND: Final = re.compile(
    r"마이너스|학자금|전세|신용|자동차|주택|주거래|월급|청약|적금|입출금|저축|예금|생활비"
)


def filtered_personal_topic(question: str) -> PersonalTopic | None:
    """Return the accounts/debts topic of a lookup that names an account or loan kind."""
    compact = re.sub(r"[?!.,]", "", _DECORATION.sub("", question))
    if _ACCOUNT_KIND.search(compact) is None:
        return None
    return _lenient_topic(_ACCOUNT_KIND.sub("", compact))


def select_personal_topic(question: str) -> PersonalTopic | None:
    """조건의 일부만 잡아 은행·기간·비교 필터를 조용히 무시하지 않는다."""
    compact = _DECORATION.sub("", question)
    matched = _QUERY.fullmatch(compact)
    if matched is not None:
        return _TOPICS[matched["topic"]]
    return _lenient_topic(re.sub(r"[?!.,]", "", compact))


_CONNECTOR: Final = re.compile(r"이랑|랑|하고|과|와|그리고|및|둘\s*다|모두|,")
_COMPARISON_MARKER: Final = re.compile(r"비교|차이")
_TOPIC_KEYS_BY_LENGTH: Final = tuple(sorted(_TOPICS, key=len, reverse=True))


# "금리 높은 대출", "고금리 대출" describe the loan; "대출 이자 얼마야?" asks the interest.
_INTEREST_ASK: Final = re.compile(
    r"(?<![고저])(?:이자|금리|이율)(?!(?:가|이)?(?:높|낮|붙|포함|싼|비싼|센|쎈))"
)
_PRINCIPAL: Final = re.compile(r"잔액|원금|잔고|남은")


def _topic_in_fragment(fragment: str) -> PersonalTopic | None:
    """조각 하나에서 가장 긴 등록 주제어를 찾는다. 짧은 부분 문자열의 오탐을 줄인다."""
    compact = re.sub(r"\s+", "", fragment)
    for key in _TOPIC_KEYS_BY_LENGTH:
        if key in compact:
            topic = _TOPICS[key]
            # "대출 이자 얼마야?" asks the interest; the debt snapshot holds only the principal.
            asks_interest = _INTEREST_ASK.search(compact) is not None and _PRINCIPAL.search(compact) is None
            return None if topic == "debts" and asks_interest else topic
    return None


def select_personal_topics(question: str) -> tuple[PersonalTopic, ...]:
    """'계좌 잔액이랑 남은 예산 알려줘' 같은 복합 질문의 조각마다 주제를 찾는다.

    단일 주제는 select_personal_topic이 이미 정확히 처리하므로, 이 함수는 연결어로
    나뉜 조각이 둘 이상이고 그중 하나 이상에서 등록된 주제를 인식할 때만 값을
    반환한다. 인식하지 못한 조각(예: '예산')은 조용히 새 수치를 만들지 않고 빈
    상태로 남겨, 호출자가 별도 안내 문구를 붙일 수 있게 한다. '비교'·'차이'처럼
    두 항목의 관계를 묻는 질문은 기존 select_personal_topic과 같은 이유로
    제외한다.
    """
    if _COMPARISON_MARKER.search(question) is not None:
        return ()
    fragments = [fragment for fragment in _CONNECTOR.split(question) if fragment.strip()]
    if len(fragments) < 2:
        return ()
    topics: list[PersonalTopic] = []
    for fragment in fragments:
        topic = _topic_in_fragment(fragment)
        if topic is not None and topic not in topics:
            topics.append(topic)
    return tuple(topics)


def connector_fragments(question: str) -> list[str]:
    """연결어로 나눈 조각들("계좌 잔액", "이번 달 외식 얼마 썼어?")."""
    return [fragment for fragment in _CONNECTOR.split(question) if fragment.strip()]


def has_unmatched_fragment(question: str) -> bool:
    """연결어로 나뉜 조각 중 등록된 주제를 찾지 못한 조각이 있으면 참이다."""
    fragments = [fragment for fragment in _CONNECTOR.split(question) if fragment.strip()]
    return any(_topic_in_fragment(fragment) is None for fragment in fragments)
