"""Score final-answer evidence delivery separately from route and transport success.

The reference here is the engine receipt, so this is an answer-fidelity regression
measure, never a forecast-accuracy or independent financial-calculation oracle.
"""

import hashlib
import math
import re
import sys
from pathlib import Path
from typing import Final, Literal, assert_never

from pydantic import Field

from benchmarks.coaching.e2e.e2e_contracts import Report
from coaching_service.schemas import Coaching, Frozen


class Rule(Frozen):
    metric: str
    topic: str
    unit: Literal["KRW", "probability", "count"]


class FactScore(Frozen):
    metric: str
    available: bool
    delivered: bool


class AnswerScore(Frozen):
    case_id: str
    ordinal: int
    mode: str
    facts: tuple[FactScore, ...]
    period_delivered: bool
    conditional_warning_delivered: bool

    @property
    def complete(self) -> bool:
        return (
            bool(self.facts)
            and all(fact.available and fact.delivered for fact in self.facts)
            and self.period_delivered
            and self.conditional_warning_delivered
        )


class AnswerQuality(Frozen):
    report_sha256: str
    answers: tuple[AnswerScore, ...]
    scored_answers: int = Field(ge=0)
    complete_answers: int = Field(ge=0)
    available_facts: int = Field(ge=0)
    delivered_facts: int = Field(ge=0)
    interpretation: str = (
        "POST dialogue answers only; GET readbacks are excluded. Checks selected metric amounts "
        "with related labels, period endpoints, and conditional-model language. The rubric is a "
        "regression for observed omissions, not a blind test, human helpfulness rating, or evidence "
        "that the engine forecast matches future customer outcomes."
    )


RULES: Final = {
    "forecast": (
        Rule(metric="total_expense_p50_krw", topic="소비", unit="KRW"),
        Rule(metric="terminal_cash_p50_krw", topic="현금", unit="KRW"),
    ),
    "risk": (
        Rule(metric="p_any_account_shortfall", topic="부족", unit="probability"),
        Rule(metric="maximum_total_cash_shortage_p50_krw", topic="부족", unit="KRW"),
    ),
    "goal": (
        Rule(metric="goal_target_krw", topic="목표", unit="KRW"),
        Rule(metric="p_goal_and_no_shortfall", topic="목표", unit="probability"),
    ),
    "what_if": (
        Rule(metric="paired_expense_saving_p50_krw", topic="소비", unit="KRW"),
        Rule(metric="paired_terminal_cash_delta_p50_krw", topic="현금", unit="KRW"),
    ),
    "optimize": (
        Rule(metric="feasible_candidate_count", topic="후보", unit="count"),
        Rule(metric="selected_expected_saving_krw", topic="소비", unit="KRW"),
    ),
}


def metric_mentioned(text: str, rule: Rule, value: float) -> bool:
    """Require the unit and topic on the same line; unrelated old amounts do not count."""
    if not math.isfinite(value):
        return False
    match rule.unit:
        case "KRW":
            number = re.escape(f"{value:,.0f}")
            suffix = r"\s*원"
        case "count":
            number = re.escape(f"{value:,.0f}")
            suffix = r"\s*개"
        case "probability":
            if not 0 <= value <= 1:
                return False
            percentage = f"{value * 100:.1f}"
            number = re.escape(percentage)
            if percentage.endswith(".0"):
                number = rf"(?:{re.escape(percentage[:-2])}|{number})"
            suffix = r"\s*%"
        case unreachable:
            assert_never(unreachable)
    pattern = re.compile(rf"(?<![\d,.]){number}{suffix}")
    return any(rule.topic in line and pattern.search(line) for line in text.splitlines())


def score_answer(coaching: Coaching, case_id: str, ordinal: int) -> AnswerScore:
    """Inspect values without importing the production renderer or its formatting helpers."""
    numeric = coaching.receipt.numeric_result
    if numeric is None:
        raise ValueError("A numeric receipt is required")
    mode = numeric.root.get("mode")
    metrics = numeric.root.get("metrics")
    if not isinstance(mode, str) or mode not in RULES or not isinstance(metrics, dict):
        raise ValueError("A supported numeric mode and metrics object are required")
    if numeric.root.get("status") != "ok":
        raise ValueError("This rubric scores successful calculations only")
    facts: list[FactScore] = []
    for rule in RULES[mode]:
        raw = metrics.get(rule.metric)
        value = raw.get("value") if isinstance(raw, dict) else None
        available = (
            isinstance(raw, dict)
            and raw.get("unit") == rule.unit
            and isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(value)
        )
        delivered = (
            available and isinstance(value, (int, float)) and metric_mentioned(coaching.text, rule, value)
        )
        facts.append(FactScore(metric=rule.metric, available=available, delivered=delivered))
    period = coaching.receipt.period
    period_delivered = (
        period is not None
        and period.forecast_start.isoformat() in coaching.text
        and period.forecast_end.isoformat() in coaching.text
    )
    warning = (
        any(word in coaching.text for word in ("조건부", "가정 아래", "가정에 따른", "가정 아래의"))
        and "보장" in coaching.text
    )
    return AnswerScore(
        case_id=case_id,
        ordinal=ordinal,
        mode=mode,
        facts=tuple(facts),
        period_delivered=period_delivered,
        conditional_warning_delivered=warning,
    )


def score_report(raw: bytes) -> AnswerQuality:
    report = Report.model_validate_json(raw)
    rows: list[AnswerScore] = []
    for exchange in report.http:
        # Persisted GET receipts are the same answer, not a second successful generation.
        if exchange.method != "POST" or not exchange.path.endswith("/messages"):
            continue
        if exchange.status_code != 200:
            raise ValueError("A dialogue request failed; do not silently shrink the denominator")
        coaching = Coaching.model_validate(exchange.response_body.root)
        if coaching.receipt.numeric_result is not None:
            rows.append(score_answer(coaching, exchange.case_id, len(rows)))
    if not rows:
        raise ValueError("No numeric dialogue answers to score")
    facts = [fact for row in rows for fact in row.facts]
    return AnswerQuality(
        report_sha256=hashlib.sha256(raw).hexdigest(),
        answers=tuple(rows),
        scored_answers=len(rows),
        complete_answers=sum(row.complete for row in rows),
        available_facts=sum(fact.available for fact in facts),
        delivered_facts=sum(fact.delivered for fact in facts),
    )


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("Usage: python -m benchmarks.coaching.answer_quality REPORT OUTPUT")
    report, output = map(Path, sys.argv[1:])
    result = score_report(report.read_bytes())
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        _ = stream.write(result.model_dump_json(indent=2))
    print(  # noqa: T201 - Only aggregate counts; raw answers stay in ignored artifacts.
        f"Answer facts: {result.delivered_facts}/{result.available_facts}; "
        f"complete answers: {result.complete_answers}/{result.scored_answers}"
    )


if __name__ == "__main__":
    main()
