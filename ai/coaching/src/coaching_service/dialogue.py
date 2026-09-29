"""Owner-bound sessions with engine tools and durable, idempotent turns."""

import re
import time
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING, Final, Literal, assert_never
from uuid import uuid4
from zoneinfo import ZoneInfo

import anyio

from coaching_service.chart_contract import budget_period
from coaching_service.chat_answers import (
    ChatAnswer,
    FinanceQuestion,
    knowledge_answer,
    missing_twin_answer,
    out_of_scope_answer,
    period_clarification_answer,
    purchase_clarification_answer,
)
from coaching_service.coaching import CoachingCore, coaching_writes, evidence_for
from coaching_service.dialogue_decision import decide_dialogue
from coaching_service.errors import ServiceError
from coaching_service.evidence import LIMITED_CONTEXT, bounded_evidence, context_limited
from coaching_service.fast_routes import (
    NaturalGoal,
    NaturalPurchase,
    NaturalWhatIf,
    asset_trade_decision,
    balance_check_question,
    balance_envelope,
    bare_envelope_question,
    budget_envelope_words,
    canonical_question,
    contextual_followup,
    deterministic_analysis_route,
    deterministic_lookup_route,
    finance_advice_decision,
    follow_core,
    goal_slots,
    has_buy_verb,
    investment_decision,
    merged_goal_question,
    merged_period_question,
    merged_purchase_question,
    merged_spending_question,
    merged_what_if_question,
    names_budget_target,
    names_own_budget,
    natural_goal,
    natural_purchase,
    natural_what_if,
    purchase_slots,
    real_estate_trade,
    spend_or_trade_decision,
    spending_followup_question,
    spending_period_fragment,
    states_purchase,
    stored_coaching_followup,
    third_party_money,
    unanswerable_turn_code,
    what_if_slots,
)
from coaching_service.finance_knowledge import (
    asks_current_rate,
    deterministic_finance_status,
    deterministic_finance_wording,
    finance_advice_wording,
    finance_evidence,
    investment_decision_wording,
    is_catalog_subject_name,
    model_selected_finance_evidence,
    names_catalog_subject,
    real_estate_wording,
    selected_finance_wording,
    third_party_wording,
)
from coaching_service.history import historical_context
from coaching_service.knowledge_retrieval import compact, is_followup
from coaching_service.llm_contract import ChatMessage, EvidenceInput, FinanceWording, Routing
from coaching_service.payments import Ledger
from coaching_service.period_request import turn_period
from coaching_service.periods import ResolvedPeriod
from coaching_service.persona import strip_bold
from coaching_service.personal_contract import PersonalContext
from coaching_service.personal_query import INTENT_TOPIC_WORDS
from coaching_service.personal_service import CONTEXT_KEY, personal_answer
from coaching_service.repository import Mutation, document, write
from coaching_service.schemas import (
    BUDGET_CONFIG_KEY,
    AnswerReference,
    BudgetConfig,
    ChartHint,
    ChartPurchaseHint,
    Coaching,
    JsonDocument,
    Message,
    PendingClarification,
    ReviewRequest,
    Session,
    SessionRequest,
    Tone,
    TurnRequest,
    TwinIdentity,
)
from coaching_service.spending_history import (
    SpendingSummary,
    history_question,
    spending_answer,
    supports_spending_question,
)
from coaching_service.store import Operation

if TYPE_CHECKING:
    from pydantic import JsonValue


def turn_numeric_request(
    analysis: JsonDocument | None,
    parsed_goal: NaturalGoal | None,
    parsed_what_if: NaturalWhatIf | None,
    route: Routing,
    horizon_days: int,
) -> JsonDocument | None:
    """Build a typed FDT request without allowing natural language to invent inputs.

    API-supplied analysis remains authoritative. Natural shortcuts can add only
    one explicitly parsed target or variable-expense branch; the calendar resolver
    provides the horizon after independently checking the user's period expression.
    """
    if analysis is not None:
        return JsonDocument({**analysis.root, "horizon_days": horizon_days})
    if parsed_goal is not None:
        return JsonDocument.model_validate({
            "mode": "goal",
            "horizon_days": horizon_days,
            "paths": 400,
            "seed": 42,
            "goal": {"target_krw": parsed_goal.target_krw},
        })
    if parsed_what_if is not None:
        return JsonDocument.model_validate({
            "mode": "what_if",
            "horizon_days": horizon_days,
            "paths": 400,
            "seed": 42,
            "scenario": parsed_what_if.scenario(),
        })
    if route.mode in {"risk", "forecast"}:
        return JsonDocument.model_validate(
            {"mode": route.mode, "horizon_days": horizon_days, "paths": 100, "seed": 42}
        )
    return None


def chart_purchase_hint(change: JsonDocument, period: ResolvedPeriod) -> ChartPurchaseHint | None:
    """확정된 구매 change에서 차트 힌트를 만든다. 예산 월·미래 조건을 못 채우면 None.

    앱이 이 힌트를 그대로 차트 요청의 ``purchase`` 로 보내면 422 없이 겹쳐 그리도록
    기준일 이후·예산 월(``period_start`` 로 파생한 예산 주기) 안에 드는 구매만 싣는다.
    """
    envelope = change.root.get("envelope")
    amount = change.root.get("amount_krw")
    on_date_raw = change.root.get("date")
    if not (isinstance(envelope, str) and isinstance(amount, int) and isinstance(on_date_raw, str)):
        return None
    try:
        on_date = date.fromisoformat(on_date_raw)
        window = budget_period(period.budget_month_start, period.reference_date)
    except (ValueError, ServiceError):
        return None
    if not window.as_of < on_date <= window.horizon_end:
        return None
    return ChartPurchaseHint(envelope=envelope, amount_krw=amount, on_date=on_date)


def balance_turn(
    request: TurnRequest,
    parsed_goal: NaturalGoal | None,
    parsed_what_if: NaturalWhatIf | None,
    parsed_purchase: NaturalPurchase | None,
) -> bool:
    """Admit a current envelope-balance check: no typed analysis, goal, branch, or purchase."""
    return (
        request.analysis is None
        and parsed_goal is None
        and parsed_what_if is None
        and parsed_purchase is None
        and balance_check_question(request.question)
    )


def forecast_chart_hint(
    numeric_request: JsonDocument | None,
    parsed_purchase: NaturalPurchase | None,
    period: ResolvedPeriod,
    question: str,
    purchase: ChartPurchaseHint | None = None,
) -> ChartHint | None:
    """예측·구매검토 대화에만 같은 예산 월의 차트 요청 본문을 힌트로 덧붙인다.

    두 번째 시뮬레이션이나 차트 쓰기 없이 대화가 이미 사용한 기준일·기간에서
    파생한다. ``period_start`` 는 기준일이 속한 예산 월의 1일이라 그 기준일을
    포함하는 유효한 예산 주기다. 기준일이 속한 예산 월에 남은 예측일이 없으면
    (기준일이 월말 경계) 차트가 가리킬 미래 구간이 없어 힌트를 만들지 않는다.
    구매검토 대화에서 확정한 예정 구매(``purchase``)가 있으면 함께 싣는다.
    """
    is_forecast = numeric_request is not None and numeric_request.root.get("mode") == "forecast"
    if not (is_forecast or parsed_purchase is not None):
        return None
    if period.budget_forecast_end <= period.reference_date:
        return None
    return ChartHint(period_start=period.budget_month_start, question=question, purchase=purchase)


