"""Conservative no-model routing for clear personal FDT forecast, risk, and review requests."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal
from typing import Final, Literal

from coaching_service.knowledge_retrieval import compact
from coaching_service.personal_query import (
    connector_fragments,
    filtered_personal_topic,
    select_personal_topic,
    select_personal_topics,
)
from coaching_service.spending_history import history_question, supports_spending_question

AnalysisRoute = Literal["forecast", "risk", "review"]
LookupRoute = Literal["history", "personal"]


@dataclass(frozen=True, slots=True)
class NaturalGoal:
    """A target amount that a deliberately narrow Korean grammar can safely supply.

    The parser is an admission gate, not a financial-language model.  It never
    infers a deadline, reserve, probability threshold, or action from prose; the
    caller must still resolve the calendar period and execute the typed FDT goal
    operation.  Keeping only the explicitly stated amount here makes the shortcut
    auditable and prevents a friendly-sounding question from silently becoming an
    optimization or investment request.
    """

    target_krw: int


@dataclass(frozen=True, slots=True)
class NaturalWhatIf:
    """One explicit, variable-expense reduction suitable for a paired FDT branch.

    This is intentionally narrower than a general scenario parser.  It admits
    only a single percentage reduction, a supported future period, and either
    one known envelope or the aggregate variable-expense multiplier.  It cannot
    infer income, fixed-cost, investment, card, or transaction-level changes.
    """

    reduction: float
    envelope: str | None

    def scenario(self) -> dict[str, object]:
        """Produce the existing vendor request shape without carrying prose into FDT."""
        if self.envelope is not None:
            return {"expense_reductions": {self.envelope: self.reduction}}
        return {"expense_multiplier": 1 - self.reduction}

# A definition-style question must remain in the finance-knowledge route even
# when it uses a word such as risk or forecast.  ``어떻게`` is intentionally
# absent because a personal future question can naturally ask how a balance
# will change.
_DEFINITION_LANGUAGE: Final = re.compile(r"(?:뭐|무엇|뜻|의미|설명|차이|원리|방법|특징|장단점|왜)")
# Everyday nouns for the same balance or spending ("남은 예산", "남는 금액", "생활비",
# "외식비", "쓰는 돈") count as forecast targets; a future marker is still required.
_FORECAST_TARGETS: Final[tuple[str, ...]] = (
    "잔액", "잔고", "소비", "지출", "현금흐름", "남을현금", "예산", "금액", "생활비", "비용", "쓰는돈",
    "쓸돈", "외식비", "식비", "교통비", "쇼핑",
)
# "월말에 돈 얼마 남을까?" asks the same end-of-month balance as "월말 잔액 얼마 남을까".
# "돈" is too common to be a forecast noun on its own ("향후 흐름이 아니라 … 돈으로"),
# so it counts only with a strong future marker and a remaining-amount verb.
_MONEY_LEFT_TERMS: Final[tuple[str, ...]] = ("남을", "남아", "남는", "남겠", "남아있", "남은거", "남은돈")
_FUTURE_MARKERS: Final[tuple[str, ...]] = ("앞으로", "이번달", "이달", "월말", "다음달")
_STRONG_FUTURE_MARKERS: Final[tuple[str, ...]] = (
    "앞으로", "월말", "이번달말", "이달말", "다음달", "향후", "말까지", "다음급여전",
    "달끝나면", "다쓰면", "다쓰고나면", "월급전", "월급날", "급여일",
)
# "얼마 나올 것 같아?", "얼마까지 갈 것 같아?", "이 페이스면" ask for the same projection
# as "예측해줘"; they still need a future marker ("이번 달", "월말") to count.
_FORECAST_TERMS: Final[tuple[str, ...]] = (
    "예측", "예상", "전망", "것같", "거같", "나올까", "나올지", "들까", "찍을", "페이스면",
    "속도면", "속도로",
)
_FORECAST_PATH_TERMS: Final[tuple[str, ...]] = ("경로", "흐름", "궤적", "전개", "변하는", "변화")
_IMPLICIT_FORECAST_TERMS: Final[tuple[str, ...]] = ("얼마", "남을", "남아")
# A future-tense spend question ("이번달 얼마 쓸까") is a spend forecast even
# without a balance noun.  Only committed future-spend forms are listed; bare
# "쓸" is excluded because it collides with 쓰다 (write/use) and 쓸쓸/쓸데.  A
# future marker is still required in the branch below, so a non-financial "쓸까"
# alone never routes here.
_SPEND_FORECAST_TERMS: Final[tuple[str, ...]] = (
    "쓸까", "쓸지", "소비할", "지출할", "쓰게될", "쓰게되", "쓸것같", "쓸거같", "속도로쓰", "페이스로쓰",
    "이대로쓰",
)
_RISK_SIGNALS: Final[tuple[str, ...]] = (
    "이번달",
    "이달",
    "월말",
    "앞으로",
    "부족",
    "잔액",
    "소비",
    "지출",
    "현금흐름",
    "필수생활비",
)
# "예산 위험해?" names neither a period nor a balance noun, so the broad risk
# signals miss it and the model sent it to a generic review (live 2026-09-23). Only
# this exact short question is admitted; anything with an amount, a purchase, a
# plan, a how-to or another subject keeps its existing route.
_BUDGET_RISK_QUESTION: Final = re.compile(
    r"(?:내|제|나의|저의)?(?:이번달|이달)?예산(?:이|은|는)?(?:지금)?"
    r"위험(?:해|한가|할까|한지|하니|해요|한가요|할까요|하지않아|하진않아)?"
    r"(?:알려줘|알려주세요|봐줘|확인해줘|확인해주세요)?[?!.\uff1f]*"
)
# "모자라다" (to fall short) conjugates to 모자라/모자란/모자랄/모자랐; the bare
# stem "모자" is deliberately excluded because it collides with 모자 (hat), whose
# case markers (모자가/모자를/모자는) never produce these insufficiency endings.
_RISK_OUTCOME_TERMS: Final[tuple[str, ...]] = ("부족", "모자라", "모자란", "모자랄", "모자랐", "감당", "적자")
# "이번 달 위험 요소 뭐 있어?", "이번 달 리스크 분석 부탁해", "이번 달 적자 리스크": the
# user's own period risk, even with 뭐 (listing, not a definition).
_PERIOD_RISK: Final = re.compile(r"(?:이번달|이달|월말|앞으로|남은기간).{0,12}(?:위험|리스크|적자)")
_LISTING: Final = re.compile(r"뭐(?:가)?있(?:어|나|을까|는지|지)")
# A product used when money runs short, somebody else's or the economy's red ink, or how to cope
# ("돈 모자랄 때 리볼빙 써도 돼?", "금리가 마이너스 되면", "적자가 나면 어떻게 해야 해?").
_OVERRUN_NOT_OWN: Final = re.compile(
    r"리볼빙|대출|비상금|신용카드|할부|마이너스통장|카드론|현금서비스|써도|받아도|만들면"
    r"|금리|수익률|성장률|경제|나라|국가|정부|회사|기업|어떻게해야|려면|방법|대처|대책"
)
_PAST_TENSE: Final = re.compile(r"지난달|저번달|어제|였어|었지|었어|였지|었었")
# The amount at this month's end: "이번 달 다 쓰고 나면 얼마", "이번 달 끝나는 시점 잔액 얼마".
_MONTH_END_AMOUNT: Final = re.compile(
    r"(?:이번달|이달|월말까지|이번달말까지)(?:다쓰(?:고나면|고|면)|끝나면|끝나는시점|끝까지가면)"
    r".{0,10}(?:얼마|잔액|총액|남)"
)
# This month's own budget asked to be looked over as a whole.
_PERIOD_REVIEW: Final = re.compile(
    r"(?:이번달|이달|요즘|지금)(?:의)?(?:전체)?(?:예산|지출|소비|재정|가계|돈관리|살림|예산상황|상황)(?:상황|상태)?"
    r"(?:을|를|이|가|은|는)?(?:관리|컨디션)?"
    r"(?:전체적으로|전반적으로|전반적|전체|좀|한번)?"
    r"(?:진단|점검|평가|분석|체크(?!카드|리스트)|검토|봐줘|잘되고|어때|어떤지|어떤데)"
    r"(?:해줘|해줄래|해봐|해주세요|좀|해|요|줘|있어|있나|있니|할래)*$"
)
# Going over later, not already over: "예산 초과 가능성", "초과할까봐", "적자 날 수 있어", "마이너스 될까".
_FUTURE_OVERRUN: Final = re.compile(
    r"(?:초과|오버)(?:가|를)?(?:할|될|하게될|할까|될까|할거|될거|할것|될것|가능성|확률|위험)"
    r"|적자(?:가|를)?(?:날|나|낼|볼|일까|될|가능성|확률)"
    r"|마이너스(?:가|로)?(?:될|날|나지|나겠|나면|가능성|확률)"
    r"|(?:예산|돈|생활비|통장|봉투|잔고)(?:이|가)?펑크(?:가)?(?:날|나)"
    r"|(?:예산|봉투)(?:을|를|이)?(?:넘을까|넘길까|넘어갈까)"
    r"|(?:봉투|예산|통장|생활비)(?:이|가)?(?:터질|빵꾸)|쪼들릴|못낼까|못갚을까"
    r"|(?:모자랄|부족할|모자라게될|부족해질)(?:확률|가능성|것같|거같|까봐)"
    r"|음수(?:가|로)?(?:될|날)"
    r"|(?:돈|잔고|잔액|통장|생활비)(?:이|가)?(?:떨어질|바닥날|바닥나|모자랄|부족할|모자라지않을까|부족하지않을까)"
    r"|넘을(?:확률|가능성|것같|거같|까봐)|(?:이대로|이추세|추세대로|지금추세)(?:로|면)?(?:가면)?.{0,6}위험"
)
# "주말에 뭐하지?" asks what to do, not what something means.
_ACTIVITY_ASK: Final = re.compile(r"뭐(?:하지|할까|하니|해(?![야줘주서도봐보라])|먹지|먹을까|사지)")
_INVESTMENT_SUBJECT: Final = re.compile(r"위험자산|안전자산|투자|자산배분|포트폴리오")
_OWN_BUDGET_SUBJECT: Final = re.compile(
    r"이번달|이달|월말|남은기간|적자|잔액|예산|생활비|봉투|카드값|부족|모자라|모자랄|버틸|버티|남은돈|가진돈"
    r"|(?<!주식)(?<!증권)(?<!투자용)(?<!투자)(?<!코인)(?<!isa)(?:통장|계좌)|(?:내|제|우리|나의|저의)돈"
    r"|(?<!투자할)(?<!투자용)(?<!주식)(?<!코인)(?<!투자)돈(?!(?:이|을)?(?:되|버|벌))"
)
# A user can contrast an earlier risk-only view with the requested balance path.
# These compacted phrases are an admission condition for the no-model forecast
# route; other mixed risk/forecast language deliberately remains model-routed.
_RISK_DEPRIORITIZED_FOR_PATH: Final[tuple[str, ...]] = (
    "위험한마디보다",
    "위험여부보다",
    "위험분석보다",
    "위험만이아니라",
    "위험보다",
    "리스크보다",
    "리스크만이아니라",
    "적자보다",
)
# "예산 괜찮을까요?", "향후 예산 괜찮아?", "남은 기간 돈 버틸 수 있을까?" ask how the
# budget holds up from here on: the period review answers that. The model router sent
# them anywhere from the budgeting concept to out of scope. A future marker is needed
# for the present tense ("예산 괜찮아?" is the ledger balance check).
# The budget noun must be the direct subject of the outcome ("예산 괜찮을까", "생활비
# 이번 달 버틸 수 있을까", "버틸 만큼 예산 있어?"); a verb in between makes it another
# question ("돈 빌려줘도 괜찮을까", "돈까스 먹어도 괜찮을까", "대출 받아도 괜찮을까").
_OUTCOME_SPAN: Final = (
    r"(?:이번달|이달|남은기간|앞으로|향후|월말까지|이번달말까지|이달말까지|끝까지|계속|동안|좀|운영"
    r"|지금처럼쓰면|이대로쓰면|이속도면|이페이스면|으로|로)*"
)
_OUTCOME_VERB: Final = (
    r"(?:괜찮을까|괜찮을지|괜찮겠|버틸수있을까|버틸까|버틸수있을지|버틸수있겠|버틸만해|버티겠|버티기가능|버틸수있어)"
)
_BUDGET_OUTCOME: Final = re.compile(
    rf"(?:예산|봉투|생활비|돈)(?:이|은|는|가|으로|로)?{_OUTCOME_SPAN}{_OUTCOME_VERB}"
    r"|(?:향후|앞으로|남은기간|월말까지|이번달말까지|이달말까지|말까지|다음주까지|이번주까지|주말까지|[0-9]{1,2}일까지)"
    r"(?:예산|봉투|생활비|돈)(?:이|은|는|가)?"
    r"(?:괜찮아|괜찮나|괜찮은|여유있어|" + _OUTCOME_VERB[3:-1] + r")"
    r"|버틸(?:수있을)?(?:만큼의?|정도의?)?(?:예산|돈|생활비)(?:이|은|는|가)?(?:있어|있을까|남았어|될까)"
)
# "이번 달 버틸 수 있을까?", "월말까지 버틸 수 있을까?": the period alone names this budget,
# unless a purchase is being asked about ("치킨 시키면 이번 달 괜찮을까?").
_PERIOD_ONLY_OUTCOME: Final = re.compile(
    rf"(?:이번달|이달|남은기간|월말까지|이번달말까지|이달말까지)(?:은|는|도)?{_OUTCOME_VERB}"
)
_OUTCOME_BLOCK: Final = re.compile(r"대출|빌려|빌리|넣어|넣으|먹어|사도|사면|투자")
# A review must name both the user's own observed finances and an FDT review action.
# This intentionally excludes broad prompts such as "소비 습관을 점검하는 방법" and
# calendar phrases such as "내년 소비"; those retain the model route.
_PERSONAL_REVIEW_TARGET: Final = re.compile(r"(?:내|나의)(?:소비습관|금융상태|현금흐름|소비|지출|재정)")
_REVIEW_ACTIONS: Final[tuple[str, ...]] = ("점검", "분석", "진단", "검토")
# A second, narrower review admission: the user names an artifact (a definition,
# label, or record) and asks to read/check it while explicitly denying that they
# want a computation re-run. All three signals are required so that a genuine
# compute request ("잔액 예측해줘") never falls through this branch; see
# scratchpad/SPEC-review-gate.md for the exact catalog grounding and yield.
_ARTIFACT_NOUN: Final = re.compile(r"의미|뜻|기준|단위|용어|집계|표기|표시|안내|자료|기록|설명")
_ARTIFACT_READ: Final = re.compile(r"확인|점검|짚|이해|읽|살펴|구별|대조|어느날짜")
_COMPUTE_NEGATED: Final = re.compile(
    r"계산(?:을)?(?:없이|새로돌리지말|하지말|해달라는뜻은아니|하라는(?:뜻|요청|건)?(?:은|이)?아니)"
    r"|(?:미래|향후|이후|앞으로의?)(?:잔고|잔액|흐름|경로|예측|전망|계산)(?:이|가|는|은)?아니라"
    r"|단정(?:하라는|해달라는|하지말)"
    r"|(?:진단|평가|판정)(?:처럼|으로)?(?:설명|말)하(?:지않|지말)"
)


def _artifact_review(normalized: str) -> bool:
    """Admit a review only when an artifact noun, a read verb, and a negated compute request all match.

    All three signals must be present in the same turn.
    """
    return (
        _ARTIFACT_NOUN.search(normalized) is not None
        and _ARTIFACT_READ.search(normalized) is not None
        and _COMPUTE_NEGATED.search(normalized) is not None
    )
_COACHING_REFERENCE: Final = re.compile(r"(?:이|이전|방금)(?:코칭|알림)")
_COACHING_REASON: Final = re.compile(r"(?:이유|근거|왜)")
_CURRENT_ENVELOPE_BALANCE: Final = re.compile(r"(?:현재|지금).*(?:봉투).*(?:잔액|남은(?:금액|돈)?)")
# A stored receipt can answer only the original cause and present-ledger balance.
# Asking for a risk assessment, probability, or future outcome requires the normal
# numeric FDT path even if the question also refers to the original coaching.
_RECOMPUTE_FOLLOW_UP_MARKERS: Final[tuple[str, ...]] = (
    "예측",
    "앞으로",
    "다음달",
    "월말",
    "위험",
    "리스크",
    "확률",
)
_GOAL_AMOUNT: Final = re.compile(
    r"(?<![\d,.])(?P<amount>(?:\d{1,3}(?:,\d{3})+|\d+))(?P<unit>만원|원)"
    # A following Hangul syllable (e.g. a verb such as "모을" in "100만원 모을 수
    # 있어") is admitted alongside the explicit particle set so a natural goal
    # question without a particle after the amount still yields exactly one
    # amount. The amount count and the other goal gates below remain unchanged.
    r"(?=$|[가-힣]|(?:을|를|이|가|은|는|에|의|으로|까지|만|도|보다|부터|에서|에게|한테|목표|[.,?!]))"
)
_GOAL_WORDS: Final[tuple[str, ...]] = (
    "목표", "모으", "모을", "모은", "모여", "모울", "저축", "저금", "달성", "만들", "모이", "모아",
    "세이브", "마련", "남길", "남겨",
)
_GOAL_FEASIBILITY: Final = re.compile(
    r"가능|될까|될수|할수|있을까|있을수|도달(?:할)?수|달성(?:할)?수|모을수|채울수|무리|되나|될지|되겠|괜찮을까"
    r"|모을까|모일까|모여있을까|모울수|남길수|어떨까|달성[?!.~]*$"
    r"|(?:모으|모을|저축하|저금하|마련하)려면(?:요)?[?!.~]*$|현실적|(?:저축|저금|모으기|달성)[?!.~]*$"
    r"|(?:모으|모아|저축하|저금하|마련하|세이브하)고싶(?:은데|어)(?:요)?[?!.~]*$"
    r"|모이나|모이려나|모아질까|어려울까|힘들까|빡셀까|확률"
)
# Already saved or spent ("30만원 마련했는데", "100만원 모은 거"), not a target ahead.
_GOAL_PAST: Final = re.compile(r"마련했|세이브했|저금했|저축했|모았|모은거|모은것|모은돈")
_GOAL_PERIOD: Final = re.compile(
    r"(?:앞으로)?\d{1,3}일|이번달|이달|월말|다음달|\d{4}-\d{2}-\d{2}"
)
_GOAL_DISALLOWED: Final = re.compile(
    r"투자|매수|매도|상품|추천|방법|어떻게|계획(?:을|을?세우|을?짜)|설정(?:해|하)|세워"
    # "뭐부터 줄여야 해?", "적금이 나을까 예금이 나을까?" ask advice or a product, not the odds.
    r"|뭐부터|뭘|무엇|줄여야|줄일까|어떤|무슨|자랑"
    r"|(?:적금|예금|통장|파킹|cma)(?:이|가|은|는|을|를|에|으로|로)?(?:나을|좋을|좋아|괜찮|들어야|들까|넣|두고|어때|추천)"
)
_MAX_NATURAL_GOAL_KRW: Final = 10_000_000_000
# Money coming in or billed ("월급 300만원 들어오면 저금 가능할까?", "카드값 50만원 나왔는데") or
# parked in a product is not the amount to save.
_GOAL_NOT_TARGET: Final = re.compile(r"월급|급여|용돈|들어오면|받으면|나왔는데|청구|카드값|연회비|넣어|예치")
_WHAT_IF_HALF: Final = re.compile(r"절반|반으로|반만")
_WHAT_IF_PERCENT: Final = re.compile(r"(?<!\d)(?P<percent>\d{1,2})\s*(?:%|퍼센트|프로|퍼)(?!\d)")
# "덜 쓰면", "아끼면", "컷하면", "줄였을 때" reduce spending the same way as "줄이면".
_WHAT_IF_REDUCTION: Final = re.compile(
    r"줄(?:이|여|였|인|일)|감소|덜쓰|덜쓸|적게쓰|적게쓸|아끼|아낀|컷|절약|절감|삭감|감축|축소|세이브"
)
_WHAT_IF_OUTCOME: Final = re.compile(
    r"어떻게|얼마|변하|달라|될까|영향|차이|비교|변화|효과|나아|이득|바뀌|시뮬레이션|결과|어때|뭐가|남는|남을|남아"
    r"|도움(?:이)?(?:될|돼|되)|괜찮|충분|여유|좋을까|나을까|잔액|잔고"
)
_WHAT_IF_DISALLOWED: Final = re.compile(
    r"고정(?:비|지출)|수입|소득|대출|보험|카드|이자|투자|매수|매도|상품|추천|방법|계획|설정"
    # how-to, income or prices falling, a sale, or a product decision is not a spending cut
    r"|려면|해야|월급|급여|연봉|물가|상승률|금리|세일|(?:%|퍼센트|프로|퍼)할인|할인되는|정기권|적금|예금|경제|다들"
    r"|(?<!의료·)(?<!의료)건강에"
)
# The cut already happened ("지난달 외식 20% 줄였더니 얼마 아꼈어?"): a lookup, not a branch.
_WHAT_IF_PAST: Final = re.compile(
    r"지난달|저번달|작년|지난해|어제|였더니|었더니|았더니|줄인효과|아낀결과|효과가있었|감소했|늘었|올랐"
    r"|었으면|았으면|였으면|줄였는데|줄였으니|아꼈"
)
# A calendar the what-if engine cannot take; "앞으로 30일 동안" is still a rolling window.
_WHAT_IF_NON_MONTH: Final = re.compile(
    r"이번주|다음주|지난주|주말|[0-9]+개월|[0-9]+일(?:까지|에)|(?<!이번)(?<!이)달동안|방학|연간|[0-9]+년"
)
# The rate is the cut itself ("20% 줄이면", "20%만 아끼면"), not a share or a growth rate.
_WHAT_IF_RATE_CUT: Final = re.compile(
    r"(?:(?<!\d)\d{1,2}\s*(?:%|퍼센트|프로|퍼)|절반|반)(?:정도|만|씩|를|을|쯤|로|으로|은|는|가량){0,2}"
    r"(?:줄|감소|감축|덜|적게|아끼|아낀|컷|절약|절감|삭감|축소|세이브|낮추|낮춰)"
)
_WHAT_IF_AMOUNT: Final = re.compile(r"\d[\d,]*\s*(?:만원|만\s*원|원)")
# "외식 20% 줄이면?" ends on the reduction itself; the outcome is what it asks.
_WHAT_IF_BARE: Final = re.compile(
    r"(?:줄이면|줄인다면|아끼면|아낀다면|덜쓰면|절약하면|절감하면|삭감하면|컷하면|감소하면|감소한다면|세이브하면"
    r"|적게쓰면|줄여보면|아껴보면)"
    r"(?:요|은|는)?[?!.~]*$"
)
_WHAT_IF_GENERIC_EXPENSE: Final = re.compile(r"(?:변동)?(?:소비|지출)")
_WHAT_IF_ENVELOPE_ALIASES: Final[dict[str, str]] = {
    "외식비": "외식",
    "외식": "외식",
    # The engine's mapping.py folds the everyday word 식비 into the 외식 envelope,
    # so accept it as an alias here too (all three collapse to the same envelope,
    # keeping the single-envelope guard satisfied even when 식비 is a substring
    # of 외식비).
    "식비": "외식",
    "교통비": "교통비",
    "의료·건강": "의료·건강",
    "의료건강": "의료·건강",
    "취미·여가": "취미·여가",
    "취미여가": "취미·여가",
    "쇼핑비": "쇼핑",
    "쇼핑": "쇼핑",
    "편의점·마트·잡화": "편의점·마트·잡화",
    "편의점마트잡화": "편의점·마트·잡화",
    "마트": "편의점·마트·잡화",
    "편의점": "편의점·마트·잡화",
    "기타": "기타",
    "의료비": "의료·건강",
    "병원비": "의료·건강",
    "여가비": "취미·여가",
    "취미비": "취미·여가",
    "취미": "취미·여가",
    "배달": "외식",
    "배달비": "외식",
    "커피값": "외식",
    "택시": "교통비",
    "택시비": "교통비",
    "버스비": "교통비",
    "마트비": "편의점·마트·잡화",
    "편의점비": "편의점·마트·잡화",
}


def natural_goal(question: str) -> NaturalGoal | None:
    """Extract one explicit goal amount only from a clear feasibility question.

    A user can ask a normal goal question without knowing the API's structured
    ``analysis`` payload.  This accepts a single Arabic-numeral KRW amount, a
    supported future period marker, a goal word, and a feasibility expression.
    It rejects multiple values and advisory/product/investment questions rather
    than guessing which number or operation the user meant.
    """
    # ``compact`` deliberately erases punctuation for broad intent matching, but
    # a KRW parser must preserve commas in numbers and hyphens in ISO dates.
    normalized = re.sub(r"\s+", "", unicodedata.normalize("NFKC", question).lower())
    if (
        not normalized
        or _GOAL_DISALLOWED.search(normalized) is not None
        or _GOAL_PAST.search(normalized) is not None
        # "다음 달 월급 받으면 90만원 모을 수 있을까?" still names the amount to save.
        or (_GOAL_NOT_TARGET.search(normalized) is not None and _GOAL_AMOUNT_VERB.search(normalized) is None)
        or not any(word in normalized for word in _GOAL_WORDS)
        or _GOAL_FEASIBILITY.search(normalized) is None
        or _GOAL_PERIOD.search(normalized) is None
        or has_buy_verb(question)  # "모은 돈으로 오늘 패딩 사도 될까?" is the purchase check
    ):
        return None
    amounts = tuple(_GOAL_AMOUNT.finditer(normalized))
    if len(amounts) != 1:
        return None
    match = amounts[0]
    try:
        amount = int(match.group("amount").replace(",", ""))
    except ValueError:
        return None
    target = amount * 10_000 if match.group("unit") == "만원" else amount
    if not 0 < target <= _MAX_NATURAL_GOAL_KRW:
        return None
    return NaturalGoal(target_krw=target)


def natural_what_if(question: str) -> NaturalWhatIf | None:
    """Admit one clear Korean spending-reduction branch without a model call.

    A what-if answer changes the FDT input, so the gate rejects more prose than
    it accepts.  In particular, two categories, multiple rates, KRW amounts,
    fixed costs, income, card payment, investment, or advice requests remain on
    the normal model-assisted path instead of being silently converted to a
    scenario.  The calendar expression is revalidated later by ``turn_period``.
    """
    normalized = re.sub(r"\s+", "", unicodedata.normalize("NFKC", question).lower())
    if (
        not normalized
        or _WHAT_IF_DISALLOWED.search(normalized) is not None
        or _WHAT_IF_AMOUNT.search(normalized) is not None
        or _WHAT_IF_NON_MONTH.search(normalized) is not None
        or _WHAT_IF_PAST.search(normalized) is not None
        or _WHAT_IF_RATE_CUT.search(normalized) is None
        or _WHAT_IF_REDUCTION.search(normalized) is None
        or (_WHAT_IF_OUTCOME.search(normalized) is None and _WHAT_IF_BARE.search(normalized) is None)
    ):
        return None
    rates = tuple(_WHAT_IF_PERCENT.finditer(normalized))
    if not rates and _WHAT_IF_HALF.search(normalized) is not None:
        reduction = 50  # "쇼핑비를 절반으로 줄이면?"
    elif len(rates) != 1:
        return None
    else:
        reduction = int(rates[0]["percent"])
    # 100% would make the request a removal/cancellation operation rather than
    # a spending-reduction estimate, and 0% provides no alternate branch.
    if not 1 <= reduction <= 90:
        return None
    envelopes = {
        envelope
        for alias, envelope in _WHAT_IF_ENVELOPE_ALIASES.items()
        if alias in normalized
    }
    if len(envelopes) > 1:
        return None
    if not envelopes and _WHAT_IF_GENERIC_EXPENSE.search(normalized) is None:
        return None
    return NaturalWhatIf(reduction=reduction / 100, envelope=next(iter(envelopes), None))


def budget_envelope_words() -> frozenset[str]:
    """Return the words that name one of the user's budget envelopes ("외식", "교통비", "식비")."""
    return frozenset(_WHAT_IF_ENVELOPE_ALIASES)


