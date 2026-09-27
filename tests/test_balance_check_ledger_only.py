# ruff: noqa: INP001
"""A current balance check reads the ledger only; forecasts keep the FDT simulation.

Live feedback 2026-09-23: "소비잔액 확인 로직이랑 미래예측 로직이 동일한 것 같다".
It was: "봉투 잔액 보여줘" ran ``Coach.review``, which draws the Monte-Carlo
projection, and its projection-based ``next_action``/warnings could be shown on
a balance answer as if they were current facts. A balance check now answers from
the envelope ledger and the engine's deterministic ``observed_budgets`` only.

The assertions compare whole answers and whole result documents, and count every
engine entry point per turn, so an added line, field, or simulation fails a test.
"""

from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import fdt.coaching
import httpx2
import pytest
from fdt.coaching import Coach, observed_budgets
from test_api import TOKEN, setup
from test_balance_check_2026_09_23 import _BALANCES, _BUDGETS
from test_multiturn_clarification_context import RouteTo
from test_purchase_what_if import two_card_fixture

from coaching_service.engine import EngineAdapter
from coaching_service.fast_routes import balance_check_question
from coaching_service.persona import present
from coaching_service.rendering import _BALANCE_TABLE_NOTE, _balance_summary, _with_ro, deterministic_advice
from coaching_service.schemas import Bootstrap, Envelope, JsonDocument, Receipt

_BALANCE_QUESTIONS = (
    "봉투 잔액 보여줘",
    "소비 잔액 확인해줘",
    "이번달 예산 잔액 어때?",
    "남은 예산 표로 보여줘",
    "예산 초과한 봉투 있어?",
    "예산 괜찮아?",
    "예산 얼마 남았어?",
    "외식 예산 얼마 남았어",
    "지금 봉투 잔액 얼마야",
    "지금까지 남은 예산 얼마야",
)
# The one envelope a balance question names; it is recorded on the request and its
# balance opens the summary line (2026-09-26: "외식 예산 얼마 남았어" had no 외식 figure).
_FOCUS = {"외식 예산 얼마 남았어": "외식"}
# A future point, an outcome, or a purchase is never a current balance check (review 2026-09-24).
_NOT_BALANCE_QUESTIONS = (
    "30일 뒤 봉투 잔액 보여줘",
    "향후 예산 괜찮아?",
    "이번달 말 예산 괜찮을까?",
    "3만원짜리 책 살 건데 예산 괜찮아?",
    "다음주까지 예산 괜찮아?",
    "일주일 동안 예산 괜찮아?",
    "예산 남을까?",
    "책 사려는데 예산 남았어?",
    "5,000원 결제할 건데 예산 괜찮아?",
)
# Wording that only a simulated future can produce. None of it is a current fact.
_FORECAST_WORDING = (
    "경로", "분위", "P50", "p50", "P10", "하위 10%", "예측", "예상", "점검 기간", "보통",
    "새로운 감축을 권하지 않습니다", "다음 달 예산", "안전 보장", "까지 확인 범위",
)
_AS_OF = "2026-09-09"
_BODY_KEYS = {
    "chart_hint", "created_at", "envelope_balances", "fallback_reason", "id", "model",
    "numeric_rows", "receipt", "text", "wording_source",
}
_RESULT_KEYS = {
    "operation", "twin_id", "revision", "input_digest", "as_of", "on_date", "status",
    "observed_budgets", "projection", "comparison", "next_action", "warnings", "executed",
    "missing_cash_inputs",
}
_ASSUMED = {
    "code": "ASSUMED_SNAPSHOT",
    "severity": "user",
    "detail": "잔액·카드 청구·예산에 사용자 또는 데모 가정이 포함되어 있습니다. "
    "실제 계좌 확인 결과가 아닙니다.",
}
_REPLAY = {
    "code": "HISTORICAL_REPLAY",
    "severity": "user",
    "detail": f"{_AS_OF} 자료 기준의 검토입니다. 오늘의 사용 가능 금액으로 안내하지 않습니다.",
}
_INCOMPLETE = {
    "code": "BUDGET_INPUT_INCOMPLETE",
    "severity": "user",
    "detail": "월초 이력 또는 지출 분류가 충분하지 않아 잔여 예산만으로 새 지출을 권하지 않습니다.",
}


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _overspent_twin() -> Bootstrap:
    base = two_card_fixture()
    snapshot = dict(base.snapshot.root)
    snapshot["budgets"] = _BUDGETS
    return base.model_copy(
        update={
            "snapshot": JsonDocument(snapshot),
            "envelopes": tuple(
                Envelope(envelope=name, balance_krw=amount) for name, amount in _BALANCES.items()
            ),
        }
    )