# Any money/finance word. Only used to tell an off-topic question that happened to
# contain a period word ("오늘") from a finance question with an ambiguous period.
# Words that only appear in chit-chat or other assistants' jobs. With no money word
# present they settle the turn as out of scope whatever the router picked.
_OFF_TOPIC_SUBJECT: Final = re.compile(
    r"날씨|비와|비가|눈와|눈이와|미세먼지|메뉴|노래|음악|영화추천|드라마|게임추천|코드|코딩|파이썬|번역"
    r"|직장|회사생활|연예인|아이돌|가수|배우|운세|사주|타로|엔지니어|개발자|반려동물|애완|취향|mbti"
    r"|자주마셔|자주가세요|자주가|좋아하는|싫어하는|에대해물어봐|얘기해줄래|얘기해줘|이야기해줘"
    r"|추천해줄래|추천해줘|추천좀|코디|내이름|뭐하는애"
    r"|농담|재밌는|재미있는|심심|이름이뭐|몇시야|며칠|몇일"
    r"|넌누구|너누구|너는누구|당신은누구|당신누구|누구야너|누구니너|누구냐너|누구냐넌"
    r"|무슨요일|잠이|졸려|배고"
    r"|사랑|연애|여자친구|남자친구|여친|남친|썸남|썸녀|썸타|권태기|화해|헤어진|전애인|애인"
    r"|축구|야구|경기결과|주말에뭐|뭐하지|좋아해|너몇살|넌몇살|생일"
    r"|git|깃허브|깃에서|브랜치|자바스크립트|비동기|스트레칭|영어공부|음식추천|먹기좋은|맛집추천|우산챙"
    r"|sql|리액트|react|useeffect|백준|알고리즘|프로그래밍|강아지|고양이|꿈꿔|소개팅|뭐먹|먹을지|끓이는|레시피|요리법"
    r"|소스뭐|기온|몇도|기분|꿀꿀|우울|비온|야식으로뭐|저녁에뭐|점심에뭐"
)
# "예산 상태 체크해줄래?", "적자 날 수 있어?", "외식 30% 아끼면 어떻게 돼?" ask about the user's own
# money even when they share a word with a catalog concept; the router decides those.
_OWN_STATE_ASK: Final = re.compile(
    r"상태|체크(?!카드|리스트)|점검|진단|적자|버틸|버티|줄이면|아끼면|덜쓰|늘리면|이번달|이달(?![라리려])|월말|남았|남을"
    r"|잔액은|잔고는|지출이|저금할|초과|가능성|확률|마이너스|추세|가계|재정|넘길|잘갈|실현"
    # "소비 습관이 건강해?", "예산 관리 잘 되고 있어?", "선택지출을 전부 삭제하면?" judge or change
    # the user's own spending.
    r"|건강해|건강한|잘되|잘하고|잘하는|어떤지|삭제하면|없애면|빼면|끊으면|안쓰면"
)
_DEFINITION_ASK: Final = re.compile(r"뭐|무엇|뜻|의미|개념|설명|차이|원리")
# What the concept shortcut admits: a definition or explanation ask ("뭐야", "뜻", "차이",
# "이란"), never "뭐 있어" (what do I have), which looks the user's own data up.
_CONCEPT_SHAPE: Final = re.compile(
    r"뭐(?:야|예요|에요|여|지|냐|임|인가|인지|니|죠|가요|란|라는|길래)|뭔(?:가요|지|데|가|질)|무엇|뜻|의미|개념"
    r"|설명|차이|원리|(?:이)?란(?:$|[?!.]|뭐|무엇)|(?:이)?라는게|정의"
)
_EXPLAIN_ASK: Final = re.compile(r"알려|가르쳐|정리|궁금|이해|공부")
_BARE_SUBJECT_TAIL: Final = re.compile(r"(?:은|는|이|가|을|를|요|이요|란|이란|이란게|이라는게)?[?!.~]*$")


_OWN_DATA_WORD: Final = re.compile(
    "|".join(
        re.escape(word)
        for word in sorted(
            {*INTENT_TOPIC_WORDS, *budget_envelope_words(), "예산", "봉투"}, key=len, reverse=True
        )
    )
)


def _names_concept_beyond_own_data(question: str) -> bool:
    """Whether a catalog concept is named by a word other than the user's own data topics.

    "리볼빙으로 청구액 일부만 내면 남은 빚은 어떻게 돼?" names 리볼빙; "자산 얼마?" and "교통비
    예산 상황?" name only the user's own assets and envelope.
    """
    return any(names_catalog_subject(part) for part in _OWN_DATA_WORD.split(compact(question)) if part)


def _concept_shaped(question: str) -> bool:
    """Whether the turn is shaped like a concept ask rather than a lookup of the user's own budget.

    "복리가 뭐야?", "ETF?", "헤징 좀 알려줘" ask what a concept means; "교통비 예산 상황?" and
    "외식 예산 다 썼어?" name the user's own envelope and are the router's to route.
    """
    text = compact(question)
    if _CONCEPT_SHAPE.search(text) is not None:
        return True
    if names_budget_target(question):
        return False
    # "복리 알려줘" asks the concept; "요즘 예산 관리 잘 되고 있는지 궁금해" names only the budget.
    if _names_concept_beyond_own_data(question) and _EXPLAIN_ASK.search(text) is not None:
        return True
    return is_catalog_subject_name(_BARE_SUBJECT_TAIL.sub("", text))


def _corrected_route(question: str, routed: str) -> tuple[Routing, FinanceWording | None] | None:
    """Correct a router mode the question's own words rule out; ``None`` keeps the router's."""
    if routed in {"purchase", "finance"} and real_estate_trade(question):
        return Routing(mode="finance", source="template"), real_estate_wording()
    if routed in _OWN_DATA_MODES and third_party_money(question):
        # "엄마 카드값 많이 나왔대" would otherwise be answered with the user's own review.
        return Routing(mode="finance", source="template"), third_party_wording()
    if routed == "purchase" and not states_purchase(question) and bare_envelope_question(question):
        # "편의점·마트 봉투는?" names an envelope with nothing bought: its balance, not a price ask.
        return Routing(mode="balance", source="template"), None
    return None


def _own_state_question(question: str) -> bool:
    """Whether the turn asks about the user's own money rather than what a concept means.

    "돈이 모자랄 때 리볼빙이 뭐야?" still asks a definition.
    """
    text = compact(question)
    if _OWN_STATE_ASK.search(text) is None or _DEFINITION_ASK.search(text) is not None:
        return False
    # "신용점수 떨어질 가능성 있어?" and "리볼빙 쓰면 이번달 부담 줄어?" are about the product.
    return _OWN_MONEY_SUBJECT.search(text) is not None or (
        _OWN_PERIOD.search(text) is not None and not names_catalog_subject(question)
    )


_OWN_MONEY_SUBJECT: Final = re.compile(
    r"예산|봉투|잔액|잔고|생활비|지출|소비|돈|통장|가계|재정|살림|외식|교통비|쇼핑|마트|편의점|의료|취미"
)
_OWN_PERIOD: Final = re.compile(r"이번달|이달|월말|요즘|남은기간")


_ROUTED_ON_DATA: Final = frozenset(
    {"review", "risk", "forecast", "personal", "history", "finance", "purchase", "goal", "what_if", "balance"}
)
_OWN_DATA_MODES: Final = frozenset({"review", "risk", "forecast", "history", "balance", "personal"})
_MODEL_INTENT_SLOTS: Final = {"purchase": purchase_slots, "goal": goal_slots, "what_if": what_if_slots}
_NEEDS_HISTORY: Final = re.compile(
    r"차이|비교|랑|그거|그것|그건|그게|이거|이건|저거|그럼|그러면|둘|반대|다른점|같은점|아까|방금|위에"
    r"|달라|다른|대비|보다|어때|도그래|는요|은요|도요"
)