def names_budget_target(question: str) -> bool:
    """Whether the text names a budget target of the user's own: an envelope, a 봉투, or a rate change."""
    normalized = re.sub(r"\s+", "", unicodedata.normalize("NFKC", question).lower())
    return (
        "봉투" in normalized
        or _WHAT_IF_PERCENT.search(normalized) is not None
        or any(alias in normalized for alias in _WHAT_IF_ENVELOPE_ALIASES)
    )


def names_own_budget(question: str) -> bool:
    """Whether the text points at the user's own budget: an envelope, the budget, or a rate change."""
    normalized = re.sub(r"\s+", "", unicodedata.normalize("NFKC", question).lower())
    return (
        "봉투" in normalized
        or "예산" in normalized
        or _WHAT_IF_PERCENT.search(normalized) is not None
        or any(alias in normalized for alias in _WHAT_IF_ENVELOPE_ALIASES)
    )


# Once the router has named the intent (a goal, a spending cut, a purchase), no phrase list
# decides it again. Only the values are read, and only from the user's own words: a missing
# or unreadable one is asked for, never guessed.
def goal_slots(question: str) -> NaturalGoal | str:
    """Read a saving goal's target and deadline; a code names the piece to ask for."""
    question = with_bare_won(question)
    normalized = re.sub(r"\s+", "", unicodedata.normalize("NFKC", question).lower())
    if _GOAL_UNSUPPORTED_PERIOD.search(normalized) is not None:
        return "goal_period_unsupported"
    digits = tuple(_GOAL_AMOUNT.finditer(normalized))
    if len(digits) == 1:
        target = int(digits[0]["amount"].replace(",", ""))
        target *= 10_000 if digits[0]["unit"] == "만원" else 1
    elif not digits and len(spoken := purchase_amounts(question)) == 1:
        target = spoken[0]
    else:
        return "goal_amount_required"
    if not 0 < target <= _MAX_NATURAL_GOAL_KRW:
        return "goal_amount_required"
    if _GOAL_PERIOD.search(normalized) is None:
        return "goal_period_required"
    return NaturalGoal(target_krw=target)


def what_if_slots(question: str) -> NaturalWhatIf | str:
    """Read a spending cut's rate and envelope; a code names the piece to ask for."""
    normalized = re.sub(r"\s+", "", unicodedata.normalize("NFKC", question).lower())
    envelopes = {envelope for alias, envelope in _WHAT_IF_ENVELOPE_ALIASES.items() if alias in normalized}
    if _WHAT_IF_NON_MONTH.search(normalized) is not None or len(envelopes) > 1:
        return "what_if_scope_unsupported"
    rates = tuple(_WHAT_IF_PERCENT.finditer(normalized))
    if len(rates) == 1:
        reduction = int(rates[0]["percent"])
    elif not rates and _WHAT_IF_HALF.search(normalized) is not None:
        reduction = 50
    else:
        return "what_if_percent_required"
    if not 1 <= reduction <= 90:
        return "what_if_scope_unsupported"
    return NaturalWhatIf(reduction=reduction / 100, envelope=next(iter(envelopes), None))


def purchase_slots(question: str) -> NaturalPurchase | str:
    """Read a purchase's amount, item, payment and date; a code names the piece to ask for."""
    outcome = natural_purchase(question, intent_known=True)
    return "purchase_amount_required" if outcome is None else outcome


@dataclass(frozen=True, slots=True)
class NaturalPurchase:
    """One explicit lump-sum purchase suitable for a single FDT ``expense`` change.

    This is a Phase 1 shortcut for a single-payment (cash or one-time deferred
    card) purchase question only. It never infers an account, card, envelope,
    or calendar date the text does not clearly state, and it never represents
    a multi-installment purchase. ``payment_hint`` is ``None`` when the text
    itself does not name cash or card; the caller must then resolve payment
    only when the user's Twin snapshot has exactly one possible account/card,
    never by guessing among several.
    """

    amount_krw: int
    envelope: str
    date_token: str
    payment_hint: Literal["cash", "card"] | None
    card_payment_date: str | None


# Clarification is required, never a guess, whenever one of these fields is
# missing or ambiguous. Reusing the same small code set as the calendar
# parser's ``period_clarification_required`` keeps the wire contract uniform:
# a 4xx code, not a fabricated financial answer.
# Strict buy verbs: an unambiguous purchase signal on their own.
_PURCHASE_VERB_STRICT: Final = re.compile(
    r"사면|사도|살까|사려고|사서|구매하면|구매하려고|구매해도|구매해서|구매할까|"
    r"지르면|질러도|지르려고|구입하면|구입해서|구입해도|구입할까|사먹어도|사먹으면|사먹을까"
)
# Casual buy phrasings. Whitespace is already stripped before matching, so
# "사고 싶어" -> "사고싶어" and "사고싶" covers both. Deliberately excluded:
# "사자" (=lion), bare "살래"/"살라" (살다=live), and "사고파" (collides with
# 사고팔다 buy-and-sell); "살까봐" is redundant since "살까" already matches.
# These collide with finance/definition/goal questions ("예금 사고싶은데 뭐가
# 좋아"), so a casual-only match needs a concrete amount or item word before it
# counts as a purchase (see ``natural_purchase``). "장만하" was dropped entirely:
# "장만하다 뜻" / "집 장만" are definition/goal, not purchase.
_PURCHASE_VERB_CASUAL: Final = re.compile(r"사고싶|사볼까|사둘까")
# Future-tense plans ("내일 70만원 스위치 사려는데"). These collide with saving goals
# ("노트북 사려는데 200만원 모을 수 있을까"), financial products ("주식 사려는데"),
# 살다 = live ("부산에 살건데 월세 50만원") and hearsay ("사려는 사람"), so they
# count only with an amount AND an item word AND none of those signals.
_PURCHASE_VERB_FUTURE: Final = re.compile(
    r"사려는데|사려는중|사려해|구매하려는데|구입하려고|구입하려는데|지르려는데"
    r"|살건데|살거야|살거예요|살예정|살생각이|살려고|살려는데"
    r"|구매할건데|구입할건데|구매할예정|구입할예정"
)
# ...or, with no amount yet, when the plan asks for permission ("노트북 사려는데 괜찮을까?").
_PLAN_PERMISSION: Final = re.compile(
    r"괜찮(?:을까|아|나|겠|은지|을지)|될까|되나|어때|어떨까|무리(?:일까|야|인가)"
    r"|(?:돼|되|가능(?:할까|해|한가|하나)?)(?:요)?[?!.~]*$"
)
# A buy verb as a noun ("사는 건?", "사는 거 어때?", "사는 게 나을까?") needs a named item:
# 사는 is also 살다 ("혼자 사는 게").
_PURCHASE_VERB_NOUN: Final = re.compile(
    r"사는(?:건|거|게|것)(?:은|는|도)?(?:[?!.~]*$|어때|어떨까|어떄|괜찮|될까|돼)"
)
# 살다 (=live) is recognised by a place before 에/에서 ("부산에 살건데", "역 근처에서
# 살 건데"), not by any 에살: "다음 주에 살 건데" and "통장에서 살 예정" are purchases.
_PURCHASE_FUTURE_BLOCK: Final = re.compile(
    r"모으|모을|모아|모이|저축|적금|예금"
    r"|월세|전세|관리비|생활비|동네|자취|원룸|혼자살|오래살|같이살|따로살"
    r"|(?:시|도|구|군|동|읍|면|리|역|근처|쪽|집|아파트|빌라|오피스텔|기숙사|고향|서울|부산|지방)(?:에|에서)살"
)
# Everyday verbs that mean spending only with a named item: "치킨 시켜도 돼?",
# "택시 타도 될까?", "헬스장 등록해도 돼?". The item is required; a missing amount is
# then asked for. "끊다" buys only a ticket ("영화표 끊어도"); "커피 끊으면" is quitting.
_PURCHASE_VERB_SPEND_ITEM: Final = re.compile(
    r"먹어도|먹으면(?!서)|먹을(?:건데|거야|예정|까|래)|먹으려"
    r"|시켜도|시켜먹어도|시키면(?!서)|시킬(?:건데|거야|까|래)"
    r"|타도|타면(?!서)|탈(?:건데|거야|까|래)"
    r"|예약하면(?!서)|예약해도|예약할(?:건데|거야|예정|까|래)|예약하려|예약하고싶|예매하고싶|시켜먹고싶|사먹고싶"
    r"|사야(?:해|돼|할|겠|하는데)|가려는데|가려고"
    r"|예매하면(?!서)|예매해도|예매할(?:건데|거야|예정|까|래)|예매하려"
    r"|등록해도|등록하면(?!서)|등록할(?:건데|거야|까|래)"
    r"|가도|가면(?!서)|갈(?:건데|거야|까|래)"
)
_PURCHASE_VERB_TICKET: Final = re.compile(r"끊어도|끊으면|끊을(?:건데|거야|까|래)")
_PURCHASE_TICKET_ITEM: Final = re.compile(r"표|티켓")
# Paying verbs: "5,000원 결제할 건데 괜찮아?" is a purchase even before the item is
# named (the envelope is then asked for).
_PURCHASE_VERB_SPEND_MONEY: Final = re.compile(
    r"결제하면(?!서)|결제해도|결제할(?:건데|거야|거예요|예정|까|래)|결제하려|결제하고싶"
    r"|내도|내면(?!서)|낼(?:건데|거야|예정|까|래)"
)
# 쓰다 names a purchase only with its price ("치킨에 3만원 써도 돼?"); with an envelope and no
# price it plans the month's spending ("취미·여가에 절반만 쓰면", "편의점을 최소한으로만 쓰면").
_PURCHASE_VERB_USE: Final = re.compile(r"써도|쓰면(?!서)")
# Bills and debts are money moves, not purchases ("카드값 30만원 결제해도 돼?"), and
# recurring, valuation and saving wording asks about a habit, not one purchase
# ("매달 커피값으로 10만원 쓰면", "치킨 시키면 2만원이야?", "배달 끊으면 아낄 수 있어?").
_PURCHASE_SPEND_BLOCK: Final = re.compile(
    r"카드값|카드대금|청구|대출|이자|보험료|세금|공과금|송금|할부금|고정비|용돈(?!(?:을|를|이|가)?(?:받|들어))"
    r"|매달|매일|매주|한달에|한달동안|월[0-9]|[0-9]+년|일년|적당|과소비|나올까|나오나|원이야|원이지"
    r"|아끼|아낄|아낀|절약|줄이|줄여|덜쓰|[0-9]%|퍼센트"
    # "여행 어디로 가면 좋을지 추천해줘" asks for a recommendation, not a budget check.
    r"|추천|어디로|어디가|어디에|어디서"
)
# Forecast and past-spending wording ("앞으로 배달 시키면 잔액 얼마 남을까?", "지난달 택시
# 타면서 얼마 썼어?") is not a purchase missing its amount. A complete purchase that only
# mentions them ("오늘 치킨 3만원 현금으로 시켜도 돼? 잔액 괜찮아?") still is one.
# The stated amount is what is left or already spent ("잔액 5만원 남았는데 치킨 시켜도 돼?"), or
# the plan is a habit ("오늘부터 계속 택시 타면"): never a one-off purchase at that price.
_RECEIVED_AMOUNT: Final = re.compile(
    r"(?<=[0-9십백천만억])원(?:이|은|가|을|를|도|만|정도|쯤)?(받으면|받았|받기로|받는데)"
)
_INCOME_SOURCE: Final = re.compile(
    r"월급|급여|용돈|보너스|상여|알바|수당|환급|환불|캐시백|페이백|세뱃돈|한테|에게|께서|로부터|부모님|엄마|아빠|친구"
)
_FEE: Final = re.compile(r"배달비|배송비|배달팁|수수료|팁")


