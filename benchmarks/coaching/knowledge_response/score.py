"""Measure returned approved evidence and explicit sums, not real-world prediction accuracy."""

from benchmarks.coaching.knowledge_response.cases import Case
from coaching_service.chat_answers import ChatAnswer
from coaching_service.knowledge_catalog import load_catalog
from coaching_service.schemas import JsonDocument

# Independent expected UI copy: do not call the product renderer to generate
# the expected answer. These limits are contract fixtures, not financial truth.
_INCOMPLETE = (
    "이 질문은 현재 제공된 개념 자료만으로 답을 확정할 수 없습니다. "
    "최신 금리·규정·상품 조건이나 해당 주제의 공식 자료가 필요합니다."
)
_MISSING = {
    "현재 금리·규정·상품 비교는 해당 금융회사의 최신 공식 공시와 가입 조건을 확인해야 합니다.",
    "실제 적용 여부는 개인 계약의 약정 기간·수수료·면제 조건을 확인해야 합니다.",
    "세후 결과를 확정하려면 실제 과세 여부·세율·공제 조건을 확인해야 합니다.",
    "정확한 값에는 입력 조건·비교 기간·계산 방식·반올림을 확인한 별도 계산이 필요합니다.",
}


def reference_ids(answer: ChatAnswer) -> tuple[str, ...]:
    raw = answer.evidence.root.get("references")
    if not isinstance(raw, list):
        return ()
    return tuple(
        identifier for item in raw if isinstance(item, dict) and isinstance(identifier := item.get("id"), str)
    )


def evaluate(case: Case, response: JsonDocument) -> bool:
    if "answer_type" not in response.root:
        return False
    answer = ChatAnswer.model_validate(response.root)
    if answer.status != case.expected_status:
        return False
    if case.reference_id is not None:
        return (
            answer.answer_type == "finance_education"
            # The score is source-fidelity and question-coverage evidence. A
            # deterministic response that renders the same pinned catalog fact
            # is at least as traceable as a model-selected response, so do not
            # call it incorrect merely because no model completion was needed.
            and answer.wording_source in {"llm", "template"}
            and answer.fallback_reason is None
            and case.reference_id in reference_ids(answer)
            and approved_body_delivered(answer)
        )
    if case.personal_topic is not None:
        if case.expected_status != "answered":
            return (
                answer.answer_type == "personal_context"
                and answer.wording_source == "engine"
                and answer.evidence.root.get("total_krw") is None
            )
        expected_rows = [150000, 250000] if case.personal_topic == "goals" else None
        rows = answer.evidence.root.get("rows")
        goals = expected_rows is None or (
            isinstance(rows, list)
            and [row.get("amount_krw") for row in rows if isinstance(row, dict)] == expected_rows
        )
        return (
            answer.answer_type == "personal_context"
            and answer.wording_source == "engine"
            and answer.evidence.root.get("topic") == case.personal_topic
            and answer.evidence.root.get("total_krw") == case.total_krw
            and goals
        )
    return (
        answer.answer_type == "scope_response"
        if case.expected_status == "out_of_scope"
        else answer.answer_type == "finance_education" and answer.wording_source == "llm"
    )


def approved_body_delivered(answer: ChatAnswer) -> bool:
    """Verify delivered statements, not just reference metadata.

    The finance API displays approved paragraphs verbatim. Comparing the actual
    body to that source detects omissions, contradictions and appended claims.
    This proves source fidelity; a separate rubric must judge question coverage
    and whether the approved source itself is correct and current.
    """
    references = reference_ids(answer)
    facts = {fact.id: fact for fact in load_catalog().facts}
    if (
        not references or len(set(references)) != len(references)
        or any(key not in facts for key in references)
    ):
        return False
    expected = "\n\n".join(
        facts[key].text + "\n출처: [" + facts[key].source_title + "](" + facts[key].source_url + ")"
        for key in references
    )
    if answer.status == "answered":
        return answer.text == expected
    if answer.status != "needs_source" or not answer.text.startswith(expected + "\n\n" + _INCOMPLETE):
        return False
    suffix = answer.text[len(expected + "\n\n" + _INCOMPLETE):]
    if not suffix:
        return True
    if not suffix.startswith("\n\n"):
        return False
    conditions = suffix[2:].split("\n\n")
    return (
        len(conditions) <= 3 and len(conditions) == len(set(conditions))
        and set(conditions).issubset(_MISSING)
    )
