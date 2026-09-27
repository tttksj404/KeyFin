# ruff: noqa: INP001
"""Phase 1 natural-language purchase what-if: lump-sum cash or single-deferred card only.

Cases (a)-(g) follow scratchpad/SPEC-purchase.md section 5. Every clarification
and the deterministic route below must never call the injected model's
``route``/``write``/``judge`` methods; a purchase question either resolves to
one FDT ``expense`` change through the existing review path, or it clarifies
before any model call. The agreed clarify codes (amount/envelope/payment
method/installment/date) now return a normal 200 ``needs_clarification`` turn (an
``answer_type=purchase_review`` ``ChatAnswer``, recorded like a spending
clarification).
"""

from pathlib import Path

import httpx2
import pytest
from test_api import TOKEN, TestModel, setup
from test_engine import fixture

from coaching_service.dialogue import _select_card, _select_cash_account
from coaching_service.fast_routes import NaturalPurchase, natural_purchase
from coaching_service.llm_contract import EvidenceInput, Routing
from coaching_service.numeric_rendering import (
    _PURCHASE_CASH_OK,
    _PURCHASE_OK,
    _PURCHASE_RISK,
    purchase_verdict_text,
)
from coaching_service.schemas import Bootstrap, JsonDocument, Receipt, Session, TwinIdentity


class RouteMustNotRun(TestModel):
    async def route(self, evidence: EvidenceInput) -> Routing:
        raise AssertionError("a deterministic purchase turn must not wait for model routing")


def card_fixture(user: str = "demo") -> Bootstrap:
    """One account plus one CREDIT card, large enough balance for the card case."""
    base = fixture(user)
    snapshot = dict(base.snapshot.root)
    snapshot["accounts"] = [{"account_id": "a", "balance_krw": 5_000_000}]
    snapshot["cards"] = [
        {
            "card_id": "c1",
            "kind": "CREDIT",
            "settlement_account_id": "a",
            "opening_payable_krw": 0,
            "payment_delay_days": 20,
        }
    ]
    return base.model_copy(update={"snapshot": JsonDocument(snapshot)})


def multi_account_fixture(user: str = "demo") -> Bootstrap:
    """Two accounts and no card: cash payment is genuinely ambiguous without a hint."""
    base = fixture(user)
    snapshot = dict(base.snapshot.root)
    snapshot["accounts"] = [
        {"account_id": "a", "balance_krw": 1_000_000},
        {"account_id": "b", "balance_krw": 1_000_000},
    ]
    return base.model_copy(update={"snapshot": JsonDocument(snapshot)})


def multi_account_income_fixture(user: str = "demo") -> Bootstrap:
    """Two accounts, one marked 주거래(is_income): an explicit cash purchase uses it."""
    base = fixture(user)
    snapshot = dict(base.snapshot.root)
    snapshot["accounts"] = [
        {"account_id": "a", "balance_krw": 1_000_000, "is_income": False},
        {"account_id": "b", "balance_krw": 5_000_000, "is_income": True},
    ]
    return base.model_copy(update={"snapshot": JsonDocument(snapshot)})


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


async def _bootstrap(client: httpx2.AsyncClient, twin: Bootstrap) -> str:
    assert (
        await client.post(
            "/v1/twin", json=twin.model_dump(mode="json"), headers={"Idempotency-Key": "init"},
        )
    ).status_code == 200
    session = await client.post("/v1/sessions", json={}, headers={"Idempotency-Key": "session"})
    return session.json()["id"]


# --- (e) adversarial: a price-only question must never be treated as a purchase ---


def test_select_cash_account_prefers_the_income_account_among_many() -> None:
    # A sole account is unambiguous regardless of the income flag.
    assert _select_cash_account([{"account_id": "a"}]) == {"account_id": "a"}
    # Several accounts resolve to the one designated 주거래(is_income).
    picked = _select_cash_account(
        [{"account_id": "a", "is_income": False}, {"account_id": "b", "is_income": True}]
    )
    assert picked == {"account_id": "b", "is_income": True}
    # Zero or several income accounts stays ambiguous (fail closed).
    assert _select_cash_account([{"account_id": "a"}, {"account_id": "b"}]) is None
    assert (
        _select_cash_account(
            [{"account_id": "a", "is_income": True}, {"account_id": "b", "is_income": True}]
        )
        is None
    )