def _amount_not_price(normalized: str) -> bool:
    """Whether a stated amount is held, received or already spent rather than the price."""
    if _AMOUNT_NOT_PRICE.search(normalized) is not None:
        return True
    for match in _RECEIVED_AMOUNT.finditer(normalized):
        head = normalized[max(0, match.start() - 12) : match.start()]
        if "견적" in head:
            continue  # "견적 30만원 받았는데" is the quoted price
        if match.group(1) == "받는데" and _INCOME_SOURCE.search(head) is None and _FEE.search(head) is None:
            continue  # "1박 10만원 받는데" is what the seller charges
        return True
    return False


_AMOUNT_NOT_PRICE: Final = re.compile(
    r"(?<=[0-9십백천만억])원(?:이|은|가|을|를|도|만|정도|쯤|밖에|넘게)?(?:남았|남아|남은|썼|쓴|나갔|나간|부족|있는데|있어서"
    r"|써서|들었|들어서|나와서|이었|였|뿐|밖에없|나왔(?!.*(?:결제|내도|내면|낼까|낼게|사도|사면|살까))"
    r"|(?:만|정도|쯤)?(?:갖고있|가지고있|들고있|들어있|남기고|남겨|남짓있|(?:으로|로)(?:만)?(?:버텨|버티|버틸|살아야|지내야))"
    r"|들어오면|들어오는데|들어와|들어왔|벌었|먹었|샀는데|탔는데|냈는데)"
)
_PURCHASE_HABIT: Final = re.compile(
    r"(?:타|시키|가|먹으|쓰|내|사먹으)면서|(?:부터.{0,12}|(?:계속|앞으로).{0,10})"
    r"(?:타면|시키면|먹으면|가면|쓰면|내면)"
)
# Under forecast, balance or past-spend wording the one amount counts as the price only when it
# is price-shaped: "치킨 3만원 현금으로", "3만원짜리", "3만원 시키면", not "5만원인데", "3만원밖에",
# "5만원으로 버텨야" or "4만원, 오늘 …".
_PRICE_SUFFIX: Final = frozenset({"", "짜리", "어치", "에", "정도", "쯤"})
_PRICE_NEXT: Final = re.compile(
    r"현금|카드|계좌|통장|체크|신용|이체|오늘|내일|이번주|이번|다음주|다음|시켜|시키|사먹|사도|사면|결제|내도|내면"
    r"|써도|쓰면|타도|타면|먹어|먹으|먹을|예약|예매|등록|끊"
)
_WORD_EDGE_MARKS: Final = "?!.,~^;:()[]\"'"
_BALANCE_WORD: Final = re.compile(r"잔액|잔고|남은돈|가진돈|예산")
_HELD_MONEY_WORD: Final = re.compile(r"잔액|잔고|남은돈|가진돈")
_BALANCE_DUE: Final = re.compile(
    r"\s*(?:을|를)?\s*(?:오늘|내일|이번\s*주|다음\s*주|지금)?\s*(?:(?:현금|카드|체크카드|계좌이체|이체)\s*(?:으로|로)?\s*)?"
    r"(?:결제|치르|치러|갚|송금|입금|내도|내면|낼)"
)
_BALANCE_STATEMENT: Final = re.compile(
    r"(?:잔액|잔고|남은\s*돈|가진\s*돈)\s*(?:이|은|는|가|도|만)?\s*(?:딱|겨우|고작|약|대략)?\s*"
    r"[0-9][0-9,.]*\s*(?:[십백천만억]\s*)*원\s*(?:이야|이지|이에요|예요|인데|이라|뿐|밖에|정도|남짓|쯤)?"
)
_HELD_AFTER: Final = re.compile(r"(?:잔액|잔고|남은돈|가진돈)(?:으로|인데|이야|이라|밖에|뿐|만|남|있)")
# A period and a spending category before the amount ("이번 달 외식 20만원인데") name a total.
_PERIOD_TOTAL: Final = re.compile(
    r"(?:이번달|이달|지난달|저번달|한달|이번주|지난주)(?:에|동안|간|은|는)?"
    r"(?:외식비?|교통비|쇼핑비?|식비|생활비|편의점|마트|의료비?|취미|카페|배달비?)"
)
_BUDGET_AFTER: Final = re.compile(r"^예산(?:으로|인데|이라|이야|이면|밖에|뿐|만)")


def _amount_reads_as_price(normalized: str, question: str) -> bool:
    """Under balance or forecast wording ("잔액 5만원인데 사도 돼?") the amount must be price-shaped."""
    if (
        _PURCHASE_SPEND_CONTEXT.search(normalized) is None
        and _BALANCE_WORD.search(normalized) is None
        and _PERIOD_TOTAL.search(normalized) is None
    ):
        return True
    return _price_shaped(question)


_CLAUSE_END: Final = re.compile(r"[?!.,]$")


_PRICE_COPULA: Final = frozenset(
    {"인데", "이면", "이래", "이라는데", "이라던데", "이던데", "이라서", "이니까", "이라"}
)
_PERIOD_NEAR: Final = re.compile(r"이번|지난|저번|달|한주|매|하루|월간|주간")


def _named_item_price(tokens: list[str], index: int) -> bool:
    """Whether the item named right before the amount prices it ("에어팟 케이스 3만원인데")."""
    token = tokens[index].lstrip(_WORD_EDGE_MARKS)
    run = next((m for m in _AMOUNT_RUN.finditer(token) if token[m.end() : m.end() + 1] == "원"), None)
    if run is None or re.sub(r"[^0-9a-z가-힣]+$", "", token[run.end() + 1 :]) not in _PRICE_COPULA:
        return False
    start = index
    while start > 0 and _CLAUSE_END.search(tokens[start - 1]) is None:
        start -= 1
    words = [*tokens[max(start, index - 2) : index], token[: run.start()]]
    near = compact(" ".join(words))
    return (
        bool(purchase_envelopes(" ".join(words)))
        and _BALANCE_WORD.search(near) is None
        and _PURCHASE_SPEND_CONTEXT.search(near) is None
        and _PERIOD_NEAR.search(near) is None
    )


def _first_amount_index(tokens: list[str]) -> int | None:
    return next((i for i, raw in enumerate(tokens) if purchase_amounts(raw.strip(_WORD_EDGE_MARKS))), None)


def _strict_price_shape(tokens: list[str], index: int) -> bool:
    """Whether the amount token reads as a price: bare or 짜리·어치·정도, then a payment, verb or item."""
    token = tokens[index].lstrip(_WORD_EDGE_MARKS)
    for match in _AMOUNT_RUN.finditer(token):
        if token[match.end() : match.end() + 1] != "원":
            continue
        suffix = token[match.end() + 1 :]
        if suffix.endswith(","):
            return False
        core = re.sub(r"[^0-9a-z가-힣]+$", "", suffix)  # "3만원ㅠㅠ", "3만원😅", "(3만원)" end the clause
        if core not in _PRICE_SUFFIX:
            return False
        if suffix != core:
            return True
        following = index + 1
        while following < len(tokens) and tokens[following].strip(_WORD_EDGE_MARKS) in _PRICE_SUFFIX:
            following += 1  # "2만원 정도 현금으로"
        word = tokens[following].strip(_WORD_EDGE_MARKS) if following < len(tokens) else ""
        return not word or _PRICE_NEXT.match(word) is not None or bool(purchase_envelopes(word))
    return False


def _price_shaped(question: str) -> bool:
    """Whether the first won amount reads as the price of the purchase being asked about.

    Only balance or forecast wording in the amount's own clause ("잔액 5만원인데", "5만원으로
    버텨야") needs the strict shape; "노트북 150만원인데 사도 돼? 월말에 괜찮을까?" keeps its price.
    """
    tokens = _joined_amounts(unicodedata.normalize("NFKC", question).lower()).split()
    index = _first_amount_index(tokens)
    if index is None:
        return False
    start = index
    while start > 0 and _CLAUSE_END.search(tokens[start - 1]) is None:
        start -= 1
    token = tokens[index].lstrip(_WORD_EDGE_MARKS)
    run = next((m for m in _AMOUNT_RUN.finditer(token) if token[m.end() : m.end() + 1] == "원"), None)
    head = [token[: run.start()]] if run else []
    before = compact(" ".join(tokens[start:index] + head))
    near_before = compact(" ".join(tokens[max(start, index - 2) : index] + head))
    after_tokens: list[str] = []
    if _CLAUSE_END.search(tokens[index]) is None:
        for following in tokens[index + 1 : index + 3]:
            after_tokens.append(following)
            if _CLAUSE_END.search(following):
                break
    after = compact(" ".join(after_tokens))
    # "노트북 150만원인데 예산 괜찮아?" asks about the budget; "5만원 예산으로" names the budget.
    # "5만원 잔액으로" labels the amount; "치킨 3만원인데 잔액 괜찮아?" asks about the balance.
    after_labelled = _HELD_AFTER.match(after) is not None or (
        bool(after_tokens) and _BUDGET_AFTER.match(after_tokens[0].strip(_WORD_EDGE_MARKS)) is not None
    )
    if _PERIOD_TOTAL.search(before) is not None:
        return _strict_price_shape(tokens, index)  # "이번 달 외식 20만원인데" is a month's total
    no_context = _PURCHASE_SPEND_CONTEXT.search(near_before + after) is None
    if no_context and _BALANCE_WORD.search(before) is None and not after_labelled:
        return True
    if _BALANCE_WORD.search(near_before) is None and not after_labelled and _named_item_price(tokens, index):
        return True  # "잔액 걱정되는데 … 노트북 150만원인데", "치킨 3만원인데 잔액 괜찮아?"
    return _strict_price_shape(tokens, index)


# Asking permission for one spend ("시켜도 돼?", "타도 될까?") rather than what a habit leads to.
_SPEND_PERMISSION: Final = re.compile(
    r"(?:먹어|시켜|시켜먹어|사먹어|타|가|예약해|예매해|등록해|결제해|내|써)도(?:돼|될까|되나|되니|되냐|괜찮)"
)
# ...unless the turn also asks a lookup or forecast ("택시 타도 돼? 지난달 교통비 얼마 썼어?") or
# describes a habit ("월말까지 택시 타도 괜찮을까?", "계속 2만원씩 배달 시켜도 돼?").
_PERMISSION_LOOKUP: Final = re.compile(r"얼마|예측|비교|보여|알려")
_PERMISSION_HABIT: Final = re.compile(r"계속|앞으로|요즘|말까지|내내|처럼|대로|씩|마다")
_PURCHASE_SPEND_CONTEXT: Final = re.compile(
    r"계속|앞으로|월말|잔액|예측|위험|부족|남을|남아|남았|들까|얼마들|나올지|얼마나올|썼|쓴|나갔|나간|지난달|면서"
)
_PURCHASE_VERB: Final = re.compile(
    _PURCHASE_VERB_STRICT.pattern + r"|" + _PURCHASE_VERB_CASUAL.pattern
)


# A buy verb counts when it starts a typed word ("노트북 사면", "사도 돼?") or is glued to an
# item ("옷사면"). Inside another word it is 이사+도, 행사+도, 회사+면 or 사면초가, and a bare
# 살까 is also 살다 ("혼자 살까", "몇 살까지"), so those need a named item.
_BUY_WORD: Final = re.compile(
    r"(?:(?:^|(?<=[\s.,!?~…·)\]\"'])|(?<=[0-9십백천만억]원)|(?<=짜리)|(?<=어치)|(?<=[가-힣][거것걸건을를]))"
    r"(?:사면(?!초가)|사도|사서|사려고|사먹|지르|질러|사고\s*싶|사볼까|사둘까)|(?:구매|구입)\s*(?:하|해|할))"
)
# "집 사려고 돈 모으는 중" is a saving plan and "사서 고생" an idiom, not a purchase to price.
_SAVING_PLAN: Final = re.compile(
    r"(?:사려고|살려고|사기위해|사려면).{0,15}(?:모으|모을|모아|모이|저축|적금|드는)"
)
_BUY_IDIOM: Final = re.compile(r"사서\s*고생")
_BUY_FILLER: Final = frozenset({
    "지금", "오늘", "요즘", "당장", "이번에", "이제", "좀", "더", "한번", "또", "다시", "미리",
    "하나", "새로", "한", "한개", "하나만", "그냥", "빨리", "결국", "차라리", "새",
})


def _buy_verb_counts(question: str) -> bool:
    return (
        _BUY_WORD.search(unicodedata.normalize("NFKC", question).lower()) is not None
        or bool(purchase_envelopes(question))
    )


def has_buy_verb(question: str) -> bool:
    """Whether the text asks about buying something ("노트북 사면", "옷사면", "노트북 살까").

    An item elsewhere in the turn does not make 이사도, 회사도 or 혼자 살까 a buy verb.
    """
    text = unicodedata.normalize("NFKC", question).lower()
    normalized = re.sub(r"\s+", "", text)
    if (
        _PURCHASE_VERB.search(normalized) is None
        or _SAVING_PLAN.search(normalized) is not None
        or _BUY_IDIOM.search(text) is not None
    ):
        return False
    if _BUY_WORD.search(text) is not None:
        return True
    tokens = [raw.strip(_WORD_EDGE_MARKS) for raw in text.split()]
    for index, token in enumerate(tokens):
        match = _PURCHASE_VERB.search(token)
        if match is None:
            continue
        head = token[: match.start()]
        if head:
            if purchase_envelopes(head):
                return True
            continue
        back = index - 1
        while back >= 0 and tokens[back] in _BUY_FILLER:
            back -= 1  # "노트북 하나 살까", "노트북 지금 살까"
        if back >= 0 and purchase_envelopes(tokens[back]):
            return True
    return False

# Securities, funds and crypto: buying them is an investment decision the coach does
# not make. Matched per typed word ("이번 주 가방" is not 주가), from the word start
# for short names and anywhere for long unambiguous ones ("미국S&P500", "나스닥100").
_INVESTMENT_ANYWHERE: Final[tuple[str, ...]] = (
    "비트코인", "이더리움", "나스닥", "코스피", "코스닥", "s&p", "삼성전자", "하이닉스", "엔비디아",
    "테슬라", "팔란티어", "에코프로", "셀트리온", "에너지솔루션", "에어로스페이스", "마이크로소프트",
    "삼성바이오", "삼성전기", "삼성sdi", "lg화학", "현대모비스", "포스코홀딩스", "크래프톤",
    "은행채", "국고채", "금융채",
)
_INVESTMENT_WORD_START: Final[tuple[str, ...]] = (
    "종목", "리플", "도지", "채권", "국채", "회사채", "미국채", "배당주", "우량주", "증권", "주가", "공모주",
    "qqq", "voo", "spy", "schd", "tqqq", "soxl",
    "jepi", "ivv", "vti", "qld", "arkk", "kodex", "tiger", "kbstar", "kb스타", "arirang", "hanaro",
    "nvda", "aapl", "tsla", "msft", "googl", "amzn", "asml", "tsm",
    "kosef", "lg엔솔",
)
# Asset-class words also end a compound ("미국주식", "알트코인", "적립식펀드", "미국etf").
_INVESTMENT_WORD_EDGE: Final[tuple[str, ...]] = ("주식", "코인", "etf", "펀드")
# Company names that are also brands ("애플펜슬", "구글 기프트카드", "기아 차") count only as a
# whole word in a question that talks about shares ("애플 주식 사는 거", "카카오 손절").
_INVESTMENT_BRANDS: Final[frozenset[str]] = frozenset({
    "카카오", "네이버", "현대차", "기아", "포스코", "두산", "애플", "아마존", "구글", "알파벳", "메타",
    "tsmc", "브로드컴", "amd", "인텔",
})
_INVESTMENT_CONTEXT: Final = re.compile(
    r"주식|주가|종목|매수|매도|손절|익절|물렸|팔까|팔아|팔면|팔고|투자|배당|상장|주주"
)
_GLUED_ASSET_DECISION: Final = re.compile(
    r"(?:주식|코인|etf|펀드)(?:을|를|은|는|좀|지금|더)?(?:사도|살까|사야|팔까|팔아도|매수|매도)"
)
_TOKEN_PARTICLE: Final = re.compile(r"(?:은|는|이|가|을|를|도|만|의|에|로|으로|주식|주가|주)$")
# A bare company name asked as a buy decision ("카카오 지금 사도 될까?", "네이버 50만원어치
# 사도 돼?") is a share. Followed by a product ("애플 워치", "구글 기프트카드", "기아 차") it is not.
_BRAND_BUY: Final = re.compile(r"사도|살까|사면|사야|사는거|사는게|들어가|넣어|매수|담아")
_BRAND_TIME: Final = frozenset(
    {"지금", "오늘", "요즘", "당장", "이번에", "이제", "좀", "더", "한번", "또", "다시", "미리"}
)
_BRAND_BUY_NEXT: Final = re.compile(
    r"사도|살까|사면|사야|사는|들어가|넣어|매수|담아|[0-9일이삼사오육칠팔구십백천만억.,]+원어치"
)
# "애플 살까 삼성 살까?" compares products; 현대차·기아 with a price or payment is a car.
_BRAND_COMPARISON: Final = re.compile(r"살까.{1,14}살까")
_CAR_PURCHASE: Final = re.compile(r"현금|할부|카드로|리스|[0-9]+만원|보험료|취득세")
_BRAND_TAIL_PLAIN: Final = (
    r"돼|될까|되나|되냐|되니|되겠|되(?:요)?[~?!.]*$|괜찮|말까|할까|해|좋을까|어때|맞|게$|거$"
)
_BRAND_TAIL: Final = re.compile(
    _BRAND_TAIL_PLAIN + r"|될지|되는지|고민|궁금|싶|모르겠|알려|말해|생각|의견|판단"
)
_MARKET_TALK_PLAIN: Final = (
    r"떨어졌|떨어지|올랐|오를|내릴|내렸|반등|폭락|폭등|급등|급락|하락|상승|실적|전망|저점|고점|물타"
)
_MARKET_TALK: Final = re.compile(
    _MARKET_TALK_PLAIN + r"|빠졌|빠지|바닥|존버|떡상|떡락|분위기|손실|수익률|시총|주주"
)
# 현대차·기아 are also cars: "현대차 살까 고민이야" and "기아 사도 될지 모르겠어" are car purchases.
_CAR_TAIL: Final = re.compile(_BRAND_TAIL_PLAIN)
_CAR_MARKET_TALK: Final = re.compile(_MARKET_TALK_PLAIN)
_RESALE: Final = re.compile(r"중고|감가|리셀|되팔")


