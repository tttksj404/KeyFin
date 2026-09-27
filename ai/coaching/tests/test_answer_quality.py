# ruff: noqa: INP001
"""The answer rubric must reject missing, unrelated, and non-finite figures."""

import pytest

from benchmarks.coaching.answer_quality import Rule, metric_mentioned


@pytest.mark.parametrize(
    ("text", "found"),
    [
        ("미래 현금 중앙값은 150,000원입니다.", True),
        ("이전 결제 150,000원.\n미래 현금은 별도로 확인해 주세요.", False),
        ("미래 현금 중앙값은 1,150,000원입니다.", False),
        ("미래 현금 중앙값은 150,000입니다.", False),
        ("과거 결제 150,000원입니다.", False),
    ],
)
def test_amount_needs_matching_topic_unit_and_complete_number(text: str, found: bool) -> None:
    assert metric_mentioned(text, Rule(metric="cash", topic="현금", unit="KRW"), 150000) is found


@pytest.mark.parametrize(("value", "found"), [(0.25, True), (0.025, False), (float("nan"), False)])
def test_probability_is_rendered_as_percentage(value: float, found: bool) -> None:
    rule = Rule(metric="risk", topic="부족", unit="probability")
    assert metric_mentioned("계좌 부족 경로의 비율은 25.0%입니다.", rule, value) is found


def test_invalid_probability_is_not_counted() -> None:
    rule = Rule(metric="risk", topic="부족", unit="probability")
    assert not metric_mentioned("계좌 부족 200.0%입니다.", rule, 2)


def test_count_requires_its_unit() -> None:
    rule = Rule(metric="candidates", topic="후보", unit="count")
    assert metric_mentioned("조건 충족 후보 2개입니다.", rule, 2)
    assert not metric_mentioned("조건 충족 후보 2원입니다.", rule, 2)