def _replaying() -> bool:
    return datetime.now(ZoneInfo("Asia/Seoul")).date().isoformat() != _AS_OF


def _focus_sentence(focus: str | None, *, cat: bool) -> str:
    if focus is None:
        return ""
    balance = _BALANCES[focus]
    ending = "다냥." if cat else "어요."
    if balance < 0:
        return f"{focus} 봉투는 예산을 {-balance:,}원 넘었{ending} "
    return f"{focus} 봉투는 {balance:,}원 남았{ending} "


def _expected_text(*, cat: bool = False, focus: str | None = None) -> str:
    total = f"{sum(_BALANCES.values()):,}"
    if cat:
        lines = [
            "**봉투별 남은 잔액은 아래 표에 정리했다냥.** 지금까지 들어온 결제를 반영한 장부 잔액이다냥.",
            f"{_focus_sentence(focus, cat=True)}봉투 잔액 합계는 {total}원이다냥.",
            "잔액·카드 청구·예산에 사용자 또는 데모 가정이 포함되어 있다냥. 실제 계좌 확인 결과가 아니다냥.",
        ]
        if _replaying():
            lines.append(f"{_AS_OF} 자료 기준의 검토이다냥. 오늘의 사용 가능 금액으로 안내하지 않는다냥.")
        lines += [
            (
                "외식 지출이 예산을 가장 많이 넘었고, 쇼핑도 예산을 넘었다냥. "
                "**이번 기간 외식 소비부터 줄여보면 좋다냥.**"
            ),
            "",
            "확인할 예정 결제, 소득 변동, 또는 지출 계획이 있으면 알려 달라냥.",
        ]
        return "\n".join(lines)
    lines = [
        "봉투별 남은 잔액은 아래 표에 정리했어요. 지금까지 들어온 결제를 반영한 장부 잔액이에요.",
        f"{_focus_sentence(focus, cat=False)}봉투 잔액 합계는 {total}원이에요.",
        _ASSUMED["detail"],
    ]
    if _replaying():
        lines.append(_REPLAY["detail"])
    lines += [
        (
            "외식 지출이 예산을 가장 많이 넘었고, 쇼핑도 예산을 넘었어요. "
            "이번 기간 외식 소비부터 줄여보면 좋아요."
        ),
        "",
        "확인할 예정 결제, 소득 변동, 또는 지출 계획이 있으면 알려 주세요.",
    ]
    return "\n".join(lines)


class _Calls:
    def __init__(self) -> None:
        self.review = 0
        self.numeric = 0
        self.balance = 0

    def snapshot(self) -> tuple[int, int, int]:
        return self.review, self.numeric, self.balance


def _spy_engine(monkeypatch: pytest.MonkeyPatch, *, forbid_simulation: bool) -> _Calls:
    """Count every engine entry point; optionally make any simulation a hard failure."""
    calls = _Calls()
    review, numeric, balance = EngineAdapter.review, EngineAdapter.numeric, EngineAdapter.balance

    def spy_review(self: EngineAdapter, document: JsonDocument, request: JsonDocument) -> JsonDocument:
        calls.review += 1
        return review(self, document, request)

    def spy_numeric(self: EngineAdapter, document: JsonDocument, request: JsonDocument) -> JsonDocument:
        calls.numeric += 1
        return numeric(self, document, request)

    def spy_balance(self: EngineAdapter, document: JsonDocument, request: JsonDocument) -> JsonDocument:
        calls.balance += 1
        return balance(self, document, request)

    monkeypatch.setattr(EngineAdapter, "review", spy_review)
    monkeypatch.setattr(EngineAdapter, "numeric", spy_numeric)
    monkeypatch.setattr(EngineAdapter, "balance", spy_balance)
    if forbid_simulation:
        # Guard below the adapter as well: no path may draw a single future path.
        def forbidden(*_args: object, **_kwargs: object) -> None:
            raise AssertionError("balance check drew a simulated future path")

        monkeypatch.setattr(fdt.coaching, "generate_bundle", forbidden)
        monkeypatch.setattr(fdt.coaching, "project", forbidden)
    return calls


