"""Single-user latency paths must avoid an unnecessary model route and FDT call."""

# ruff: noqa: INP001
from __future__ import annotations

from typing import TYPE_CHECKING, Final

import anyio
import httpx2
import pytest
from fastapi import FastAPI
from pydantic import SecretStr
from typing_extensions import override

from benchmarks.coaching.e2e.e2e_runtime import serve
from coaching_service.api import create_app
from coaching_service.fast_routes import (
    deterministic_analysis_route,
    deterministic_lookup_route,
    natural_goal,
    natural_what_if,
    stored_coaching_followup,
)
from coaching_service.finance_knowledge import finance_evidence, model_selected_finance_evidence
from coaching_service.llm import OpenAICompatibleCoachModel
from coaching_service.llm_contract import EvidenceInput, ModelConfig, Routing, Wording
from coaching_service.request_timing import RequestTiming, measure_fdt, run_measured_fdt
from coaching_service.schemas import JsonDocument, Session
from coaching_service.settings import Client, Settings
from tests.test_api import TestModel, event
from tests.test_engine import fixture

if TYPE_CHECKING:
    from pathlib import Path

TOKEN: Final = "test-only-interactive-latency-token-000000000000"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def completion(content: str) -> httpx2.Response:
    return httpx2.Response(200, json={"choices": [{
        "message": {"content": content}, "finish_reason": "stop",
    }]})


async def session_id(client: httpx2.AsyncClient) -> str:
    response = await client.post("/v1/sessions", json={}, headers={"Idempotency-Key": "session"})
    assert response.status_code == 200, response.text
    return Session.model_validate_json(response.content).id


@pytest.mark.anyio
async def test_general_finance_question_uses_one_short_fact_selection_without_a_twin(tmp_path: Path) -> None:
    """A general concept must not first wait for a route, then fail on a missing Twin."""
    calls: list[object] = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        payload = JsonDocument.model_validate_json(request.content).root
        assert isinstance(payload, dict)
        calls.append(payload)
        response_format = payload["response_format"]
        assert isinstance(response_format, dict)
        json_schema = response_format["json_schema"]
        assert isinstance(json_schema, dict)
        assert json_schema["name"] == "finance_facts"
        # Fact selection has a bounded JSON response; it never needs the generic writer ceiling.
        assert payload["max_tokens"] == 96
        return completion('{"status":"answered","fact_ids":["deposits"],"missing":[]}')

    config = ModelConfig(endpoint_url="http://model.test", token_preflight=False)
    async with httpx2.AsyncClient(transport=httpx2.MockTransport(respond)) as model_client:
        app = create_app(Settings(
            database=tmp_path / "one-call.sqlite3",
            clients=(Client(user_id="demo", token=SecretStr(TOKEN)),),
        ), OpenAICompatibleCoachModel(config, client=model_client))
        async with httpx2.AsyncClient(
            transport=httpx2.ASGITransport(app=app), base_url="http://test",
            headers={"Authorization": "Bearer " + TOKEN},
        ) as client:
            response = await client.post(
                f"/v1/sessions/{await session_id(client)}/messages",
                json={"question": "1년 만기 예금과 적금 차이가 뭐야?"},
                headers={"Idempotency-Key": "one-call"},
            )

    assert response.status_code == 200, response.text
    answer = JsonDocument.model_validate_json(response.content).root
    assert isinstance(answer, dict)
    assert answer["answer_type"] == "finance_education"
    assert answer["status"] == "answered"
    assert answer["wording_source"] == "llm"
    assert len(calls) == 1