# "안녕", "고마워", "누구세요?" are chit-chat only as the whole message: "고마워 지난달은?" and
# "안녕하세요 이번 달 괜찮을까요?" still ask about money, and "피부양자는 누구예요?" is a concept.
_GREETING_ONLY: Final = re.compile(
    r"(?:냥냥(?:아|이)?|안녕(?:하세요|하십니까)?|반가워(?:요)?|반갑습니다|고마워(?:요)?|고맙습니다"
    r"|감사(?:합니다|해요|해)?|뭐해(?:요)?|뭐하니|뭐하세요|하이|굿모닝|좋은아침|잘자(?:요)?|잘지냈어(?:요)?"
    r"|수고했어(?:요)?|수고하셨습니다|수고많았어(?:요)?"
    r"|(?:아니(?:야|요|에요|다)?)?(?:됐어(?:요)?|됐다|됐습니다|괜찮아요?|괜찮습니다)|아니(?:야|요|에요|다)?"
    r"|알겠(?:어|어요|습니다)|알았어(?:요)?|오케이|오키|응|웅|네|넵|예|그래(?:요)?|좋아(?:요)?|싫어(?:요)?"
    r"|(?:너|넌|니|당신)?(?:는|은)?(?:누구(?:야|니|세요|예요|에요|신가요|신지|냐)|몇살(?:이야|이에요|이세요|이니|인가요|이냐)?))+"
)
_GREETING_NOISE: Final = re.compile(r"[\u3131-\u318e~!?.,^;…♡♥]+")
_GREETING_MAX: Final = 30


def chit_chat(question: str) -> bool:
    """Whether the turn names a chit-chat subject and no money word at all."""
    text = compact(question)
    off_topic = _OFF_TOPIC_SUBJECT.search(text) is not None
    money_outcome = _MONEY_OUTCOME.search(text) is not None and (
        not off_topic or _MONEY_SCOPE.search(text) is not None  # "여친 생일인데 이번 달 버틸 수 있을까?"
    )
    if _FINANCE_SIGNAL.search(text) is not None or money_outcome:
        # "잠이 부족해" names a chit-chat subject; "이번 달 버틸 수 있을까?" does not.
        return False
    greeting = _GREETING_NOISE.sub("", text)
    return off_topic or (
        0 < len(greeting) <= _GREETING_MAX and _GREETING_ONLY.fullmatch(greeting) is not None
    )


def off_topic_route(question: str, mode: str, *, catalog_subject: bool) -> bool:
    """Tell whether a router decision would answer a chit-chat question from the user's data.

    Only an explicit chit-chat subject overrides the router. A turn with no money word
    can still be a legitimate follow-up ("지난달은?", "고정비 목록 보여줘", "적자야?"),
    and those keep the router's mode.
    """
    if mode not in _ROUTED_ON_DATA or catalog_subject:
        return False
    return chit_chat(question)


_FINANCE_SIGNAL: Final = re.compile(
    r"돈|원|얼마|소비|지출|예산|잔액|잔고|결제|카드|계좌|통장|현금|저축|적금|예금|이자|대출|빚|부채|자산"
    r"|수입|소득|월급|급여|용돈|봉투|구매|샀|살까|사도|쓴|썼|쓸|비용|요금|가격|청구|할부|투자|주식|보험|세금"
    r"|환율|금리|펀드|연금|위험|예측|전망|목표|모으|절약|아끼|줄이|코칭|가계|재정|금융"
    r"|외식|식비|교통|쇼핑|편의점|마트|잡화|의료|취미|여가|생활비|장보|구독|결제일|출금"
    r"|etf|isa|dsr|재테크|연말정산|청약|옵션|신용|리볼빙|코인|채권|배당|주가|증권|복리|비상금"
    r"|적자"
)
_MONEY_OUTCOME: Final = re.compile(r"부족|모자라|버틸|버티")
_MONEY_SCOPE: Final = re.compile(
    r"이번달|이달|월말|다음달|남은기간|이번주|생활비|월급|용돈|카드|통장|잔액|월세"
)


def _select_cash_account(accounts: "list[JsonValue]") -> "dict[str, JsonValue] | None":
    """Pick the single account a cash purchase should draw from, or None if ambiguous.

    One real account is unambiguous. With several, the user already chose the
    method (cash), so the remaining ambiguity is *which* account, not cash-vs-card:
    resolve it to the designated income (주거래) account when exactly one carries
    ``is_income`` true. Zero or several income accounts stays genuinely ambiguous
    and fails closed. (Older twins without the ``is_income`` field keep the
    single-account behaviour and fall through to the caller's fail-closed clarify.)
    """
    valid = [a for a in accounts if isinstance(a, dict) and isinstance(a.get("account_id"), str)]
    if len(valid) == 1:
        return valid[0]
    income = [a for a in valid if a.get("is_income") is True]
    if len(income) == 1:
        return income[0]
    return None


def _select_card(
    cards: "list[JsonValue]", accounts: "list[JsonValue]"
) -> "dict[str, JsonValue] | None":
    """Pick the card a card purchase should use, or None if genuinely ambiguous.

    One real card is unambiguous. With several, the user already chose the method
    (card), so the remaining ambiguity is *which* card: default to the card that
    settles from the designated income (주거래) account when exactly one does. No
    income account, several, or several cards on it stays ambiguous and fails closed.
    """
    valid = [c for c in cards if isinstance(c, dict) and isinstance(c.get("card_id"), str)]
    if len(valid) == 1:
        return valid[0]
    income_ids = [
        a.get("account_id")
        for a in accounts
        if isinstance(a, dict) and isinstance(a.get("account_id"), str) and a.get("is_income") is True
    ]
    if len(income_ids) != 1:
        return None
    # The card path always carries a deferred settlement date, which the engine only
    # accepts for CREDIT (a DEBIT card must settle on the purchase date), so a
    # default among several is only ever a CREDIT card.
    on_income = [
        c for c in valid
        if c.get("settlement_account_id") == income_ids[0] and c.get("kind") == "CREDIT"
    ]
    return on_income[0] if len(on_income) == 1 else None


