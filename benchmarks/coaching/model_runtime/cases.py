"""Small public prompt suite for actual model candidates, separate from customer data."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class RouteCase:
    """A single model-owned route decision with a fully known expected mode."""

    id: str
    question: str
    mode: Literal["review", "risk", "forecast", "finance", "history", "personal", "other"]


@dataclass(frozen=True, slots=True)
class FinanceCase:
    """A constrained approved-fact selection, never a request for free-form advice."""

    id: str
    question: str
    status: Literal["answered", "needs_source", "needs_data", "out_of_scope"]
    required_fact_ids: tuple[str, ...] = ()
    required_missing: tuple[Literal["latest_source", "contract_terms", "tax_terms", "calculation"], ...] = ()


ROUTE_CASES: tuple[RouteCase, ...] = (
    RouteCase("route_finance_definition", "DSR이 뭐야?", "finance"),
    RouteCase("route_finance_term", "1년 만기 예금과 적금 차이가 뭐야?", "finance"),
    RouteCase("route_history", "지난달 외식비는 얼마 썼어?", "history"),
    RouteCase("route_personal", "내 계좌 잔액은 얼마야?", "personal"),
    RouteCase("route_forecast", "앞으로 7일 잔액을 예측해줘.", "forecast"),
    RouteCase("route_risk", "다음 달에 잔액이 부족할 위험이 있을까?", "risk"),
    RouteCase("route_review", "내 소비 습관을 점검해줘.", "review"),
    RouteCase("route_other", "오늘 날씨가 어때?", "other"),
)

FINANCE_CASES: tuple[FinanceCase, ...] = (
    FinanceCase("finance_dsr", "DSR의 의미와 계산에 들어가는 항목을 설명해줘.", "answered", ("dsr",)),
    FinanceCase(
        "finance_deposits", "예금과 적금은 돈을 넣는 방식이 왜 다른지 설명해줘.", "answered", ("deposits",),
    ),
    FinanceCase(
        "finance_fixed_variable", "고정금리와 변동금리는 어떤 차이가 있어?", "answered", ("interest_types",),
    ),
    FinanceCase(
        "finance_current_rate", "지금 가장 금리가 높은 예금은 뭐야?", "needs_source", (), ("latest_source",),
    ),
    FinanceCase(
        "finance_tax_calculation", "예금 이자를 세후로 정확히 계산해줘.", "needs_source", (),
        ("tax_terms", "calculation"),
    ),
    FinanceCase("finance_unknown", "채권 듀레이션이 뭐야?", "needs_source"),
)