def two_card_fixture(user: str = "demo") -> Bootstrap:
    """주거래 a + 보조 b 계좌, 각 계좌에서 출금되는 카드 두 장(라이브 테스트 계정 구성)."""
    base = fixture(user)
    snapshot = dict(base.snapshot.root)
    snapshot["accounts"] = [
        {"account_id": "a", "balance_krw": 5_000_000, "is_income": True},
        {"account_id": "b", "balance_krw": 45_400, "is_income": False},
    ]
    snapshot["cards"] = [
        {"card_id": "side", "kind": "CREDIT", "settlement_account_id": "b",
         "opening_payable_krw": 0, "payment_delay_days": 20},
        {"card_id": "main", "kind": "CREDIT", "settlement_account_id": "a",
         "opening_payable_krw": 0, "payment_delay_days": 20},
    ]
    return base.model_copy(update={"snapshot": JsonDocument(snapshot)})


def test_select_card_defaults_to_the_card_settling_from_the_income_account() -> None:
    accounts = two_card_fixture().snapshot.root["accounts"]
    cards = two_card_fixture().snapshot.root["cards"]
    assert isinstance(accounts, list)
    assert isinstance(cards, list)
    assert _select_card(cards, accounts) == cards[1]
    # A sole card is unambiguous without any income flag.
    assert _select_card([cards[0]], [{"account_id": "b"}]) == cards[0]
    # No income account, or two cards on it, stays ambiguous (fail closed).
    assert _select_card(cards, [{"account_id": "a"}, {"account_id": "b"}]) is None
    both_on_income = [{**cards[0], "settlement_account_id": "a"}, cards[1]]
    assert _select_card(both_on_income, accounts) is None
    # A DEBIT card must settle on the purchase date, so it is never the deferred default.
    debit_on_income = [cards[0], {**cards[1], "kind": "DEBIT"}]
    assert _select_card(debit_on_income, accounts) is None


def test_price_only_question_is_not_a_purchase_route() -> None:
    assert natural_purchase("아이폰 가격이 얼마야?") is None


# --- casual purchase phrasings are now recognized as purchase intent (DO a) ---


def test_casual_buy_phrasing_is_recognized_as_purchase_missing_amount() -> None:
    # "사고싶어" must no longer fall through to off-topic: it is a purchase with a
    # missing amount, so it clarifies rather than returning None.
    assert natural_purchase("닌텐도 스위치 사고싶어") == "purchase_amount_required"


def test_casual_buy_phrasing_variants_are_recognized() -> None:
    # Casual verbs are recognized only alongside a concrete purchase signal (here
    # an item alias). "장만하" was removed entirely (collides with 장만하다 뜻 / 집 장만).
    for question in ("에어팟 사볼까", "청소기 사둘까", "냉장고 사고싶어"):
        assert natural_purchase(question) == "purchase_amount_required", question


def test_casual_buy_with_all_fields_parses_to_full_natural_purchase() -> None:
    parsed = natural_purchase("40만원짜리 닌텐도 스위치 이번주에 현금으로 사도 될까")
    assert isinstance(parsed, NaturalPurchase)
    assert parsed.amount_krw == 400_000
    assert parsed.envelope == "기타"
    assert parsed.date_token == "this_week"
    assert parsed.payment_hint == "cash"


def test_given_casual_cash_question_recognized_but_missing_amount() -> None:
    # The exact casual phrasing from the task: recognized as a purchase (verb
    # "사도"), missing only its amount, so it clarifies instead of guessing.
    assert natural_purchase("닌텐도 스위치 이번주에 현금으로 사도 될까") == "purchase_amount_required"


# --- new consumer-item aliases resolve to an envelope (DO c) ---