def resolve_purchase_change(  # noqa: C901, PLR0912 - each guard is one explicit fail-closed payment boundary.
    purchase: NaturalPurchase, twin: JsonDocument, reference: date, period_end: date | None = None,
) -> JsonDocument:
    """Turn one text-admitted purchase into a single vendor ``expense`` change.

    The text parser never knows which account or card the change belongs to;
    it only names cash/card when the user said so. This still refuses to guess
    among several real candidates, and it still refuses a card purchase with no
    real settlement account. A resolved account/card is the last gate before
    the FDT vendor's own ``validate_change`` (``coaching_contract.py``).
    """
    snapshot = twin.root.get("snapshot")
    raw_accounts = snapshot.get("accounts") if isinstance(snapshot, dict) else None
    raw_cards = snapshot.get("cards") if isinstance(snapshot, dict) else None
    accounts = raw_accounts if isinstance(raw_accounts, list) else []
    cards = raw_cards if isinstance(raw_cards, list) else []
    match purchase.payment_hint:
        case "cash":
            use_card = False
        case "card":
            use_card = True
        case None:
            # Unspecified in the prose is only safe when exactly one real
            # payment source exists at all; two or more is genuine ambiguity.
            if len(accounts) + len(cards) != 1:
                raise ServiceError("purchase_payment_method_required")
            use_card = len(cards) == 1
    if use_card and purchase.card_payment_date is None:
        # A card payment (named, or inferred from a single-card snapshot) still
        # needs its own settlement date; ask precisely for that rather than
        # re-asking cash-vs-card, which only loops on a clean card phrasing.
        raise ServiceError("purchase_card_payment_date_required")
    if purchase.date_token == "today":  # noqa: S105 - a calendar token, not a credential.
        purchase_date = reference
    elif purchase.date_token == "tomorrow":  # noqa: S105 - a calendar token, not a credential.
        purchase_date = reference + timedelta(days=1)
    elif purchase.date_token == "this_week":  # noqa: S105 - a calendar token, not a credential.
        purchase_date = reference
    elif purchase.date_token == "next_week":  # noqa: S105 - a calendar token, not a credential.
        # Mirrors ``this_week`` (which resolves to the reference day) shifted by one
        # week, giving a concrete representative day for the coming week.
        purchase_date = reference + timedelta(days=7)
    else:
        try:
            purchase_date = date.fromisoformat(purchase.date_token)
        except ValueError:
            raise ServiceError("purchase_date_required") from None
    if purchase_date < reference or (period_end is not None and purchase_date > period_end):
        # "다음 주" near the month's end or "2026-10-01" lies outside the review window the
        # engine checks against; the date is asked for again instead of failing the turn.
        raise ServiceError("purchase_date_out_of_period")
    change: dict[str, JsonValue] = {
        "kind": "expense",
        "date": purchase_date.isoformat(),
        "amount_krw": purchase.amount_krw,
        "envelope": purchase.envelope,
    }
    if use_card:
        card = _select_card(cards, accounts)
        if card is None:
            raise ServiceError("purchase_payment_method_required")
        card_id = card.get("card_id")
        if not isinstance(card_id, str):
            raise ServiceError("purchase_payment_method_required")
        change["card_id"] = card_id
        change["payment_date"] = purchase.card_payment_date
    else:
        account = _select_cash_account(accounts)
        if account is None:
            raise ServiceError("purchase_payment_method_required")
        account_id = account.get("account_id")
        if not isinstance(account_id, str):
            raise ServiceError("purchase_payment_method_required")
        change["account_id"] = account_id
    return JsonDocument(change)


def resolve_purchase_or_clarify(
    purchase: NaturalPurchase, twin: JsonDocument, reference: date, period_end: date | None = None,
) -> tuple[JsonDocument, ...] | ChatAnswer:
    """Resolve one purchase into an FDT change tuple, or a 200 clarification answer.

    A twin-snapshot ambiguity whose code has an agreed clarify sentence becomes a
    ``ChatAnswer(status="needs_clarification")`` the caller records as a normal
    turn; any other ``ServiceError`` without an agreed clarify sentence propagates
    and keeps its existing 4xx contract.
    """
    try:
        return (resolve_purchase_change(purchase, twin, reference, period_end),)
    except ServiceError as error:
        clarification = purchase_clarification_answer(error.code)
        if clarification is None:
            raise
        return clarification


def chat_history(session: Session, *, include_subject: bool = False) -> tuple[ChatMessage, ...]:
    """Use recent context for intent; keep every original message intact in storage."""
    messages = session.messages[-4:]
    if include_subject:
        # Preserve one explicit topic through repeated short follow-ups without resending the full session.
        subject = next((
            row for row in reversed(session.messages) if row.role == "user" and not is_followup(row.content)
        ), None)
        if subject is not None and subject not in messages:
            messages = (subject, *messages[-2:])
    return tuple(
        ChatMessage(
            role=row.role,
            content=strip_bold(row.content)[:800] + (" [이력 일부 생략]" if len(row.content) > 800 else ""),
        )
        for row in messages
    )


def spending_chat_answer(
    identity: TwinIdentity, route: Routing, summary: SpendingSummary
) -> ChatAnswer:
    """Render one confirmed-ledger spending summary as its typed ``ChatAnswer``.

    Mirrors the engine-sourced needs_clarification/needs_data/answered contract:
    ``wording_source="engine"``, no model call, the same value on ``rows`` and in
    ``evidence.spending`` so first-class fields and evidence never disagree.
    """
    return ChatAnswer(
        id=uuid4().hex,
        answer_type="spending_history",
        status=summary.status,
        text=summary.text,
        wording_source="engine",
        model="not_called",
        evidence=JsonDocument(
            {
                "identity": document(identity).root,
                "routing": document(route).root,
                "spending": summary.model_dump(mode="json"),
            }
        ),
        rows=summary.rows,
        total_krw=summary.total_krw,
        created_at=time.time(),
    )


def merged_clarification_question(pending: PendingClarification, followup: str) -> str | None:
    """Merge a bare follow-up into a stored clarification, or None to handle it fresh.

    Only a follow-up that is a bare fragment answering the pending question merges;
    a complete different turn returns None so the caller discards the stale context.
    """
    match pending.kind:
        case "purchase":
            return merged_purchase_question(pending.question, followup)
        case "spending":
            return merged_spending_question(pending.question, followup)
        case "goal":
            return merged_goal_question(pending.question, followup)
        case "what_if":
            return merged_what_if_question(pending.question, followup)
        case "period":
            return merged_period_question(pending.question, followup)
        case unreachable:
            assert_never(unreachable)


def _pending_for(question: str, answer: Coaching | ChatAnswer) -> PendingClarification | None:
    """Derive the next pending clarification from this turn's answer.

    A purchase/spending needs_clarification stores the (possibly merged) question so
    the next bare follow-up can merge; every other outcome returns None, which clears
    any prior pending context (resolution or a superseding fresh turn).
    """
    if not (isinstance(answer, ChatAnswer) and answer.status == "needs_clarification"):
        return None
    if answer.answer_type == "purchase_review":
        return PendingClarification(
            kind="purchase", question=question, code=answer.fallback_reason or "purchase_review"
        )
    if answer.answer_type == "spending_history":
        return PendingClarification(
            kind="spending", question=question, code=answer.fallback_reason or "spending_clarification"
        )
    # The clarifications ``unanswerable_turn_code`` asks keep their question so the
    # literal answer ("다음 달까지", "20%", "이번 달") completes it on the next turn.
    kind = _ASKED_PIECE_KINDS.get(answer.fallback_reason or "")
    if answer.answer_type == "period_review" and kind is not None:
        return PendingClarification(kind=kind, question=question, code=answer.fallback_reason or kind)
    return None


_ASKED_PIECE_KINDS: Final[dict[str, Literal["goal", "what_if", "spending", "period"]]] = {
    "period_clarification_required": "period",
    "invalid_question_period": "period",
    "period_unsupported_calendar": "period",
    "goal_period_required": "goal",
    "goal_period_unsupported": "goal",
    "what_if_percent_required": "what_if",
    "spending_period_unsupported": "spending",
}


_FOLLOWUP_CHAIN_LIMIT: Final = 8
_CONCEPT_ASK: Final = re.compile(r"뭐|무엇|뜻|의미|설명|차이|원리|개념")


def _previous_user_question(session: Session) -> str | None:
    return next((row.content for row in reversed(session.messages) if row.role == "user"), None)


def _trade_followup(session: Session, question: str) -> bool:
    """Whether "그럼 이더리움은?" swaps the asset of the buy or sell decision just asked."""
    previous = _previous_user_question(session)
    core = follow_core(question)
    return (
        previous is not None
        and bool(core)
        and len(core) <= _TRADE_FOLLOW_CORE_MAX
        and not _concept_shaped(question)
        and (investment_decision(previous) or asset_trade_decision(previous))
    )


_TRADE_FOLLOW_CORE_MAX: Final = 12