def _brand_bought(tokens: list[str], index: int, words: str) -> bool:
    """Whether a bare company name is asked as a share buy ("카카오 지금 사도 될까?")."""
    if _BRAND_BUY.search(words) is None or _BRAND_COMPARISON.search(words) is not None:
        return False
    car_maker = _TOKEN_PARTICLE.sub("", tokens[index]) in {"현대차", "기아"}
    if car_maker and _CAR_PURCHASE.search(words) is not None:
        return False
    tail_words, market_words = (_CAR_TAIL, _CAR_MARKET_TALK) if car_maker else (_BRAND_TAIL, _MARKET_TALK)
    if _RESALE.search(words) is not None and _CAR_MARKET_TALK.search(words) is None:
        return False  # "애플 사면 중고로 팔 때 손실 커?" is about the product
    rest = tokens[index + 1 :]
    while rest and rest[0] in _BRAND_TIME:
        rest = rest[1:]
    if rest and _BRAND_BUY_NEXT.match(rest[0]) is None:
        return False
    if market_words.search(words) is not None:
        return True
    # "기아 사면 연비 좋아?" / "현대차 사도 될까? 차 바꿀 때 됐는데" talk about the car after the verb.
    verbs = [
        position for position in range(index + 1, len(tokens))
        if _BRAND_BUY_NEXT.match(tokens[position]) or _BRAND_BUY.search(tokens[position])
    ]
    return not verbs or all(not tail or tail_words.match(tail) for tail in tokens[verbs[-1] + 1 :])
# Everyday services that share a company's name are not investments.
_INVESTMENT_NOT: Final[tuple[str, ...]] = (
    "코인노래방", "코인세탁", "코인빨래", "코인워시", "카카오페이", "카카오택시", "카카오톡", "카카오t",
    "네이버페이", "네이버쇼핑", "애플페이", "애플워치", "애플뮤직", "아마존프라임", "구글플레이", "메타버스",
    "기아자동차서비스", "주가게", "코인육수", "카카오뱅크", "카카오프렌즈", "애플펜슬", "애플망고",
    "구글기프트", "메타몽",
)


def investment_product(question: str) -> bool:
    """Whether a typed word names a stock, fund, ETF or coin."""
    text = unicodedata.normalize("NFKC", question).lower()
    words = re.sub(r"\s+", "", text)
    share_talk = _INVESTMENT_CONTEXT.search(words) is not None
    tokens = [raw.strip("?!.,~^;:()[]\"'") for raw in text.split()]
    for index, token in enumerate(tokens):
        if not token or token.startswith(_INVESTMENT_NOT):
            continue
        if any(word in token for word in _INVESTMENT_ANYWHERE) or token.startswith(_INVESTMENT_WORD_START):
            return True
        core = re.sub(r"(?:은|는|이|가|을|를|도|만|의|에|로|으로)$", "", token)
        if core.startswith(_INVESTMENT_WORD_EDGE) or core.endswith(_INVESTMENT_WORD_EDGE):
            return True
        if _TOKEN_PARTICLE.sub("", token) in _INVESTMENT_BRANDS and (
            share_talk or _brand_bought(tokens, index, words)
        ):
            return True
    # "지금코인사도될까?" typed without spaces still names the asset right before the verb.
    return _GLUED_ASSET_DECISION.search(words) is not None


# A completed/past-tense purchase statement ("커피 3만원 샀어", "노트북 구매했어")
# is a fresh independent turn, not a bare field answering a pending clarification.
# ``natural_purchase`` returns ``None`` for these (it only admits a prospective
# purchase), so they must be rejected explicitly in the bare-fragment guard below
# or they would be force-merged into the stale pending purchase context.
_PURCHASE_VERB_COMPLETE: Final = re.compile(r"샀|구매했|구입했|질렀")
_PURCHASE_INSTALLMENT: Final = re.compile(r"할부")
# One won amount as people type it: "30만원", "15,000원", "5천원", "2.5만원",
# "1만 5천원", "백만원", "3만 원". Numeral runs are found with one flat character class
# (no nested repetition, so a long digit string costs linear time) and then read by
# ``_krw``. A Hangul numeral must start its own word so the particle in "치킨이 만원"
# is never read as 이(=2); digits may follow a word directly ("노트북300만원").
_AMOUNT_RUN: Final = re.compile(r"[0-9일이삼사오육칠팔구십백천만억.,]+")
_AMOUNT_JOIN_UNIT: Final = re.compile(
    r"(?<=[만억])\s+(?=(?:[0-9][0-9,]*|[일이삼사오육칠팔구])?[천백십]|[0-9][0-9,]*\s*원)"
)
_AMOUNT_JOIN_WON: Final = re.compile(r"(?<=[0-9십백천만억])\s+(?=원)")
# "300 만원", "백 만원", "5 천원": a numeral before a spaced unit belongs to it. A bare
# Hangul digit is not joined ("이 만원" is "this 10,000 won"), and a Hangul numeral must be
# its own word ("에코백 만원", "인천 만원", "명품백 백만원" keep their amount).
_AMOUNT_JOIN_NUMERAL: Final = re.compile(r"(?<=[0-9])\s+(?=[십백천만억])")
_AMOUNT_JOIN_HANGUL: Final = re.compile(
    r"(?:(?<=\s)|^)([0-9]*[일이삼사오육칠팔구십백천]*[십백천])\s+(?=[만억])"
)
_AMOUNT_JOIN_SMALL: Final = re.compile(
    r"(?:(?<=\s)|^)([0-9]*[일이삼사오육칠팔구십백천]*[십백천])\s+"
    r"(?=[0-9일이삼사오육칠팔구십백천만억.,]*+(?:원|(?<=[만억])))"
)


def _joined_amounts(text: str) -> str:
    numerals = _AMOUNT_JOIN_HANGUL.sub(r"\1", _AMOUNT_JOIN_NUMERAL.sub("", text))
    numerals = _AMOUNT_JOIN_SMALL.sub(r"\1", numerals)
    return _AMOUNT_JOIN_WON.sub("", _AMOUNT_JOIN_UNIT.sub("", numerals))
_AMOUNT_WORD: Final = re.compile(r"[0-9][0-9,]*(?:\.[0-9]+)?|[일이삼사오육칠팔구십백천만억]")
_AMOUNT_MAX_DIGITS: Final = 15
_HANGUL_DIGITS: Final[dict[str, int]] = {
    "일": 1, "이": 2, "삼": 3, "사": 4, "오": 5, "육": 6, "칠": 7, "팔": 8, "구": 9,
}
_SMALL_UNITS: Final[dict[str, int]] = {"십": 10, "백": 100, "천": 1_000}
_BIG_UNITS: Final[dict[str, int]] = {"만": 10_000, "억": 100_000_000}


def _numeral(token: str) -> Decimal | None:
    if token in _HANGUL_DIGITS:
        return Decimal(_HANGUL_DIGITS[token])
    digits = token.replace(",", "")
    if len(digits.partition(".")[0]) > _AMOUNT_MAX_DIGITS:
        return None
    return Decimal(digits)


def _krw(number: str) -> int | None:  # noqa: C901, PLR0911 - one return per malformed-numeral case.
    """Read one Korean/Arabic mixed amount ("1만5천", "2.5만", "3백만") as whole won.

    Exact decimal arithmetic; units must descend ("1만2만" is rejected); a stated zero
    stays zero ("0만원" is not 1만원); an implicit 1 applies only to a bare unit ("만원").
    """
    tokens = [match.group(0) for match in _AMOUNT_WORD.finditer(number)]
    if "".join(tokens) != number:
        return None
    total = Decimal(0)
    section = Decimal(0)
    section_stated = False
    pending: Decimal | None = None
    last_big: int | None = None
    last_small: int | None = None
    for token in tokens:
        if token[0].isdigit() or token in _HANGUL_DIGITS:
            if pending is not None:
                return None
            pending = _numeral(token)
            if pending is None:
                return None
        elif token in _SMALL_UNITS:
            unit = _SMALL_UNITS[token]
            if last_small is not None and unit >= last_small:
                return None
            section += (Decimal(1) if pending is None else pending) * unit
            section_stated = True
            last_small = unit
            pending = None
        else:
            unit = _BIG_UNITS[token]
            if last_big is not None and unit >= last_big:
                return None
            if pending is not None:
                section += pending
                section_stated = True
            if not section_stated:
                section = Decimal(1)
            total += section * unit
            section = Decimal(0)
            section_stated = False
            pending = None
            last_big = unit
            last_small = None
    value = total + section + (Decimal(0) if pending is None else pending)
    if value <= 0 or value != value.to_integral_value():
        return None
    return int(value)


# "2만5천짜리", "5천 어치": a price written without 원 right before 짜리/어치.
_WONLESS_PRICE: Final = re.compile(
    r"(?<![0-9.,])([0-9][0-9,.]*\s*(?:만|천)(?:\s*[0-9]+\s*(?:천|백))?)(?=\s*(?:짜리|어치))"
)


def with_won_units(question: str) -> str:
    """Write the won unit people leave out before 짜리/어치 ("커피 2만5천짜리" → "커피 2만5천원짜리")."""
    return _WONLESS_PRICE.sub(r"\1원", question)


# Once the router has named a purchase or a goal, "5만", "2만5천", "25,000" or "130000" is the
# amount with its 원 left off. A count, date or time keeps its own unit ("5만 명", "2026년"), and a
# bare number that is not a round hundred reads as a model name ("RTX 4090"), so neither is read.
_BARE_WON: Final = re.compile(
    r"(?<![0-9a-z.,:/\-])"
    r"([0-9][0-9,]*(?:\.[0-9]+)?\s*(?:만|천)(?:\s*[0-9]+\s*(?:천|백))?|[0-9]{1,3}(?:,[0-9]{3})+|[1-9][0-9]+00)"
    r"(?![0-9a-z.,:/\-])"
    # "4인분" counts people, but "4만인데" is the copula after a price.
    r"(?!\s*(?:원|%|퍼|프로|개월|켤레|인(?:분|용|실|석)|[개명일월시분초년주회번살세층호배위등차박장권병잔벌마]))",
    re.IGNORECASE,
)


def with_bare_won(question: str) -> str:
    """Write the won unit left off an amount ("옷 5만 현금으로" → "옷 5만원 현금으로")."""
    return _BARE_WON.sub(r"\1원", unicodedata.normalize("NFKC", question))


# "담달", "내달" are 다음 달 to the period parser too (내달리다 is not).
_SLANG_NEXT_MONTH: Final = re.compile(r"(?<![가-힣])(?:담\s?달|내달(?!리|려|린|렸))")


# "낼 현금으로 사도 돼?" opens with 내일; mid-sentence 낼 is the verb 내다 ("회비 낼까?").
_SLANG_TOMORROW: Final = re.compile(r"^(\s*)낼(?=\s)")


def canonical_question(question: str) -> str:
    """Normalize the spellings every grammar reads the same way before any of them runs."""
    question = _SLANG_TOMORROW.sub(r"\1내일", question)
    return _SLANG_NEXT_MONTH.sub("다음 달", with_won_units(question))


def purchase_amounts(question: str) -> tuple[int, ...]:
    """Every won amount stated in the question, in order; an unreadable token is skipped."""
    text = _joined_amounts(unicodedata.normalize("NFKC", question).lower())
    found: list[int] = []
    for match in _AMOUNT_RUN.finditer(text):
        if text[match.end():match.end() + 1] != "원":
            continue
        number = match.group(0)
        before = text[match.start() - 1] if match.start() > 0 else " "
        digit = re.search(r"[0-9]", number)
        if not number[0].isdigit() and before.isalnum() and digit is not None:
            # "내일100만원": the 일 of 내일 is part of the word; the amount starts at the digits.
            before, number = number[digit.start() - 1], number[digit.start() :]
        if number[0].isdigit():
            if before.isdigit() or before in ".,":
                continue
        elif (
            not ("가" <= number[0] <= "힣")
            or before.isalnum()
            or re.search(r"[십백천만억]", number) is None
        ):
            # ``str.isalnum`` is true for Hangul syllables, so "치킨이만원" is skipped.
            continue
        value = _krw(number)
        if value is not None:
            found.append(value)
    return tuple(found)


_PURCHASE_DATE_TOMORROW: Final = re.compile(r"내일")
# "다음주" is a distinct string from "이번주" (no substring overlap), but it is checked
# before "이번주" in ``_purchase_date_token`` so the ordering stays unambiguous.
_PURCHASE_DATE_NEXT_WEEK: Final = re.compile(r"다음주")
_PURCHASE_DATE_THIS_WEEK: Final = re.compile(r"이번주")
_PURCHASE_DATE_TODAY: Final = re.compile(r"오늘|지금(?!까지|처럼|껏|부터|보다)|당장|이따")
_PURCHASE_DATE_ISO: Final = re.compile(r"(?P<date>\d{4}-\d{2}-\d{2})")
_PURCHASE_CARD: Final = re.compile(r"(?<!체크)카드")
# "체크로", "체크 결제" shorten 체크카드; "체크해줘" (check it) does not pay.
_PURCHASE_CASH: Final = re.compile(r"현금|계좌|통장|이체|체크카드|체크(?=로|결제)")
_PURCHASE_PAYMENT_DATE: Final = re.compile(
    r"(?:결제일|카드값|출금)\D{0,10}(?P<date>\d{4}-\d{2}-\d{2})"
    r"|(?P<date2>\d{4}-\d{2}-\d{2})\D{0,10}(?:결제|출금)"
)
# Item word -> the KeyFin envelope its backend subcategory belongs to (V1__init.sql
# 세분류: 음식점·카페·배달·주점 / 대중교통·택시·주유 / 병원·약국·운동·헬스 /
# 영화·공연·전시·스포츠 관람·게임·콘텐츠·여행·숙박 / 패션·잡화·뷰티·온라인 쇼핑 /
# 편의점·마트·생활용품 / 교육·해외 결제·경조사·기타). Durable electronics keep the
# original 기타 mapping. Words that are also everyday non-item words are left out
# on purpose: 약(=about, 예약), 모자(모자라다), 반지(반지하), 술(기술·수술), 밥(밥솥),
# 저녁/점심(time of day), 운동(운동화), 경기(경기도). A shorter word inside a longer
# matched word is ignored ("스마트폰" is not 마트, "게임기" is not 게임).
_PURCHASE_ITEMS: Final[dict[str, tuple[str, ...]]] = {
    "기타": (
        "노트북", "랩탑", "맥북", "폰", "휴대폰", "핸드폰", "스마트폰", "아이폰", "갤럭시", "태블릿",
        "아이패드", "가전", "전자제품", "카메라", "닌텐도", "스위치", "게임기", "플스", "플레이스테이션",
        "에어팟", "이어폰", "헤드폰", "헤드셋", "티비", "tv", "청소기", "에어컨", "냉장고", "세탁기",
        "건조기", "전자레인지", "모니터", "키보드", "마우스", "스마트워치", "애플워치", "워치", "컴퓨터",
        "데스크탑", "학원", "강의", "수강료", "교재", "인강", "자격증", "축의금", "부조금", "조의금",
        "경조사", "직구", "책상", "의자", "침대", "가구", "소파", "중고폰", "새폰", "공기계",
        "우편료", "택배비", "헌금", "기부", "후원금",
    ),
    "외식": (
        "음식점", "식당", "외식", "카페", "커피", "음료", "배달", "주점", "술값", "술자리", "맥주",
        "소주", "와인", "치킨", "피자", "햄버거", "버거", "짜장면", "짬뽕", "국밥", "초밥", "스시",
        "오마카세", "삼겹살", "고기", "회식", "저녁밥", "점심밥", "저녁식사", "점심식사", "식사",
        "밥값", "떡볶이", "브런치", "디저트", "케이크", "빵", "마라탕", "라멘", "파스타", "스테이크",
        "뷔페", "족발", "보쌈", "버블티", "도시락", "김밥", "분식", "야식", "치맥", "소고기",
        "돼지고기", "닭고기", "식빵", "밥", "돈까스", "돈가스", "빅맥", "맥도날드", "점심값", "저녁값",
    ),
    "교통비": (
        "대중교통", "버스", "지하철", "택시", "기차", "ktx", "srt", "비행기", "항공권", "주유",
        "기름값", "주차비", "톨비", "통행료", "교통카드", "렌터카", "킥보드", "주차", "톨게이트", "항공편",
    ),
    "의료·건강": (
        "병원", "약국", "약값", "감기약", "두통약", "진통제", "영양제", "비타민", "진료", "치과",
        "한의원", "안과", "피부과", "검진", "안경", "렌즈", "헬스", "pt", "필라테스", "요가", "수영장",
        "핫요가",
    ),
    "취미·여가": (
        "영화", "콘서트", "공연", "뮤지컬", "연극", "전시", "티켓", "야구", "축구", "여행", "호텔",
        "리조트", "숙소", "숙박", "펜션", "에어비앤비", "캠핑", "게임", "스팀", "웹툰", "책", "도서",
        "만화책", "전공책", "동화책", "그림책", "소설책", "영어책", "수학책", "요리책", "자기계발책",
        "문제집", "참고서", "노래방", "pc방", "볼링", "놀이공원",
        "테마파크", "취미", "입장료", "화분", "악기", "자전거", "스포츠",
    ),
    "쇼핑": (
        "옷", "신발", "가방", "의류", "운동화", "구두", "패딩", "코트", "청바지", "바지", "셔츠",
        "티셔츠", "원피스", "자켓", "재킷", "니트", "후드티", "시계", "지갑", "액세서리", "악세사리",
        "목걸이", "귀걸이", "화장품", "향수", "립스틱", "선크림", "뷰티", "명품", "러닝화", "스니커즈",
        "슬리퍼", "샌들", "부츠", "선글라스", "텀블러", "겨울옷", "여름옷", "잠옷", "속옷",
        "손목시계", "벽시계", "에코백", "숄더백", "크로스백", "토트백", "클러치", "백팩",
        "모자", "양말", "장갑", "목도리", "머플러", "벨트", "운동용품", "스포츠용품", "스카프",
    ),
    "편의점·마트·잡화": (
        "편의점", "마트", "대형마트", "이마트", "홈플러스", "코스트코", "생필품", "생활용품", "장보기",
        "장바구니", "식료품", "식재료", "휴지", "화장지", "세제", "샴푸", "치약", "칫솔", "물티슈",
        "라면", "과일", "우유", "간식", "우산", "컵라면", "진라면", "신라면", "짜장라면", "볶음라면",
        "딸기우유", "바나나우유", "초코우유", "비빔라면", "열라면", "틈새라면", "짬뽕라면",
        "주방용품", "세면도구", "욕실용품",
    ),
}
# Short words that are also parts of everyday words count only at the start of a typed
# word: 라면 (…이라면, 아니라면), 요가 (필요가), 마트 (스마트), pt (gpt), 책 (산책, 대책),
# 폰 (쿠폰), 옷, 빵, 고기, 우유, 시계. Real compounds (컵라면, 겨울옷, 소고기, 중고폰) are
# listed as items of their own. A few word starts are still not items (책임, 책정, 고기압).
_ITEM_START_ONLY: Final = frozenset(
    {"라면", "요가", "마트", "pt", "책", "폰", "옷", "빵", "고기", "우유", "시계", "모자", "밥", "주차"}
)
_ITEM_NOT_START: Final[tuple[str, ...]] = (
    "책임", "책정", "고기압", "빵빵", "시계방향", "모자라", "모자랄", "모자란", "모자랐", "모자람",
    "밥솥", "주차장", "주차권",
)
# Of these, words with few collisions also end a compound ("불고기", "알람시계", "붕어빵",
# "롯데마트", "플라잉요가", "개인pt"), unless the syllable before is listed (스마트, 필요가, gpt,
# ppt, 빵빵). 라면·책·폰 collide with conditionals and idioms (아니라면, 대책, 쿠폰), so their
# compounds are listed as items instead.
_ITEM_END_OK: Final[dict[str, str]] = {
    "마트": "스", "요가": "필중주수", "pt": "gp", "빵": "빵", "고기": "", "옷": "", "시계": "", "우유": "",
    "밥": "",
    "폰": "쿠스",
}
_ITEM_TOKEN_PARTICLE: Final = re.compile(r"(?:이랑|하고|이요|으로|을|를|이|가|은|는|에|도|만|요|로|랑)$")