async def _ask(
    tmp_path: Path,
    twin: Bootstrap,
    questions: tuple[str, ...],
    calls: _Calls | None = None,
) -> list[tuple[dict[str, Any], tuple[int, int, int]]]:
    """Ask each question in a fresh session; pair each body with its own engine-call delta."""
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=setup(tmp_path / "ledger.sqlite3", RouteTo("review"))),
        base_url="http://t",
        headers={"Authorization": "Bearer " + TOKEN},
    ) as client:
        pushed = await client.post(
            "/v1/twin", json=twin.model_dump(mode="json"), headers={"Idempotency-Key": "t"}
        )
        assert pushed.status_code == 200, pushed.text
        answers = []
        for index, question in enumerate(questions):
            session = await client.post("/v1/sessions", json={}, headers={"Idempotency-Key": f"s{index}"})
            assert session.status_code == 200, session.text
            before = calls.snapshot() if calls is not None else (0, 0, 0)
            reply = await client.post(
                f"/v1/sessions/{session.json()['id']}/messages",
                json={"question": question},
                headers={"Idempotency-Key": f"q{index}"},
            )
            assert reply.status_code == 200, (question, reply.text)
            after = calls.snapshot() if calls is not None else (0, 0, 0)
            answers.append((reply.json(), (after[0] - before[0], after[1] - before[1], after[2] - before[2])))
        return answers


def _expected_result(twin: Bootstrap) -> dict[str, Any]:
    engine = EngineAdapter()
    loaded = engine._twin(engine.create(twin, "demo"))
    return {
        "operation": "balance_check",
        "twin_id": loaded.twin_id,
        "revision": loaded.revision,
        "input_digest": loaded.content_digest,
        "as_of": _AS_OF,
        "on_date": _AS_OF,
        "status": "ready",
        "observed_budgets": observed_budgets(loaded),
        "projection": None,
        "comparison": None,
        "next_action": None,
        "warnings": [_ASSUMED, _REPLAY] if _replaying() else [_ASSUMED],
        "executed": False,
        "missing_cash_inputs": [],
    }


@pytest.mark.anyio
async def test_every_balance_question_is_answered_from_the_ledger_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _spy_engine(monkeypatch, forbid_simulation=True)
    twin = _overspent_twin()
    answers = await _ask(tmp_path, twin, _BALANCE_QUESTIONS, calls)
    expected_result = _expected_result(twin)
    assert len(answers) == len(_BALANCE_QUESTIONS)
    for (body, delta), question in zip(answers, _BALANCE_QUESTIONS, strict=True):
        # exactly one ledger read, no review, no numeric simulation
        assert delta == (0, 0, 1), question
        assert set(body) == _BODY_KEYS, question
        receipt = body["receipt"]
        assert receipt["trigger"] == "balance_check", question
        focus = _FOCUS.get(question)
        assert receipt["request"] == {
            "operation": "balance_check", "on_date": _AS_OF, "replay": _replaying(),
        } | ({"envelope": focus} if focus is not None else {}), question
        assert set(receipt["result"]) == _RESULT_KEYS, question
        assert receipt["result"] == expected_result, question
        assert receipt["numeric_request"] is None
        assert receipt["numeric_result"] is None
        assert receipt["payment"] is None
        assert receipt["historical"] is None
        assert body["text"] == _expected_text(focus=focus), question
        assert body["envelope_balances"] == [
            {"envelope": name, "balance_krw": amount} for name, amount in _BALANCES.items()
        ], question
        assert body["numeric_rows"] is None, question
        assert body["chart_hint"] is None, question
        assert body["wording_source"] == "template", question
        assert body["model"] == "not_called", question
        assert body["fallback_reason"] is None, question
        for wording in _FORECAST_WORDING:
            assert wording not in body["text"], (question, wording)