def test_new_item_aliases_resolve_to_envelope() -> None:
    for item, envelope in (
        ("닌텐도", "기타"),
        ("스위치", "기타"),
        ("게임기", "기타"),
        ("에어팟", "기타"),
        ("티비", "기타"),
        ("tv", "기타"),
        ("청소기", "기타"),
        ("에어컨", "기타"),
        ("냉장고", "기타"),
    ):
        parsed = natural_purchase(f"50만원짜리 {item} 이번주에 현금으로 사도 될까")
        assert isinstance(parsed, NaturalPurchase), item
        assert parsed.envelope == envelope, item


# --- FALSE-POSITIVE guard: non-purchase sentences must stay non-purchase (DO a) ---


def test_added_verbs_do_not_create_false_positive_purchases() -> None:
    assert natural_purchase("동물원에서 사자 봤어") is None  # 사자 = lion, not 사다
    assert natural_purchase("여기서 며칠 살래") is None  # 살다 = live, not buy
    assert natural_purchase("복리가 뭐야") is None
    assert natural_purchase("이번달 소비 얼마야") is None


def test_casual_verb_without_concrete_signal_does_not_hijack_finance_routing() -> None:
    # Regression: casual buy verbs (사고싶/사볼까/사둘까) with no amount and no item
    # alias must fall through to finance/definition/goal routing, not emit a
    # purchase clarify. "장만하" is gone entirely.
    assert natural_purchase("예금 사고싶은데 뭐가 좋아") is None  # finance concept
    assert natural_purchase("장만하다 뜻이 뭐야") is None  # definition
    assert natural_purchase("집 장만하려면 얼마 모아야 해") is None  # goal/concept
    assert natural_purchase("이거 사고싶다는 생각만 했어") is None  # no amount, no item


def test_casual_verb_with_concrete_signal_is_recognized() -> None:
    # An item alias is enough of a concrete signal to admit the casual verb.
    assert natural_purchase("닌텐도 스위치 사고싶어") == "purchase_amount_required"
    # A full casual purchase parses through to NaturalPurchase (or the next
    # missing-field code); here every field is present, so it is a full purchase.
    parsed = natural_purchase("닌텐도 스위치 30만원 이번주에 현금으로 사고싶어")
    assert isinstance(parsed, (NaturalPurchase, str))
    if isinstance(parsed, NaturalPurchase):
        assert parsed.amount_krw == 300_000
        assert parsed.envelope == "기타"


def test_already_covered_buy_edge_stays_sane() -> None:
    # "사서" is a pre-existing verb form; behavior is unchanged: it is a purchase
    # with a missing amount, so it clarifies (it must not crash or become None).
    assert natural_purchase("책을 사서 읽었어") == "purchase_amount_required"


# --- (a) a clear single-payment purchase reaches the review route deterministically ---


@pytest.mark.anyio
async def test_clear_cash_purchase_reaches_review_with_expense_change_and_no_model_call(
    tmp_path: Path,
) -> None:
    model = RouteMustNotRun()
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=setup(tmp_path / "purchase-a.sqlite3", model)),
        base_url="http://test", headers={"Authorization": "Bearer " + TOKEN},
    ) as client:
        path = "/v1/sessions/" + await _bootstrap(client, fixture())
        response = await client.post(
            path + "/messages",
            json={"question": "300만원짜리 노트북 이번 주에 사면 이번 달 괜찮아?"},
            headers={"Idempotency-Key": "turn"},
        )
        assert response.status_code == 200, response.text
        answer = response.json()
        receipt = answer["receipt"]
        assert receipt["routing"] == {"mode": "review", "source": "template", "fallback_reason": None}
        changes = receipt["request"]["changes"]
        assert changes == [
            {
                "kind": "expense",
                "date": "2026-09-09",
                "amount_krw": 3_000_000,
                "envelope": "기타",
                "account_id": "a",
            }
        ]
        # A cash lump sum of 3,000,000 against a 1,000,000 balance must trip the
        # existing shortfall signal: the binary verdict renders as "risk", and the
        # answer opens with it, followed by the envelope overage (기타 holds 100,000).
        lines = answer["text"].split("\n")
        assert lines[0] == "구매 후 예측상 계좌 잔액이 부족해질 수 있어요."
        assert lines[1] == "기타 봉투 예산도 2,900,000원 초과해요."
        assert "부족 예측 있음." in answer["text"]
        assert answer["wording_source"] == "template"
        assert answer["model"] == "not_called"
        assert model.writes == 0
        assert model.routes == 0


