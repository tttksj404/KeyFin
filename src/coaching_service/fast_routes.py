"""Conservative no-model routing for clear personal FDT forecast, risk, and review requests."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Final, Literal

from coaching_service.knowledge_retrieval import compact
from coaching_service.personal_query import select_personal_topic
from coaching_service.spending_history import supports_spending_question

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
_FORECAST_TARGETS: Final[tuple[str, ...]] = ("잔액", "잔고", "소비", "지출", "현금흐름", "남을현금")
_FUTURE_MARKERS: Final[tuple[str, ...]] = ("앞으로", "이번달", "이달", "월말", "다음달")
_STRONG_FUTURE_MARKERS: Final[tuple[str, ...]] = (
    "앞으로", "월말", "이번달말", "이달말", "다음달", "향후", "말까지", "다음급여전",
)
_FORECAST_TERMS: Final[tuple[str, ...]] = ("예측", "예상", "전망")
_FORECAST_PATH_TERMS: Final[tuple[str, ...]] = ("경로", "흐름", "궤적", "전개", "변하는", "변화")
_IMPLICIT_FORECAST_TERMS: Final[tuple[str, ...]] = ("얼마", "남을", "남아")
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
_RISK_OUTCOME_TERMS: Final[tuple[str, ...]] = ("부족", "모자라", "감당")
# A user can contrast an earlier risk-only view with the requested balance path.
# These compacted phrases are an admission condition for the no-model forecast
# route; other mixed risk/forecast language deliberately remains model-routed.
_RISK_DEPRIORITIZED_FOR_PATH: Final[tuple[str, ...]] = (
    "위험한마디보다",
    "위험여부보다",
    "위험분석보다",
    "위험만이아니라",
    "위험보다",
)
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
    r"(?=$|(?:을|를|이|가|은|는|에|의|으로|까지|만|도|보다|부터|에서|에게|한테|목표|[.,?!]))"
)
_GOAL_WORDS: Final[tuple[str, ...]] = ("목표", "모으", "모을", "저축", "달성", "만들")
_GOAL_FEASIBILITY: Final = re.compile(
    r"가능|될까|될수|할수|있을까|있을수|도달(?:할)?수|달성(?:할)?수|모을수|채울수"
)
_GOAL_PERIOD: Final = re.compile(
    r"(?:앞으로)?\d{1,3}일|이번달|이달|월말|다음달|\d{4}-\d{2}-\d{2}"
)
_GOAL_DISALLOWED: Final = re.compile(
    r"투자|매수|매도|상품|추천|방법|어떻게|계획(?:을|을?세우|을?짜)|설정(?:해|하)|세워"
)
_MAX_NATURAL_GOAL_KRW: Final = 10_000_000_000
_WHAT_IF_PERCENT: Final = re.compile(r"(?<!\d)(?P<percent>\d{1,2})\s*%(?!\d)")
_WHAT_IF_REDUCTION: Final = re.compile(r"줄(?:이|여)|감소")
_WHAT_IF_OUTCOME: Final = re.compile(r"어떻게|얼마|변하|달라지|될까|영향|차이|비교")
_WHAT_IF_DISALLOWED: Final = re.compile(
    r"고정(?:비|지출)|수입|소득|대출|보험|카드|이자|투자|매수|매도|상품|추천|방법|계획|설정"
)
_WHAT_IF_AMOUNT: Final = re.compile(r"\d[\d,]*\s*(?:만원|만\s*원|원)")
_WHAT_IF_GENERIC_EXPENSE: Final = re.compile(r"(?:변동)?(?:소비|지출)")
_WHAT_IF_ENVELOPE_ALIASES: Final[dict[str, str]] = {
    "외식비": "외식",
    "외식": "외식",
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
        or not any(word in normalized for word in _GOAL_WORDS)
        or _GOAL_FEASIBILITY.search(normalized) is None
        or _GOAL_PERIOD.search(normalized) is None
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
        or _GOAL_PERIOD.search(normalized) is None
        or _WHAT_IF_REDUCTION.search(normalized) is None
        or _WHAT_IF_OUTCOME.search(normalized) is None
    ):
        return None
    rates = tuple(_WHAT_IF_PERCENT.finditer(normalized))
    if len(rates) != 1:
        return None
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
_PURCHASE_VERB: Final = re.compile(
    r"사면|사도|살까|사려고|사서|구매하면|구매하려고|구매해도|구매해서|"
    r"지르면|질러도|지르려고|구입하면|구입해서"
)
_PURCHASE_INSTALLMENT: Final = re.compile(r"할부")
_PURCHASE_AMOUNT: Final = re.compile(
    r"(?<![\d,.])(?P<amount>(?:\d{1,3}(?:,\d{3})+|\d+))(?P<unit>만원|원)"
)
_PURCHASE_DATE_TOMORROW: Final = re.compile(r"내일")
_PURCHASE_DATE_THIS_WEEK: Final = re.compile(r"이번주")
_PURCHASE_DATE_TODAY: Final = re.compile(r"오늘")
_PURCHASE_DATE_ISO: Final = re.compile(r"(?P<date>\d{4}-\d{2}-\d{2})")
_PURCHASE_CARD: Final = re.compile(r"(?<!체크)카드")
_PURCHASE_CASH: Final = re.compile(r"현금|계좌|통장|이체|체크카드")
_PURCHASE_PAYMENT_DATE: Final = re.compile(
    r"(?:결제일|카드값|출금)\D{0,10}(?P<date>\d{4}-\d{2}-\d{2})"
    r"|(?P<date2>\d{4}-\d{2}-\d{2})\D{0,10}(?:결제|출금)"
)
_PURCHASE_ENVELOPE_ALIASES: Final[dict[str, str]] = {
    "노트북": "기타", "랩탑": "기타", "맥북": "기타", "폰": "기타", "휴대폰": "기타",
    "스마트폰": "기타", "아이폰": "기타", "갤럭시": "기타", "태블릿": "기타", "아이패드": "기타",
    "가전": "기타", "전자제품": "기타", "카메라": "기타",
    "옷": "쇼핑", "신발": "쇼핑", "가방": "쇼핑", "의류": "쇼핑",
}


def natural_purchase(  # noqa: C901, PLR0911 - each branch is one explicit clarify-vs-admit boundary.
    question: str,
) -> NaturalPurchase | str | None:
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
    normalized = re.sub(r"\s+", "", unicodedata.normalize("NFKC", question).lower())
    if not normalized or _PURCHASE_VERB.search(normalized) is None:
        return None
    if _PURCHASE_INSTALLMENT.search(normalized) is not None:
        # Multi-installment purchases need a payment schedule the FDT contract
        # cannot express yet (see scratchpad/PURCHASE-SPIKE.md ``4. Installment``).
        return "purchase_installment_unsupported"
    amounts = tuple(_PURCHASE_AMOUNT.finditer(normalized))
    if len(amounts) != 1:
        return "purchase_amount_required"
    try:
        amount = int(amounts[0].group("amount").replace(",", ""))
    except ValueError:
        return "purchase_amount_required"
    amount_krw = amount * 10_000 if amounts[0].group("unit") == "만원" else amount
    if not 0 < amount_krw <= _MAX_NATURAL_GOAL_KRW:
        return "purchase_amount_required"
    envelopes = {
        envelope for alias, envelope in _PURCHASE_ENVELOPE_ALIASES.items() if alias in normalized
    }
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
            return "purchase_payment_method_required"
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
# is a clean, complete lookup.
_TWIN_BACKED_TOPICS: Final[frozenset[str]] = frozenset({"accounts", "assets", "debts", "payments"})


def deterministic_lookup_route(question: str) -> LookupRoute | None:
    """Reuse existing exact lookup grammars before consulting the model.

    These are current-state or historical lookup requests, not a semantic
    classifier.  Both downstream handlers independently validate the stored
    snapshot or ledger before displaying a value.  Keeping the admission here
    equal to their established grammars prevents the speed path from silently
    accepting filters, comparisons, forecasts, or a broader personal request.
    """
    topic = select_personal_topic(question)
    if topic is not None and topic in _TWIN_BACKED_TOPICS:
        return "personal"
    if supports_spending_question(question):
        return "history"
    return None


def deterministic_analysis_route(question: str) -> AnalysisRoute | None:
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
    if _DEFINITION_LANGUAGE.search(normalized) is None:
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
        has_explicit_risk = "위험" in normalized
        risk_is_deprioritized = any(phrase in normalized for phrase in _RISK_DEPRIORITIZED_FOR_PATH)
        if (
            has_forecast_target
            and (explicit_forecast or implicit_forecast or path_forecast)
            and (not has_explicit_risk or risk_is_deprioritized)
        ):
            return "forecast"
        risk_outcome = has_explicit_risk or any(term in normalized for term in _RISK_OUTCOME_TERMS)
        if (
            risk_outcome
            and any(signal in normalized for signal in _RISK_SIGNALS)
            and (has_explicit_risk or has_future_marker)
        ):
            return "risk"
        if _PERSONAL_REVIEW_TARGET.search(normalized) is not None and any(
            action in normalized for action in _REVIEW_ACTIONS
        ):
            return "review"
    if _artifact_review(normalized):
        return "review"
    return None


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