@pytest.mark.anyio
async def test_catalog_backed_narrative_question_uses_pinned_wording_without_model_generation(
    tmp_path: Path,
) -> None:
    """A fully explicit stable fact is safer and faster when rendered from the pinned catalog."""
    operations: list[str] = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        payload = JsonDocument.model_validate_json(request.content).root
        assert isinstance(payload, dict)
        response_format = payload["response_format"]
        assert isinstance(response_format, dict)
        schema = response_format["json_schema"]
        assert isinstance(schema, dict)
        name = schema["name"]
        assert isinstance(name, str)
        operations.append(name)
        match name:
            case "route":
                return completion('{"mode":"finance"}')
            case "finance_facts":
                return completion('{"status":"answered","fact_ids":["bonds"],"missing":[]}')
            case _:
                raise AssertionError("unexpected model operation")

    config = ModelConfig(endpoint_url="http://model.test", token_preflight=False)
    async with httpx2.AsyncClient(transport=httpx2.MockTransport(respond)) as model_client:
        app = create_app(Settings(
            database=tmp_path / "narrative-one-call.sqlite3",
            clients=(Client(user_id="demo", token=SecretStr(TOKEN)),),
        ), OpenAICompatibleCoachModel(config, client=model_client))
        async with httpx2.AsyncClient(
            transport=httpx2.ASGITransport(app=app), base_url="http://test",
            headers={"Authorization": "Bearer " + TOKEN},
        ) as client:
            response = await client.post(
                f"/v1/sessions/{await session_id(client)}/messages",
                json={"question": "채권을 산다는 건 발행자에게 돈을 빌려주고 돌려받을 권리를 갖는 거야?"},
                headers={"Idempotency-Key": "narrative-one-call"},
            )

    assert response.status_code == 200, response.text
    assert response.json()["answer_type"] == "finance_education"
    assert response.json()["status"] == "answered"
    assert response.json()["wording_source"] == "template"
    assert operations == []


@pytest.mark.anyio
async def test_structured_analysis_never_enters_the_general_finance_shortcut(tmp_path: Path) -> None:
    """Goal/what-if/optimization payloads bypass routing and retain numeric intent."""
    operations: list[str] = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        payload = JsonDocument.model_validate_json(request.content).root
        assert isinstance(payload, dict)
        response_format = payload.get("response_format")
        if isinstance(response_format, dict):
            schema = response_format["json_schema"]
            assert isinstance(schema, dict)
            name = schema["name"]
            assert isinstance(name, str)
            operations.append(name)
            assert name == "route"
            return completion('{"mode":"review"}')
        operations.append("write")
        return completion("추가로 확인할 자료를 알려 주세요.")

    config = ModelConfig(endpoint_url="http://model.test", token_preflight=False)
    async with httpx2.AsyncClient(transport=httpx2.MockTransport(respond)) as model_client:
        app = create_app(Settings(
            database=tmp_path / "analysis.sqlite3",
            clients=(Client(user_id="demo", token=SecretStr(TOKEN)),),
        ), OpenAICompatibleCoachModel(config, client=model_client))
        async with httpx2.AsyncClient(
            transport=httpx2.ASGITransport(app=app), base_url="http://test",
            headers={"Authorization": "Bearer " + TOKEN},
        ) as client:
            bootstrapped = await client.post(
                "/v1/twin", json=fixture().model_dump(mode="json"), headers={"Idempotency-Key": "bootstrap"}
            )
            assert bootstrapped.status_code == 200, bootstrapped.text
            response = await client.post(
                f"/v1/sessions/{await session_id(client)}/messages",
                json={
                    "question": (
                        "앞으로 7일 잔액 예측도 보되 후보 계산은 읽고 실제 예산은 바꾸지 "
                        "말고 필요한 정보를 알려줘."
                    ),
                    "analysis": {
                        "mode": "optimize",
                        "horizon_days": 7,
                        "paths": 20,
                        "seed": 42,
                        "optimization": {"envelopes": ["기타"], "reduction_grid": [0, 0.1]},
                    },
                },
                headers={"Idempotency-Key": "optimize"},
            )

    assert response.status_code == 200, response.text
    assert response.json()["wording_source"] == "template"
    assert response.json()["model"] == "not_called"
    assert operations == []