def _item_word_ok(token: str, word: str, start: int) -> bool:
    """Accept a start-only item word at the start of a word, or ending a low-collision compound."""
    if start == 0:
        return not token.startswith(_ITEM_NOT_START)
    if word not in _ITEM_END_OK:
        return False
    end = start + len(word)
    core = _ITEM_TOKEN_PARTICLE.sub("", token)
    return end in {len(token), len(core)} and token[start - 1] not in _ITEM_END_OK[word]


def purchase_envelopes(question: str) -> frozenset[str]:
    """Envelopes named by item words, each found inside one typed word.

    Matching per word keeps "택시 계좌이체" from reading 시계 across the space.
    """
    named: set[str] = set()
    for raw in unicodedata.normalize("NFKC", question).lower().split():
        token = raw.strip("?!.,~^;:()[]\"'")
        spans: list[tuple[int, int, str]] = []
        for envelope, words in _PURCHASE_ITEMS.items():
            for word in words:
                start = token.find(word)
                while start != -1:
                    if word not in _ITEM_START_ONLY or _item_word_ok(token, word, start):
                        spans.append((start, start + len(word), envelope))
                    start = token.find(word, start + 1)
        named.update(
            envelope
            for start, end, envelope in spans
            if not any(
                other_start <= start and end <= other_end and other_end - other_start > end - start
                for other_start, other_end, _ in spans
            )
        )
    return frozenset(named)


_ENVELOPE_NAMES: Final[dict[str, str]] = {
    "외식": "외식", "교통비": "교통비", "교통": "교통비", "의료·건강": "의료·건강", "의료건강": "의료·건강",
    "취미·여가": "취미·여가", "취미여가": "취미·여가", "쇼핑": "쇼핑", "편의점·마트·잡화": "편의점·마트·잡화",
    "편의점마트잡화": "편의점·마트·잡화", "기타": "기타",
}
_ENVELOPE_NAME_TAIL: Final = re.compile(
    r"(?:봉투|항목)?(?:에서|으로|로|에|이요|요|이에요|예요|이고|이야|야|이랑|으로요|로요)?"
    r"(?:해줘|해주세요|할게|할게요|할래|쳐줘|넣어줘|잡아줘)?"
)


def named_envelopes(question: str) -> frozenset[str]:
    """Envelopes the user names by the envelope itself ("쇼핑이요", "의료·건강 봉투로", "기타로 해줘").

    Read only once the turn is a purchase: the answer to "어떤 항목의 지출인지" names the
    envelope, not an item. A longer word ("쇼핑몰", "기타줄") is not the envelope.
    """
    named: set[str] = set()
    for raw in unicodedata.normalize("NFKC", question).lower().split():
        token = raw.strip("?!.,~^;:()[]\"'")
        for name, envelope in _ENVELOPE_NAMES.items():
            if token.startswith(name) and _ENVELOPE_NAME_TAIL.fullmatch(token[len(name):]) is not None:
                named.add(envelope)
    return frozenset(named)


_CONSUMER_PURCHASE: Final = re.compile(r"구매|구입|지르|질러|지를|짜리|결제|써도|쓰면")


def _has_purchase_intent(normalized: str, question: str) -> bool:  # noqa: PLR0911 - one return per intent boundary.
    """Decide whether the whitespace-free text is a purchase question at all.

    Strict buy verbs count on their own. Casual verbs ("사고싶"/"사볼까"/"사둘까")
    collide with finance/definition/goal questions, so they need an amount or a
    known item. Future-tense plans need both. Everyday spending verbs ("시켜도",
    "타도") need a named item and paying verbs ("결제해도", "내도") an amount or an
    item; none of them may carry saving-goal, 살다, bill or habit wording.
    """
    has_item = bool(purchase_envelopes(question))
    if not has_item and _CONSUMER_PURCHASE.search(normalized) is None:
        # "비트코인 사도 돼?", "XRP 지금 사도 될까요?", "Tesla 50만원어치 사도 돼?": a name no
        # envelope knows may be a share, a coin or a product. The router tells them apart, not a
        # list of tickers; a purchase it names still has its values read from the text. 사다
        # alone is shared with shares; 구매·구입·지르다·"짜리" say the spending themselves.
        return False
    if _PURCHASE_VERB_STRICT.search(normalized) is not None and _buy_verb_counts(question):
        return True
    has_amount = bool(purchase_amounts(question))
    if _PURCHASE_VERB_CASUAL.search(normalized) is not None:
        return has_amount or has_item
    if _PURCHASE_FUTURE_BLOCK.search(normalized) is not None:
        return False
    if _PURCHASE_VERB_FUTURE.search(normalized) is not None:
        return has_item and (has_amount or _PLAN_PERMISSION.search(normalized) is not None)
    if (
        has_item
        and _PURCHASE_VERB_NOUN.search(normalized) is not None
        and _PURCHASE_SPEND_BLOCK.search(normalized) is None
        and _PURCHASE_HABIT.search(normalized) is None
    ):
        return True  # "운동화 10만원 오늘 현금으로 사는 건?"
    return _spend_intent(normalized, question, has_item=has_item, has_amount=has_amount)


def _spend_intent(normalized: str, question: str, *, has_item: bool, has_amount: bool) -> bool:  # noqa: PLR0911
    """Decide the everyday-spend tier ("치킨 시켜도 돼?", "택시 타도 될까?", "결제해도 돼?")."""
    if _PURCHASE_SPEND_BLOCK.search(normalized) is not None or _PURCHASE_HABIT.search(normalized) is not None:
        return False
    permission = _SPEND_PERMISSION.search(normalized)
    if (
        has_item
        and permission is not None
        and _PERMISSION_LOOKUP.search(normalized) is None
        and (_PERMISSION_HABIT.search(normalized) is None or _amount_not_price(normalized))
        and _PURCHASE_SPEND_CONTEXT.search(normalized, permission.end()) is None
    ):
        # "잔액 5만원 남았는데 오늘 치킨 시켜도 돼?" asks permission for a purchase whose price
        # is still missing; the stated balance or past spend is asked about, not booked.
        return True
    if _amount_not_price(normalized):
        return False
    if _PURCHASE_SPEND_CONTEXT.search(normalized) is not None and not (
        len(purchase_amounts(question)) == 1
        and has_item
        and _purchase_date_token(normalized, exclude=None) is not None
        and _price_shaped(question)
    ):
        return False
    if _PURCHASE_VERB_SPEND_ITEM.search(normalized) is not None or (
        _PURCHASE_VERB_TICKET.search(normalized) is not None
        and _PURCHASE_TICKET_ITEM.search(normalized) is not None
    ):
        return has_item
    if _PURCHASE_VERB_SPEND_MONEY.search(normalized) is not None:
        return has_amount or has_item
    if _PURCHASE_VERB_USE.search(normalized) is not None:
        return has_amount
    return (
        has_item
        and has_amount
        and (_PURCHASE_CASH.search(normalized) is not None or _PURCHASE_CARD.search(normalized) is not None)
        and _purchase_date_token(normalized, exclude=None) is not None
        and _PLAN_PERMISSION.search(normalized) is not None
    )


def natural_purchase(question: str, *, intent_known: bool = False) -> NaturalPurchase | str | None:
    """Admit one clear, single-payment Korean purchase question without a model call.

    Returns ``None`` when the text shows no clear purchase intent at all (the
    caller must keep its existing finance/out-of-scope routing). Returns one of
    the ``purchase_*_required``/``purchase_installment_unsupported`` codes when
    purchase intent is clear but a required field is missing, ambiguous, or out
    of the supported single-payment scope; the caller must surface this as a
    clarification, never as a guessed expense change. Returns ``NaturalPurchase``
    only when amount, item envelope, and purchase date are all unambiguous from
    the text alone. Account/card selection may still need the caller's Twin
    snapshot and can still fail closed there.
    """
    text = unicodedata.normalize("NFKC", question).lower()
    balance = _BALANCE_STATEMENT.search(text)
    if balance is None or _BALANCE_DUE.match(text, balance.end()) is not None:
        return _admit_purchase(question, intent_known=intent_known)
    # "잔액 3만원이야. 오늘 치킨 시켜도 돼?" states what is left; the price is read from the rest,
    # and only a price-shaped amount counts there ("월급 250만원 들어오면" is not the price).
    rest = text[: balance.start()] + " " + text[balance.end() :]
    result = natural_purchase(rest, intent_known=intent_known)
    if isinstance(result, NaturalPurchase):
        tokens = _joined_amounts(rest).split()
        index = _first_amount_index(tokens)
        if index is None or not (_strict_price_shape(tokens, index) or _named_item_price(tokens, index)):
            return "purchase_amount_required"
    return result


def _asks_purchase(question: str) -> bool:
    """Whether the text asks about a purchase at all, priced or not."""
    return _has_purchase_intent(re.sub(r"\s+", "", unicodedata.normalize("NFKC", question).lower()), question)


def _admit_purchase(  # noqa: PLR0911 - one return per clarify boundary.
    question: str, *, intent_known: bool = False,
) -> NaturalPurchase | str | None:
    normalized = re.sub(r"\s+", "", unicodedata.normalize("NFKC", question).lower())
    if not normalized or not (intent_known or _has_purchase_intent(normalized, question)):
        return None
    # Once the text is a purchase, "커피 40000짜리", "치킨 4만인데" name the price without 원.
    question = with_bare_won(question)
    normalized = re.sub(r"\s+", "", unicodedata.normalize("NFKC", question).lower())
    if _PURCHASE_INSTALLMENT.search(normalized) is not None:
        # Multi-installment purchases need a payment schedule the FDT contract
        # cannot express yet (see scratchpad/PURCHASE-SPIKE.md ``4. Installment``).
        return "purchase_installment_unsupported"
    amounts = purchase_amounts(question)
    if (
        len(amounts) != 1
        or _amount_not_price(normalized)
        or not _amount_reads_as_price(normalized, question)
    ):
        # "잔액 5만원 남았는데 노트북 사도 돼?" names the balance, not the price.
        return "purchase_amount_required"
    amount_krw = amounts[0]
    if not 0 < amount_krw <= _MAX_NATURAL_GOAL_KRW:
        return "purchase_amount_required"
    # An item names its envelope; once the text is a purchase, so does the envelope's own name
    # ("가습기 3만원 사도 돼?" → "쇼핑이요").
    envelopes = purchase_envelopes(question) or named_envelopes(question)
    if len(envelopes) != 1:
        return "purchase_envelope_required"
    is_card = _PURCHASE_CARD.search(normalized) is not None
    is_cash = _PURCHASE_CASH.search(normalized) is not None
    if is_card and is_cash:
        return "purchase_payment_method_required"
    payment_hint: Literal["cash", "card"] | None = "card" if is_card else "cash" if is_cash else None
    card_payment_date: str | None = None
    if payment_hint == "card":
        payment_match = _PURCHASE_PAYMENT_DATE.search(normalized)
        if payment_match is None:
            # A card purchase without its own real payment date would silently
            # treat the purchase date as the settlement date, which the vendor
            # contract explicitly forbids (see coaching_contract.py card rule).
            # A clean single-card phrasing already named the method, so the
            # generic "cash or card?" clarify only loops; a distinct code asks
            # precisely for the missing settlement date instead of re-asking the
            # method. Inferring a default settlement date is deliberately not
            # done here (the text-only parser has no billing cycle and the vendor
            # forbids reusing the purchase date), so this stays fail-closed.
            return "purchase_card_payment_date_required"
        card_payment_date = payment_match.group("date") or payment_match.group("date2")
    date_token = _purchase_date_token(normalized, exclude=card_payment_date)
    if date_token is None:
        return "purchase_date_required"
    return NaturalPurchase(
        amount_krw=amount_krw,
        envelope=next(iter(envelopes)),
        date_token=date_token,
        payment_hint=payment_hint,
        card_payment_date=card_payment_date,
    )


def _purchase_date_token(normalized: str, *, exclude: str | None) -> str | None:
    """Resolve only the four calendar expressions the spec admits, never a guess."""
    if _PURCHASE_DATE_TOMORROW.search(normalized) is not None:
        return "tomorrow"
    if _PURCHASE_DATE_NEXT_WEEK.search(normalized) is not None:
        return "next_week"
    if _PURCHASE_DATE_THIS_WEEK.search(normalized) is not None:
        return "this_week"
    if _PURCHASE_DATE_TODAY.search(normalized) is not None:
        return "today"
    dates = [match.group("date") for match in _PURCHASE_DATE_ISO.finditer(normalized)]
    if exclude is not None:
        dates = [found for found in dates if found != exclude]
    if len(dates) != 1:
        return None
    return dates[0]


# Model-free only for the twin/FDT-backed topics: an insurance, income,
# fixed-cost, or goal question resolves against the separately submitted
# personal-context profile, which is optional and far less established than the
# Twin snapshot, so it keeps the model-routed path even when the grammar itself
# is a clean, complete lookup.  ``budget`` is included because its summary is
# rendered directly from the ledger (``personal_service._budget_summary``,
# ``model="not_called"``), so it is as grounded as the snapshot topics.
_TWIN_BACKED_TOPICS: Final[frozenset[str]] = frozenset(
    {"accounts", "assets", "debts", "payments", "budget"}
)


# A balance check asks how much is left in the envelopes now ("봉투 잔액 보여줘",
# "소비 잔액 확인해줘", "예산 괜찮아?", "예산 초과한 봉투 있어?"). It is answered by
# the envelope table plus a short summary, never by the forecast/risk simulation.
# An envelope name is a budget subject too ("교통비 얼마 남았더라?"); 건강·교통·여가 alone
# are everyday words, so only their unambiguous forms count.
_BALANCE_SUBJECT: Final = re.compile(
    r"봉투|예산|소비|지출|외식|식비|교통비|의료|취미|쇼핑|마트|편의점|잡화"
    r"|기타(?=봉투|예산|는|은|얼마|잔액|잔고|남은|남았|지금)"  # 기타 alone is also a guitar
    r"|여가비|취미비|의료비|병원비|쇼핑비|마트비|편의점비"
)
_BALANCE_ASK: Final = re.compile(
    r"잔액|잔고|잔여|남은|남았|남아|남음|여유|초과|넘은|넘었|넘어|괜찮|얼마있|얼마나있|쓸수있는|balance"
)
# Looking words ask the balance only with a budget noun: "쇼핑 봉투 현황", not "오늘 외식 지출 상태".
_BALANCE_ASK_WEAK: Final = re.compile(r"현황|상태|확인|봐도|봐줘|보여")
_BALANCE_BUDGET_NOUN: Final = re.compile(r"봉투|예산|잔액|잔고")
# "교통비 봉투를 확인할 수 있을까요?" is a polite request, not an outcome question.
_POLITE_REQUEST: Final = re.compile(
    r"(?:확인|알려|보여|볼|알)(?:해|줄|주실|할)?수있(?:을까|을까요|나요|어|어요|니)|봐도(?:될까|되나|돼)"
)
# "쇼핑 봉투는 얼마야?", "외식 예산 얼마야?": a bare 얼마 asks the balance only next to 봉투/예산.
_BALANCE_HOW_MUCH: Final = re.compile(
    r"(?:봉투|예산)(?:은|는|이|가|도)?(?:다|전부|전체|합쳐서|합치면|총)?얼마"
)
_BALANCE_EXCLUDE: Final = re.compile(
    r"예측|전망|앞으로|다음달|다음주|내일|모레|월말|말까지|말에|위험|부족|하면|되면|줄이|늘리"
    r"|계좌|통장|현금|카드|대출|빚|부채|자산|보험|소득|월급|목표|지난|작년|썼|쓴|내역|기간|risk|리스크"
)
# The balance check answers from the ledger alone, so anything that needs a future
# point ("30일 뒤", "향후", "이번달 말까지"), an outcome ("남을까", "괜찮을까"), or a
# purchase review ("3만원짜리 책 살 건데") keeps its forecast/purchase route instead.
_BALANCE_NOT_NOW: Final = re.compile(
    r"뒤|후|향후|(?<!지금)까지|동안|달말|말일|을까|될까|할까|가능성|확률|(?:을|할|될|날|랄|갈|질)(?:것|거)같"
    r"|살(?:건|거|게|까|래|려|예정)|사려|사면|사도|사고싶|구매|구입|결제할|결제하려"
    r"|\d[\d,]*(?:만|천|백)?원"
)


_BALANCE_ENVELOPE_WORDS: Final[dict[str, str]] = {
    **_WHAT_IF_ENVELOPE_ALIASES,
    "교통": "교통비",
    "의료": "의료·건강",
    "건강": "의료·건강",
    "취미": "취미·여가",
    "여가": "취미·여가",
    "잡화": "편의점·마트·잡화",
}


