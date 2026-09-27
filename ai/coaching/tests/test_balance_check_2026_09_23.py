# ruff: noqa: INP001
"""Live feedback 2026-09-23 on the envelope balance check.

The balance check shows the envelope table and what is left; it is not a forecast.
"봉투 잔액 보여줘" was a sentence list, "소비 잔액 확인해줘" failed, "예산 괜찮아?" got a
budget definition, every balance answer opened with the forecast-window header, the
advice named the first over-budget envelope (0.7% over) instead of the 2,000% one, and
the "경로 수와 분위수…" / "다음 달 예산을…" caveats were still shown.
"""

from pathlib import Path

import httpx2
import pytest
from test_api import TOKEN, setup
from test_multiturn_clarification_context import RouteTo
from test_purchase_what_if import two_card_fixture

from coaching_service.fast_routes import balance_check_question
from coaching_service.rendering import _BALANCE_TABLE_NOTE, deterministic_advice, user_warnings
from coaching_service.schemas import Envelope, JsonDocument, Receipt

_BUDGETS = {
    "외식": 10_000, "교통비": 150_000, "의료·건강": 150_000, "취미·여가": 150_000,
    "쇼핑": 208_000, "편의점·마트·잡화": 148_700, "기타": 50_000,
}
# 쇼핑 is listed first and only 0.7% over; 외식 is 2,000% over.
_BALANCES = {
    "쇼핑": -1_500, "외식": -200_000, "교통비": 150_000, "의료·건강": 150_000,
    "취미·여가": 150_000, "편의점·마트·잡화": 148_700, "기타": 50_000,
}


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.parametrize(
    "question",
    [
        "봉투 잔액 보여줘", "소비 잔액 확인해줘", "이번달 예산 잔액 어때?", "남은 예산 표로 보여줘",
        "예산 초과한 봉투 있어?", "예산 괜찮아?", "예산 얼마 남았어?", "외식 예산 얼마 남았어",
    ],
)
def test_balance_questions_are_balance_checks(question: str) -> None:
    assert balance_check_question(question)


@pytest.mark.parametrize(
    "question",
    [
        "예산이 뭐야", "계좌 잔액 보여줘", "이번달 식비 얼마 썼어", "다음달 예산 괜찮을까", "예산 위험해?",
        "이번달 소비 예측해줘", "내일 노트북 200만원 현금으로 사도 괜찮아?", "식비 20% 줄이면 괜찮아?",
        "남은 기간 소비 괜찮을까", "통장 잔고 얼마야", "월말 잔액 얼마 남을까",
    ],
)
def test_other_questions_keep_their_routes(question: str) -> None:
    assert not balance_check_question(question)


def _review_receipt(balances: dict[str, int]) -> Receipt:
    rows = [
        {
            "envelope": name,
            "basis": "approved_snapshot_budget_minus_observed_budgeted_spending",
            "budget_krw": _BUDGETS[name],
            "observed_remaining_krw": balance,
        }
        for name, balance in balances.items()
    ]
    return Receipt.model_validate(
        {
            "engine_commit": "pinned-engine",
            "identity": {
                "user_id": "user", "twin_id": "twin", "revision": 1,
                "input_digest": "digest", "as_of": "2026-09-21",
            },
            "request": {"on_date": "2026-09-21", "through_date": "2026-09-28"},
            "result": {"status": "ready", "observed_budgets": rows},
            "trigger": "requested_review",
            "current_envelopes": [
                {"envelope": name, "balance_krw": balance} for name, balance in balances.items()
            ],
        }
    )


def test_advice_names_the_most_exceeded_envelope_first() -> None:
    advice = deterministic_advice(_review_receipt(_BALANCES))
    assert advice is not None
    assert advice.startswith("외식 지출이 예산을 가장 많이 넘었고, 쇼핑도 예산을 넘었어요.")
    assert "**이번 기간 외식 소비부터 줄여보면 좋아요.**" in advice


def test_near_limit_and_healthy_pick_the_extreme_envelope() -> None:
    near = deterministic_advice(_review_receipt({"쇼핑": 20_000, "외식": 500, "기타": 50_000}))
    assert near is not None
    assert near.startswith("외식 예산이 거의 다 찼어요.")
    healthy = deterministic_advice(_review_receipt({"기타": 45_000, "교통비": 150_000}))
    assert healthy is not None
    assert healthy.startswith("교통비 예산에 여유가 있어요.")


def test_engine_boilerplate_caveats_are_hidden() -> None:
    result = JsonDocument(
        {
            "warnings": [
                {"code": "CONDITIONAL_MODEL", "severity": "user", "detail": "경로 수와 분위수는 계산입니다."},
                {
                    "code": "NEXT_MONTH_BUDGET_UNCONFIRMED",
                    "severity": "user",
                    "detail": "다음 달 예산을 이번 달 예산과 같다고 가정하지 않습니다.",
                },
                {"code": "LIMITED_HISTORY", "severity": "user", "detail": "거래 이력이 짧습니다."},
            ]
        }
    )
    assert user_warnings(result) == ["거래 이력이 짧습니다."]


@pytest.mark.anyio
async def test_balance_answers_are_the_table_and_summary_without_forecast_header(tmp_path: Path) -> None:
    base = two_card_fixture()
    snapshot = dict(base.snapshot.root)
    snapshot["budgets"] = _BUDGETS
    twin = base.model_copy(
        update={
            "snapshot": JsonDocument(snapshot),
            "envelopes": tuple(
                Envelope(envelope=name, balance_krw=amount) for name, amount in _BALANCES.items()
            ),
        }
    )
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=setup(tmp_path / "b.sqlite3", RouteTo("review"))),
        base_url="http://t",
        headers={"Authorization": "Bearer " + TOKEN},
    ) as client:
        pushed = await client.post(
            "/v1/twin", json=twin.model_dump(mode="json"), headers={"Idempotency-Key": "t"}
        )
        assert pushed.status_code == 200, pushed.text
        texts = []
        for index, question in enumerate(("봉투 잔액 보여줘", "소비 잔액 확인해줘", "예산 괜찮아?")):
            session = await client.post("/v1/sessions", json={}, headers={"Idempotency-Key": f"s{index}"})
            reply = await client.post(
                f"/v1/sessions/{session.json()['id']}/messages",
                json={"question": question},
                headers={"Idempotency-Key": f"q{index}"},
            )
            assert reply.status_code == 200, reply.text
            body = reply.json()
            assert len(body["envelope_balances"]) == len(_BALANCES)
            texts.append(body["text"])
    # conftest pins the plain persona, which strips bold; the stored note carries it.
    assert _BALANCE_TABLE_NOTE.startswith("**봉투별 남은 잔액은 아래 표에 정리했어요.**")
    for text in texts:
        assert text.startswith("봉투별 남은 잔액은 아래 표에 정리했어요.")
        assert f"봉투 잔액 합계는 {sum(_BALANCES.values()):,}원이에요." in text
        assert "예측 구간" not in text
        assert "외식 지출이 예산을 가장 많이 넘었고" in text
        assert "경로 수와 분위수" not in text
