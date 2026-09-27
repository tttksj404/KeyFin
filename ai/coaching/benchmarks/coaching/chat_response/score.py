"""Score transport, answer meaning, and model admission as separate observations."""

from __future__ import annotations

import argparse
import calendar
import hashlib
import math
import re
import statistics
from datetime import date, timedelta
from pathlib import Path
from typing import assert_never

from benchmarks.coaching.answer_quality import score_answer
from benchmarks.coaching.chat_response.cases import CASES, ChatCase
from benchmarks.coaching.chat_response.contracts import (
    CaseResult,
    CaseScore,
    LatencyScore,
    LayerScore,
    ModelObservation,
    ModelScore,
    RunReport,
    ScoreReport,
)
from coaching_service.chat_answers import ChatAnswer
from coaching_service.schemas import Coaching, Frozen

NUMBERED_FINANCE = re.compile(r"\d[\d,.]*\s*(?:원|%)")


class CliArguments(Frozen):
    report: Path
    output: Path


def transport_passed(case: CaseResult) -> bool:
    return (
        bool(case.http)
        and all(stage.status == 200 for stage in case.http.values())
        and case.stored_exact
        and case.history_isolated
    )


def reference_ids(answer: ChatAnswer) -> tuple[str, ...]:
    references = answer.evidence.root.get("references")
    if not isinstance(references, list):
        return ()
    identifiers: list[str] = []
    for reference in references:
        if isinstance(reference, dict):
            identifier = reference.get("id")
            if isinstance(identifier, str):
                identifiers.append(identifier)
    return tuple(identifiers)


def finance_passed(case: ChatCase, answer: ChatAnswer) -> bool:
    expected_type = "scope_response" if case.expected_status == "out_of_scope" else "finance_education"
    if answer.answer_type != expected_type or answer.status != case.expected_status:
        return False
    if case.expected_status == "answered":
        return (
            # Catalog-template answers preserve the same approved reference and
            # body as model-selected answers; scoring must measure correctness,
            # not whether an avoidable inference call happened.
            answer.wording_source in {"llm", "template"}
            and answer.fallback_reason is None
            and reference_ids(answer) == (case.reference_id,)
            and all(any(marker in answer.text for marker in group) for group in case.markers)
        )
    return (
        reference_ids(answer) == ()
        and NUMBERED_FINANCE.search(answer.text) is None
        and (
            answer.fallback_reason == "non_financial_question"
            if case.expected_status == "out_of_scope"
            else answer.wording_source == "llm" and answer.fallback_reason is None
        )
    )


def data_request_passed(answer: ChatAnswer) -> bool:
    return (
        answer.answer_type == "data_request"
        and answer.status == "needs_data"
        and answer.wording_source == "template"
        and answer.fallback_reason == "twin_not_connected"
        and "연결" in answer.text
    )


def history_passed(answer: ChatAnswer) -> bool:
    spending = answer.evidence.root.get("spending")
    if answer.answer_type != "spending_history" or answer.status != "answered":
        return False
    if answer.wording_source != "engine" or answer.model != "not_called" or not isinstance(spending, dict):
        return False
    total = spending.get("total_krw")
    start = spending.get("start")
    end = spending.get("end")
    return (
        isinstance(total, int)
        and not isinstance(total, bool)
        and isinstance(start, str)
        and isinstance(end, str)
        and f"{total:,}원" in answer.text
        and start in answer.text
        and end in answer.text
        and "7봉투 소비만 집계" in answer.text
        and "월 전체 또는 모든 계좌의 소비 합계로 확정할 수 없습니다" in answer.text
    )


def expected_forecast_window(case_id: str, as_of: date) -> tuple[date, date]:
    """Derive the question's dates from the fixture, without the product resolver."""
    end = (
        as_of + timedelta(days=7)
        if case_id == "forecast_7d_balance"
        else as_of.replace(day=calendar.monthrange(as_of.year, as_of.month)[1])
    )
    return as_of + timedelta(days=1), end


def numeric_passed(case: ChatCase, answer: Coaching, ordinal: int, as_of: date) -> bool:
    scored = score_answer(answer, case.id, ordinal)
    period = answer.receipt.period
    numeric = answer.receipt.numeric_result
    expected_start, expected_end = expected_forecast_window(case.id, as_of)
    return (
        scored.complete
        and period is not None
        and period.reference_date == as_of
        and period.forecast_start == expected_start
        and period.forecast_end == expected_end
        and period.forecast_days == (expected_end - as_of).days
        and numeric is not None
        and numeric.root.get("mode") == case.expected_kind
    )


