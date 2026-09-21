# ruff: noqa: INP001
"""Phase 1 natural-language purchase what-if: lump-sum cash or single-deferred card only.

Cases (a)-(g) follow scratchpad/SPEC-purchase.md section 5. Every clarification
and the deterministic route below must never call the injected model's
``route``/``write``/``judge`` methods; a purchase question either resolves to
one FDT ``expense`` change through the existing review path, or it is refused
with a clarification code before any model call, exactly like the existing
``period_clarification_required`` contract.
"""

from pathlib import Path

import httpx2
import pytest
from test_api import TOKEN, TestModel, setup
from test_engine import fixture

from coaching_service.fast_routes import natural_purchase
from coaching_service.llm_contract import EvidenceInput, Routing
from coaching_service.numeric_rendering import _PURCHASE_OK, _PURCHASE_RISK, purchase_verdict_text
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


def test_price_only_question_is_not_a_purchase_route() -> None:
    assert natural_purchase("아이폰 가격이 얼마야?") is None


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
        # existing shortfall signal: the binary verdict renders as "risk".
        assert "구매 후 예측상 예산을 넘겨 이번 기간이 어려울 수 있어요." in answer["text"]
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
        before = await client.get(path)
        response = await client.post(
            path + "/messages",
            json={"question": "노트북 이번 주에 사면 이번 달 괜찮아?"},
            headers={"Idempotency-Key": "turn"},
        )
        assert response.status_code == 422
        assert response.json()["error"] == "purchase_amount_required"
        assert Session.model_validate_json((await client.get(path)).content) == Session.model_validate_json(
            before.content
        )
        assert model.writes == 0
        assert model.routes == 0


@pytest.mark.anyio
async def test_missing_date_clarifies_without_model_call(tmp_path: Path) -> None:
    model = RouteMustNotRun()
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=setup(tmp_path / "purchase-c2.sqlite3", model)),
        base_url="http://test", headers={"Authorization": "Bearer " + TOKEN},
    ) as client:
        path = "/v1/sessions/" + await _bootstrap(client, fixture())
        response = await client.post(
            path + "/messages",
            json={"question": "300만원짜리 노트북 사면 이번 달 괜찮아?"},
            headers={"Idempotency-Key": "turn"},
        )
        assert response.status_code == 422
        assert response.json()["error"] == "purchase_date_required"
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
        assert response.status_code == 422
        assert response.json()["error"] == "purchase_envelope_required"
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
        assert response.status_code == 422
        assert response.json()["error"] == "purchase_payment_method_required"
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
        assert response.status_code == 422
        assert response.json()["error"] == "purchase_installment_unsupported"
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
        assert "예측상 예산 안에 들어와 괜찮아요." in answer["text"]
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
    pieces = purchase_verdict_text(_verdict_receipt(baseline_fraction=0.0, planned_fraction=0.0))
    assert _PURCHASE_OK in pieces
    assert _PURCHASE_RISK not in pieces
    assert "부족 예측 없음." in pieces