_WHAT_IF_REDUCE: Final = re.compile(
    r"줄이면|줄인다면|줄여서|줄여도|아끼면|아낀다면|덜쓰면|빼면|컷하면|절약하면|절감하면|삭감하면"
)
# How-to, saving-plan and plain arithmetic questions are not a what-if branch.
# "외식 줄이면 될까?", "쇼핑 아끼면 어떻게 돼?" ask what a cut does, with no rate yet.
_WHAT_IF_ASKS_OUTCOME: Final = re.compile(
    r"(?:면|다면).{0,8}(?:어떻게|될까|괜찮|어때|얼마|남을|나아|달라|도움|아껴|아낄)"
)
_WHAT_IF_AMOUNT_NOT: Final = re.compile(
    r"어떻게해야|방법|모으려면|모으려고|계획|1년에|일년에|한달에|매달|월[0-9]"
)
_SPENDING_ASK: Final = re.compile(
    r"얼마(?:나)?(?:썼|쓴|지출|소비|나갔|나왔|했)|(?:썼|쓴|지출했|소비했|나갔|나간|나왔).{0,6}(?:얼마|몇)"
    r"|(?:지출|소비)(?:은|는|이|가)?(?:얼마|총액|합계|알려|보여)|(?:총|전체)(?:지출|소비)"
)
# The amount must be what is saved ("100만원 모을 수 있을까"), not merely next to a saving
# word ("저축은행에 5천만원 넣어도", "카드 만들 때 연회비 3만원이면").
_GOAL_AMOUNT_VERB: Final = re.compile(
    r"원(?:이라도|라도|이나|정도|쯤|까지|넘게|이상|목표|을|를|이|은|는|도|만|씩|따로|더|좀|만큼){0,3}"
    r"(?:모으|모을|모은|모아|모이|모여|모울|저축|저금|달성|만들|채우|채울|마련|남길|세이브)"
    r"|원(?:을|를|이|의)?목표(?:가|는|를|로)?(?:실현|달성|현실|가능|어떨|괜찮|될)"
)
_GOAL_NOT_SAVING: Final = re.compile(
    r"넣어|예치해|예치하|연회비|(?:대출|마이너스|한도).{0,12}(?:만들|채우|채울|받)|(?:모이|모으|모아)면"
)
_FIXED_COST: Final = re.compile(r"월세|관리비|통신비|구독|보험료|고정비")
_SPENDING_NOT_LOOKUP: Final = re.compile(r"공제|연말정산|해야|하려면|받으려면")
# A goal deadline the goal branch cannot compute yet ("1년 동안", "연말까지", "6개월 안에").
_GOAL_UNSUPPORTED_PERIOD: Final = re.compile(
    r"[0-9]+개월|[0-9]+년|연말|올해|내년|급여|월급|[0-9]+주|반년|일년|[0-9]+월(?![급세])"
)
# Calendar words the spending parser does not take (it takes 지난달·이번 달·오늘·어제·현재까지).
_UNSUPPORTED_SPENDING_PERIOD: Final = re.compile(
    r"이번주|지난주|저번주|주말|올해|작년|지난해|상반기|하반기|분기|최근\d+일|지난\d+일|\d+월"
)


_ALIAS_PARTICLE: Final = re.compile(
    r"(?:이랑|랑|하고|와|과|을|를|은|는|이|가|도|에서|에다가|에다|에|이나|나|이든|든|까지|부터|만|및|,)$"
)


def _envelopes_before_amount(question: str) -> set[str]:
    """Envelopes the reduction names ("외식비랑 교통비 3만원씩"), read before the amount as whole words."""
    # "3만원씩", "각각" or two amounts reduce every named envelope, so keep reading past the amount.
    each = "씩" in question or "각각" in question or len(purchase_amounts(question)) > 1
    named: set[str] = set()
    for raw in unicodedata.normalize("NFKC", question).lower().split():
        token = raw.strip(_WORD_EDGE_MARKS)
        if purchase_amounts(token):
            if not each:
                break
            continue
        core = _ALIAS_PARTICLE.sub("", token)
        if core != "기타" and core in _WHAT_IF_ENVELOPE_ALIASES:
            named.add(_WHAT_IF_ENVELOPE_ALIASES[core])
    return named


def unanswerable_turn_code(question: str) -> str | None:  # noqa: PLR0911 - one return per missing piece.
    """Name the one missing piece of an otherwise clear goal, what-if or spending question.

    "100만원 모을 수 있을까?" has no deadline, "외식비 3만원 줄이면?" gives an amount
    where the what-if branch takes a percentage, and "이번 주에 얼마 썼어?" names a
    period the ledger query does not support. Each used to reach the router and come
    back as the generic envelope review; asking for the missing piece keeps the intent.
    """
    normalized = re.sub(r"\s+", "", unicodedata.normalize("NFKC", question).lower())
    if not normalized or natural_goal(question) is not None or natural_what_if(question) is not None:
        return None
    if investment_product(question):
        return None
    if (
        _GOAL_AMOUNT_VERB.search(normalized) is not None
        and _GOAL_FEASIBILITY.search(normalized) is not None
        and _GOAL_PERIOD.search(normalized) is None
        and _GOAL_DISALLOWED.search(normalized) is None
        and _GOAL_NOT_SAVING.search(normalized) is None
        and _GOAL_PAST.search(normalized) is None
        and not has_buy_verb(question)
        and len(purchase_amounts(question)) == 1
    ):
        if _GOAL_UNSUPPORTED_PERIOD.search(normalized) is not None:
            return "goal_period_unsupported"
        return "goal_period_required"
    if (
        _WHAT_IF_REDUCE.search(normalized) is not None
        and purchase_amounts(question)
        and _WHAT_IF_PERCENT.search(normalized) is None
        and _WHAT_IF_AMOUNT_NOT.search(normalized) is None
        and _WHAT_IF_DISALLOWED.search(normalized) is None
        and _FIXED_COST.search(normalized) is None
        and (
            any(alias in normalized for alias in _WHAT_IF_ENVELOPE_ALIASES)
            or _WHAT_IF_GENERIC_EXPENSE.search(normalized) is not None
        )
    ):
        # A week, a day count or two envelopes cannot take the percentage either
        # ("다음 주 외식비 3만원 줄이면", "외식비랑 교통비 3만원씩 줄이면").
        named = _envelopes_before_amount(question)
        if _STORED_NON_MONTH.search(normalized) is not None or len(named) > 1:
            return "what_if_scope_unsupported"
        return "what_if_percent_required"
    rate_cut = (
        _WHAT_IF_RATE_CUT.search(normalized) is not None
        and _WHAT_IF_DISALLOWED.search(normalized) is None
        and _WHAT_IF_PAST.search(normalized) is None
        and (_WHAT_IF_OUTCOME.search(normalized) is not None or _WHAT_IF_BARE.search(normalized) is not None)
    )
    rate_envelopes = {
        envelope for alias, envelope in _WHAT_IF_ENVELOPE_ALIASES.items() if alias in normalized
    }
    if rate_cut and (
        (_STORED_NON_MONTH.search(normalized) is not None
         and (rate_envelopes or _WHAT_IF_GENERIC_EXPENSE.search(normalized) is not None))
        or len(rate_envelopes) > 1  # "외식이랑 쇼핑 20%씩 줄이면?"
    ):
        return "what_if_scope_unsupported"
    if (
        _WHAT_IF_REDUCE.search(normalized) is not None
        and not purchase_amounts(question)
        and _WHAT_IF_PERCENT.search(normalized) is None
        and _WHAT_IF_DISALLOWED.search(normalized) is None
        and _WHAT_IF_AMOUNT_NOT.search(normalized) is None
        and _FIXED_COST.search(normalized) is None
        and _STORED_NON_MONTH.search(normalized) is None
        and _WHAT_IF_ASKS_OUTCOME.search(normalized) is not None
        and len({
            envelope for alias, envelope in _WHAT_IF_ENVELOPE_ALIASES.items() if alias in normalized
        }) == 1
    ):
        return "what_if_percent_required"
    if (
        not supports_spending_question(question)
        and _SPENDING_ASK.search(normalized) is not None
        and _UNSUPPORTED_SPENDING_PERIOD.search(normalized) is not None
        and _SPENDING_NOT_LOOKUP.search(normalized) is None
    ):
        return "spending_period_unsupported"
    return None


# Deciding to buy or sell a named investment ("삼성전자 지금 사도 될까?", "QQQ 담아도
# 돼?", "테슬라 팔까?") is declined deterministically; the router sent these anywhere
# from a purchase clarification to the envelope review.
_INVESTMENT_ACTION: Final = re.compile(
    r"사도|살까|사면|사야|사볼까|사고싶|사는거|사는게|사모으|사모아|매수|팔까|팔아|팔면|팔고|파는거|매도"
    r"|들어가도|들어갈까|들어가는거|들어가는게|들어가면|넣어도|넣을까|넣으면|투자해도|투자할까|투자하면"
    r"|담아도|담을까|손절|물렸|정리할|정리해야|갈아탈|환매할까|환매해도|환매하는|가입해도|가입할까|타이밍|추천해"
    r"|투자해볼만|투자할만|투자하는게|투자하는거|숏쳐|숏칠|공매도|롱쳐|롱칠|투자하려는데|좋은투자|투자가치"
)
# A definition, a how-to or a tax/fee question about trading is a concept question,
# unless it also asks the decision itself ("테슬라 지금 사도 되는지 설명해줘").
_INVESTMENT_NOT_DECISION: Final = re.compile(
    r"뭐야|뭐예요|뭔가요|뭐지|뜻|의미|설명|방법|세금|수수료|공부|차이|개념"
)
_INVESTMENT_DECIDE: Final = re.compile(
    r"^(?=.*(?:지금|오늘|당장|요즘|이번에|이제|언제|더사|더매수|추가로|추가매수|물타|[0-9][0-9,.]*(?:[십백천만억]*원|주)))"
    r"(?!.*(?:까하는데|까고민|까생각|까싶은데)).*?(?:"
    r"(?:사도|팔아도|매수해도|매도해도|들어가도|넣어도|투자해도|담아도|환매해도)(?:돼|될까|되나|되는|되냐|괜찮|되$)"
    r"|살까|팔까|사야할까|사야돼|사야해|팔아야|매수할까|매도할까|들어갈까|넣을까|투자할까|담을까"
    r"|손절할까|손절해야|익절할까|익절해야|환매할까|갈아탈까|사는게좋|사는거어때"
    r"|투자해볼만|투자할만|투자하는게(?:좋|나을|괜찮|어때|스마트|맞)|숏쳐도|숏칠까|공매도해도|롱쳐도"
    r"|투자하려는데(?:어떨|어때|괜찮)|좋은투자일|투자가치가?있)"
)


def investment_decision(question: str) -> bool:
    """Whether the turn asks whether to buy or sell a named stock, fund, ETF or coin."""
    words = compact(question)
    if (
        investment_product(question)
        and not purchase_envelopes(question)
        and _BARE_BUY_END.search(unicodedata.normalize("NFKC", question).lower()) is not None
    ):
        return True  # "애플 주식 지금 사?", "비트코인 지금 사?"
    return (
        investment_product(question)
        and not purchase_envelopes(question)
        and _INVESTMENT_ACTION.search(words) is not None
        and (
            _INVESTMENT_DECIDE.search(words) is not None
            or _INVESTMENT_NOT_DECISION.search(words) is None
            or _decision_ends_sentence(question)
        )
    )


_ASSET_TRADE: Final = re.compile(
    r"사도|살까|사야|매수|팔까|팔아|팔면|팔어|매도|들어가도|들어갈까|물타|손절|익절|환매|넣어도|넣을까"
    r"|담아도|담을까|투자해도|투자할까|올인|실을까|타이밍"
)


def spend_or_trade_decision(question: str) -> bool:
    """Whether the turn asks to buy, pay for or trade something ("전기포트 3만원 사도 될까?").

    Such a turn is a purchase or an investment decision, never a concept question, so the
    concept shortcut leaves it to the router to tell which.
    """
    normalized = re.sub(r"\s+", "", unicodedata.normalize("NFKC", question).lower())
    return (
        has_buy_verb(question)
        or _PURCHASE_VERB_STRICT.search(normalized) is not None
        or _SPEND_PERMISSION.search(normalized) is not None
        or _ASSET_TRADE.search(normalized) is not None
    )


def asset_trade_decision(question: str) -> bool:
    """Whether a finance-routed turn asks to buy or sell something no envelope knows.

    Only the router's finance intent makes "XRP 지금 사도 될까요?" or "금 선물 지금 살 타이밍?" a
    trade on an asset; no ticker list decides it. A definition or method ask is not a decision.
    """
    words = compact(question)
    return (
        not purchase_envelopes(question)
        and _ASSET_TRADE.search(words) is not None
        and (_INVESTMENT_NOT_DECISION.search(words) is None or _decision_ends_sentence(question))
    )


# "종신보험 가입해야 할까", "퇴직연금 어디로 옮기는 게 좋아", "이 코인 단타 쳐도 될까" ask for advice on a
# product or position; "비트코인 앞으로 올라갈까?", "이 회사 주식 전망 어때" ask for a market outlook.
# No approved fact settles either, and only the router's finance intent makes the words mean this.
_FINANCE_ADVICE: Final = re.compile(
    r"해야할까|해야할지|해야하나|해야돼|하는게좋|하는게나아|하는게맞|어디로|어느쪽|어느게나아|살지말지|할지말지"
    r"|쳐도|해도될까|해도돼|해도되나|해도괜찮|갈아타|옮길까|옮겨야|리모델링|비중.{0,6}조절"
)
_MARKET_OUTLOOK: Final = re.compile(
    r"올라갈까|내려갈까|오를까|떨어질까|오르겠|떨어지겠|전망|목표가|반등할|폭락할|폭등할|종목분석"
)


def finance_advice_decision(question: str) -> bool:
    """Whether a finance-routed turn asks for product advice or a market outlook, not a concept."""
    words = compact(question)
    if purchase_envelopes(question) or (
        _INVESTMENT_NOT_DECISION.search(words) is not None and not _decision_ends_sentence(question)
    ):
        return False
    if _FINANCE_ADVICE.search(words) is not None:
        return True
    outlook = _MARKET_OUTLOOK.search(words)
    # "금리 인상되면 채권 가격 떨어질까?" asks how one thing moves another, a concept.
    return outlook is not None and _CONDITION.search(words[:outlook.start()]) is None


_CONDITION: Final = re.compile(r"[가-힣]면|때|경우")


# "이 아파트 지금 사도 될까", "집 살까?": a home is bought with savings and loans, not this month's
# envelopes, so no purchase check can judge it. "집들이 선물 사도 돼?" buys a gift.
_REAL_ESTATE_TRADE: Final = re.compile(
    r"(?:아파트|주택|부동산|오피스텔|빌라|토지|땅|상가|분양권|(?<![가-힣])집)(?:을|를|이|은|는|도)?"
    r"(?:지금|이번에|올해|내년에)?"
    r"(?:사도|사야|사려|사면|사고|사는|살까|살거|살래|살려|살지|사[?!.]*$|매수|매매|구매|구입|팔까|팔아|팔면|매도|계약)"
)


def real_estate_trade(question: str) -> bool:
    """Whether the turn asks to buy or sell a home or land rather than a consumer good."""
    words = compact(question)
    return _REAL_ESTATE_TRADE.search(words) is not None and _INVESTMENT_NOT_DECISION.search(words) is None


# "엄마 카드값 많이 나왔대", "형이 적자래": another person's money, which no connected data holds.
# The user's own decision about them ("엄마 선물 5만원 사도 될까?", "동생 용돈 주면 괜찮아?") stays.
_THIRD_PARTY: Final = re.compile(
    r"^(?:우리\s*)?(?:엄마|아빠|어머니|아버지|부모님|시어머니|시아버지|장모님|장인어른|형|누나|언니|오빠|동생"
    r"|남편|아내|와이프|남친|여친|남자\s*친구|여자\s*친구|애인|친구|룸메이트|룸메|아들|딸|동료|팀장님?|사장님?)"
    r"(?:가|이|는|은|도|께서|네|의)?(?=\s|$)"
)
_THIRD_PARTY_MONEY: Final = re.compile(
    r"돈|카드|적자|흑자|저축|용돈|월급|빚|대출|지출|소비|결제|생활비|통장|잔액|써|썼|쓰는|쓴"
)
_OWN_SIDE: Final = re.compile(
    r"(?:^|\s)(?:내|나|제|저)(?:가|는|도|의)?\s|내가|제가|나도|저도|나한테|저한테|우리집|예산|봉투"
    r"|써도|사도|사줘도|줘도|드려도|보내도|보태|선물|될까|할까|괜찮|되나|해줘도|받으면|주면|드리면"
)


def third_party_money(question: str) -> bool:
    """Whether the turn is about another person's money with nothing of the user's own asked."""
    text = unicodedata.normalize("NFKC", question).strip()
    return (
        _THIRD_PARTY.search(text) is not None
        and _THIRD_PARTY_MONEY.search(text) is not None
        and _OWN_SIDE.search(text) is None
    )


_BARE_ENVELOPE_TAIL: Final = re.compile(
    r"(?:봉투|예산|항목)?(?:은|는|이|가|요|이요)?(?:얼마(?:야|예요|남았어)?|남았어|잔액(?:은)?|어때)?[?!.~]*"
)


def bare_envelope_question(question: str) -> bool:
    """Whether the text is only an envelope's name with an asking tail ("편의점·마트 봉투는?", "외식은?")."""
    words = compact(question)
    names = sorted(
        {compact(name) for name in (*_ENVELOPE_NAMES, *_WHAT_IF_ENVELOPE_ALIASES)} | {"편의점마트"},
        key=len, reverse=True,
    )
    name = next((name for name in names if words.startswith(name)), None)
    return name is not None and _BARE_ENVELOPE_TAIL.fullmatch(words[len(name):]) is not None


def states_purchase(question: str) -> bool:
    """Whether the text itself carries a purchase: an amount, a payment, a buy or pay verb."""
    normalized = re.sub(r"\s+", "", unicodedata.normalize("NFKC", question).lower())
    # "오늘 옷 5만 현금으로 가능할까" states its price and payment without a buy verb.
    return bool(purchase_amounts(with_bare_won(question))) or any(
        pattern.search(normalized) is not None
        for pattern in (
            _PURCHASE_VERB, _PURCHASE_VERB_STRICT, _PURCHASE_VERB_CASUAL, _PURCHASE_VERB_FUTURE,
            _PURCHASE_VERB_NOUN, _PURCHASE_VERB_SPEND_ITEM, _PURCHASE_VERB_TICKET,
            _PURCHASE_VERB_SPEND_MONEY, _PURCHASE_VERB_USE, _CONSUMER_PURCHASE, _SPEND_PERMISSION,
            _PURCHASE_CARD, _PURCHASE_CASH,
        )
    )


# A typed word "사" closing the question buys ("지금 사?"); inside 회사 or 사기 it does not.
_BARE_BUY_END: Final = re.compile(r"(?:^|\s)사(?:요|야)?\s*[?!.~]*$")