def semantic_passed(case: ChatCase, result: CaseResult, ordinal: int, as_of: date) -> bool:
    answer = result.response
    match case.expected_kind:
        case "finance":
            return isinstance(answer, ChatAnswer) and finance_passed(case, answer)
        case "data_request":
            return isinstance(answer, ChatAnswer) and data_request_passed(answer)
        case "history":
            return isinstance(answer, ChatAnswer) and history_passed(answer)
        case "forecast" | "risk":
            return isinstance(answer, Coaching) and numeric_passed(case, answer, ordinal, as_of)
        case unreachable:
            assert_never(unreachable)


def model_observation(case: ChatCase, result: CaseResult) -> ModelObservation:
    answer = result.response
    source = answer.wording_source if isinstance(answer, Coaching | ChatAnswer) else None
    fallback = answer.fallback_reason if isinstance(answer, Coaching | ChatAnswer) else None
    role = "evidence_selector" if case.expected_kind == "finance" else "supplementary_writer"
    if fallback == "non_financial_question":
        outcome = "deterministic_scope_response"
        role = "intent_router"
    elif fallback == "twin_not_connected":
        outcome = "deterministic_data_request"
        role = "none"
    elif source == "engine":
        outcome = "engine_answer_no_writer"
        role = "none"
    elif source == "llm" and fallback is None:
        outcome = "accepted"
    elif source == "template":
        outcome = "template_fallback"
    else:
        outcome = "invalid_metadata"
    return ModelObservation(id=case.id, role=role, outcome=outcome, fallback_reason=fallback)


def latency_summary(results: tuple[CaseResult, ...]) -> LatencyScore:
    values = tuple(
        stage.latency_ms
        for result in results
        if (stage := result.http.get("message")) is not None and math.isfinite(stage.latency_ms)
    )
    return LatencyScore(
        observations=len(values),
        minimum_ms=min(values) if values else None,
        median_ms=statistics.median(values) if values else None,
        maximum_ms=max(values) if values else None,
    )


def score(raw: bytes) -> ScoreReport:
    report = RunReport.model_validate_json(raw)
    indexed = {result.id: result for result in report.cases}
    if len(indexed) != len(CASES) or set(indexed) != {case.id for case in CASES}:
        raise ValueError("Report must contain each fixed case exactly once")
    transports = tuple(transport_passed(indexed[case.id]) for case in CASES)
    semantics = tuple(
        semantic_passed(case, indexed[case.id], ordinal, date.fromisoformat(report.as_of))
        for ordinal, case in enumerate(CASES)
    )
    model = tuple(model_observation(case, indexed[case.id]) for case in CASES)
    return ScoreReport(
        report_sha256=hashlib.sha256(raw).hexdigest(),
        suite_version=report.suite_version,
        http=LayerScore(
            passed=sum(transports),
            total=len(transports),
            interpretation="HTTP, isolated history, and stored readback only.",
        ),
        semantic=LayerScore(
            passed=sum(semantics),
            total=len(semantics),
            interpretation=(
                "Deterministic receipt/reference delivery regression; not a human rating or proof "
                "that forecasts match future outcomes."
            ),
        ),
        model_admission=ModelScore(
            accepted=sum(row.outcome == "accepted" for row in model),
            template_fallback=sum(row.outcome == "template_fallback" for row in model),
            deterministic_scope_response=sum(
                row.outcome == "deterministic_scope_response" for row in model
            ),
            deterministic_data_request=sum(row.outcome == "deterministic_data_request" for row in model),
            engine_answer_no_writer=sum(row.outcome == "engine_answer_no_writer" for row in model),
            observations=model,
            interpretation=(
                "An accepted finance answer means the model selected grounded reference IDs; "
                "the server assembled the displayed facts."
            ),
        ),
        message_latency=latency_summary(report.cases),
        cases=tuple(
            CaseScore(id=case.id, transport_passed=transports[index], semantic_passed=semantics[index])
            for index, case in enumerate(CASES)
        ),
    )


def arguments() -> CliArguments:
    parser = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument("report", type=Path)
    _ = parser.add_argument("output", type=Path)
    return CliArguments.model_validate(vars(parser.parse_args()))


def main() -> None:
    options = arguments()
    if "artifacts" not in {part.casefold() for part in options.output.resolve().parts}:
        raise SystemExit("Score output must be written below an artifacts directory")
    result = score(options.report.read_bytes())
    _ = options.output.parent.mkdir(parents=True, exist_ok=True)
    with options.output.open("x", encoding="utf-8") as stream:
        _ = stream.write(result.model_dump_json(indent=2))
    print(  # noqa: T201 - Raw responses remain in the ignored input artifact.
        f"HTTP: {result.http.passed}/{result.http.total}; "
        f"semantic: {result.semantic.passed}/{result.semantic.total}"
    )


if __name__ == "__main__":
    main()