@pytest.mark.anyio
async def test_cat_voice_balance_answer_keeps_the_bold_table_note(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("COACHING_PERSONA", "cat")
    calls = _spy_engine(monkeypatch, forbid_simulation=True)
    [(body, delta)] = await _ask(tmp_path, _overspent_twin(), ("봉투 잔액 보여줘",), calls)
    assert delta == (0, 0, 1)
    assert body["text"] == _expected_text(cat=True)
    assert body["text"].startswith("**봉투별 남은 잔액은 아래 표에 정리했다냥.**")


def test_table_note_is_bold_in_both_voices() -> None:
    assert _BALANCE_TABLE_NOTE == (
        "**봉투별 남은 잔액은 아래 표에 정리했어요.** 지금까지 들어온 결제를 반영한 장부 잔액이에요."
    )
    assert present(_BALANCE_TABLE_NOTE, "cat") == (
        "**봉투별 남은 잔액은 아래 표에 정리했다냥.** 지금까지 들어온 결제를 반영한 장부 잔액이다냥."
    )


@pytest.mark.anyio
async def test_idempotent_retry_replays_the_stored_balance_turn(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _spy_engine(monkeypatch, forbid_simulation=True)
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=setup(tmp_path / "retry.sqlite3", RouteTo("review"))),
        base_url="http://t",
        headers={"Authorization": "Bearer " + TOKEN},
    ) as client:
        pushed = await client.post(
            "/v1/twin", json=_overspent_twin().model_dump(mode="json"), headers={"Idempotency-Key": "t"}
        )
        assert pushed.status_code == 200, pushed.text
        session = await client.post("/v1/sessions", json={}, headers={"Idempotency-Key": "s"})
        path = f"/v1/sessions/{session.json()['id']}/messages"
        turn = {"question": "봉투 잔액 보여줘"}
        first = await client.post(path, json=turn, headers={"Idempotency-Key": "q"})
        again = await client.post(path, json=turn, headers={"Idempotency-Key": "q"})
    assert first.status_code == again.status_code == 200
    assert again.json() == first.json()
    assert calls.snapshot() == (0, 0, 1)


# (question, engine calls (review, numeric, balance), receipt trigger, chart hint)
_FDT_QUESTIONS = (
    ("이번달 소비 예측해줘", (0, 1, 0), "numeric_dialogue", True),
    ("이번 달 위험을 알려줘", (0, 1, 0), "numeric_dialogue", False),
    ("300만원짜리 노트북 이번 주에 현금으로 사면 이번 달 괜찮아?", (1, 0, 0), "requested_review", True),
    ("월말 잔액 얼마 남을까", (0, 1, 0), "numeric_dialogue", True),
    ("남은 기간 소비 괜찮을까", (1, 0, 0), "requested_review", False),
    ("30일 뒤 봉투 잔액 보여줘", (1, 0, 0), "requested_review", False),
    ("향후 예산 괜찮아?", (1, 0, 0), "requested_review", False),
    ("이번달 말 예산 괜찮을까?", (1, 0, 0), "requested_review", False),
    ("3만원짜리 책 이번 주에 현금으로 살 건데 예산 괜찮아?", (1, 0, 0), "requested_review", True),
)


@pytest.mark.parametrize("question", _BALANCE_QUESTIONS)
def test_current_balance_questions_are_balance_checks(question: str) -> None:
    assert balance_check_question(question)


@pytest.mark.parametrize("question", _NOT_BALANCE_QUESTIONS)
def test_future_outcome_and_purchase_questions_are_not_balance_checks(question: str) -> None:
    assert not balance_check_question(question)


@pytest.mark.anyio
async def test_forecast_risk_and_purchase_questions_keep_the_fdt_simulation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _spy_engine(monkeypatch, forbid_simulation=False)
    questions = tuple(question for question, _, _, _ in _FDT_QUESTIONS)
    answers = await _ask(tmp_path, _overspent_twin(), questions, calls)
    for (body, delta), expected in zip(answers, _FDT_QUESTIONS, strict=True):
        question, expected_calls, trigger, chart = expected
        assert delta == expected_calls, question
        assert body["receipt"]["trigger"] == trigger, question
        assert body["receipt"]["result"].get("operation") != "balance_check", question
        assert (body["chart_hint"] is not None) == chart, question
        if trigger == "numeric_dialogue":
            assert body["receipt"]["numeric_result"] is not None, question
        else:
            assert body["receipt"]["result"]["projection"] is not None, question
    by_question = {question: body for (body, _), question in zip(answers, questions, strict=True)}
    assert by_question["이번달 소비 예측해줘"]["receipt"]["numeric_request"]["mode"] == "forecast"
    assert by_question["이번 달 위험을 알려줘"]["receipt"]["numeric_request"]["mode"] == "risk"
    purchase = by_question["300만원짜리 노트북 이번 주에 현금으로 사면 이번 달 괜찮아?"]
    assert purchase["receipt"]["result"]["comparison"] is not None