def _decision_ends_sentence(question: str) -> bool:
    """Whether a buy/sell decision ends a sentence with no concept ask after it.

    "세금 신경 안 쓰고 테슬라 사도 돼?" asks the decision; "ISA에서 ETF 사도 되나요? 세금은?" asks the tax.
    """
    text = re.sub(r"\s+", "", unicodedata.normalize("NFKC", question).lower())
    found = list(_DECIDE_FINAL.finditer(text))
    if not found or _ELIGIBLE_BEFORE.search(text, 0, found[-1].start()) is not None:
        return False  # "주식 수수료 설명해줘. 미성년자도 사도 돼?" asks who may, not whether to
    return _INVESTMENT_NOT_DECISION.search(text, found[-1].end()) is None


_ELIGIBLE_BEFORE: Final = re.compile(
    r"(?:누구나|아무나|미성년자도?|외국인도|학생도|초보도|초보자도|어디서|어디에서|어떻게|거기서|거기에서|매달|매월)$"
)
_DECIDE_FINAL: Final = re.compile(
    r"(?:(?:사도|팔아도|매수해도|매도해도|들어가도|넣어도|투자해도|담아도|환매해도)(?:돼|될까|되나|되는|되냐|괜찮)"
    r"|살까|팔까|사야할까|사야돼|사야해|팔아야|매수할까|매도할까|들어갈까|넣을까|투자할까|담을까"
    r"|손절할까|손절해야|익절할까|환매할까|갈아탈까|사는게좋|사는거어때)"
    r"(?:요|야|어|지|니|냐|나요|까요|거야|건가|걸까|는거야|는건가|ㅠ|ㅜ|ㅋ|ㅎ)*(?=[?!.~]|$)"
)
_GOAL_PERIOD_FRAGMENT: Final = re.compile(
    r"(?:(?:앞으로)?[0-9]{1,3}일|이번달|이달|다음달|월말|[0-9]{1,2}개월|[0-9]{1,2}월|[0-9]+년|연말|올해|내년|반년)"
    r"(?:말)?(?:까지|에|안에|안으로|내에|동안|중에|말까지|전까지|전에|뒤)?(?:요|이요)?"
)
_STORED_GOAL_PERIOD: Final = re.compile(
    r"(?:[0-9]+\s*개월|[0-9]+\s*년|[0-9]+\s*월(?![급세])|연말|올해|내년|반년|일년)"
    r"\s*(?:말)?\s*(?:동안|안에|안으로|까지|내에|뒤)?"
)


# "다음주까지 예산 괜찮아?" asks when; "이번 달", "월말까지" answer it.
_REVIEW_PERIOD_FRAGMENT: Final = re.compile(
    r"(?:그럼|그러면|음|아)*(?:이번달|이달|이번달말|이달말|월말|다음달|지난달|저번달|오늘|어제|현재까지|지금까지)"
    r"(?:까지|기준|동안|으로|로|에|요|이요)*"
)
_STORED_REVIEW_PERIOD: Final = re.compile(
    r"(?:다음|이번|지난|저번)\s*주\s*(?:말)?(?:까지|에|동안|는|은)?|주말\s*(?:까지|에|동안)?"
    r"|[0-9]{1,2}\s*일\s*(?:까지|동안|뒤|후)?|한\s*달\s*(?:뒤|후|동안)?|음력|윤달|영업일|공휴일"
    r"|[0-9]{4}\s*-\s*[0-9]{1,2}\s*-\s*[0-9]{1,2}\s*(?:까지)?"
)


def merged_period_question(question_so_far: str, followup: str) -> str | None:
    """Put a bare period answer ("이번 달") in place of the one the stored question could not use."""
    if _REVIEW_PERIOD_FRAGMENT.fullmatch(compact(followup)) is None:
        return None
    stored = " ".join(_STORED_REVIEW_PERIOD.sub(" ", question_so_far).split())
    return f"{followup.strip()} {stored}"


def merged_goal_question(question_so_far: str, followup: str) -> str | None:
    """Put a bare deadline answer ("다음 달까지", "3개월") in front of the stored goal question.

    The deadline the stored question already failed on is dropped, so "1년 동안 …" answered
    with "다음 달까지" is computed for next month; an unsupported answer is asked again.
    """
    fragment = compact(followup)
    if not fragment or _GOAL_PERIOD_FRAGMENT.fullmatch(fragment) is None:
        return None
    stored = _STORED_GOAL_PERIOD.sub(" ", question_so_far)
    return f"{followup.strip()} {' '.join(stored.split())}"


_WHAT_IF_ALIAS_PATTERN: Final = "|".join(
    re.escape(alias) for alias in sorted(_WHAT_IF_ENVELOPE_ALIASES, key=len, reverse=True)
)
_WHAT_IF_RATE_FRAGMENT: Final = re.compile(
    rf"(?:(?P<envelope>{_WHAT_IF_ALIAS_PATTERN})(?:을|를|은|는)?)?(?P<percent>\d{{1,2}})(?:%|퍼센트|프로)"
    r"(?:로|요|정도|만|씩)?(?:줄이면|줄여서|줄여줘|줄일게|줄이면요|로줄이면)?(?:요)?[?!.]*"
)
# "앞으로" is the rest of this month for the what-if engine; weeks and day counts are not.
_STORED_NON_MONTH: Final = re.compile(r"[0-9]+일|이번주|다음주|지난주|주말|[0-9]+개월")


def merged_what_if_question(question_so_far: str, followup: str) -> str | None:
    """Rebuild the stored won-amount what-if with the bare percentage the follow-up gives.

    Only "20%", "20%로", "쇼핑 10%" style answers merge; "아니 20% 더 쓰면?" or a new question
    is handled fresh. An envelope named in the answer wins over the stored one.
    """
    normalized = re.sub(r"\s+", "", unicodedata.normalize("NFKC", followup).lower())
    answer = _WHAT_IF_RATE_FRAGMENT.fullmatch(normalized)
    if answer is None:
        return None
    stored = re.sub(r"\s+", "", unicodedata.normalize("NFKC", question_so_far).lower())
    if _STORED_NON_MONTH.search(stored) is not None:
        return None
    stored_envelopes = {envelope for alias, envelope in _WHAT_IF_ENVELOPE_ALIASES.items() if alias in stored}
    if answer["envelope"]:
        subject = _WHAT_IF_ENVELOPE_ALIASES[answer["envelope"]]
    elif len(stored_envelopes) == 1:
        subject = next(iter(stored_envelopes))
    elif not stored_envelopes:
        subject = "소비"
    else:
        return None
    period = "다음 달" if "다음달" in stored else "이번 달"
    return f"{period} {subject} {answer['percent']}% 줄이면 어떻게 될까?"


def balance_envelope(question: str) -> str | None:
    """Return the single envelope a balance question names ("외식 예산 얼마 남았어"), if any."""
    normalized = compact(question)
    named = {envelope for word, envelope in _BALANCE_ENVELOPE_WORDS.items() if compact(word) in normalized}
    return next(iter(named)) if len(named) == 1 else None


def balance_check_question(question: str) -> bool:
    """Admit a current envelope-balance check; forecasts, lookups and purchases stay out."""
    normalized = compact(question)
    if (
        not normalized
        or _DEFINITION_LANGUAGE.search(normalized) is not None
        or _BALANCE_EXCLUDE.search(normalized) is not None
        or _BALANCE_NOT_NOW.search(_POLITE_REQUEST.sub("", normalized)) is not None
        or _FUTURE_OVERRUN.search(normalized) is not None
        or natural_purchase(question) is not None
        or supports_spending_question(question)  # "이번달 지출 확인해줘" is the spending lookup
    ):
        return False
    return _BALANCE_SUBJECT.search(normalized) is not None and (
        _BALANCE_ASK.search(normalized) is not None
        or _BALANCE_HOW_MUCH.search(normalized) is not None
        or (
            _BALANCE_ASK_WEAK.search(normalized) is not None
            and _BALANCE_BUDGET_NOUN.search(normalized) is not None
        )
    )


# A connector split can cut a word ("결과를" holds 과), so a multi-part lookup is taken only
# with a lookup verb and never with forecast or definition wording.
_SPENT_ON_WHAT: Final = re.compile(r"뭐(?:에|를|로)?(?:썼|쓴|샀|결제)")
_MULTI_TOPIC_LOOKUP: Final = re.compile(r"얼마|알려|보여|확인")
_MULTI_TOPIC_BLOCK: Final = re.compile(
    r"앞으로|향후|월말|예측|예상|흘러|될까|것같|거같|어떻게|살펴"
    r"|은행|뱅크|증권|토스|(?:국민|신한|우리|하나|농협)(?:은행|뱅크|카드)|마이너스|학자금|전세|월급(?!통장)|청약|적금|예금"
)


def deterministic_lookup_route(question: str) -> LookupRoute | None:
    """Reuse existing exact lookup grammars before consulting the model.

    These are current-state or historical lookup requests, not a semantic
    classifier.  Both downstream handlers independently validate the stored
    snapshot or ledger before displaying a value.  Keeping the admission here
    equal to their established grammars prevents the speed path from silently
    accepting filters, comparisons, forecasts, or a broader personal request.
    """
    # A definition-shaped question ("대출이 뭐야", "예산이 뭐야") must reach the
    # finance-concept path, not be captured as a personal-data lookup. The lookup
    # grammar accepts ``<alias> 뭐야``, so mirror the analysis route's guard here so
    # both no-model paths treat 뭐/뜻/의미/무엇/... identically.
    if _DEFINITION_LANGUAGE.search(_SPENT_ON_WHAT.sub("", compact(question))) is not None:
        return None
    topic = select_personal_topic(question) or filtered_personal_topic(question)
    if topic is not None and topic in _TWIN_BACKED_TOPICS:
        return "personal"
    topics = select_personal_topics(question)
    words = compact(question)
    if (
        topics
        and not any(supports_spending_question(part) for part in connector_fragments(question))
        and _MULTI_TOPIC_LOOKUP.search(words) is not None
        and _MULTI_TOPIC_BLOCK.search(words) is None
        and all(item in _TWIN_BACKED_TOPICS for item in topics)
    ):
        # "총 자산이랑 부채 한 번에 보여줘": each fragment is a stored-snapshot lookup. A
        # fragment no topic covers ("계좌 잔액이랑 이자") is named as unanswered in the reply.
        return "personal"
    if supports_spending_question(question):
        return "history"
    return None


def deterministic_analysis_route(question: str) -> AnalysisRoute | None:  # noqa: C901, PLR0911 - one return per route.
    """Return a route only when the text unambiguously asks about this user's FDT.

    This is a latency shortcut, not an intent model.  Any unsupported, product,
    market, definition, goal, what-if, or ambiguous question returns ``None``
    and follows the existing model router unchanged.  A separate, narrower
    artifact-review admission (``_artifact_review``) runs last, after the
    definition-language guard and the forecast/risk/personal-review block, so
    it can never pre-empt those routes.
    """
    normalized = compact(question)
    if not normalized:
        return None
    # "이번 달 위험 요소 뭐 있어?" lists items; that 뭐 is not a definition request.
    if _DEFINITION_LANGUAGE.search(_ACTIVITY_ASK.sub("", _LISTING.sub("", normalized))) is None:
        has_future_marker = (
            any(marker in normalized for marker in _FUTURE_MARKERS)
            or any(marker in normalized for marker in _STRONG_FUTURE_MARKERS)
            or bool(re.search(r"\d{1,3}일", normalized))
        )
        has_strong_future_marker = any(marker in normalized for marker in _STRONG_FUTURE_MARKERS)
        has_forecast_target = any(target in normalized for target in _FORECAST_TARGETS)
        explicit_forecast = any(term in normalized for term in _FORECAST_TERMS) and has_future_marker
        path_forecast = any(term in normalized for term in _FORECAST_PATH_TERMS) and has_future_marker
        implicit_forecast = (
            has_strong_future_marker
            and any(term in normalized for term in _IMPLICIT_FORECAST_TERMS)
        )
        has_explicit_risk = "위험" in normalized or "리스크" in normalized or "risk" in normalized
        # "앞으로 주식 리스크 어때?" / "투자할 만한 위험자산" ask about markets, not this budget.
        investment_risk = _OWN_BUDGET_SUBJECT.search(normalized) is None and (
            investment_product(question) or _INVESTMENT_SUBJECT.search(normalized) is not None
        )
        risk_is_deprioritized = any(phrase in normalized for phrase in _RISK_DEPRIORITIZED_FOR_PATH)
        # A future-tense spend question is a spend forecast on its own, without a
        # balance/spend noun.  Beyond the future marker it also requires a
        # money/quantity signal (얼마/돈/소비/지출) so a non-financial "쓸까"
        # ("편지 쓸까") never routes here.
        spend_forecast = (
            has_future_marker
            and any(term in normalized for term in _SPEND_FORECAST_TERMS)
            and any(signal in normalized for signal in ("얼마", "돈", "소비", "지출"))
        )
        money_left_forecast = (
            has_strong_future_marker
            and ("돈" in normalized or "얼마" in normalized)
            and any(term in normalized for term in _MONEY_LEFT_TERMS)
        )
        if (
            (
                (has_forecast_target and (explicit_forecast or implicit_forecast or path_forecast))
                or spend_forecast
                or (
                    (money_left_forecast or _MONTH_END_AMOUNT.search(normalized) is not None)
                    and _PAST_TENSE.search(normalized) is None
                )
            )
            and (not has_explicit_risk or risk_is_deprioritized)
            and not investment_product(question)
        ):
            return "forecast"
        if _PERIOD_RISK.search(normalized) is not None and not risk_is_deprioritized and not investment_risk:
            return "risk"
        if (
            _FUTURE_OVERRUN.search(normalized) is not None
            and not investment_risk
            and _OVERRUN_NOT_OWN.search(normalized) is None
        ):
            return "risk"
        risk_outcome = has_explicit_risk or any(term in normalized for term in _RISK_OUTCOME_TERMS)
        if _BUDGET_RISK_QUESTION.fullmatch(normalized) is not None or (
            not investment_risk
            and risk_outcome
            and any(signal in normalized for signal in _RISK_SIGNALS)
            and (has_explicit_risk or has_future_marker)
        ):
            return "risk"
        if _PERSONAL_REVIEW_TARGET.search(normalized) is not None and any(
            action in normalized for action in _REVIEW_ACTIONS
        ):
            return "review"
        if (
            (
                _BUDGET_OUTCOME.search(normalized) is not None
                or (_PERIOD_ONLY_OUTCOME.search(normalized) is not None and not _asks_purchase(question))
            )
            and re.search(r"\d", normalized) is None
            and _OUTCOME_BLOCK.search(normalized) is None
            and not investment_product(question)
        ):
            return "review"
        if _PERIOD_REVIEW.search(normalized) is not None and not investment_product(question):
            return "review"
    if _artifact_review(normalized):
        return "review"
    return None


# A stored needs_clarification carries only the accumulated question text. A bare
# follow-up ("30만원", "내일", "현금으로", "이번달") is merged into that text and the
# single existing parser re-runs, so these helpers never build partial financial
# state themselves; they only decide whether a follow-up is a bare fragment that
# answers the pending question, or a fresh complete turn that must discard it.
# The period tokens mirror ``spending_history._Period`` exactly.
# The merged text is re-parsed and re-stored as the pending context each turn, so a
# pathological chain of re-clarifying fragments could otherwise append without bound
# and eventually exceed ``schemas.PendingClarification.question`` (4000) inside
# ``save_turn``. Bound the merged/stored text to the same order as the per-turn input
# cap (``TurnRequest.question`` is 2000); once the bound is reached we drop the new
# fragment (keeping the leading question the parser needs) rather than append forever.
_MERGED_QUESTION_MAX_CHARS: Final = 2000
_SPENDING_PERIOD_FRAGMENT: Final = re.compile(
    r"(?:그럼|그러면|그면|그렇다면|그리고|근데|아|음)*"
    r"(?P<period>지난달|저번달|이번달|이달|오늘|어제|현재까지|지금까지|현재)"
    # "지난달 기준으로는?", "어제 쓴 건?", "이번 달 거는 어때?", "이번 달 지금까지는?"
    r"(?:지금까지|현재까지)?(?:기준|쓴|쓴거|쓴건|거|건|꺼)?"
    r"(?:동안|까지|의|에|은|는|이야|로|으로)?(?:요)?(?:얼마야|얼마|어때|어떻게돼|어떻게되|는|는요)?"
    r"[?!.~\uff1f\u3002]*"
)


def _parses_to_any_route(question: str) -> bool:
    """Whether a message independently satisfies any existing complete grammar.

    A follow-up that is itself a whole purchase/lookup/analysis/goal/what-if turn
    must never be force-merged into a stale clarification; it is handled fresh.
    """
    return (
        natural_purchase(question) is not None
        or deterministic_lookup_route(question) is not None
        or deterministic_analysis_route(question) is not None
        or natural_goal(question) is not None
        or natural_what_if(question) is not None
    )


def is_bare_purchase_fragment(question: str) -> bool:
    """Admit a follow-up that only supplies a missing purchase field, never a new route.

    It must carry at least one purchase field (amount/date/payment/envelope) and
    must not parse as any complete route on its own, so an unrelated question
    ("복리가 뭐야", off-topic) is discarded rather than merged.
    """
    normalized = re.sub(r"\s+", "", unicodedata.normalize("NFKC", question).lower())
    if (
        not normalized
        or _parses_to_any_route(question)
        # "외식 잔액?", "네이버 지금 사도 돼" are questions of their own, not a field answer.
        or balance_check_question(question)
        or investment_product(question)
    ):
        return False
    if (
        _PURCHASE_VERB.search(normalized) is not None
        or _PURCHASE_VERB_COMPLETE.search(normalized) is not None
    ) and purchase_envelopes(question):
        # The follow-up names its own item with a (prospective or completed) purchase
        # verb, so it is a fresh independent purchase, not a bare field answering the
        # pending question; discard the stale context and handle it fresh. Without an
        # item the verb only restates the pending purchase ("150만원이고 현금으로 오늘 살 거야").
        return False
    has_amount = bool(purchase_amounts(question))
    has_date = any(
        pattern.search(normalized) is not None
        for pattern in (
            _PURCHASE_DATE_TOMORROW,
            _PURCHASE_DATE_NEXT_WEEK,
            _PURCHASE_DATE_THIS_WEEK,
            _PURCHASE_DATE_TODAY,
            _PURCHASE_DATE_ISO,
        )
    )
    has_payment = (
        _PURCHASE_CARD.search(normalized) is not None or _PURCHASE_CASH.search(normalized) is not None
    )
    has_envelope = bool(purchase_envelopes(question) or named_envelopes(question))
    if not (has_amount or has_date or has_payment or has_envelope):
        return False
    # A field answer is the field plus particles ("30만원이요", "현금으로 할게요",
    # "카드, 결제일은 2026-10-15"). A new question that merely contains a field word
    # ("오늘 날씨 어때", "현금흐름이 뭐야", "영화 추천해줘") has words left over and
    # is handled fresh instead of being merged into the stale purchase.
    residue = _RESTATED_VERB.sub("", _fragment_residue(question, normalized))
    if not (has_amount or has_date or has_payment or named_envelopes(question)):
        # An item word alone answers the envelope only as a bare word ("영화요"); "영화 평점?"
        # and "책 소개?" ask something of their own.
        return not residue
    return len(residue) <= _FRAGMENT_RESIDUE_MAX and _FRAGMENT_QUESTION.search(residue) is None