@pytest.mark.parametrize("question", [
    "내 DSR은 얼마야?",
    "이번 달 내 지출은 얼마야?",
    "DSR이 뭐야? 그리고 앞으로 내 잔액도 예측해줘.",
    "DSR이 40%면 대출을 얼마나 받을 수 있어?",
    "현재 DSR 규정과 한도는 어떻게 돼?",
    "ETF와 채권 중 무엇을 사야 해?",
    "우리은행 계좌 잔액만 알려줘.",
    "월 고정비 합계 보여줘.",
])
def test_one_call_finance_selection_rejects_personal_history_and_forecast_requests(question: str) -> None:
    """Only a clearly general knowledge request may skip the model route decision."""
    assert model_selected_finance_evidence(finance_evidence(question)) is None


@pytest.mark.parametrize(("question", "mode"), [
    ("앞으로 7일 잔액 예측해줘", "forecast"),
    ("이번 달 말까지 남을 현금을 예측해줘", "forecast"),
    ("이번 달 말에 내 잔액은 얼마 남을까?", "forecast"),
    ("위험 한마디보다 다음 급여 전까지 잔액이 변하는 흐름을 보여 줘.", "forecast"),
    ("다음 달 계좌 잔고의 변화 경로를 보고 싶어.", "forecast"),
    ("이번 달 위험을 알려줘", "risk"),
    ("필수 생활비가 부족해질 위험을 따로 점검하고 싶어요.", "risk"),
    ("다음 달 잔액이 부족할까?", "risk"),
    ("내 소비 습관을 점검해줘", "review"),
    ("내 지출을 분석해줘", "review"),
    # 라이브 2026-09-23: 모델이 "예산 위험해?"를 매번 일반 리뷰로 보내 위험 수치가 빠졌다.
    # 개인 코칭에서 "예산 위험"은 사용자 자신의 예산이므로 결정적 risk 로 보낸다.
    ("예산 위험 알려줘", "risk"),
    ("이번 달 지출은 얼마야?", None),
    ("다음 달 예산 부족을 막는 방법은 뭐야?", None),
    ("유동성 위험이 뭐야?", None),
    ("향후 금리는 어떻게 예측해?", None),
    ("소비 습관을 점검하는 방법이 뭐야?", None),
    ("내년 소비를 분석해줘", None),
])
def test_deterministic_analysis_route_only_accepts_clear_personal_fdt_language(
    question: str, mode: str | None,
) -> None:
    assert deterministic_analysis_route(question) == mode


@pytest.mark.parametrize(("question", "route"), [
    ("내 계좌 잔액은 얼마야?", "personal"),
    ("내 자산 알려줘", "personal"),
    ("현재까지 소비 알려줘", "history"),
    ("지난달 외식비 얼마 썼어?", "history"),
    ("내 계좌 잔액과 자산을 비교해줘", None),
    ("이번 달 카드 사용액 알려줘", None),
    ("내 계좌 잔액을 다음 달까지 예측해줘", None),
])
def test_deterministic_lookup_route_reuses_only_existing_complete_grammars(
    question: str, route: str | None,
) -> None:
    """Personal and historical speed paths cannot broaden the underlying query contract."""
    assert deterministic_lookup_route(question) == route


@pytest.mark.parametrize(("question", "target_krw"), [
    ("이번 달 말까지 100만원을 모을 수 있을까?", 1_000_000),
    ("다음 달 말까지 50만 원 목표를 달성할 수 있을까요?", 500_000),
    ("2026-10-31까지 1,200,000원을 저축할 수 있을까?", 1_200_000),
])
def test_natural_goal_requires_one_explicit_amount_and_feasibility(
    question: str, target_krw: int,
) -> None:
    parsed = natural_goal(question)

    assert parsed is not None
    assert parsed.target_krw == target_krw