def _rebuilt_followup(session: Session, question: str) -> str | None:
    """Complete a short follow-up ("외식은?", "위험은?", "150만원이면?", "적금은?") from the last question."""
    previous = _previous_user_question(session)
    if previous is None:
        return None
    rebuilt = contextual_followup(previous, question)
    if rebuilt is not None:
        return rebuilt
    # "복리가 뭐야?" → "적금은?": another named catalog concept asks its definition.
    core = follow_core(question)
    if (
        core
        and names_catalog_subject(previous)
        and _CONCEPT_ASK.search(compact(previous)) is not None
        and not any(ch.isdigit() for ch in core)
        and len(core) <= 10
        and is_catalog_subject_name(core)  # "예산 잔액 좀 보여줘" merely contains 예산
    ):
        final_consonant = "가" <= core[-1] <= "힣" and (ord(core[-1]) - 0xAC00) % 28 != 0
        return f"{core}{'이' if final_consonant else '가'} 뭐야?"
    return None


def _previous_spending_question(session: Session) -> str | None:
    """Return the spending lookup the previous turns continue; any other turn ends the topic.

    "이번 달 교통비 얼마 썼어?" → "지난달은?" → "이번 달은?": the bare period turns in
    between keep the first question as the topic.
    """
    users = [row.content for row in reversed(session.messages) if row.role == "user"]
    for content in users[:_FOLLOWUP_CHAIN_LIMIT]:
        # "지난달 외식비 총액 좀 알려줘" was answered in its canonical lookup form; a balance or
        # budget word ("남았어", "예산") never reads as one.
        if supports_spending_question(content) or supports_spending_question(history_question(content) or ""):
            return content
        if spending_period_fragment(content) is None:
            return None
    return None


def _spending_question(session: Session, question: str) -> str:
    """Repeat the previous spending query for a bare period follow-up ("지난달은?")."""
    if supports_spending_question(question):
        return question
    previous = _previous_spending_question(session)
    followup = None if previous is None else spending_followup_question(question, previous)
    return followup or history_question(question) or question


def save_turn(session: Session, question: str, answer: Coaching | ChatAnswer) -> Mutation:
    """Commit the delivered answer and session text together, including retries.

    The pending-clarification context is written into the same session mutation as
    the turn: set when this answer is a purchase/spending clarification, cleared
    otherwise. Joining the single mutation keeps it idempotent with the recorded turn.
    """
    match answer:
        case Coaching():
            response = AnswerReference(kind="coaching", id=answer.id)
            answer_writes = coaching_writes(answer, notify=False)
        case ChatAnswer():
            response = AnswerReference(kind="chat", id=answer.id)
            answer_writes = (write("answer/" + answer.id, answer),)
        case unreachable:
            assert_never(unreachable)
    updated = session.model_copy(
        update={
            "messages": (
                *session.messages,
                Message(role="user", content=question),
                Message(role="assistant", content=answer.text, response=response),
            ),
            "pending_clarification": _pending_for(question, answer),
        }
    )
    # 참조만 먼저 저장하거나 별도 호출로 재생성하지 않아 재시도에도 원문과 ID가 일치한다.
    return Mutation(result=document(answer), writes=(write("session/" + session.id, updated), *answer_writes))


