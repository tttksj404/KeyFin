# ruff: noqa: INP001
"""Period regressions against the actual pinned FDT and service orchestration."""

from pathlib import Path

import httpx2
import pytest
from test_api import TOKEN, TestModel, setup
from test_engine import fixture

from coaching_service.llm_contract import EvidenceInput, Routing
from coaching_service.schemas import JsonDocument


class ForecastModel(TestModel):
    async def route(self, evidence: EvidenceInput) -> Routing:
        self.routes += 1
        self.seen.append(evidence)
        return Routing(mode="forecast", source="llm")


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("question", "days", "end"),
    [
        ("30일 뒤 잔액을 예측해 줘", 30, "2026-10-09"),
        ("이번 달 말까지 예측해 줘", 21, "2026-09-30"),
        # The service fixture is observed through 2026-09-09, so Oct 31 is 52 future days away.
        ("다음 달 잔액을 예측해 줘", 52, "2026-10-31"),
        ("2026-12-08까지 예측해 줘", 90, "2026-12-08"),
    ],
)
async def test_question_period_reaches_real_engine(
    tmp_path: Path, question: str, days: int, end: str
) -> None:
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=setup(tmp_path / "period.sqlite3", ForecastModel())),
        base_url="http://test",
        headers={"Authorization": "Bearer " + TOKEN},
    ) as client:
        initialized = await client.post(
            "/v1/twin", json=fixture().model_dump(mode="json"), headers={"Idempotency-Key": "init"}
        )
        assert initialized.status_code == 200
        reviewed = await client.post(
            "/v1/coaching/reviews",
            json={"on_date": "2026-09-09", "through_date": "2026-09-16", "paths": 20},
            headers={"Idempotency-Key": "review"},
        )
        assert reviewed.status_code == 200, reviewed.text
        session = await client.post(
            "/v1/sessions",
            json={"coaching_id": reviewed.json()["id"]},
            headers={"Idempotency-Key": "session"},
        )
        response = await client.post(
            f"/v1/sessions/{session.json()['id']}/messages",
            json={"question": question},
            headers={"Idempotency-Key": "turn"},
        )
        assert response.status_code == 200, response.text
        receipt = response.json()["receipt"]
        assert receipt["numeric_request"]["horizon_days"] == days
        assert receipt["request"]["on_date"] == "2026-09-09"
        assert receipt["request"]["through_date"] == end
        projection = receipt["numeric_result"]["datasets"]["projection"]
        assert len(projection) == days + 1
        assert projection[0]["date"] == "2026-09-09"
        assert projection[1]["date"] == "2026-09-10"
        assert projection[-1]["date"] == end
        assert response.json()["fallback_reason"] is None


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("body", "error"),
    [
        (JsonDocument({"question": "한 달 뒤 예측"}), "period_clarification_required"),
        (
            JsonDocument({"question": "30일 뒤 예측", "analysis": {"mode": "forecast", "horizon_days": 7}}),
            "period_conflict",
        ),
        (JsonDocument({"question": "2026-09-09까지 예측"}), "period_has_no_future_days"),
        (JsonDocument({"question": "2026-09-08까지 예측"}), "period_ends_before_reference"),
    ],
)
async def test_invalid_forecast_period_is_rejected_after_intent_before_writer_or_session_mutation(
    tmp_path: Path, body: JsonDocument, error: str
) -> None:
    model = ForecastModel()
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=setup(tmp_path / "invalid-period.sqlite3", model)),
        base_url="http://test",
        headers={"Authorization": "Bearer " + TOKEN},
    ) as client:
        assert (
            await client.post(
                "/v1/twin", json=fixture().model_dump(mode="json"), headers={"Idempotency-Key": "init"}
            )
        ).status_code == 200
        reviewed = await client.post(
            "/v1/coaching/reviews",
            json={"on_date": "2026-09-09", "through_date": "2026-09-16"},
            headers={"Idempotency-Key": "review"},
        )
        assert reviewed.status_code == 200
        session = await client.post(
            "/v1/sessions",
            json={"coaching_id": reviewed.json()["id"]},
            headers={"Idempotency-Key": "session"},
        )
        path = f"/v1/sessions/{session.json()['id']}"
        seen_before = (model.writes, model.routes, model.judgments)
        result = await client.post(path + "/messages", json=body.root, headers={"Idempotency-Key": "invalid"})
        assert result.status_code == 422
        assert error in result.text
        # Natural-language requests still route before period parsing; structured forecast
        # already supplies its intent. Neither path may generate or save an invalid period.
        assert (model.writes, model.routes, model.judgments) == (
            seen_before[0],
            seen_before[1] + (0 if "analysis" in body.root else 1),
            seen_before[2],
        )
        assert (await client.get(path)).json() == session.json()