@pytest.mark.parametrize("question", [
    "이번 달 말까지 100만원 또는 200만원을 모으는 방법은 뭐야?",
    "다음 달에 100만원 목표를 세워줘.",
    "앞으로 30일에 100만원을 어디에 투자할까?",
    "100만원을 모을 수 있을까?",
    "이번 달 말까지 백만원을 모을 수 있을까?",
])
def test_natural_goal_rejects_ambiguous_or_advisory_language(question: str) -> None:
    assert natural_goal(question) is None


@pytest.mark.parametrize(("question", "scenario"), [
    ("이번 달 외식비를 20% 줄이면 어떻게 될까?", {"expense_reductions": {"외식": 0.2}}),
    # 일상어 "식비"도 엔진 매핑(식비→외식)대로 외식 봉투 절감으로 접힌다.
    ("이번 달 식비를 20% 줄이면 어떻게 될까?", {"expense_reductions": {"외식": 0.2}}),
    ("다음 달 변동 지출을 10% 줄이면 잔액이 어떻게 달라져?", {"expense_multiplier": 0.9}),
    ("외식비를 20% 줄이면 어떻게 될까?", {"expense_reductions": {"외식": 0.2}}),
])
def test_natural_what_if_requires_one_explicit_variable_expense_branch(
    question: str, scenario: dict[str, object],
) -> None:
    parsed = natural_what_if(question)

    assert parsed is not None
    assert parsed.scenario() == scenario


@pytest.mark.parametrize("question", [
    "이번 달 외식비와 쇼핑비를 20% 줄이면 어떻게 될까?",
    "이번 달 외식비를 20% 줄이는 방법 알려줘.",
    "이번 달 고정비를 20% 줄이면 어떻게 될까?",
    # A cut that already happened, a how-to, or a week cannot be an FDT branch. A cut with
    # no period at all is this budget cycle's, like every other period-less turn.
    "지난달 외식비를 20% 줄였더니 얼마나 아꼈어?",
    "외식비를 20% 줄이려면 어떻게 해야 돼?",
    "다음 주 외식비를 20% 줄이면 어떻게 될까?",
    "이번 달 외식비를 20% 줄이고 30% 더 줄이면 어떻게 될까?",
    "이번 달 외식비를 100% 줄이면 어떻게 될까?",
    "이번 달 외식비를 20% 줄여서 10만원이 되면 어떻게 될까?",
])
def test_natural_what_if_rejects_ambiguous_or_out_of_scope_changes(question: str) -> None:
    assert natural_what_if(question) is None


@pytest.mark.parametrize(("question", "expected"), [
    ("이 코칭이 나온 이유를 확인하고 싶어요.", True),
    ("결제를 취소했어요. 현재 봉투 잔액은 얼마인가요?", True),
    ("이 코칭의 예측은 앞으로 어떻게 변하나요?", False),
    ("왜 이 코칭이 나왔고 위험은 뭐야?", False),
    ("현재 봉투 잔액을 예측해줘", False),
    ("봉투 잔액이 무엇인가요?", False),
])
def test_stored_coaching_followup_stays_narrow(question: str, expected: bool) -> None:
    """Only an existing coaching session may use this helper's zero-inference response."""
    assert stored_coaching_followup(question) is expected


