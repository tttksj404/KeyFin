"""등록 현황의 금액은 Python 정수로 계산하고 LLM 숫자는 사용하지 않는다."""

from typing import Final, assert_never

from coaching_service.personal_contract import PersonalContext, PersonalRow, PersonalSummary, PersonalTopic

LABELS: Final = {
    "accounts": "보고된 계좌 잔액",
    "assets": "보고된 비계좌 자산가액",
    "debts": "보고된 대출 원금",
    "insurance": "등록된 월 보험료",
    "income": "등록된 월 소득",
    "fixed_costs": "등록된 월 고정비",
    "payments": "기준일 이후 등록된 카드 청구액",
    "goals": "등록된 목표",
    "budget": "봉투 예산 잔액",
}


def finish(summary: PersonalSummary) -> PersonalSummary:
    """부분 범위를 전체 재산/총부채로 오인하지 않도록 범위와 기준일을 답에 포함한다."""
    if summary.status != "answered":
        return summary
    label = summary.total_label or "등록 항목"
    detail = (
        f"{label} 합계는 {summary.total_krw:,}원입니다."
        if summary.total_krw is not None
        else label + "입니다."
    )
    rows = " ".join(
        f"{row.label}: {row.amount_krw:,}원"
        + (f" / 목표 {row.target_krw:,}원" if row.target_krw is not None else "")
        + (f" ({row.due_date.isoformat()})" if row.due_date is not None else "")
        + "."
        for row in summary.rows
    )
    coverage = (
        "backend가 해당 항목을 모두 보고했다고 표시했습니다."
        if summary.coverage == "complete"
        else ("연결된 일부 항목의 합계이며 전체 보유 현황으로 확정할 수 없습니다.")
    )
    return summary.model_copy(
        update={
            "text": " ".join(
                (
                    f"{summary.as_of} 기준 {detail}",
                    rows,
                    coverage,
                    *summary.warnings,
                )
            ).strip()
        }
    )


def context_summary(context: PersonalContext, topic: PersonalTopic) -> PersonalSummary:
    """월 소득/고정비는 backend의 등록 월 금액이며 실현 거래 집계나 예측값이 아니다."""
    match topic:
        case "income" | "fixed_costs":
            section = context.income if topic == "income" else context.fixed_costs
            coverage = section.coverage
            rows = tuple(
                PersonalRow(id=r.id, label=r.label, amount_krw=r.monthly_amount_krw) for r in section.items
            )
            warnings = ("실제 입출금 합계가 아니라 backend에 등록된 월 금액입니다.",)
        case "insurance":
            coverage = context.insurance.coverage
            rows = tuple(
                PersonalRow(
                    id=r.id,
                    label=r.label,
                    amount_krw=r.monthly_premium_krw,
                    coverage_amount_krw=r.coverage_amount_krw,
                )
                for r in context.insurance.items
            )
            warnings = (
                (
                    "보장액은 보장 조건이 겹칠 수 있어 합산하지 않습니다. "
                    "보험 보장 적정성 평가는 포함하지 않습니다."
                ),
            )
        case "goals":
            coverage = context.goals.coverage
            rows = tuple(
                PersonalRow(
                    id=r.id,
                    label=r.label,
                    amount_krw=r.saved_krw,
                    target_krw=r.target_krw,
                    due_date=r.target_date,
                )
                for r in context.goals.items
            )
            warnings = (
                (
                    "목표별 적립액이며 목표 간 중복 적립 여부를 알 수 없어 합산하지 않습니다. "
                    "달성 가능성 예측은 아닙니다."
                ),
            )
        case "accounts" | "assets" | "debts" | "payments" | "budget":
            return missing(topic)
        case unreachable:
            assert_never(unreachable)
    if coverage == "unknown" or (coverage == "partial" and not rows):
        return missing(topic)
    return finish(
        PersonalSummary(
            topic=topic,
            status="answered",
            text="",
            coverage=coverage,
            as_of=context.as_of,
            total_krw=None if topic == "goals" else sum(row.amount_krw for row in rows),
            total_label=LABELS[topic],
            rows=rows,
            source_system=context.source_system,
            source_record_id=context.source_record_id,
            provenance=context.provenance,
            received_at=context.received_at,
            revision=context.revision,
            warnings=(*warnings, "이 등록 현황은 조회용이며 예측 계산에 반영되었다는 뜻은 아닙니다."),
        )
    )


def missing(topic: PersonalTopic) -> PersonalSummary:
    return PersonalSummary(
        topic=topic,
        status="needs_data",
        text=f"{LABELS[topic]} 자료가 연결되지 않았거나 보고 범위가 확인되지 않았습니다. "
        "모르는 금액을 0원으로 계산하지 않습니다.",
    )