# --- (b) baseline-vs-purchase determinism: identical seed, identical bytes on rerun ---


@pytest.mark.anyio
async def test_purchase_verdict_is_deterministic_across_reruns(tmp_path: Path) -> None:
    model = RouteMustNotRun()
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=setup(tmp_path / "purchase-b.sqlite3", model)),
        base_url="http://test", headers={"Authorization": "Bearer " + TOKEN},
    ) as client:
        path = "/v1/sessions/" + await _bootstrap(client, fixture())
        body = {"question": "300만원짜리 노트북 이번 주에 사면 이번 달 괜찮아?"}
        first = await client.post(path + "/messages", json=body, headers={"Idempotency-Key": "turn-1"})
        second = await client.post(path + "/messages", json=body, headers={"Idempotency-Key": "turn-2"})
        assert first.status_code == second.status_code == 200
        first_receipt, second_receipt = first.json()["receipt"], second.json()["receipt"]
        assert first_receipt["request"] == second_receipt["request"]
        assert first_receipt["result"] == second_receipt["result"]
        assert first.json()["text"] == second.json()["text"]


# --- (c) any missing/ambiguous required field clarifies instead of guessing ---


@pytest.mark.anyio
async def test_missing_amount_clarifies_without_model_call(tmp_path: Path) -> None:
    model = RouteMustNotRun()
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=setup(tmp_path / "purchase-c1.sqlite3", model)),
        base_url="http://test", headers={"Authorization": "Bearer " + TOKEN},
    ) as client:
        session_id = await _bootstrap(client, fixture())
        path = "/v1/sessions/" + session_id
        response = await client.post(
            path + "/messages",
            json={"question": "노트북 이번 주에 사면 이번 달 괜찮아?"},
            headers={"Idempotency-Key": "turn"},
        )
        assert response.status_code == 200, response.text
        answer = response.json()
        assert answer["answer_type"] == "purchase_review"
        assert answer["status"] == "needs_clarification"
        assert answer["fallback_reason"] == "purchase_amount_required"
        assert answer["evidence"]["purchase"]["clarification"] == "purchase_amount_required"
        assert answer["text"] == (
            "얼마짜리 구매인지 금액을 알려주시면 이번 예산에 미치는 영향을 확인해 드릴게요."
        )
        assert answer["model"] == "not_called"
        # A 200 clarification is a normal recorded turn (user + assistant message).
        session = Session.model_validate_json((await client.get(path)).content)
        assert len(session.messages) == 2
        assert model.writes == 0
        assert model.routes == 0


@pytest.mark.anyio
async def test_missing_date_clarifies_without_model_call(tmp_path: Path) -> None:
    # A clear purchase (amount + item + verb) that only omits its date now
    # returns the same 200 needs_clarification turn as the other clarify codes,
    # not a 422.
    model = RouteMustNotRun()
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=setup(tmp_path / "purchase-c2.sqlite3", model)),
        base_url="http://test", headers={"Authorization": "Bearer " + TOKEN},
    ) as client:
        session_id = await _bootstrap(client, fixture())
        path = "/v1/sessions/" + session_id
        response = await client.post(
            path + "/messages",
            json={"question": "300만원짜리 노트북 사면 이번 달 괜찮아?"},
            headers={"Idempotency-Key": "turn"},
        )
        assert response.status_code == 200, response.text
        answer = response.json()
        assert answer["answer_type"] == "purchase_review"
        assert answer["status"] == "needs_clarification"
        assert answer["fallback_reason"] == "purchase_date_required"
        assert answer["evidence"]["purchase"]["clarification"] == "purchase_date_required"
        assert answer["text"] == (
            "언제 구매할 예정인지 알려주세요. "
            "오늘·내일·이번주처럼 시점을 알려주시면 그 기준으로 확인해 드릴게요."
        )
        assert answer["model"] == "not_called"
        # A 200 clarification is a normal recorded turn (user + assistant message).
        session = Session.model_validate_json((await client.get(path)).content)
        assert len(session.messages) == 2
        assert model.writes == 0
        assert model.routes == 0


