"""FDT review answers do not wait for a supplementary language-model sentence."""

# ruff: noqa: INP001
from __future__ import annotations

from typing import TYPE_CHECKING

import httpx2
import pytest

from coaching_service.llm_contract import EvidenceInput, Routing
from coaching_service.schemas import Session
from tests.test_api import TOKEN, TestModel, setup
from tests.test_engine import fixture

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class ReviewRouteModel(TestModel):
    """Route one ambiguous personal question to the real deterministic review."""

    async def route(self, evidence: EvidenceInput) -> Routing:
        self.routes += 1
        self.seen.append(evidence)
        return Routing(mode="review", source="llm")


@pytest.mark.anyio
async def test_fdt_review_returns_before_supplementary_writer_is_called(tmp_path: Path) -> None:
    """A complete review receipt is the authoritative response for an interactive turn."""
    model = ReviewRouteModel()
    app = setup(tmp_path / "review-no-writer.sqlite3", model)
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": "Bearer " + TOKEN},
    ) as client:
        created = await client.post(
            "/v1/twin", json=fixture().model_dump(mode="json"), headers={"Idempotency-Key": "twin"},
        )
        assert created.status_code == 200, created.text
        session_response = await client.post("/v1/sessions", json={}, headers={"Idempotency-Key": "session"})
        session = Session.model_validate_json(session_response.content)

        response = await client.post(
            "/v1/sessions/" + session.id + "/messages",
            json={"question": "내 소비 습관을 점검해줘"},
            headers={"Idempotency-Key": "review"},
        )

    assert response.status_code == 200, response.text
    answer = response.json()
    assert answer["receipt"]["trigger"] == "requested_review"
    assert answer["wording_source"] == "template"
    assert answer["model"] == "not_called"
    assert model.routes == 0
    assert model.writes == 0
