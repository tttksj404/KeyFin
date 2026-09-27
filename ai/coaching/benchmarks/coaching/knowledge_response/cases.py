"""Fixed paraphrased questions; no questions are generated from the production aliases."""

from typing import Final

from coaching_service.schemas import Frozen


class Case(Frozen):
    id: str
    question: str
    expected_status: str = "answered"
    reference_id: str | None = None
    personal_topic: str | None = None
    total_krw: int | None = None


CONCEPTS: Final = (
    Case(
        id="compound",
        question="복리로 돈을 맡기면 이전에 받은 이자도 다음 계산에 포함돼?",
        reference_id="compound_interest",
    ),
    Case(
        id="deposits",
        question="목돈을 한번에 넣는 예금과 매달 붓는 적금은 어떤 점이 달라?",
        reference_id="deposits",
    ),
    Case(
        id="revolving",
        question="리볼빙으로 이번 청구액 일부만 내면 남은 빚은 어떻게 되는 거야?",
        reference_id="revolving",
    ),
    Case(id="dsr", question="DSR 심사에서 이자뿐 아니라 갚는 원금도 보는지 궁금해.", reference_id="dsr"),
    Case(
        id="rate-types",
        question="대출의 고정금리와 변동금리 중에서 시장금리가 바뀔 때 같이 움직이는 쪽은 뭐야?",
        reference_id="interest_types",
    ),
    Case(
        id="emergency",
        question="예상하지 못한 의료비에 대비하는 비상금은 왜 별도로 두는 거야?",
        reference_id="emergency_fund",
    ),
    Case(
        id="diversification",
        question="여러 상품으로 분산투자를 하면 실제 종목이 겹치는지도 확인해야 해?",
        reference_id="diversification",
    ),
    Case(
        id="etf",
        question="ETF는 주식처럼 거래되는데 안에는 여러 투자 자산이 들어 있는 거야?",
        reference_id="etf",
    ),
    Case(
        id="credit-score",
        question="대출 전에 보는 신용점수는 어떤 정보를 알려주는 지표야?",
        reference_id="credit_score",
    ),
    Case(
        id="budget",
        question="처음 가계부와 예산 계획을 만들 때 실제로 쓴 돈과 비교해야 하는 이유가 뭐야?",
        reference_id="budget",
    ),
    Case(
        id="needs-wants",
        question="필수 지출인지 선택 지출인지는 사람의 생활 조건에 따라 달라질 수 있어?",
        reference_id="needs_wants",
    ),
    Case(
        id="cash-flow",
        question="현금흐름 예산에서는 월급날과 청구서를 내는 날을 왜 같이 살펴봐?",
        reference_id="cash_flow_budget",
    ),
    Case(
        id="net-worth",
        question="자산이 늘어도 대출이 같이 늘면 순자산이 그대로일 수 있는 거야?",
        reference_id="net_worth",
    ),
    Case(
        id="loan-components",
        question="대출 원금과 이자를 구분해서 보면 각각 무엇을 갚는 돈이야?",
        reference_id="loan_principal_interest",
    ),
    Case(
        id="amortization",
        question="원리금 분할상환을 하면 매번 납입한 돈 전부가 원금을 줄여주는 건 아니야?",
        reference_id="amortization",
    ),
    Case(
        id="debt-order",
        question="빚을 갚을 때 눈덩이 방식과 고금리 우선 방식은 어떤 기준으로 순서를 정해?",
        reference_id="debt_repayment_methods",
    ),
    Case(
        id="early-repay",
        question="대출을 만기보다 일찍 갚는데도 중도상환수수료가 생길 수 있어?",
        reference_id="early_repayment",
    ),
    Case(
        id="rate-request",
        question="취업이나 승진 후 금리인하요구권을 신청하면 금리가 반드시 내려가?",
        reference_id="rate_reduction_request",
    ),
    Case(
        id="bonds",
        question="채권을 산다는 건 발행자에게 돈을 빌려주고 돌려받을 권리를 갖는 거야?",
        reference_id="bonds",
    ),
    Case(
        id="duration",
        question="듀레이션이 긴 채권은 금리가 움직일 때 가격이 더 민감할 수 있어?",
        reference_id="bond_duration",
    ),
    Case(
        id="credit-risk",
        question="채권 발행 기업이 돈을 못 갚는 위험을 신용위험이라고 하는 거야?",
        reference_id="bond_credit_risk",
    ),
    Case(
        id="liquidity",
        question="유동성 위험이 있다는 건 급하게 팔 때 원하는 가격에 못 팔 수도 있다는 뜻이야?",
        reference_id="liquidity_risk",
    ),
    Case(
        id="fees",
        question="펀드 총보수와 거래 수수료를 살펴보는 게 실제 수익에 왜 중요해?",
        reference_id="fund_fees",
    ),
    Case(
        id="nav",
        question="ETF의 시장가격이 순자산가치와 똑같지 않을 수도 있어?",
        reference_id="nav_market_price",
    ),
    Case(
        id="inflation",
        question="물가가 오르면 명목금리와 실질금리 중 구매력 변화를 보는 데 어떤 걸 참고해?",
        reference_id="real_interest",
    ),
    Case(
        id="deductible",
        question="보험료를 계속 냈어도 사고가 나면 자기부담금을 또 내야 할 수 있어?",
        reference_id="insurance_deductible",
    ),
    Case(
        id="exclusions",
        question="보험에 가입했어도 면책이나 보장 제외 조항 때문에 보험금을 못 받을 수 있어?",
        reference_id="insurance_exclusions",
    ),
)
SCOPE: Final = (
    Case(
        id="current-rates",
        question="오늘 가입할 수 있는 예금 중 이율이 제일 높은 상품을 정확한 금리와 함께 골라줘.",
        expected_status="needs_source",
    ),
    Case(
        id="non-financial",
        question="내일 서울 날씨랑 우산이 필요한지 알려줘.",
        expected_status="out_of_scope",
    ),
    Case(
        id="unconnected-account",
        question="지금 내 계좌 잔액은 얼마야?",
        expected_status="needs_data",
        personal_topic="accounts",
    ),
)
FOLLOWUP: Final = Case(id="followup", question="그럼 더 설명해줘.", reference_id="compound_interest")
PERSONAL: Final = (
    Case(
        id="accounts", question="제 계좌 잔액 합계 알려주세요", personal_topic="accounts", total_krw=1300000
    ),
    Case(id="assets", question="내 자산 현황 보여줘", personal_topic="assets", total_krw=1550000),
    Case(id="debts", question="내 부채 총액은 얼마야?", personal_topic="debts", total_krw=500000),
    Case(id="insurance", question="내 보험료는 얼마야?", personal_topic="insurance", total_krw=65000),
    Case(id="income", question="현재 월 소득 알려줘", personal_topic="income", total_krw=3050000),
    Case(id="fixed-costs", question="월 고정비 합계 보여줘", personal_topic="fixed_costs", total_krw=547000),
    Case(id="payments", question="예정 결제 금액은 얼마야?", personal_topic="payments", total_krw=90000),
    Case(id="goals", question="내 금융 목표 목록 보여줘", personal_topic="goals"),
)
UNSUPPORTED: Final = Case(
    id="institution-filter",
    question="우리은행 계좌 잔액만 알려줘",
    expected_status="needs_clarification",
    personal_topic="accounts",
)
