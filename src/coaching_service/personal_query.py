"""개인 질문은 계산 가능한 범위를 명확히 고른 뒤 서버가 그대로 집계한다."""

import re
from typing import Final

from coaching_service.personal_contract import PersonalTopic

_TOPICS: Final[dict[str, PersonalTopic]] = {
    "계좌잔액": "accounts",
    "통장잔액": "accounts",
    "계좌": "accounts",
    "잔액": "accounts",
    "자산": "assets",
    "부채": "debts",
    "대출잔액": "debts",
    "대출금": "debts",
    "보험": "insurance",
    "보험료": "insurance",
    "소득": "income",
    "월소득": "income",
    "월급": "income",
    "고정비": "fixed_costs",
    "월고정비": "fixed_costs",
    "예정결제": "payments",
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
    r"(?:현황|내역|목록|총액|합계)?(?:은|는|이|가|을|를)?(?:현재|지금)?(?:좀)?"
    r"(?:얼마(?:야|인가요|예요|지|나돼|남았어)?|뭐(?:야|가있어)|어떻게돼|알려(?:줘|주세요)|"
    r"보여(?:줘|주세요)|조회해(?:줘|주세요)|확인해(?:줘|주세요))?[?!.]*"
)


def select_personal_topic(question: str) -> PersonalTopic | None:
    """조건의 일부만 잡아 은행·기간·비교 필터를 조용히 무시하지 않는다."""
    matched = _QUERY.fullmatch(re.sub(r"\s+", "", question))
    return _TOPICS[matched["topic"]] if matched is not None else None


_CONNECTOR: Final = re.compile(r"이랑|랑|하고|과|와|그리고|및|둘\s*다|모두")
_COMPARISON_MARKER: Final = re.compile(r"비교|차이")
_TOPIC_KEYS_BY_LENGTH: Final = tuple(sorted(_TOPICS, key=len, reverse=True))


def _topic_in_fragment(fragment: str) -> PersonalTopic | None:
    """조각 하나에서 가장 긴 등록 주제어를 찾는다. 짧은 부분 문자열의 오탐을 줄인다."""
    compact = re.sub(r"\s+", "", fragment)
    for key in _TOPIC_KEYS_BY_LENGTH:
        if key in compact:
            return _TOPICS[key]
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


def has_unmatched_fragment(question: str) -> bool:
    """연결어로 나뉜 조각 중 등록된 주제를 찾지 못한 조각이 있으면 참이다."""
    fragments = [fragment for fragment in _CONNECTOR.split(question) if fragment.strip()]
    return any(_topic_in_fragment(fragment) is None for fragment in fragments)