class Dialogue:
    def __init__(self, core: CoachingCore) -> None:
        self.core: CoachingCore = core

    async def review(self, op: Operation, request: ReviewRequest) -> JsonDocument:
        async def action() -> Mutation:
            receipt = await self.core.receipt(await self.core.twin(op.owner), request)
            coaching = await self.core.compose(receipt, evidence_for(receipt))
            return Mutation(result=document(coaching), writes=coaching_writes(coaching, notify=False))

        return await self.core.repository.mutate(op, action)

    async def session(self, op: Operation, request: SessionRequest) -> JsonDocument:
        async def action() -> Mutation:
            if request.coaching_id is not None:
                _ = await self.core.repository.load(op.owner, "coaching/" + request.coaching_id)
            now = time.time()
            session = Session(
                id=uuid4().hex, coaching_id=request.coaching_id, created_at=now, expires_at=now + 86400
            )
            return Mutation(result=document(session), writes=(write("session/" + session.id, session),))

        return await self.core.repository.mutate(op, action)

    async def finance(self, op: Operation, request: FinanceQuestion) -> JsonDocument:
        """Allow a source-backed concept question without a Twin or initial review."""

        async def action() -> Mutation:
            evidence = finance_evidence(request.question)
            direct = deterministic_finance_wording(evidence) if self._direct_finance_enabled() else None
            answer = knowledge_answer(direct if direct is not None else await self.core.model.write(evidence))
            return Mutation(result=document(answer), writes=(write("answer/" + answer.id, answer),))

        return await self.core.repository.mutate(op, action)

    async def standalone_answer(
        self, owner: str, request: TurnRequest, route: Routing, history: tuple[ChatMessage, ...],
        finance: FinanceWording | None = None,
    ) -> ChatAnswer | None:
        """Answer concepts before loading financial data; explicit analysis takes precedence."""
        if request.analysis is not None:
            return None
        if route.mode in {"finance", "history", "personal", "other"} and request.period is not None:
            # The period object specifies a future interval, never a historical filter.
            raise ServiceError("period_not_supported_for_intent", 422)
        match route.mode:
            case "finance":
                return knowledge_answer(
                    finance if finance is not None else
                    await self.core.model.write(finance_evidence(request.question, history))
                )
            case "other":
                return out_of_scope_answer()
            case "personal":
                return await personal_answer(self.core.repository, owner, request.question)
            case "history" | "review" | "risk" | "forecast" | "purchase" | "goal" | "what_if" | "balance":
                return None
            case unreachable:
                assert_never(unreachable)

    async def active_session(self, owner: str, session_id: str) -> Session:
        session = Session.model_validate_json(await self.core.repository.load(owner, "session/" + session_id))
        if session.expires_at <= time.time():
            raise ServiceError("session_expired", 410)
        if len(session.messages) >= 40:
            raise ServiceError("session_turn_limit", 409)
        return session

    async def _budget_start_day(self, owner: str) -> int:
        """저장된 예산 시작일을 읽어 기간 계산에 넘긴다. 없으면 1일로 폴백한다.

        구버전 Twin(설정 이전 부트스트랩)에는 이 키가 없어 기존 1일 동작을 그대로
        유지한다. 값은 부트스트랩에서 1~28로 검증돼 저장되므로 여기서는 신뢰한다.
        """
        stored = await anyio.to_thread.run_sync(
            self.core.repository.store.load, owner, BUDGET_CONFIG_KEY
        )
        if stored is None:
            return 1
        return BudgetConfig.model_validate_json(stored).start_day

    async def _effective_tone(self, owner: str, request: TurnRequest) -> Tone | None:
        """Resolve the tone for a turn: an explicit request tone always wins.

        Falls back to the stored personal context's tone when the request omits
        one. When neither is set this returns ``None``, which preserves the
        existing encouraging-by-default ``deterministic_advice`` wording exactly.
        """
        if request.tone is not None:
            return request.tone
        stored = await anyio.to_thread.run_sync(self.core.repository.store.load, owner, CONTEXT_KEY)
        if stored is None:
            return None
        return PersonalContext.model_validate_json(stored).tone

    async def turn(  # noqa: C901, PLR0915 - one durable turn orchestrates every admitted no-model shortcut in sequence.
        self, op: Operation, session_id: str, request: TurnRequest
    ) -> JsonDocument:
        async def action() -> Mutation:  # noqa: C901, PLR0911, PLR0912, PLR0915 - each admitted no-model shortcut (now including the purchase clarifications and the pending-clarification merge) is one explicit boundary recorded in a single atomic mutation.
            nonlocal request
            session = await self.active_session(op.owner, session_id)
            canonical = canonical_question(request.question)
            if request.analysis is None and canonical != request.question:
                request = request.model_copy(update={"question": canonical})
            pending = session.pending_clarification
            if pending is not None and request.analysis is None:
                # A bare follow-up answering the previous clarification is merged into
                # the accumulated question and re-resolved by the same parser below; a
                # complete different turn returns None and is handled fresh, and
                # ``save_turn`` then clears or replaces the stale pending context.
                merged = merged_clarification_question(pending, request.question)
                if merged is not None:
                    request = request.model_copy(update={"question": merged})
            else:
                merged = None
            if request.analysis is None and merged is None:
                # "외식은?" after "봉투 잔액 보여줘" and "150만원이면?" after a purchase verdict
                # are completed from the previous question; a question of its own is kept.
                rebuilt = _rebuilt_followup(session, request.question)
                if rebuilt is not None:
                    request = request.model_copy(update={"question": rebuilt})
            history = chat_history(session)
            # A natural goal is accepted only when the parser found one exact KRW
            # amount.  It is carried as a local typed value rather than mutating the
            # user's request, so the receipt can still distinguish API-supplied
            # analysis from an admitted natural-language shortcut.
            parsed_goal = natural_goal(request.question) if request.analysis is None else None
            parsed_what_if = natural_what_if(request.question) if request.analysis is None else None
            # A purchase clarification is handled before any twin load or model
            # call, never a guessed expense. Agreed clarify codes return a normal
            # 200 ``needs_clarification`` turn (recorded like spending); any code
            # without an agreed sentence keeps the existing 4xx contract.
            # A goal or what-if sentence ("외식 15% 덜 쓰면 이번 달 어떻게 될까?") is never a
            # purchase even when it names an item and a spending verb.
            parsed_purchase_outcome = (
                # A field answer merged into a pending purchase is still that purchase, even when
                # its item is one no envelope knows ("가습기 3만원 사도 돼? 통장으로요").
                natural_purchase(
                    request.question, intent_known=merged is not None and pending is not None
                    and pending.kind == "purchase",
                )
                if request.analysis is None and parsed_goal is None and parsed_what_if is None
                else None
            )
            if (
                isinstance(parsed_purchase_outcome, str)
                and not has_buy_verb(request.question)
                and (
                    deterministic_analysis_route(request.question) is not None
                    or deterministic_lookup_route(request.question) is not None
                )
            ):
                # "배달 시키면 이번 달 잔액 얼마 남을까?" is a forecast, not a purchase missing
                # its amount. "노트북 사면 월말에 돈 얼마 남을까?" still asks for the amount.
                parsed_purchase_outcome = None
            if isinstance(parsed_purchase_outcome, str):
                clarification = purchase_clarification_answer(parsed_purchase_outcome)
                if clarification is None:
                    raise ServiceError(parsed_purchase_outcome)
                return save_turn(session, request.question, clarification)
            parsed_purchase: NaturalPurchase | None = (
                parsed_purchase_outcome if isinstance(parsed_purchase_outcome, NaturalPurchase) else None
            )
            missing = (
                unanswerable_turn_code(request.question)
                if request.analysis is None and parsed_purchase_outcome is None
                else None
            )
            if missing is not None:
                # A clear goal/what-if/spending question missing one piece is asked for
                # that piece; the router would only turn it into the generic review.
                asked = period_clarification_answer(missing)
                if asked is not None:
                    return save_turn(session, request.question, asked)
            route, finance = await self._route_for_turn(
                request, session, history, parsed_goal, parsed_what_if, parsed_purchase,
            )
            if route.mode in _MODEL_INTENT_SLOTS and request.analysis is None:
                # The router named the intent; the amount, item, payment, date, rate and
                # deadline still come only from the question text, and a missing one is asked.
                values = _MODEL_INTENT_SLOTS[route.mode](request.question)
                if isinstance(values, str):
                    asked = purchase_clarification_answer(values) or period_clarification_answer(values)
                    if asked is None:
                        raise ServiceError(values)
                    return save_turn(session, request.question, asked)
                if isinstance(values, NaturalPurchase):
                    parsed_purchase = values
                elif isinstance(values, NaturalGoal):
                    parsed_goal = values
                else:
                    parsed_what_if = values
            if route.mode == "finance" and finance is None and (
                asset_trade_decision(request.question) or _trade_followup(session, request.question)
            ):
                # The router kept "XRP 지금 사도 될까요?" out of the purchase check; a buy or sell
                # decision on an asset is declined with what the coach can do instead.
                finance = investment_decision_wording()
            elif route.mode == "finance" and finance is None and finance_advice_decision(request.question):
                # "종신보험 가입해야 할까", "비트코인 앞으로 올라갈까?" are declined the same way.
                finance = finance_advice_wording()
            try:
                standalone = await self.standalone_answer(
                    op.owner, request, route,
                    chat_history(session, include_subject=True) if route.mode == "finance" else history,
                    finance,
                )
            except ServiceError as error:
                # A period-family clarification on the chat turn becomes the same 200
                # needs_clarification turn as the purchase codes; a code without an
                # agreed sentence (never a validation/chart code) keeps its 4xx contract.
                clarification = period_clarification_answer(error.code)
                if clarification is None:
                    raise
                return save_turn(session, request.question, clarification)
            if standalone is not None:
                # Keep actual router adoption separate from answer generation and HTTP success.
                standalone = standalone.model_copy(update={
                    "evidence": JsonDocument({**standalone.evidence.root, "routing": document(route).root})
                })
                return save_turn(session, request.question, standalone)
            try:
                twin = await self.core.twin(op.owner)
            except ServiceError as error:
                if error.code != "resource_not_found":
                    raise
                return save_turn(session, request.question, missing_twin_answer(route))
            original = (
                None
                if session.coaching_id is None
                else Coaching.model_validate_json(
                    await self.core.repository.load(op.owner, "coaching/" + session.coaching_id)
                )
            )
            if original is not None and stored_coaching_followup(request.question):
                # A question about an already delivered coaching cause or the current
                # envelope balance does not ask for a new future-state simulation. Keep
                # the original receipt immutable, update only the separately labelled
                # historical/current ledger facts, and avoid both model phases.
                transactions = await anyio.to_thread.run_sync(self.core.engine.transactions, twin)
                current_envelopes = Ledger.model_validate_json(
                    await self.core.repository.load(op.owner, "ledger")
                ).envelopes
                identity = await anyio.to_thread.run_sync(self.core.engine.identity, twin)
                receipt = original.receipt.model_copy(
                    update={
                        "identity": identity,
                        "request": JsonDocument(
                            {"operation": "historical_coaching_followup", "coaching_id": original.id}
                        ),
                        # The original engine result is retained only under the explicitly
                        # labelled historical field below. Presenting it as a new FDT result
                        # would incorrectly bind past numbers to the current Twin revision.
                        "result": JsonDocument(
                            {"status": "not_run", "reason": "historical_coaching_followup"}
                        ),
                        "payment": None,
                        "trigger": "historical_coaching_followup",
                        "original_coaching_id": original.id,
                        "numeric_request": None,
                        "numeric_result": None,
                        "historical": historical_context(original, transactions),
                        "current_envelopes": current_envelopes,
                        "period": None,
                        "routing": document(route),
                    }
                )
                # The answer is entirely template-rendered from the stored receipt and
                # current ledger. Do not serialize the original receipt into a model
                # prompt merely to decide that no model call is necessary.
                coaching = await self.core.compose(
                    receipt,
                    EvidenceInput(question=request.question, facts_json=LIMITED_CONTEXT),
                    tone=await self._effective_tone(op.owner, request),
                )
                return save_turn(session, request.question, coaching)
            identity = await anyio.to_thread.run_sync(self.core.engine.identity, twin)
            reference = date.fromisoformat(identity.as_of)
            if route.mode == "history" and request.analysis is None:
                summary = spending_answer(
                    reference,
                    await anyio.to_thread.run_sync(self.core.engine.transactions, twin),
                    _spending_question(session, request.question),
                )
                return save_turn(session, request.question, spending_chat_answer(identity, route, summary))
            budget_start_day = await self._budget_start_day(op.owner)
            try:
                period = turn_period(
                    reference, request.question, request.period, request.analysis, budget_start_day,
                )
            except ServiceError as error:
                clarification = period_clarification_answer(error.code)
                if clarification is None:
                    raise
                if parsed_purchase is None:
                    if (
                        _FINANCE_SIGNAL.search(compact(request.question)) is None
                        and _MONEY_OUTCOME.search(compact(request.question)) is None
                    ):
                        # A question with no money word at all ("오늘 날씨 어때") that the
                        # model routed to a finance mode only trips the period parser on
                        # "오늘"; asking it for a period is wrong, so treat it as off-topic.
                        return save_turn(session, request.question, out_of_scope_answer())
                    # A genuine period ambiguity/conflict on the chat turn becomes a 200
                    # needs_clarification turn instead of a 503, like the purchase codes.
                    return save_turn(session, request.question, clarification)
                # A purchase supplies its own authoritative date token (다음주/내일/오늘/
                # ISO), which the period parser treats as ambiguous prose. The purchase
                # date is authoritative, so derive the review window from the request's
                # explicit period/analysis (default horizon otherwise) without the
                # purchase's own timing prose, rather than re-asking for a period.
                period = turn_period(reference, "", request.period, request.analysis, budget_start_day)
            today = datetime.now(ZoneInfo("Asia/Seoul")).date()
            numeric_request = turn_numeric_request(
                request.analysis, parsed_goal, parsed_what_if, route, period.forecast_days,
            )
            purchase_hint: ChartPurchaseHint | None = None
            if numeric_request is not None:
                receipt = await self.core.numeric_receipt(
                    twin, identity, numeric_request, period, replay=reference != today
                )
            elif (route.mode == "review" and balance_turn(
                request, parsed_goal, parsed_what_if, parsed_purchase
            )) or (route.mode == "balance" and parsed_purchase is None):
                # A balance check asks what is left now. The review's Monte-Carlo
                # projection would only add future-path actions and caveats to it.
                receipt = await self.core.balance_receipt(
                    twin, reference, replay=reference != today, envelope=balance_envelope(request.question),
                )
            else:
                changes: tuple[JsonDocument, ...] = ()
                if parsed_purchase is not None:
                    # A twin-snapshot ambiguity (e.g. ``purchase_payment_method_required``)
                    # becomes the same 200 ``needs_clarification`` turn as the text-only
                    # codes; a code without an agreed sentence keeps its 4xx contract.
                    resolved = resolve_purchase_or_clarify(
                        parsed_purchase, twin, reference, period.forecast_end,
                    )
                    if isinstance(resolved, ChatAnswer):
                        return save_turn(session, request.question, resolved)
                    changes = resolved
                    purchase_hint = chart_purchase_hint(resolved[0], period)
                receipt = await self.core.receipt(
                    twin,
                    ReviewRequest(
                        on_date=reference,
                        through_date=period.forecast_end,
                        replay=reference != today,
                        changes=changes,
                    ),
                )
            receipt = receipt.model_copy(
                update={
                    "original_coaching_id": original.id if original is not None else None,
                    "historical": historical_context(
                        original, await anyio.to_thread.run_sync(self.core.engine.transactions, twin)
                    )
                    if original is not None
                    else None,
                    "current_envelopes": Ledger.model_validate_json(
                        await self.core.repository.load(op.owner, "ledger")
                    ).envelopes,
                    "period": period,
                }
            )
            if numeric_request is None and context_limited(
                bounded_evidence(receipt, request.question, history)
            ):
                # An intent-only route is not permission to analyze incomplete financial evidence.
                route = Routing(mode="review", source="template", fallback_reason="context_limit")
            receipt = receipt.model_copy(update={"routing": document(route)})
            evidence = bounded_evidence(receipt, request.question, history)
            coaching = await self.core.compose(
                receipt, evidence, tone=await self._effective_tone(op.owner, request)
            )
            coaching = coaching.model_copy(
                update={
                    "chart_hint": forecast_chart_hint(
                        numeric_request, parsed_purchase, period, request.question, purchase_hint
                    )
                }
            )
            return save_turn(session, request.question, coaching)

        return await self.core.repository.mutate(op, action)

    async def _route_for_turn(  # noqa: PLR0911, PLR0913, PLR0917 - each admitted no-model shortcut is one explicit route boundary.
        self,
        request: TurnRequest,
        session: Session,
        history: tuple[ChatMessage, ...],
        parsed_goal: NaturalGoal | None,
        parsed_what_if: NaturalWhatIf | None,
        parsed_purchase: NaturalPurchase | None = None,
    ) -> tuple[Routing, FinanceWording | None]:
        """Choose a route without changing the established FDT/numeric validation path."""
        if (
            request.analysis is None
            and session.coaching_id is not None
            and stored_coaching_followup(request.question)
        ):
            # The session itself establishes which immutable coaching receipt "this"
            # denotes. A model route would add latency without improving the historical
            # cause or the current ledger values returned below.
            return Routing(mode="review", source="template"), None
        if request.analysis is not None:
            return await self._explicit_analysis_route(request, session, history)
        previous_spending = _previous_spending_question(session)
        if previous_spending is not None and (
            spending_period_fragment(request.question) is not None
            or spending_followup_question(request.question, previous_spending) is not None
        ):
            # "지난달은?" or "이번 달 기타는?" right after "이번 달 외식 얼마 썼어?" is the same
            # ledger query for another period or envelope.
            return Routing(mode="history", source="template"), None
        if investment_decision(request.question):
            # Whether to buy or sell a named stock, fund, ETF or coin is declined with
            # what the coach can do instead; no purchase check, review or model call.
            return Routing(mode="finance", source="template"), investment_decision_wording()
        if parsed_goal is not None or parsed_what_if is not None:
            # A goal supplies one target and a paired branch supplies one
            # variable-expense change; the deadline remains the independently
            # validated calendar result below. ``review`` is the existing route
            # label for entering a typed numeric operation without asking a
            # model to invent an FDT parameter.
            return Routing(mode="review", source="template"), None
        if balance_turn(request, parsed_goal, parsed_what_if, parsed_purchase):
            # "봉투 잔액 보여줘"/"예산 괜찮아?" is the envelope table plus a short
            # summary on the review route, not a sentence list or a finance concept.
            # The turn below answers it from the ledger without an FDT simulation.
            return Routing(mode="review", source="template"), None
        if parsed_purchase is not None:
            # A complete purchase ("적자 안 나게 노트북 100만원 오늘 현금으로 사도 돼?") is the
            # purchase review; a risk or lookup word in it must not drop the expense change.
            return Routing(mode="review", source="template"), None
        lookup_route = deterministic_lookup_route(request.question)
        if lookup_route is not None:
            # Both the current-snapshot and historical-spending parsers accept
            # only their own complete grammar.  The handlers below still
            # validate availability and never turn a missing ledger into a
            # guessed amount.
            return Routing(mode=lookup_route, source="template"), None
        direct_route = deterministic_analysis_route(request.question)
        if direct_route is not None:
            # This narrow grammar chooses only an unambiguous personal FDT mode.  Calculation,
            # period validation, and final grounded wording still use the existing path below.
            return Routing(mode=direct_route, source="template"), None
        return await self._route_or_direct_finance(request, session, history)

    async def _explicit_analysis_route(
        self, request: TurnRequest, session: Session, history: tuple[ChatMessage, ...],
    ) -> tuple[Routing, FinanceWording | None]:
        """Honor typed numeric intent before the dialogue model sees its prose."""
        analysis = request.analysis
        if analysis is None:
            raise RuntimeError("structured_analysis_missing")
        match analysis.root.get("mode"):
            case "forecast" | "risk" as mode:
                # An explicit numeric request already supplies the intended mode. It does
                # not need a second model decision; downstream still validates the period
                # and all supplied numeric fields.
                return Routing(mode=mode, source="template"), None
            case "goal" | "optimize" | "what_if":
                # The structured operation is authoritative. The routing schema does not
                # represent these three FDT modes, and a model cannot safely improve the
                # supplied financial parameters.
                return Routing(mode="review", source="template", fallback_reason="structured_numeric"), None
            case _:
                return await self._route_or_direct_finance(request, session, history)

    async def _route_or_direct_finance(  # noqa: C901, PLR0911 - one return per no-model finance boundary.
        self, request: TurnRequest, session: Session, history: tuple[ChatMessage, ...],
    ) -> tuple[Routing, FinanceWording | None]:
        """Use a catalog definition only when its full question grammar is satisfied."""
        finance_input = finance_evidence(request.question, chat_history(session, include_subject=True))
        # The catalog shortcuts judge the question text alone. A complete question
        # ("복리가 뭐야?", "지금 가장 금리가 높은 예금은?") means the same thing after
        # any earlier turn; letting a previous purchase or balance answer disable them
        # handed every later question to the router, which kept answering with the
        # envelope review (2026-09-26 live). A follow-up that needs the history
        # ("그럼 그건?") retrieves no subject on its own and still falls through.
        standalone = finance_evidence(request.question) if finance_input.history else finance_input
        # A structured analysis may be goal/what-if/optimization even when its
        # prose resembles a general concept.  Preserve its original route and
        # numeric-operation observation instead of taking a knowledge shortcut.
        shortcut_allowed = request.analysis is None and self._direct_finance_enabled()
        if shortcut_allowed and third_party_money(request.question):
            # "친구 돈 관리 좀 봐줄 수 있어?" is not a 돈 관리 concept card nor the user's own review.
            return Routing(mode="finance", source="template"), third_party_wording()
        bounded_status = deterministic_finance_status(standalone) if shortcut_allowed else None
        direct = (
            deterministic_finance_wording(standalone)
            if shortcut_allowed
            and not _own_state_question(request.question)
            and (_concept_shaped(request.question) or _names_concept_beyond_own_data(request.question))
            else None
        )
        # A current-rate question is answered with its source gap before a concept that
        # merely shares a word ("요즘 정기예금 금리 몇 %야?" is not "예금이 뭐야?"); without
        # a rate noun the concept wins ("요즘 적금이 뭐야?").
        if bounded_status is not None and (direct is None or asks_current_rate(request.question)):
            # The question explicitly requires current external material or
            # individual tax/calculation conditions. Returning that gap is
            # safer than making a model infer a catalog status from prose.
            return Routing(mode="finance", source="template"), bounded_status
        if direct is not None:
            # This strict grammar cannot choose FDT routes or construct values; it
            # supplies one pinned catalog definition only.
            return Routing(mode="finance", source="template"), direct
        if shortcut_allowed and not names_catalog_subject(request.question) and chit_chat(request.question):
            # "잠이 안 오는데 어떻게 해?" needs neither a model call nor a catalog fact.
            return Routing(mode="other", source="template", fallback_reason="no_finance_signal"), None
        # The model's fact selection keeps the conversation: "신용카드랑 차이가 뭐야?"
        # after "체크카드가 뭐야?" needs both subjects, and the helper refuses history.
        # A self-contained paraphrase ("ETF가 뭔지 하나도 모르겠어") is judged on its own;
        # a comparison or pointer ("신용카드랑 차이가 뭐야?", "그건?") keeps the history, which
        # the helper then refuses so the router sees the whole conversation.
        selection_input = (
            finance_input
            if is_followup(request.question) or _NEEDS_HISTORY.search(compact(request.question)) is not None
            else standalone
        )
        fast_selection = (
            model_selected_finance_evidence(selection_input)
            if shortcut_allowed
            and not _own_state_question(request.question)
            # "전기포트 3만원 사도 될까?", "XRP 지금 사도 될까요?" decide a purchase or a trade.
            and not spend_or_trade_decision(request.question)
            # A question about the user's own budget ("편의점 비용을 40% 줄면?", "외식 예산 다
            # 썼어?") is the router's to name: a spending cut, a balance, a review.
            and not names_own_budget(request.question)
            and not chit_chat(request.question)
            # Only a question shaped like a concept ask takes the shortcut: "NAV란", "복리
            # 알려줘", "혹시 헤징이 뭔지 알려줄 수 있을까?". A lookup of the user's own data
            # ("다음 결제 예정 뭐 있어?", "가입한 보험이 뭐 있어?") is the router's too.
            and _concept_shaped(request.question)
            else None
        )
        unanswered: FinanceWording | None = None
        if fast_selection is not None:
            # A non-exact general concept still needs the model to choose approved facts,
            # but it does not need a preceding route call or any Twin/FDT lookup.
            wording = await self.core.model.write(fast_selection)
            if not isinstance(wording, FinanceWording):
                # A model adapter must not convert its own invalid finance response into a
                # personal-data/FDT request after the deterministic scope was accepted.
                return Routing(mode="finance", source="template"), selected_finance_wording(
                    None, wording.model, "invalid_finance_wording"
                )
            own_money = _OWN_MONEY_SUBJECT.search(compact(request.question)) is not None
            if wording.answer_status == "answered" or not own_money:
                return Routing(mode="finance", source="template"), wording
            # No approved fact answers a question about the user's own money ("편의점 비용을
            # 40% 줄면?", "헬스 등록하는데 의료·건강 봉투 충분할까?"): the router names its
            # intent, and a finance route keeps the answer already selected.
            unanswered = wording
        decision = await decide_dialogue(
            self.core.model,
            EvidenceInput(
                question=request.question,
                history=history,
                facts_json='{"operation":"dialogue"}',
            ),
            finance_input,
        )
        if off_topic_route(
            request.question, decision.routing.mode, catalog_subject=names_catalog_subject(request.question),
        ):
            # The router may still pick an FDT or personal mode for a question with no
            # money word at all ("너 누구야?", "잠이 안 와"); that answered with the
            # envelope review. Such a turn gets the fixed out-of-scope sentence instead.
            return Routing(mode="other", source="template", fallback_reason="no_finance_signal"), None
        corrected = _corrected_route(request.question, decision.routing.mode)
        if corrected is not None:
            return corrected
        if unanswered is not None and decision.routing.mode == "finance":
            return Routing(mode="finance", source="template"), unanswered
        return decision.routing, decision.finance

    def _direct_finance_enabled(self) -> bool:
        """Keep injected legacy/test adapters on their established model-backed behavior."""
        return bool(getattr(self.core.model, "deterministic_finance_fast_path", False))
