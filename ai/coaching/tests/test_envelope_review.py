# ruff: noqa: INP001
"""POST /v1/coaching/envelope-reviews: one envelope's 50·20·5%·over alert evaluation.

Amounts come from the backend ledger (Bootstrap.envelopes) and the snapshot budget,
the period from the configured budget cycle, and the text is plain (no bold marks).
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import httpx2
import pytest
from test_api import TestModel
from test_backend_multitenant import ALPHA_USER_TOKEN, BACKEND_TOKEN, setup
from test_engine import fixture

from coaching_service.schemas import Envelope, JsonDocument


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _twin(
    *, start_day: int = 15, balance: int = 60_000, budget: int = 300_000, as_of: str | None = "2026-09-23"
) -> dict[str, object]:
    base = fixture("alpha")
    snapshot = dict(base.snapshot.root)
    snapshot["budgets"] = {"외식": budget, "기타": 100_000}
    if as_of is not None:
        snapshot["as_of"] = as_of
    twin = base.model_copy(
        update={
            "snapshot": JsonDocument(snapshot),
            "envelopes": (
                Envelope(envelope="외식", balance_krw=balance),
                Envelope(envelope="기타", balance_krw=100_000),
            ),
            "budget_start_day": start_day,
        }
    )
    dumped = twin.model_dump(mode="json")
    if as_of is not None:
        dumped["as_of"] = as_of
    return dumped


@asynccontextmanager
async def _client(tmp_path: Path, twin: dict[str, object] | None = None) -> AsyncIterator[httpx2.AsyncClient]:
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=setup(tmp_path / "env.sqlite3", TestModel())),
        base_url="http://test",
        headers={"Authorization": "Bearer " + BACKEND_TOKEN, "X-Coaching-User": "alpha"},
    ) as client:
        if twin is not None:
            created = await client.post("/v1/twin", json=twin, headers={"Idempotency-Key": "twin"})
            assert created.status_code == 200, created.text
        yield client


async def _review(client: httpx2.AsyncClient, body: dict[str, object], key: str) -> httpx2.Response:
    return await client.post("/v1/coaching/envelope-reviews", json=body, headers={"Idempotency-Key": key})


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("tier", "balance", "expected"),
    [
        ("50", 150_000, "외식 예산이 50% 남았어요. 예산 300,000원 중 150,000원이 남았어요."),
        ("20", 60_000, "남은 기간에는 꼭 필요한 외식 지출 위주로 조절해 보세요."),
        ("5", 15_000, "거의 다 썼으니 10월 14일까지는 외식 지출을 최대한 미루는 편이 좋아요."),
        ("over", -20_000, "외식 예산을 20,000원 넘었어요(예산 300,000원)."),
    ],
)
async def test_tier_text_uses_the_backend_ledger_and_budget_cycle(
    tmp_path: Path, tier: str, balance: int, expected: str
) -> None:
    async with _client(tmp_path, _twin(balance=balance)) as client:
        reply = await _review(client, {"envelope": "외식", "tier": tier, "on_date": "2026-09-23"}, "a1")
    assert reply.status_code == 200, reply.text
    body = reply.json()
    # Numbers are the ledger balance and the snapshot budget, nothing simulated.
    amounts = (body["remaining_krw"], body["budget_krw"], body["used_krw"])
    assert amounts == (balance, 300_000, 300_000 - balance)
    # budget_start_day=15 → cycle 9/15..10/14; 9/23..10/14 inclusive is 22 days.
    assert (body["period_start"], body["period_end"], body["days_left"]) == ("2026-09-15", "2026-10-14", 22)
    assert expected in body["text"]
    assert "**" not in body["text"]
    if balance > 0:
        assert body["daily_allowance_krw"] == balance // 22
        assert f"하루 {balance // 22:,}원" in body["text"]
    else:
        assert body["daily_allowance_krw"] is None


@pytest.mark.anyio
async def test_on_date_defaults_to_the_pushed_twin_date(tmp_path: Path) -> None:
    async with _client(tmp_path, _twin(start_day=1, as_of=None)) as client:
        body = (await _review(client, {"envelope": "외식", "tier": "20"}, "d1")).json()
    assert body["as_of"] == fixture("alpha").snapshot.root["as_of"]
    assert body["period_start"].endswith("-01")


@pytest.mark.anyio
async def test_cat_persona_voices_the_alert_without_bold(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("COACHING_PERSONA", "cat")
    async with _client(tmp_path, _twin()) as client:
        request = {"envelope": "외식", "tier": "20", "on_date": "2026-09-23"}
        body = (await _review(client, request, "c1")).json()
    assert "다냥" in body["text"]
    assert "남았어요" not in body["text"]
    assert "**" not in body["text"]
    assert "60,000원" in body["text"]


@pytest.mark.anyio
async def test_retry_replays_and_a_different_body_conflicts(tmp_path: Path) -> None:
    async with _client(tmp_path, _twin()) as client:
        body = {"envelope": "외식", "tier": "20", "on_date": "2026-09-23"}
        first = await _review(client, body, "alert-42")
        again = await _review(client, body, "alert-42")
        other = await _review(client, {**body, "tier": "5"}, "alert-42")
    assert first.json() == again.json()
    assert other.status_code == 409


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("body", "status", "code"),
    [
        ({"envelope": "커피", "tier": "20"}, 422, "envelope_unknown"),
        ({"envelope": "쇼핑", "tier": "20"}, 422, "envelope_not_in_ledger"),
        ({"envelope": "외식", "tier": "30"}, 422, None),
    ],
)
async def test_invalid_requests_are_rejected(
    tmp_path: Path, body: dict[str, object], status: int, code: str | None
) -> None:
    async with _client(tmp_path, _twin()) as client:
        reply = await _review(client, body, "bad")
    assert reply.status_code == status, reply.text
    if code is not None:
        assert code in reply.text


@pytest.mark.anyio
async def test_missing_budget_and_missing_twin(tmp_path: Path) -> None:
    twin = _twin()
    snapshot = twin["snapshot"]
    assert isinstance(snapshot, dict)
    snapshot["budgets"] = {"기타": 100_000}
    async with _client(tmp_path / "a", twin) as client:
        no_budget = await _review(client, {"envelope": "외식", "tier": "20"}, "nb")
    assert no_budget.status_code == 422
    assert "envelope_budget_missing" in no_budget.text
    async with _client(tmp_path / "b") as client:
        no_twin = await _review(client, {"envelope": "외식", "tier": "20"}, "nt")
    assert no_twin.status_code == 404


@pytest.mark.anyio
async def test_user_tokens_cannot_call_the_backend_alert_endpoint(tmp_path: Path) -> None:
    async with _client(tmp_path, _twin()) as client:
        reply = await client.post(
            "/v1/coaching/envelope-reviews",
            json={"envelope": "외식", "tier": "20"},
            headers={"Authorization": "Bearer " + ALPHA_USER_TOKEN, "Idempotency-Key": "u"},
        )
    assert reply.status_code == 403


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("tier", "balance", "present", "absent"),
    [
        # 알림은 초과인데 장부엔 잔액이 남음: 거짓 "모두 썼어요" 대신 장부 숫자를 말한다.
        ("over", 150_000, "예산 300,000원 중 150,000원이 남았어요.", "모두 썼어요"),
        ("over", 150_000, "꼭 필요한 외식 지출 위주로", "거의 다 썼으니"),
        ("over", 15_000, "거의 다 썼으니", "모두 썼어요"),
        ("over", 0, "외식 예산을 모두 썼어요(예산 300,000원).", "남았어요."),
        ("50", 360_000, "외식 예산 300,000원보다 60,000원 많은 360,000원이 남아 있어요.", "120%"),
        ("5", 1_400, "외식 예산이 1% 미만 남았어요.", "0% 남았어요"),
        ("5", 10, "10원이 남았어요.", "하루 0원"),
    ],
)
async def test_wording_follows_the_ledger_numbers(
    tmp_path: Path, tier: str, balance: int, present: str, absent: str
) -> None:
    async with _client(tmp_path, _twin(balance=balance)) as client:
        request = {"envelope": "외식", "tier": tier, "on_date": "2026-09-23"}
        body = (await _review(client, request, "w")).json()
    assert present in body["text"], body["text"]
    assert absent not in body["text"]
    assert body["used_krw"] >= 0


@pytest.mark.anyio
async def test_integral_float_budget_is_accepted(tmp_path: Path) -> None:
    twin = _twin()
    snapshot = twin["snapshot"]
    assert isinstance(snapshot, dict)
    snapshot["budgets"] = {"외식": 300_000.0, "기타": 100_000}
    async with _client(tmp_path, twin) as client:
        reply = await _review(client, {"envelope": "외식", "tier": "20", "on_date": "2026-09-23"}, "f")
    assert reply.status_code == 200, reply.text
    assert reply.json()["budget_krw"] == 300_000


@pytest.mark.anyio
async def test_on_date_outside_the_pushed_cycle_is_rejected(tmp_path: Path) -> None:
    async with _client(tmp_path, _twin()) as client:
        # push 기준일 9/23은 9/15~10/14 주기, 10/15는 다음 주기라 장부 잔액을 붙일 수 없다.
        reply = await _review(client, {"envelope": "외식", "tier": "20", "on_date": "2026-10-15"}, "o")
        same = await _review(client, {"envelope": "외식", "tier": "20", "on_date": "2026-10-14"}, "o2")
    assert same.status_code == 200, same.text
    assert reply.status_code == 422
    assert "envelope_on_date_out_of_cycle" in reply.text
