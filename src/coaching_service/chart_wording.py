"""The model selects grounded chart facts; financial sentences remain deterministic."""

from typing import Annotated

from pydantic import Field

from coaching_service.chart_contract import ChartResult
from coaching_service.llm_contract import EvidenceInput, FrozenContract, Wording


class ChartFact(FrozenContract):
    id: str
    text: str


class ChartFacts(FrozenContract):
    required_ids: tuple[str, str] = ("period", "total")
    facts: tuple[ChartFact, ...]
    context_notes: tuple[str, ...] = ()


class ChartSelection(FrozenContract):
    selected_fact_ids: Annotated[tuple[str, str, str], Field(description="period, total, and one focus ID")]


def chart_evidence(chart: ChartResult) -> EvidenceInput:
    period = chart.meta
    facts = [
        ChartFact(
            id="period",
            text=(f"예산 기간 {period.period_start}~{period.horizon_end}, 기준일 {period.as_of}입니다."),
        ),
        ChartFact(
            id="total",
            text=(
                f"입력에서 확인된 현재 변동소비 {chart.total_current:,}원, "
                f"기간 말 예상 총소비 {chart.total_forecast:,}원입니다."
                + (" " + period.quality.summary if period.quality and period.quality.summary else "")
            ),
        ),
    ]
    if period.purchase is not None and chart.balance.baseline:
        before = chart.balance.baseline[-1].p50_krw
        after = chart.total_forecast
        if chart.total_budget is None:
            crosses = "전체 예산 정보가 없어 예산 초과 여부는 알 수 없습니다"
        elif after > chart.total_budget >= before:
            crosses = "구매 후 전체 예산을 새로 넘습니다"
        elif after > chart.total_budget:
            crosses = "구매 전부터 전체 예산을 넘은 상태가 이어집니다"
        else:
            crosses = "구매 후에도 전체 예산 안에 머뭅니다"
        facts.append(
            ChartFact(
                id="purchase",
                text=(
                    f"계획 구매 전 기간 말 예상 소비 {before:,}원에서 구매 후 {after:,}원으로 "
                    f"{after - before:,}원 늘며, {crosses}. "
                    "예산·소비 관점이며 계좌 잔액이나 결제 가능 여부는 보장하지 않습니다."
                ),
            )
        )
    for category in sorted(
        chart.categories,
        key=lambda row: row.forecast - row.budget if row.budget is not None else -float("inf"),
        reverse=True,
    ):
        if category.budget is not None:
            delta = category.forecast - category.budget
            state = f"{delta:,}원 초과" if delta > 0 else f"{-delta:,}원 남는"
            facts.append(
                ChartFact(
                    id="category:" + category.id,
                    text=(
                        f"{category.label}의 기간 말 예상 소비는 {category.forecast:,}원으로, "
                        f"예산 대비 {state} 예측입니다."
                    ),
                )
            )
    if len(facts) == 2:
        facts.append(
            ChartFact(id="missing_budget", text="예산 정보가 없어 예산 초과 여부는 비교할 수 없습니다.")
        )
    context_notes = period.quality.notices if period.quality else ()
    if period.purchase_note:
        context_notes = (*context_notes, period.purchase_note)
    return EvidenceInput(
        purpose="chart",
        question=chart.question,
        facts_json=ChartFacts(
            facts=tuple(facts),
            context_notes=context_notes,
        ).model_dump_json(),
    )


def selected_chart_wording(
    evidence: EvidenceInput, raw: str | None, model: str, reason: str | None = None
) -> Wording:
    facts = ChartFacts.model_validate_json(evidence.facts_json)
    by_id = {fact.id: fact.text for fact in facts.facts}
    selected = (*facts.required_ids, facts.facts[2].id)
    problem = reason
    if raw is not None:
        try:
            chosen = ChartSelection.model_validate_json(raw).selected_fact_ids
        except ValueError:
            problem = "invalid_chart_fact_selection"
        else:
            if (
                chosen[:2] != facts.required_ids
                or len(set(chosen)) != 3
                or any(key not in by_id for key in chosen)
            ):
                problem = "invalid_chart_fact_selection"
            else:
                selected = chosen
    elif problem is None:
        problem = "missing_chart_fact_selection"
    return Wording(
        text=" ".join(by_id[key] for key in selected),
        source="template" if problem else "llm",
        model=model,
        fallback_reason=problem,
    )