@pytest.mark.anyio
async def test_an_open_ended_window_asks_for_the_period_instead(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _spy_engine(monkeypatch, forbid_simulation=True)
    [(body, delta)] = await _ask(tmp_path, _overspent_twin(), ("다음주까지 예산 괜찮아?",), calls)
    assert delta == (0, 0, 0)
    assert body["status"] == "needs_clarification"
    assert "receipt" not in body


def _engine_pair(
    bootstrap: Bootstrap, *, replay: bool, on_date: str | None = None
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return the ledger result and the pinned review result for one identical request."""
    engine = EngineAdapter()
    document = engine.create(bootstrap, "demo")
    as_of = engine.identity(document).as_of
    day = on_date or as_of
    through = (date.fromisoformat(day) + timedelta(days=7)).isoformat()
    request = {"on_date": day, "through_date": through, "replay": replay}
    ledger = engine.balance(document, JsonDocument(request)).root
    review = Coach(engine._twin(document)).review({**request, "paths": 20})
    return ledger, review


_KEPT = {"ASSUMED_SNAPSHOT", "BUDGET_INPUT_INCOMPLETE", "HISTORICAL_REPLAY"}


@pytest.mark.parametrize("replay", [False, True])
def test_ledger_facts_equal_the_review_engine(replay: bool) -> None:
    ledger, review = _engine_pair(_overspent_twin(), replay=replay)
    assert set(ledger) == _RESULT_KEYS
    assert ledger["observed_budgets"] == review["observed_budgets"]
    assert ledger["warnings"] == [warning for warning in review["warnings"] if warning["code"] in _KEPT]
    assert ledger["warnings"] == ([_ASSUMED, _REPLAY] if replay else [_ASSUMED])
    assert ledger["status"] == review["status"] == "ready"
    for key in ("twin_id", "revision", "as_of", "on_date"):
        assert ledger[key] == review[key], key
    assert ledger["input_digest"] == review["input_digest"]
    assert (ledger["projection"], ledger["comparison"], ledger["next_action"]) == (None, None, None)
    # The review engine did simulate; the ledger result carries none of it.
    assert review["projection"] is not None


def _late_history(bootstrap: Bootstrap) -> Bootstrap:
    """History that starts after the first day of the budget month."""
    return bootstrap.model_copy(
        update={
            "transactions": tuple(
                JsonDocument({**row.root, "transaction_date": "2026-09-05"}) for row in bootstrap.transactions
            )
        }
    )


def test_incomplete_budget_input_is_reported_exactly_like_the_review_engine() -> None:
    ledger, review = _engine_pair(_late_history(_overspent_twin()), replay=False)
    incomplete = [warning for warning in review["warnings"] if warning["code"] == "BUDGET_INPUT_INCOMPLETE"]
    assert incomplete == [_INCOMPLETE]
    assert ledger["warnings"] == [_ASSUMED, _INCOMPLETE]
    assert ledger["warnings"] == [warning for warning in review["warnings"] if warning["code"] in _KEPT]
    assert ledger["observed_budgets"] == review["observed_budgets"]


def test_a_mismatched_reference_date_needs_data_like_the_review_engine() -> None:
    ledger, review = _engine_pair(_late_history(_overspent_twin()), replay=True, on_date="2026-09-08")
    assert review["status"] == ledger["status"] == "needs_data"
    # The review stops at the refresh request before any budget-input check or simulation.
    assert ledger["warnings"] == [warning for warning in review["warnings"] if warning["code"] in _KEPT]
    assert all(warning["code"] != "BUDGET_INPUT_INCOMPLETE" for warning in ledger["warnings"])
    assert review["projection"] is None
    assert ledger["next_action"] is None


def test_the_ledger_result_never_simulates(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("engine.balance drew a simulated future path")

    monkeypatch.setattr(fdt.coaching, "generate_bundle", forbidden)
    monkeypatch.setattr(fdt.coaching, "project", forbidden)
    engine = EngineAdapter()
    document = engine.create(_overspent_twin(), "demo")
    result = engine.balance(document, JsonDocument({"on_date": _AS_OF, "replay": False})).root
    assert result["status"] == "ready"


def _ledger_receipt(budgets: dict[str, int], balances: dict[str, int], *, status: str = "ready") -> Receipt:
    rows = [
        {
            "envelope": name,
            "basis": "approved_snapshot_budget_minus_observed_budgeted_spending",
            "budget_krw": budgets[name],
            "observed_remaining_krw": balance,
        }
        for name, balance in balances.items()
    ]
    return Receipt.model_validate(
        {
            "engine_commit": "pinned-engine",
            "identity": {
                "user_id": "user", "twin_id": "twin", "revision": 1,
                "input_digest": "digest", "as_of": _AS_OF,
            },
            "request": {"operation": "balance_check", "on_date": _AS_OF, "replay": False},
            "result": {
                "operation": "balance_check", "status": status, "observed_budgets": rows, "warnings": [],
            },
            "trigger": "balance_check",
            "current_envelopes": [
                {"envelope": name, "balance_krw": amount} for name, amount in balances.items()
            ],
        }
    )


@pytest.mark.parametrize(
    "balances",
    [
        {"쇼핑": -1_500, "외식": -200_000, "기타": 50_000},  # 0.7% listed before 2,000%
        {"외식": -200_000, "쇼핑": -1_500, "기타": 50_000},  # 2,000% listed first
    ],
)
def test_the_most_exceeded_envelope_leads_whatever_the_order(balances: dict[str, int]) -> None:
    budgets = {"쇼핑": 208_000, "외식": 10_000, "기타": 50_000}
    receipt = _ledger_receipt(budgets, balances)
    assert deterministic_advice(receipt) == (
        "외식 지출이 예산을 가장 많이 넘었고, 쇼핑도 예산을 넘었어요. "
        "**이번 기간 외식 소비부터 줄여보면 좋아요.**"
    )
    assert deterministic_advice(receipt, tone="direct") == (
        "외식 예산을 가장 크게 초과했고, 쇼핑도 초과했어요. **외식 소비부터 줄이세요.**"
    )


def test_overage_is_ranked_by_share_of_budget_not_by_won_amount() -> None:
    # 쇼핑 is 100,000원 over (48%); 외식 only 20,000원 over but 200%; 교통비 5% over.
    budgets = {"쇼핑": 208_000, "외식": 10_000, "교통비": 150_000}
    receipt = _ledger_receipt(budgets, {"교통비": -7_500, "쇼핑": -100_000, "외식": -20_000})
    assert deterministic_advice(receipt) == (
        "외식 지출이 예산을 가장 많이 넘었고, 쇼핑, 교통비도 예산을 넘었어요. "
        "**이번 기간 외식 소비부터 줄여보면 좋아요.**"
    )


def test_a_single_overage_names_only_that_envelope() -> None:
    receipt = _ledger_receipt({"외식": 10_000, "기타": 50_000}, {"외식": -70, "기타": 50_000})
    assert deterministic_advice(receipt) == (
        "외식 지출이 예산을 넘고 있어요. **이번 기간 외식 소비를 조금 줄여보면 좋아요.**"
    )


def test_a_needs_data_ledger_result_keeps_only_the_confirmed_ledger_overage() -> None:
    # Observed-budget bands are not trusted when the result needs data; a negative
    # ledger balance is still a confirmed overage.
    budgets = {"쇼핑": 208_000, "외식": 10_000}
    receipt = _ledger_receipt(budgets, {"쇼핑": -1_500, "외식": 500}, status="needs_data")
    assert deterministic_advice(receipt) == (
        "쇼핑 지출이 예산을 넘고 있어요. **이번 기간 쇼핑 소비를 조금 줄여보면 좋아요.**"
    )


def _stale_snapshot(bootstrap: Bootstrap) -> Bootstrap:
    """A snapshot older than the Twin: the review asks for fresh balances first."""
    snapshot = dict(bootstrap.snapshot.root)
    snapshot["as_of"] = "2026-09-08"
    return bootstrap.model_copy(update={"snapshot": JsonDocument(snapshot)})


def _funded_twin() -> Bootstrap:
    """Every envelope still holds its whole budget; no overage anywhere."""
    return _overspent_twin().model_copy(
        update={
            "envelopes": tuple(
                Envelope(envelope=name, balance_krw=amount) for name, amount in _BUDGETS.items()
            )
        }
    )


def test_missing_cash_state_needs_data_exactly_like_the_review_engine() -> None:
    ledger, review = _engine_pair(_stale_snapshot(_overspent_twin()), replay=False)
    assert review["status"] == ledger["status"] == "needs_data"
    assert ledger["missing_cash_inputs"] == ["snapshot.as_of (새 기준일의 권위 잔액 필요)"]
    assert ledger["next_action"] is None
    assert ledger["warnings"] == [warning for warning in review["warnings"] if warning["code"] in _KEPT]
    assert ledger["observed_budgets"] == review["observed_budgets"]


@pytest.mark.anyio
async def test_surplus_advice_needs_a_complete_cash_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _spy_engine(monkeypatch, forbid_simulation=True)
    [(ready, ready_delta)] = await _ask(tmp_path / "ready", _funded_twin(), ("봉투 잔액 보여줘",), calls)
    [(stale, stale_delta)] = await _ask(
        tmp_path / "stale", _stale_snapshot(_funded_twin()), ("봉투 잔액 보여줘",), calls
    )
    assert ready_delta == stale_delta == (0, 0, 1)
    head = [
        "봉투별 남은 잔액은 아래 표에 정리했어요. 지금까지 들어온 결제를 반영한 장부 잔액이에요.",
        (
            f"봉투 잔액 합계는 {sum(_BUDGETS.values()):,}원이에요. "
            "가장 적게 남은 봉투는 외식으로 10,000원이 남았어요."
        ),
        _ASSUMED["detail"],
        *([_REPLAY["detail"]] if _replaying() else []),
    ]
    tail = ["", "확인할 예정 결제, 소득 변동, 또는 지출 계획이 있으면 알려 주세요."]
    assert ready["receipt"]["result"]["status"] == "ready"
    assert ready["text"] == "\n".join(
        [*head, "외식 예산에 여유가 있어요. 남는 만큼은 저축이나 비상금으로 옮겨 두면 좋아요.", *tail]
    )
    # Without authoritative balances the engine gives no surplus nudge, and neither do we.
    assert stale["receipt"]["result"]["status"] == "needs_data"
    assert stale["text"] == "\n".join([*head, *tail])


@pytest.mark.anyio
async def test_a_confirmed_overage_is_advised_even_when_cash_state_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _spy_engine(monkeypatch, forbid_simulation=True)
    [(body, delta)] = await _ask(tmp_path, _stale_snapshot(_overspent_twin()), ("예산 괜찮아?",), calls)
    assert delta == (0, 0, 1)
    assert body["receipt"]["result"]["status"] == "needs_data"
    assert "외식 지출이 예산을 가장 많이 넘었고, 쇼핑도 예산을 넘었어요." in body["text"]


@pytest.mark.parametrize(
    ("word", "expected"),
    [
        ("외식", "외식으로"),
        ("쇼핑", "쇼핑으로"),
        ("기타", "기타로"),
        ("교통비", "교통비로"),
        ("취미·여가", "취미·여가로"),
        ("편의점·마트·잡화", "편의점·마트·잡화로"),
        ("의료·건강", "의료·건강으로"),
        ("생활", "생활로"),  # ㄹ받침은 '로'
        ("ATM", "ATM(으)로"),
    ],
)
def test_the_particle_follows_the_last_syllable(word: str, expected: str) -> None:
    assert _with_ro(word) == expected


def test_the_summary_names_the_lowest_envelope_with_the_right_particle() -> None:
    envelopes = (Envelope(envelope="쇼핑", balance_krw=3_000), Envelope(envelope="기타", balance_krw=9_000))
    assert _balance_summary(envelopes) == (
        "봉투 잔액 합계는 12,000원이에요. 가장 적게 남은 봉투는 쇼핑으로 3,000원이 남았어요."
    )