_FRAGMENT_RESIDUE_MAX: Final = 2
# A question word or small talk left over ("오늘 뭐해?", "내일 비 와?") is a new turn, not a field.
_FRAGMENT_QUESTION: Final = re.compile(
    r"뭐|뭔|왜|언제|누구|어디|무슨|몇|차이|잔액|잔고|세요|비와|비가|눈와|눈이|날씨|춥|덥"
)
# A field answer may restate the pending purchase's verb ("현금으로 오늘 살 거야", "내일 시킬게").
_RESTATED_VERB: Final = re.compile(
    r"(?:살|사|시킬|시켜|결제할|결제|낼|탈|예약할|예매할)(?:거야|거예요|건데|게요|게|래|예정|려고|려는데|도돼|면|까)"
    r"|살거|사려|사도|사면|살까"
)
# Hedges and dates people add to a bare field answer ("30만원 정도 할 것 같아요",
# "카드요 다음 달 15일에 빠져나가요") are fillers too; a question word is not.
_FRAGMENT_FILLER: Final = re.compile(
    r"할것같아요|할것같아|할거같아요|할거같아|들것같아요|들것같아|들거같아요|들거같아|나올것같아요|나올것같아"
    r"|될것같아요|될것같아|일것같아요|일것같아|같아요|같아|대략|아마|일거예요|일거야|예정이에요|예정이야|예정"
    r"|빠져나가요|빠져나가|나가요|출금돼요|출금돼|다음달|이번달|[0-9]{1,2}일"
    r"|결제일|출금일|결제예정일|결제|출금|일시불|신용|체크|할게요|할께요|할게|할께|할래요|할래"
    r"|이에요|입니다|예요|이요|으로|로|이고|이랑|하고|짜리|정도|쯤|에|은|는|이|가|을|를|요|고|네|응"
    r"|[0-9]{4}-[0-9]{2}-[0-9]{2}|[?!.,~\uff1f\u3002]|[\u3131-\u318e]"
)


def _fragment_residue(question: str, normalized: str) -> str:
    """Return what remains after removing every purchase field and filler from the text."""
    text = _joined_amounts(unicodedata.normalize("NFKC", question).lower())
    source = text
    text = re.sub(
        r"\s+", "",
        _AMOUNT_RUN.sub(lambda m: "" if source[m.end():m.end() + 1] == "원" else m.group(0), source),
    )
    text = text.replace("원", "")
    for pattern in (
        _PURCHASE_DATE_TOMORROW, _PURCHASE_DATE_NEXT_WEEK, _PURCHASE_DATE_THIS_WEEK,
        _PURCHASE_DATE_TODAY, _PURCHASE_CARD, _PURCHASE_CASH,
    ):
        text = pattern.sub("", text)
    for words in _PURCHASE_ITEMS.values():
        for word in sorted(words, key=len, reverse=True):
            if word in normalized:
                text = text.replace(word, "")
    if named_envelopes(question):
        # "쇼핑 봉투로", "기타로 해줘" answer which envelope the purchase belongs to.
        for name in sorted(_ENVELOPE_NAMES, key=len, reverse=True):
            text = text.replace(name, "")
        text = re.sub(r"봉투|항목|해줘|해주세요", "", text)
    return _FRAGMENT_FILLER.sub("", text)


def spending_period_fragment(question: str) -> str | None:
    """Return the canonical period token when the follow-up is only a bare period.

    A full spending question ("이번달 소비 얼마야") is not a fragment; it fullmatch-fails
    here and is handled fresh (it already routes on its own), so this never hijacks
    a complete turn.
    """
    stripped = re.sub(r"\s+", "", unicodedata.normalize("NFKC", question).lower())
    if not stripped or _parses_to_any_route(question):
        return None
    match = _SPENDING_PERIOD_FRAGMENT.fullmatch(stripped)
    return match.group("period") if match is not None else None


def _payment_answer_override(question_so_far: str, followup: str) -> str:
    """Let a single-method follow-up answer overwrite a stale conflicting payment token.

    A payment-method clarification only stores accumulated text, so a plain append
    can never resolve it: once the stored text carries both a cash and a card token
    (e.g. the user wrote "현금결제 신용카드로"), every later "카드"/"현금" answer keeps
    both tokens present and ``natural_purchase`` re-asks the same method question
    forever. When the follow-up names exactly one payment method, that answer is
    authoritative, so remove the *conflicting* method's tokens from the prior text
    before merging. A follow-up that names both methods, or neither, is left to the
    normal append path (no method was actually chosen).
    """
    fu = re.sub(r"\s+", "", unicodedata.normalize("NFKC", followup).lower())
    fu_card = _PURCHASE_CARD.search(fu) is not None
    fu_cash = _PURCHASE_CASH.search(fu) is not None
    if fu_card == fu_cash:  # both or neither -> not a clean single-method answer.
        return question_so_far
    conflicting = _PURCHASE_CASH if fu_card else _PURCHASE_CARD
    return conflicting.sub("", question_so_far)


_CORRECTION: Final = re.compile(r"아니고|아니라|말고|대신에|대신")
_CORRECTION_LEAD: Final = re.compile(r"^(?:아니요|아니야|아냐|아니|앗|아|잠깐|정정)[,.!~\s]*")


def _corrected(base: str, followup: str) -> str | None:
    """"2만원 아니고 만오천원", "아니 현금 말고 계좌이체로": the value after the correction wins.

    Both sides must be bare purchase fields; the new amount, payment, date or envelope replaces
    the one in ``base`` instead of being appended beside it (two amounts would ask again).
    """
    text = " ".join(unicodedata.normalize("NFKC", followup).split())
    parts = _CORRECTION.split(text)
    if len(parts) > 2 or (len(parts) == 1 and _CORRECTION_LEAD.match(text) is None):
        return None
    old = _CORRECTION_LEAD.sub("", parts[0]).strip() if len(parts) == 2 else ""
    new = _CORRECTION_LEAD.sub("", parts[-1]).strip()
    if not new or not is_bare_purchase_fragment(new) or (old and not is_bare_purchase_fragment(old)):
        return None
    rebuilt = unicodedata.normalize("NFKC", base).lower()
    amounts = purchase_amounts(with_bare_won(new))
    if len(amounts) > 1:
        return None
    if amounts:
        rebuilt = _with_amount(rebuilt, amounts[0])
    compact_new = re.sub(r"\s+", "", new.lower())
    payment = _PURCHASE_CARD.search(compact_new) or _PURCHASE_CASH.search(compact_new)
    if payment is not None and (_PURCHASE_CARD.search(compact_new) is None) != (
        _PURCHASE_CASH.search(compact_new) is None
    ):
        rebuilt = f"{_PURCHASE_CASH.sub(' ', _PURCHASE_CARD.sub(' ', rebuilt))} {payment.group(0)}으로"
    date = _FOLLOW_DATE_WORD.search(new.lower())
    if date is not None:
        rebuilt = f"{_FOLLOW_DATE_WORD.sub(' ', rebuilt)} {date.group(0)}"
    if named_envelopes(new):
        rebuilt = f"{rebuilt} {new}"
    rebuilt = " ".join(rebuilt.split())
    unchanged = rebuilt == " ".join(unicodedata.normalize("NFKC", base).lower().split())
    return None if unchanged and not old else rebuilt


def merged_purchase_question(question_so_far: str, followup: str) -> str | None:
    """Combine a stored purchase clarification with a bare follow-up, or None to discard."""
    corrected = _corrected(question_so_far, followup)
    if corrected is not None:
        return corrected if len(corrected) <= _MERGED_QUESTION_MAX_CHARS else None
    if not is_bare_purchase_fragment(followup):
        return None
    base = _payment_answer_override(question_so_far, followup)
    combined = f"{base} {followup}"
    if len(combined) > _MERGED_QUESTION_MAX_CHARS:
        # Bound the re-stored pending text: drop this fragment rather than append
        # unboundedly. ``base`` is bounded by ``question_so_far`` (itself a prior
        # merged result or the validated request), so the stored state cannot grow;
        # returning the override-applied ``base`` keeps a resolved method sticky even
        # when the fresh fragment cannot be appended.
        return base
    return combined


_ANY_SPENDING_PERIOD: Final = re.compile(
    r"지난\s*달|저번\s*달|이번\s*달|이달|오늘|어제|지금까지|현재까지|현재"
)


_SPENDING_PERIOD_ENVELOPE: Final = re.compile(
    r"(?:그럼|그러면|그면|근데|아)*"
    r"(?P<period>지난달|저번달|이번달|이달|오늘|어제)"
    r"(?P<envelope>" + "|".join(re.escape(word) for word in sorted(
        {*_BALANCE_ENVELOPE_WORDS, "기타"}, key=len, reverse=True
    )) + r")(?:봉투)?(?:은|는|도)?(?:요)?(?:얼마야|얼마|어때|는)?[?!.~]*"
)


def spending_followup_question(followup: str, previous: str) -> str | None:
    """Rebuild "지난달은?" as the previous spending query ("이번 달 외식 얼마 썼어?") for that period.

    "이번 달 기타는?" changes the period and the envelope together.
    """
    if not supports_spending_question(previous):
        # "지난달 외식비 총액 좀 알려줘" was read once its lookup intent was known; its canonical
        # form ("지난달외식소비얼마야") carries the period and envelope the follow-up changes.
        previous = history_question(previous) or ""
        if not supports_spending_question(previous):
            return None
    period = spending_period_fragment(followup)
    base = _ANY_SPENDING_PERIOD.sub("", previous).strip()
    if period is None:
        compact_followup = re.sub(r"\s+", "", unicodedata.normalize("NFKC", followup))
        found = _SPENDING_PERIOD_ENVELOPE.fullmatch(compact_followup)
        envelope = None if found is None else _FOLLOW_ENVELOPES.get(found["envelope"])
        if found is None or envelope is None:
            return None
        period = found["period"]
        base = " ".join(_FOLLOW_SPENDING_ENVELOPE.sub(" ", base).split())
        base = f"{envelope} {base}"
    candidate = f"{period} {base}"
    return candidate if supports_spending_question(candidate) else None


# Short follow-ups that lean on the previous question: "봉투 잔액 보여줘" → "외식은?", "이번 달
# 교통비 얼마 썼어?" → "외식은?", "월말 잔액 얼마 남을까" → "위험은 어때?", "300만원 노트북 오늘
# 현금으로 사도 돼?" → "150만원이면?". With no subject of their own these reached the router and
# came back as the generic review or the out-of-scope sentence.
_FOLLOW_LEAD: Final = re.compile(r"^(?:그럼|그러면|그면|그렇다면|그리고|근데|혹시|아|음)+")
_FOLLOW_TAIL: Final = re.compile(
    r"(?:은|는|도)?(?:요)?"
    r"(?:어때|어떄|어떻게돼|어떻게되|어떻게되나|어떻게됨|얼마야|얼마예요|얼마에요|얼마|남았어|알려줘|보여줘|봐줘)?"
    r"(?:요)?$"
)
_FOLLOW_CORE_MAX: Final = 12
_FOLLOW_ALL: Final = frozenset({"전체", "전부", "다", "총", "모두", "전체봉투", "봉투전체", "합계"})
_FOLLOW_ENVELOPES: Final[dict[str, str]] = {
    **{compact(word): envelope for word, envelope in _BALANCE_ENVELOPE_WORDS.items()},
    "기타": "기타",
    "취미생활": "취미·여가",
    "병원비": "의료·건강",
    "마트비": "편의점·마트·잡화",
    "편의점비": "편의점·마트·잡화",
}
_FOLLOW_RISK: Final = re.compile(r"위험|위험도|위험성|리스크|부족위험|적자위험")
_FOLLOW_FORECAST: Final = re.compile(r"월말|월말에|월말엔|월말잔액|예측|전망")
_FOLLOW_SPENDING_ENVELOPE: Final = re.compile(
    "(?:" + "|".join(re.escape(word) for word in sorted(
        {*_BALANCE_ENVELOPE_WORDS, "기타"}, key=len, reverse=True
    )) + r")(?:봉투)?(?:에서|에|으로|로|은|는|이|가|을|를)?"
)
_FOLLOW_DATE_WORD: Final = re.compile(r"오늘|내일|이번\s*주|다음\s*주|지금|당장|이따")
# What a changed-field follow-up adds around the field: "150만원이면?", "그럼 150만원짜리는?",
# "카드로 하면 어때?", "내일 사면?".
_FOLLOW_PURCHASE_FILLER: Final = re.compile(
    r"그럼|그러면|그면|이면|라면|하면|사면|결제하면|시키면|면|는|은|도|요|어때|괜찮아|괜찮을까|될까|돼|로|으로|결제"
)


def follow_core(question: str) -> str:
    """Strip the follow-up's lead-in ("그럼") and its asking tail ("은 얼마야?")."""
    core = _FOLLOW_LEAD.sub("", compact(question))
    return _FOLLOW_TAIL.sub("", core, count=1)


def _analysis_question(question: str) -> bool:
    return (
        deterministic_analysis_route(question) in {"forecast", "risk"}
        or natural_what_if(question) is not None
        or natural_goal(question) is not None
        or balance_check_question(question)
    )


def contextual_followup(previous: str, question: str) -> str | None:  # noqa: PLR0911 - one return per follow-up kind.
    """Rebuild a short follow-up from the previous question, or None to handle it as typed.

    Only a fragment qualifies: a question that parses on its own is never rewritten.
    """
    if not previous:
        return None
    # "내일 사면?" parses as a purchase of its own that misses everything; after a verdict it
    # changes one field of the purchase just judged.
    changed = _purchase_followup(previous, question)
    if changed is not None or _parses_to_any_route(question) or balance_check_question(question):
        return changed
    core = follow_core(question)
    if not core or len(core) > _FOLLOW_CORE_MAX:
        return None
    if core in _FOLLOW_ENVELOPES or core in _FOLLOW_ALL:
        return _envelope_followup(previous, _FOLLOW_ENVELOPES.get(core))
    if _analysis_question(previous):
        if _FOLLOW_RISK.fullmatch(core) is not None:
            return "이번 달 위험 알려줘"
        if _FOLLOW_FORECAST.fullmatch(core) is not None:
            return "월말 잔액 얼마 남을까?"
    return None


def _envelope_followup(previous: str, envelope: str | None) -> str | None:
    """"외식은?" after a balance check or a spending lookup asks the same about that envelope."""
    if balance_check_question(previous):
        return f"{envelope} 봉투 얼마 남았어?" if envelope else "봉투 잔액 보여줘"
    if not supports_spending_question(previous):
        return None
    base = " ".join(_FOLLOW_SPENDING_ENVELOPE.sub(" ", previous).split())
    candidates = (f"{envelope} {base}", _envelope_after_period(base, envelope)) if envelope else (base,)
    for candidate in candidates:
        if candidate and supports_spending_question(candidate):
            return candidate
    return None


def _envelope_after_period(base: str, envelope: str) -> str | None:
    match = _ANY_SPENDING_PERIOD.search(base)
    if match is None:
        return None
    return f"{base[: match.end()]} {envelope} {base[match.end() :].strip()}"


def _purchase_followup(previous: str, question: str) -> str | None:
    """"150만원이면?" or "내일 사면?" after a purchase verdict asks the same purchase with that change."""
    if isinstance(natural_purchase(previous, intent_known=True), NaturalPurchase):
        # "2만원 아니고 만오천원", "아니 현금 말고 계좌이체로" correct the purchase just judged.
        corrected = _corrected(previous, question)
        if corrected is not None and natural_purchase(corrected, intent_known=True) is not None:
            return corrected
    if not isinstance(natural_purchase(previous), NaturalPurchase) or purchase_envelopes(question):
        return None
    normalized = re.sub(r"\s+", "", unicodedata.normalize("NFKC", question).lower())
    if _FOLLOW_PURCHASE_FILLER.sub("", _fragment_residue(question, normalized)):
        return None
    amounts = purchase_amounts(question)
    if len(amounts) > 1:
        return None
    rebuilt = unicodedata.normalize("NFKC", previous).lower()
    if amounts:
        rebuilt = _with_amount(rebuilt, amounts[0])
    date = _FOLLOW_DATE_WORD.search(unicodedata.normalize("NFKC", question).lower())
    if date is not None:
        rebuilt = f"{_FOLLOW_DATE_WORD.sub(' ', rebuilt)} {date.group(0)}"
    card = _PURCHASE_CARD.search(normalized) is not None
    cash = _PURCHASE_CASH.search(normalized) is not None
    if card != cash:
        rebuilt = f"{_payment_answer_override(rebuilt, question)} {'카드로' if card else '현금으로'}"
    rebuilt = " ".join(rebuilt.split())
    if rebuilt == " ".join(unicodedata.normalize("NFKC", previous).lower().split()):
        return None
    return rebuilt if natural_purchase(rebuilt) is not None else None


def _with_amount(text: str, amount: int) -> str:
    tokens = _joined_amounts(text).split()
    index = _first_amount_index(tokens)
    if index is None:
        return f"{text} {amount}원"
    token = tokens[index]
    run = next((m for m in _AMOUNT_RUN.finditer(token) if token[m.end() : m.end() + 1] == "원"), None)
    if run is None:
        return f"{text} {amount}원"
    tokens[index] = f"{token[: run.start()]}{amount}{token[run.end() :]}"
    return " ".join(tokens)


def merged_spending_question(question_so_far: str, followup: str) -> str | None:
    """Synthesize a valid spending query from a stored clarification plus a period fragment.

    Prepending the period preserves any envelope/verb the original stated; when the
    original was too bare to re-form a supported query, it falls back to the
    all-envelope aggregate for that period so the follow-up is still answered.
    """
    period = spending_period_fragment(followup)
    if period is None:
        return None
    # "지난주 외식 얼마 썼어?" answered with "지난달" becomes "지난달 외식 얼마 썼어?".
    joined = re.sub(r"\s*(지난|저번|이번)\s*(주말?)", r"\1\2", question_so_far)
    question_so_far = _UNSUPPORTED_SPENDING_PERIOD.sub("", joined)
    combined = f"{period} {question_so_far}"
    # Falling back to the short aggregate when the combined text would exceed the
    # bound keeps the re-stored pending context from growing without limit across a
    # long chain of period-fragment turns.
    if len(combined) > _MERGED_QUESTION_MAX_CHARS:
        return f"{period} 소비 얼마야"
    if supports_spending_question(combined):
        return combined
    return f"{period} 소비 얼마야"


def stored_coaching_followup(question: str) -> bool:
    """Recognize only a session-bound request for an existing coaching cause or balance.

    The caller must additionally confirm that the session has an immutable original
    coaching receipt. These phrases therefore reuse that receipt and the current
    ledger instead of asking a model or re-running a future simulation. Forecast
    wording remains on the normal FDT path even when it contains "현재".
    """
    normalized = compact(question)
    if not normalized or any(marker in normalized for marker in _RECOMPUTE_FOLLOW_UP_MARKERS):
        return False
    return bool(
        (
            _COACHING_REFERENCE.search(normalized) is not None
            and _COACHING_REASON.search(normalized) is not None
        )
        or _CURRENT_ENVELOPE_BALANCE.search(normalized) is not None
    )