@pytest.mark.anyio
@pytest.mark.parametrize("question", [
    "앞으로 7일 잔액 예측해줘",
    "이번 달 말에 내 잔액은 얼마 남을까?",
    "이번 달 위험을 알려줘",
    "다음 달 잔액이 부족할까?",
    "내 소비 습관을 점검해줘",
])
async def test_clear_natural_fdt_question_skips_model_routing(tmp_path: Path, question: str) -> None:
    """Clear personal FDT wording must skip both model routing and supplementary wording."""

    class RouteMustNotRun(TestModel):
        @override
        async def route(self, evidence: EvidenceInput) -> Routing:
            del evidence
            raise AssertionError("clear FDT language must not wait for model routing")

    model = RouteMustNotRun()
    app = create_app(Settings(
        database=tmp_path / "natural-fdt.sqlite3",
        clients=(Client(user_id="demo", token=SecretStr(TOKEN)),),
    ), model)
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=app), base_url="http://test",
        headers={"Authorization": "Bearer " + TOKEN},
    ) as client:
        bootstrapped = await client.post(
            "/v1/twin", json=fixture().model_dump(mode="json"), headers={"Idempotency-Key": "bootstrap"}
        )
        assert bootstrapped.status_code == 200, bootstrapped.text
        response = await client.post(
            f"/v1/sessions/{await session_id(client)}/messages",
            json={"question": question},
            headers={"Idempotency-Key": "natural"},
        )

    assert response.status_code == 200, response.text
    assert response.json()["wording_source"] == "template"
    assert response.json()["model"] == "not_called"
    assert model.routes == 0
    assert model.writes == 0


@pytest.mark.anyio
@pytest.mark.parametrize(("question", "answer_type"), [
    ("내 계좌 잔액은 얼마야?", "personal_context"),
    ("현재까지 소비 알려줘", "spending_history"),
])
async def test_clear_lookup_question_uses_existing_engine_handler_without_model(
    tmp_path: Path, question: str, answer_type: str,
) -> None:
    """The exact existing lookup parser must be the authority for a model-free turn."""

    class ModelMustNotRun(TestModel):
        @override
        async def route(self, evidence: EvidenceInput) -> Routing:
            del evidence
            raise AssertionError("complete lookup grammar must not wait for model routing")

        @override
        async def write(self, evidence: EvidenceInput) -> Wording:
            del evidence
            raise AssertionError("complete lookup grammar must not invoke model wording")

    model = ModelMustNotRun()
    app = create_app(Settings(
        database=tmp_path / f"lookup-{answer_type}.sqlite3",
        clients=(Client(user_id="demo", token=SecretStr(TOKEN)),),
    ), model)
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=app), base_url="http://test",
        headers={"Authorization": "Bearer " + TOKEN},
    ) as client:
        bootstrapped = await client.post(
            "/v1/twin", json=fixture().model_dump(mode="json"), headers={"Idempotency-Key": "bootstrap"}
        )
        assert bootstrapped.status_code == 200, bootstrapped.text
        response = await client.post(
            f"/v1/sessions/{await session_id(client)}/messages",
            json={"question": question},
            headers={"Idempotency-Key": f"lookup-{answer_type}"},
        )

    assert response.status_code == 200, response.text
    assert response.json()["answer_type"] == answer_type
    assert response.json()["wording_source"] == "engine"
    assert response.json()["model"] == "not_called"
    assert model.routes == 0
    assert model.writes == 0


@pytest.mark.anyio
@pytest.mark.parametrize(("question", "target_krw", "forecast_days"), [
    ("이번 달 말까지 100만원을 모을 수 있을까?", 1_000_000, 21),
    # The fixture is observed through 2026-09-09, so Oct. 31 is 52 future days away.
    ("다음 달 말까지 50만 원 목표를 달성할 수 있을까요?", 500_000, 52),
])
async def test_clear_natural_goal_uses_typed_goal_fdt_without_model_routing(
    tmp_path: Path, question: str, target_krw: int, forecast_days: int,
) -> None:
    """Natural goal questions preserve the amount and calendar period in the FDT receipt."""

    class RouteMustNotRun(TestModel):
        @override
        async def route(self, evidence: EvidenceInput) -> Routing:
            del evidence
            raise AssertionError("clear goal feasibility must not wait for model routing")

    model = RouteMustNotRun()
    app = create_app(Settings(
        database=tmp_path / "natural-goal.sqlite3",
        clients=(Client(user_id="demo", token=SecretStr(TOKEN)),),
    ), model)
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=app), base_url="http://test",
        headers={"Authorization": "Bearer " + TOKEN},
    ) as client:
        bootstrapped = await client.post(
            "/v1/twin", json=fixture().model_dump(mode="json"), headers={"Idempotency-Key": "bootstrap"}
        )
        assert bootstrapped.status_code == 200, bootstrapped.text
        response = await client.post(
            f"/v1/sessions/{await session_id(client)}/messages",
            json={"question": question},
            headers={"Idempotency-Key": "natural-goal"},
        )

    assert response.status_code == 200, response.text
    answer = response.json()
    assert answer["wording_source"] == "template"
    assert answer["model"] == "not_called"
    assert answer["receipt"]["numeric_request"] == {
        "mode": "goal",
        "horizon_days": forecast_days,
        "paths": 400,
        "seed": 42,
        "goal": {"target_krw": target_krw},
    }
    assert answer["receipt"]["numeric_result"]["mode"] == "goal"
    assert model.routes == 0
    assert model.writes == 0


