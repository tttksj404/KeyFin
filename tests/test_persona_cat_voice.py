# ruff: noqa: INP001
"""The KeyFin coach speaks as a cat (~다냥); suggestion sentences are bold (**…**)."""

from pathlib import Path

import httpx2
import pytest
from test_api import TOKEN, TestModel, event, setup
from test_engine import fixture
from test_multiturn_clarification_context import RouteTo

from coaching_service.llm_prompt import wording_problem
from coaching_service.persona import cat_voice, present, strip_bold


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.parametrize(
    ("plain", "cat"),
    [
        ("소비는 139,600원, 4건입니다.", "소비는 139,600원, 4건이다냥."),
        ("합계와 다를 수 있어요.", "합계와 다를 수 있다냥."),
        ("아래 표에 정리했어요. 장부 잔액이에요.", "아래 표에 정리했다냥. 장부 잔액이다냥."),
        ("현금은 부족해지지 않아요.", "현금은 부족해지지 않는다냥."),
        ("0원으로 계산하지 않습니다.", "0원으로 계산하지 않는다냥."),
        ("확인되지 않았습니다.", "확인되지 않았다냥."),
        ("지출 계획이 있으면 알려 주세요.", "지출 계획이 있으면 알려 달라냥."),
        ("영향을 확인해 드릴게요.", "영향을 확인해 주겠다냥."),
        ("외식 소비를 줄이세요.", "외식 소비를 줄이라냥."),
        ("예산 안에 들어와 괜찮아요.", "예산 안에 들어와 괜찮다냥."),
        ("이번 달 외식 예산 괜찮을까요?", "이번 달 외식 예산 괜찮을까냥?"),
        # A bracketed note after the verb keeps its figures and gets no voice itself.
        ("잔액이 모자랄 수 있어요(예측한 경우 중 100%).", "잔액이 모자랄 수 있다냥(예측한 경우 중 100%)."),
        # Bold suggestion marks survive and the sentence inside them is voiced.
        ("**남는 만큼은 저축으로 옮겨 두면 좋아요.**", "**남는 만큼은 저축으로 옮겨 두면 좋다냥.**"),
        # Review D1: adjective 하다, ㅂ니다 verbs/adjectives, action verbs, contractions.
        ("공식 자료가 필요합니다.", "공식 자료가 필요하다냥."),
        ("관측값을 구분합니다.", "관측값을 구분한다냥."),
        ("안전 보장이 아닙니다.", "안전 보장이 아니다냥."),
        ("결과가 달라집니다.", "결과가 달라진다냥."),
        ("기준이 다릅니다.", "기준이 다르다냥."),
        ("더 크게 움직입니다.", "더 크게 움직인다냥."),
        ("이자가 붙습니다.", "이자가 붙는다냥."),
        ("예산이 거의 다 찼어요.", "예산이 거의 다 찼다냥."),
        ("적용하기 어려워요.", "적용하기 어렵다냥."),
        ("두 가지로 읽혀요.", "두 가지로 읽힌다냥."),
        # Re-review: 우-verbs contract to 워요 too, but are verbs, not ㅂ-adjectives.
        ("비상금을 채워요.", "비상금을 채운다냥."),
        ("계획을 세워요.", "계획을 세운다냥."),
        # Line ends without punctuation and noun-only fragments.
        ("예산 안에 들어와 괜찮아요\n부족 예측 없음.", "예산 안에 들어와 괜찮다냥\n부족 예측 없음."),
    ],
)
def test_cat_voice_rewrites_only_sentence_endings(plain: str, cat: str) -> None:
    assert cat_voice(plain) == cat


def test_cat_voice_is_idempotent_and_keeps_every_number() -> None:
    text = (
        "자료 기준일은 2026-09-23 마감입니다. 예측 구간은 2026-09-24부터 7일입니다.\n"
        "구매 후 기간 말 현금은 보통 5,281,220원으로 예상돼요. **큰 지출은 미루는 편이 좋아요.**"
    )
    voiced = cat_voice(text)
    assert cat_voice(voiced) == voiced
    digits = [c for c in text if c.isdigit() or c in ",-."]
    assert [c for c in voiced if c.isdigit() or c in ",-."] == digits


def test_present_keeps_bold_only_for_the_cat_app_surface() -> None:
    text = "여유가 있어요. **옮겨 두면 좋아요.**"
    assert present(text, "cat") == "여유가 있다냥. **옮겨 두면 좋다냥.**"
    assert present(text, "cat", bold=False) == "여유가 있다냥. 옮겨 두면 좋다냥."
    assert present(text, "plain") == strip_bold(text) == "여유가 있어요. 옮겨 두면 좋아요."


@pytest.mark.anyio
async def test_api_speaks_as_a_cat_and_keeps_bold_suggestions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("COACHING_PERSONA", "cat")
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=setup(tmp_path / "cat.sqlite3", RouteTo("review"))),
        base_url="http://test", headers={"Authorization": "Bearer " + TOKEN},
    ) as client:
        assert (
            await client.post(
                "/v1/twin", json=fixture().model_dump(mode="json"), headers={"Idempotency-Key": "t"}
            )
        ).status_code == 200
        session = (await client.post("/v1/sessions", json={}, headers={"Idempotency-Key": "s"})).json()["id"]
        reply = await client.post(
            f"/v1/sessions/{session}/messages",
            json={"question": "노트북 30만원 현금으로 이번주에 사도될까"},
            headers={"Idempotency-Key": "q"},
        )
        assert reply.status_code == 200, reply.text
        text = reply.json()["text"]
        assert "입니다." not in text
        assert "다냥" in text
        assert "**" in text  # the budget-headroom suggestion is marked bold
        # The stored history is voiced the same way as the live answer.
        history = (await client.get(f"/v1/sessions/{session}")).json()
        assert history["messages"][-1]["content"] == text
        # A retried turn replays the same voiced text.
        again = await client.post(
            f"/v1/sessions/{session}/messages",
            json={"question": "노트북 30만원 현금으로 이번주에 사도될까"},
            headers={"Idempotency-Key": "q"},
        )
        assert again.json()["text"] == text


def test_model_wording_guard_rejects_any_asterisk() -> None:
    # Review D4: bold marks come only from the server renderer.
    assert wording_problem("**지출 계획을 알려 주세요.") is not None
    assert wording_problem("지출 계획을 알려 주세요.") is None


@pytest.mark.anyio
async def test_event_coaching_is_voiced_like_the_stored_read_and_push_has_no_bold(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Review D2: POST /v1/events returned the neutral text with raw "**".
    monkeypatch.setenv("COACHING_PERSONA", "cat")
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=setup(tmp_path / "event.sqlite3", TestModel())),
        base_url="http://test", headers={"Authorization": "Bearer " + TOKEN},
    ) as client:
        assert (
            await client.post(
                "/v1/twin", json=fixture().model_dump(mode="json"), headers={"Idempotency-Key": "t"}
            )
        ).status_code == 200
        applied = await client.post("/v1/events", json=event(), headers={"Idempotency-Key": "pay"})
        assert applied.status_code == 200, applied.text
        coaching = applied.json()["coaching"]
        stored = (await client.get(f"/v1/coaching/{coaching['id']}")).json()
        assert coaching["text"] == stored["text"]
        assert "다냥" in coaching["text"]
        pushes = (await client.get("/v1/notifications")).json()["items"]
        assert all("**" not in item["text"] for item in pushes)