@pytest.mark.anyio
async def test_missing_envelope_mapping_clarifies_without_model_call(tmp_path: Path) -> None:
    model = RouteMustNotRun()
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=setup(tmp_path / "purchase-c3.sqlite3", model)),
        base_url="http://test", headers={"Authorization": "Bearer " + TOKEN},
    ) as client:
        path = "/v1/sessions/" + await _bootstrap(client, fixture())
        response = await client.post(
            path + "/messages",
            json={"question": "300만원짜리 이번 주에 사면 이번 달 괜찮아?"},
            headers={"Idempotency-Key": "turn"},
        )
        assert response.status_code == 200, response.text
        answer = response.json()
        assert answer["answer_type"] == "purchase_review"
        assert answer["status"] == "needs_clarification"
        assert answer["fallback_reason"] == "purchase_envelope_required"
        assert answer["text"] == "어떤 항목의 지출인지 알려주시면 해당 봉투 기준으로 살펴볼게요."
        assert answer["model"] == "not_called"
        assert model.writes == 0
        assert model.routes == 0


@pytest.mark.anyio
async def test_ambiguous_payment_method_clarifies_without_model_call(tmp_path: Path) -> None:
    # Two real accounts and no card, with no cash/card word in the question:
    # the payment source is genuinely ambiguous and must not be guessed.
    model = RouteMustNotRun()
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=setup(tmp_path / "purchase-c4.sqlite3", model)),
        base_url="http://test", headers={"Authorization": "Bearer " + TOKEN},
    ) as client:
        path = "/v1/sessions/" + await _bootstrap(client, multi_account_fixture())
        response = await client.post(
            path + "/messages",
            json={"question": "300만원짜리 노트북 이번 주에 사면 이번 달 괜찮아?"},
            headers={"Idempotency-Key": "turn"},
        )
        assert response.status_code == 200, response.text
        answer = response.json()
        assert answer["answer_type"] == "purchase_review"
        assert answer["status"] == "needs_clarification"
        assert answer["fallback_reason"] == "purchase_payment_method_required"
        assert answer["text"] == (
            "현금·계좌 결제인지 카드 결제인지 알려주세요. "
            "카드라면 결제 예정일도 함께 알려주시면 정확히 반영할 수 있어요."
        )
        assert answer["model"] == "not_called"
        assert model.writes == 0
        assert model.routes == 0


@pytest.mark.anyio
async def test_cash_purchase_with_multiple_accounts_resolves_to_income_account(
    tmp_path: Path,
) -> None:
    # The user named the method (cash); with several accounts the remaining
    # ambiguity is which account, resolved to the designated 주거래(is_income)
    # instead of looping the misleading cash-vs-card clarification.
    model = RouteMustNotRun()
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=setup(tmp_path / "purchase-inc.sqlite3", model)),
        base_url="http://test", headers={"Authorization": "Bearer " + TOKEN},
    ) as client:
        path = "/v1/sessions/" + await _bootstrap(client, multi_account_income_fixture())
        response = await client.post(
            path + "/messages",
            json={"question": "30만원짜리 노트북 이번 주에 현금으로 사면 이번 달 괜찮아?"},
            headers={"Idempotency-Key": "turn"},
        )
        assert response.status_code == 200, response.text
        answer = response.json()
        receipt = answer["receipt"]
        # Resolved (no clarification), and the change draws from the income account.
        assert receipt["routing"]["fallback_reason"] is None
        assert receipt["request"]["changes"][0]["account_id"] == "b"
        assert model.routes == 0