@pytest.mark.anyio
@pytest.mark.parametrize(("question", "scenario"), [
    ("이번 달 외식비를 20% 줄이면 어떻게 될까?", {"expense_reductions": {"외식": 0.2}}),
    ("다음 달 변동 지출을 10% 줄이면 잔액이 어떻게 달라져?", {"expense_multiplier": 0.9}),
])
async def test_clear_natural_what_if_uses_typed_paired_fdt_without_model_routing(
    tmp_path: Path, question: str, scenario: dict[str, object],
) -> None:
    """A clear one-rate branch preserves its scenario and calendar in the receipt."""

    class RouteMustNotRun(TestModel):
        @override
        async def route(self, evidence: EvidenceInput) -> Routing:
            del evidence
            raise AssertionError("clear what-if language must not wait for model routing")

    model = RouteMustNotRun()
    app = create_app(Settings(
        database=tmp_path / "natural-what-if.sqlite3",
        clients=(Client(user_id="demo", token=SecretStr(TOKEN)),),
    ), model)
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=app), base_url="http://test",
        headers={"Authorization": "Bearer " + TOKEN},
    ) as client:
        bootstrapped = await client.post(
            "/v1/twin", json=fixture().model_dump(mode="json"), headers={"Idempotency-Key": "bootstrap"}
        )
        assert bootstrapped.status_code == 200, bootstrapped.text
        response = await client.post(
            f"/v1/sessions/{await session_id(client)}/messages",
            json={"question": question},
            headers={"Idempotency-Key": "natural-what-if"},
        )

    assert response.status_code == 200, response.text
    answer = response.json()
    assert answer["wording_source"] == "template"
    assert answer["model"] == "not_called"
    assert answer["receipt"]["numeric_request"] == {
        "mode": "what_if",
        "horizon_days": 21 if "이번 달" in question else 52,
        "paths": 400,
        "seed": 42,
        "scenario": scenario,
    }
    assert answer["receipt"]["numeric_result"]["mode"] == "what_if"
    assert "가정했어요" in answer["text"]
    assert model.routes == 0
    assert model.writes == 0


def timing_application() -> FastAPI:
    app = FastAPI()
    app.add_middleware(RequestTiming)

    async def fdt_route() -> dict[str, str]:
        with measure_fdt():
            _ = run_measured_fdt(lambda: "measured")
            await anyio.lowlevel.checkpoint()
        return {"status": "ok"}

    app.add_api_route("/fdt", fdt_route, methods=["GET"])
    return app


@pytest.mark.anyio
async def test_opt_in_trace_reports_fdt_time_without_payload() -> None:
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=timing_application()), base_url="http://test"
    ) as client:
        response = await client.get("/fdt", headers={"X-Coaching-Trace": "1"})

    assert response.status_code == 200
    timing = response.headers["server-timing"]
    assert "api;dur=" in timing
    assert "fdt;dur=" in timing
    assert "fdt_compute;dur=" in timing
    assert "fdt_wait;dur=" in timing
    assert "status" not in timing


