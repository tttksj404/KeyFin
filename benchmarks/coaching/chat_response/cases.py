"""Public questions and evidence expectations; fixtures and answers stay external."""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class ChatCase:
    id: str
    question: str
    setup: Literal["without_twin", "with_twin"]
    expected_kind: Literal["finance", "history", "forecast", "risk", "data_request"]
    expected_status: str | None = None
    reference_id: str | None = None
    markers: tuple[tuple[str, ...], ...] = ()


CASES = (
    ChatCase(
        "no_twin_compound",
        "복리가 뭐야?",
        "without_twin",
        "finance",
        "answered",
        "compound_interest",
        (("이자에도 이자", "이자에 이자"),),
    ),
    ChatCase(
        "finance_one_year_deposit",
        "1년 만기 예금과 적금 차이가 뭐야?",
        "without_twin",
        "finance",
        "answered",
        "deposits",
        (("목돈",), ("납입 시점", "나누어")),
    ),
    ChatCase(
        "finance_fixed_variable",
        "고정금리와 변동금리는 어떻게 달라?",
        "without_twin",
        "finance",
        "answered",
        "interest_types",
        (("고정금리",), ("변동금리",), ("기준금리", "지표")),
    ),
    ChatCase(
        "finance_emergency_fund",
        "비상금이 뭐야?",
        "without_twin",
        "finance",
        "answered",
        "emergency_fund",
        (("갑작스러운", "예산에 없던"), ("현금성", "여유 자금")),
    ),
    ChatCase(
        "finance_diversification",
        "분산투자가 뭐야?",
        "without_twin",
        "finance",
        "answered",
        "diversification",
        (("여러 자산", "나누어"), ("집중된 위험",)),
    ),
    ChatCase(
        "finance_etf",
        "ETF가 뭐야?",
        "without_twin",
        "finance",
        "answered",
        "etf",
        (("펀드",), ("거래소",)),
    ),
    ChatCase(
        "finance_credit_score",
        "신용점수가 뭐야?",
        "without_twin",
        "finance",
        "answered",
        "credit_score",
        (("신용거래 기록",), ("제때 갚을 가능성", "신용 행동")),
    ),
    ChatCase(
        "finance_unsupported_topic",
        "채권 듀레이션이 뭐야?",
        "without_twin",
        "finance",
        "needs_source",
    ),
    ChatCase(
        "finance_current_rate",
        "지금 가장 금리가 높은 예금은 뭐야?",
        "without_twin",
        "finance",
        "needs_source",
    ),
    ChatCase(
        "finance_out_of_scope",
        "오늘 날씨 어때?",
        "without_twin",
        "finance",
        "out_of_scope",
    ),
    ChatCase(
        "finance_personal_score",
        "내 신용점수는 얼마야?",
        "without_twin",
        "data_request",
        "needs_data",
    ),
    ChatCase(
        "no_twin_spending",
        "이번 달 내 지출은 얼마야?",
        "without_twin",
        "data_request",
        "needs_data",
    ),
    ChatCase(
        "general_compound_interest",
        "복리가 뭐야?",
        "with_twin",
        "finance",
        "answered",
        "compound_interest",
        (("이자에도 이자", "이자에 이자"),),
    ),
    ChatCase(
        "general_deposit_savings",
        "예금과 적금 차이가 뭐야?",
        "with_twin",
        "finance",
        "answered",
        "deposits",
        (("목돈",), ("납입 시점", "나누어")),
    ),
    ChatCase(
        "general_revolving",
        "신용카드 리볼빙이 뭐야?",
        "with_twin",
        "finance",
        "answered",
        "revolving",
        (("이월",), ("이자", "수수료")),
    ),
    ChatCase(
        "general_dsr",
        "DSR이 뭐야?",
        "with_twin",
        "finance",
        "answered",
        "dsr",
        (("원금과 이자", "원리금"), ("소득",)),
    ),
    ChatCase(
        "current_month_spending",
        "이번 달 내 지출은 얼마야?",
        "with_twin",
        "history",
        "answered",
    ),
    ChatCase(
        "forecast_7d_balance",
        "앞으로 7일 잔액 예측해줘",
        "with_twin",
        "forecast",
    ),
    ChatCase(
        "forecast_month_end_balance",
        "이번 달 말까지 잔액 예측해줘",
        "with_twin",
        "forecast",
    ),
    ChatCase(
        "risk_month",
        "이번 달 위험을 알려줘",
        "with_twin",
        "risk",
    ),
)