@pytest.mark.anyio
async def test_card_purchase_with_two_cards_uses_the_income_account_card(tmp_path: Path) -> None:
    # Live 2026-09-23: with two cards the card turn fell back to the misleading
    # cash-vs-card question. The card settling from the 주거래 account is the default.
    model = RouteMustNotRun()
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=setup(tmp_path / "purchase-card2.sqlite3", model)),
        base_url="http://test", headers={"Authorization": "Bearer " + TOKEN},
    ) as client:
        path = "/v1/sessions/" + await _bootstrap(client, two_card_fixture())
        response = await client.post(
            path + "/messages",
            json={"question": "30만원짜리 노트북 이번 주에 신용카드로 사면 이번 달 괜찮아? 2026-10-05 결제"},
            headers={"Idempotency-Key": "turn"},
        )
        assert response.status_code == 200, response.text
        receipt = response.json()["receipt"]
        assert receipt["routing"]["fallback_reason"] is None
        change = receipt["request"]["changes"][0]
        assert (change["card_id"], change["payment_date"]) == ("main", "2026-10-05")
        assert model.routes == 0


@pytest.mark.anyio
async def test_conflicting_payment_words_clarify_at_200_without_model_call(tmp_path: Path) -> None:
    # Both a cash word and a card word appear: the text-only parser (site 1)
    # emits purchase_payment_method_required before any twin load, and it must
    # also surface as a 200 needs_clarification turn, not a 422.
    model = RouteMustNotRun()
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=setup(tmp_path / "purchase-c5.sqlite3", model)),
        base_url="http://test", headers={"Authorization": "Bearer " + TOKEN},
    ) as client:
        path = "/v1/sessions/" + await _bootstrap(client, fixture())
        response = await client.post(
            path + "/messages",
            json={"question": "300만원짜리 노트북 이번 주에 카드로 현금으로 사면 이번 달 괜찮아?"},
            headers={"Idempotency-Key": "turn"},
        )
        assert response.status_code == 200, response.text
        answer = response.json()
        assert answer["answer_type"] == "purchase_review"
        assert answer["status"] == "needs_clarification"
        assert answer["fallback_reason"] == "purchase_payment_method_required"
        assert answer["model"] == "not_called"
        assert model.writes == 0
        assert model.routes == 0


# --- (d) multi-installment purchases are out of Phase 1 scope: never a single-payment answer ---


@pytest.mark.anyio
async def test_installment_purchase_is_refused_not_answered_as_single_payment(tmp_path: Path) -> None:
    model = RouteMustNotRun()
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=setup(tmp_path / "purchase-d.sqlite3", model)),
        base_url="http://test", headers={"Authorization": "Bearer " + TOKEN},
    ) as client:
        path = "/v1/sessions/" + await _bootstrap(client, fixture())
        response = await client.post(
            path + "/messages",
            json={"question": "300만원짜리 노트북 12개월 할부로 사면 이번 달 괜찮아?"},
            headers={"Idempotency-Key": "turn"},
        )
        assert response.status_code == 200, response.text
        answer = response.json()
        assert answer["answer_type"] == "purchase_review"
        assert answer["status"] == "needs_clarification"
        assert answer["fallback_reason"] == "purchase_installment_unsupported"
        assert answer["text"] == (
            "할부 구매는 아직 지원하지 않아요. 일시불 기준으로 다시 여쭤봐 주시면 확인해 드릴게요."
        )
        assert answer["model"] == "not_called"
        assert model.writes == 0
        assert model.routes == 0


# --- (g) card purchase defers the cash outflow to the given payment date ---