@pytest.mark.anyio
async def test_real_forecast_turn_adds_fdt_time_to_the_opt_in_trace(tmp_path: Path) -> None:
    """The diagnostic header must cover the same FDT adapter used by a chat forecast."""
    app = create_app(Settings(
        database=tmp_path / "traced-forecast.sqlite3",
        clients=(Client(user_id="demo", token=SecretStr(TOKEN)),),
    ), TestModel())
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=app), base_url="http://test",
        headers={"Authorization": "Bearer " + TOKEN},
    ) as client:
        bootstrapped = await client.post(
            "/v1/twin", json=fixture().model_dump(mode="json"), headers={"Idempotency-Key": "bootstrap"}
        )
        assert bootstrapped.status_code == 200, bootstrapped.text
        response = await client.post(
            f"/v1/sessions/{await session_id(client)}/messages",
            json={
                "question": "앞으로 7일 잔액 예측해줘",
                "analysis": {"mode": "forecast", "horizon_days": 7, "paths": 20, "seed": 42},
            },
            headers={"Idempotency-Key": "forecast", "X-Coaching-Trace": "1"},
        )

    assert response.status_code == 200, response.text
    assert "fdt;dur=" in response.headers["server-timing"]
    assert "fdt_compute;dur=" in response.headers["server-timing"]
    assert "fdt_wait;dur=" in response.headers["server-timing"]
    assert "model;dur=" not in response.headers["server-timing"]


@pytest.mark.anyio
async def test_tcp_historical_coaching_followup_has_no_fdt_or_model_phase(tmp_path: Path) -> None:
    """An existing-coaching explanation is served from stored facts over real TCP.

    The setup deliberately creates one P0 coaching first. The measured follow-up
    itself must neither launch a new FDT request nor call a model phase.
    """
    model = TestModel()
    app = create_app(Settings(
        database=tmp_path / "traced-historical-followup.sqlite3",
        clients=(Client(user_id="demo", token=SecretStr(TOKEN)),),
    ), model)
    headers = {"Authorization": "Bearer " + TOKEN}
    async with serve(app) as base, httpx2.AsyncClient(trust_env=False) as client:
        created = await client.post(
            base + "/v1/twin", json=fixture().model_dump(mode="json"),
            headers={**headers, "Idempotency-Key": "bootstrap"},
        )
        assert created.status_code == 200, created.text
        delivered = await client.post(
            base + "/v1/events", json=event(), headers={**headers, "Idempotency-Key": "payment"}
        )
        assert delivered.status_code == 200, delivered.text
        coaching_id = delivered.json()["coaching"]["id"]
        session = await client.post(
            base + "/v1/sessions", json={"coaching_id": coaching_id},
            headers={**headers, "Idempotency-Key": "session"},
        )
        assert session.status_code == 200, session.text
        before = (model.routes, model.writes, model.judgments)
        response = await client.post(
            base + f"/v1/sessions/{session.json()['id']}/messages",
            json={"question": "이 코칭이 나온 이유를 확인하고 싶어요."},
            headers={**headers, "Idempotency-Key": "followup", "X-Coaching-Trace": "1"},
        )

    assert response.status_code == 200, response.text
    assert response.json()["receipt"]["trigger"] == "historical_coaching_followup"
    assert response.json()["model"] == "not_called"
    assert response.json()["wording_source"] == "template"
    assert (model.routes, model.writes, model.judgments) == before
    timing = response.headers["server-timing"]
    assert "api;dur=" in timing
    assert "fdt;dur=" not in timing
    assert "model;dur=" not in timing