@pytest.mark.anyio
async def test_card_purchase_defers_cash_outflow_to_payment_date(tmp_path: Path) -> None:
    model = RouteMustNotRun()
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=setup(tmp_path / "purchase-g.sqlite3", model)),
        base_url="http://test", headers={"Authorization": "Bearer " + TOKEN},
    ) as client:
        path = "/v1/sessions/" + await _bootstrap(client, card_fixture())
        response = await client.post(
            path + "/messages",
            json={
                # An explicit structured period is supplied because the calendar
                # parser otherwise treats any bare "YYYY-MM-DD" substring in the
                # question as an unresolved second period, independent of this
                # purchase feature (see period_request.py's ``_UNRESOLVED``).
                "question": (
                    "300만원짜리 노트북 이번 주에 카드로 사서 2026-10-05에 결제하면 이번 달 안에 괜찮아?"
                ),
                "period": {"kind": "month_end"},
            },
            headers={"Idempotency-Key": "turn"},
        )
        assert response.status_code == 200, response.text
        answer = response.json()
        receipt = answer["receipt"]
        assert receipt["request"]["changes"] == [
            {
                "kind": "expense",
                "date": "2026-09-09",
                "amount_krw": 3_000_000,
                "envelope": "기타",
                "card_id": "c1",
                "payment_date": "2026-10-05",
            }
        ]
        # The card settlement date (2026-10-05) falls outside the review window
        # (through the end of September), so the review period's own cash
        # effect is zero and the verdict must not read as a shortfall.
        effect = receipt["result"]["comparison"]["effect"]
        assert effect["terminal_cash_change"]["p50_krw"] == 0
        # No account shortfall, but a 3,000,000 laptop does not fit the 100,000 left
        # in 기타: the verdict must say so instead of "괜찮아요" (2026-09-26 live).
        assert answer["text"].split("\n")[0] == (
            "계좌 잔액으로는 결제할 수 있지만 기타 봉투에 남은 100,000원보다 많아 "
            "봉투 예산을 2,900,000원 초과해요."
        )
        assert "괜찮" not in answer["text"].split("\n")[0]
        assert "부족 예측 없음." in answer["text"]
        assert model.writes == 0
        assert model.routes == 0


# --- (h) the binary verdict must reflect the ABSOLUTE post-purchase shortfall,
#         not the baseline-vs-planned delta: a purchase that keeps an
#         already-shortfall user in shortfall (planned_fraction unchanged from
#         baseline) must still render as "risk", never as false-reassurance "OK" ---


def _verdict_receipt(baseline_fraction: float, planned_fraction: float) -> Receipt:
    """Minimal Receipt exercising only what ``purchase_verdict_text`` reads."""
    identity = TwinIdentity(user_id="demo", twin_id="t1", revision=1, input_digest="d", as_of="2026-09-09")
    return Receipt(
        engine_commit="c",
        identity=identity,
        request=JsonDocument(root={"changes": [{"kind": "expense"}]}),
        result=JsonDocument(
            root={
                "comparison": {
                    "baseline": {"cash": {"period_account_shortfall": {"fraction": baseline_fraction}}},
                    "planned": {
                        "cash": {
                            "period_account_shortfall": {"fraction": planned_fraction},
                            "terminal_balance": {"p50_krw": 0},
                        }
                    },
                }
            }
        ),
        trigger="message",
    )


def test_purchase_verdict_uses_absolute_shortfall_when_already_over_budget() -> None:
    # Already fully in shortfall before AND after the purchase: the delta is
    # zero (no "worsening"), but the absolute post-purchase state is still a
    # shortfall, so the verdict must be risk, consistent with "부족 예측 있음.".
    pieces = purchase_verdict_text(_verdict_receipt(baseline_fraction=1.0, planned_fraction=1.0))
    assert _PURCHASE_RISK in pieces
    assert _PURCHASE_OK not in pieces
    assert "부족 예측 있음." in pieces


def test_purchase_verdict_uses_absolute_shortfall_when_partially_over_budget() -> None:
    pieces = purchase_verdict_text(_verdict_receipt(baseline_fraction=0.5, planned_fraction=0.5))
    assert _PURCHASE_RISK in pieces
    assert _PURCHASE_OK not in pieces
    assert "부족 예측 있음." in pieces


def test_purchase_verdict_stays_ok_when_no_shortfall_before_or_after() -> None:
    # This minimal receipt names no envelope, so only the account check is claimed.
    pieces = purchase_verdict_text(_verdict_receipt(baseline_fraction=0.0, planned_fraction=0.0))
    assert pieces[0] == _PURCHASE_CASH_OK
    assert _PURCHASE_RISK not in pieces
    assert "부족 예측 없음." in pieces