@pytest.mark.anyio
async def test_tcp_stable_finance_narrative_has_no_fdt_or_model_phase(tmp_path: Path) -> None:
    """A complete pinned education answer reaches the real HTTP API without inference.

    This is deliberately a normal, non-definition Korean question.  It proves that
    the expanded high-precision shortcut is observable at the same network boundary
    as the app, rather than only through an in-process helper test.
    """
    calls = 0

    def unexpected_model_call(_: httpx2.Request) -> httpx2.Response:
        nonlocal calls
        calls += 1
        raise AssertionError("a pinned catalog narrative must not call the model")

    config = ModelConfig(endpoint_url="http://model.test", token_preflight=False)
    async with httpx2.AsyncClient(transport=httpx2.MockTransport(unexpected_model_call)) as model_client:
        app = create_app(Settings(
            database=tmp_path / "traced-catalog-narrative.sqlite3",
            clients=(Client(user_id="demo", token=SecretStr(TOKEN)),),
        ), OpenAICompatibleCoachModel(config, client=model_client))
        headers = {"Authorization": "Bearer " + TOKEN}
        async with serve(app) as base, httpx2.AsyncClient(trust_env=False) as client:
            session = await client.post(
                base + "/v1/sessions", json={}, headers={**headers, "Idempotency-Key": "session"}
            )
            assert session.status_code == 200, session.text
            response = await client.post(
                base + f"/v1/sessions/{session.json()['id']}/messages",
                json={"question": "채권을 산다는 건 발행자에게 돈을 빌려주고 돌려받을 권리를 갖는 거야?"},
                headers={**headers, "Idempotency-Key": "catalog-narrative", "X-Coaching-Trace": "1"},
            )

    assert response.status_code == 200, response.text
    assert response.json()["model"] == "not_called"
    assert response.json()["wording_source"] == "template"
    references = response.json()["evidence"]["references"]
    assert references
    assert references[0]["id"] == "bonds"
    assert calls == 0
    timing = response.headers["server-timing"]
    assert "api;dur=" in timing
    assert "fdt;dur=" not in timing
    assert "model;dur=" not in timing


@pytest.mark.anyio
async def test_tcp_forecast_keeps_fdt_and_model_time_separate_with_default_worker_limit(
    tmp_path: Path,
) -> None:
    """A real HTTP forecast exposes FDT work but never waits for optional wording.

    The explicit setting makes this a wiring regression too: the application must
    pass the bounded FDT worker policy into the same core used by the TCP request.
    """
    model = TestModel()
    app = create_app(Settings(
        database=tmp_path / "traced-forecast-tcp.sqlite3",
        clients=(Client(user_id="demo", token=SecretStr(TOKEN)),),
        fdt_max_concurrency=2,
    ), model)
    headers = {"Authorization": "Bearer " + TOKEN}
    async with serve(app) as base, httpx2.AsyncClient(trust_env=False) as client:
        created = await client.post(
            base + "/v1/twin", json=fixture().model_dump(mode="json"),
            headers={**headers, "Idempotency-Key": "bootstrap"},
        )
        assert created.status_code == 200, created.text
        session = await client.post(
            base + "/v1/sessions", json={}, headers={**headers, "Idempotency-Key": "session"}
        )
        assert session.status_code == 200, session.text
        before = (model.routes, model.writes, model.judgments)
        response = await client.post(
            base + f"/v1/sessions/{session.json()['id']}/messages",
            json={
                "question": "앞으로 7일 잔액 예측해줘",
                "analysis": {"mode": "forecast", "horizon_days": 7, "paths": 20, "seed": 42},
            },
            headers={**headers, "Idempotency-Key": "forecast", "X-Coaching-Trace": "1"},
        )

    assert response.status_code == 200, response.text
    assert response.json()["model"] == "not_called"
    assert (model.routes, model.writes, model.judgments) == before
    timing = response.headers["server-timing"]
    assert "api;dur=" in timing
    assert "fdt;dur=" in timing
    assert "fdt_compute;dur=" in timing
    assert "fdt_wait;dur=" in timing
    assert "model;dur=" not in timing
