"""Deterministic artifact-review gate: a narrow, conjunctive grammar for f023-f037 style
questions that name an artifact noun, a read verb, and an explicit negation of a computation
request. See scratchpad/SPEC-review-gate.md for the grounding and exact yield."""

# ruff: noqa: INP001
from __future__ import annotations

from typing import TYPE_CHECKING, Final

import httpx2
import pytest
from pydantic import SecretStr
from typing_extensions import override

from benchmarks.coaching.cases import load_catalog, text_context
from coaching_service.api import create_app
from coaching_service.fast_routes import deterministic_analysis_route
from coaching_service.schemas import Coaching, JsonDocument
from coaching_service.settings import Client, Settings
from tests.test_api import TestModel
from tests.test_engine import fixture

if TYPE_CHECKING:
    from pathlib import Path

    from coaching_service.llm_contract import EvidenceInput, Routing

TOKEN: Final = "test-only-review-artifact-gate-token-0000000000"

_CATALOG = load_catalog()
_FAMILIES = {family.family_id: family for family in _CATALOG.families}
_ATTACKS = {attack.template_id: attack for attack in _CATALOG.attacks}

_REVIEW_FIDS: Final[tuple[str, ...]] = (
    "f025", "f029", "f030", "f031", "f034", "f036", "f037",
)
_ALL_TARGET_FIDS: Final[tuple[str, ...]] = (
    "f023", "f025", "f029", "f030", "f031", "f034", "f036", "f037",
)
_COLLIDING_FIDS: Final[tuple[str, ...]] = (
    "f059", "f060", "f065", "f068", "f077", "f040", "f042", "f044", "f050", "f039", "f053", "f076",
)


def fam(fid: str) -> object:
    return _FAMILIES[fid]


def strings(fid: str) -> tuple[str, str]:
    family = fam(fid)
    attack = _ATTACKS[family.attack_template_id]
    complete_q, _ = text_context(family, None)
    adversarial_q, _ = text_context(family, attack)
    return complete_q, adversarial_q


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.parametrize("fid", _ALL_TARGET_FIDS)
def test_artifact_meaning_review_routes_deterministically(fid: str) -> None:
    complete_q, _ = strings(fid)
    assert deterministic_analysis_route(complete_q) == "review"


@pytest.mark.parametrize("fid", _COLLIDING_FIDS)
def test_colliding_compute_negations_are_never_captured_as_review(fid: str) -> None:
    complete_q, adversarial_q = strings(fid)
    assert deterministic_analysis_route(complete_q) != "review"
    assert deterministic_analysis_route(adversarial_q) != "review"


def test_catalog_wide_sweep_never_misroutes_a_non_review_family() -> None:
    for family in _CATALOG.families:
        if family.family_id in _ALL_TARGET_FIDS:
            continue
        attack = _ATTACKS[family.attack_template_id]
        complete_q, _ = text_context(family, None)
        adversarial_q, _ = text_context(family, attack)
        for question in (complete_q, adversarial_q):
            result = deterministic_analysis_route(question)
            assert result in (None, "forecast", "risk"), (family.family_id, question, result)


@pytest.mark.parametrize("fid", _ALL_TARGET_FIDS)
def test_injected_decoy_adversarial_review_variants_route_review(fid: str) -> None:
    _, adversarial_q = strings(fid)
    assert deterministic_analysis_route(adversarial_q) == "review"


@pytest.mark.parametrize("fid", ["f024", "f032"])
def test_ambiguous_review_without_negation_falls_through(fid: str) -> None:
    complete_q, adversarial_q = strings(fid)
    assert deterministic_analysis_route(complete_q) is None
    assert deterministic_analysis_route(adversarial_q) is None


@pytest.mark.parametrize("question", [
    "이 안내의 의미를 확인해 줘",
    "자료 기준을 짚어 줘",
    "소비 습관을 점검하는 방법이 뭐야?",
    "유동성 위험이 뭐야?",
])
def test_ambiguous_review_literals_fall_through(question: str) -> None:
    assert deterministic_analysis_route(question) is None


@pytest.mark.anyio
@pytest.mark.parametrize("fid", ["f029", "f034"])
async def test_artifact_review_turn_skips_model_routing(tmp_path: Path, fid: str) -> None:
    """Clear artifact-review wording must skip model routing entirely."""
    complete_q, _ = strings(fid)

    class RouteMustNotRun(TestModel):
        @override
        async def route(self, evidence: EvidenceInput) -> Routing:
            del evidence
            raise AssertionError("artifact-review grammar must not wait for model routing")

    model = RouteMustNotRun()
    app = create_app(Settings(
        database=tmp_path / f"review-gate-{fid}.sqlite3",
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
        session = await client.post("/v1/sessions", json={}, headers={"Idempotency-Key": "session"})
        session_id = session.json()["id"]
        response = await client.post(
            f"/v1/sessions/{session_id}/messages",
            json={"question": complete_q},
            headers={"Idempotency-Key": f"review-{fid}"},
        )

    assert response.status_code == 200, response.text
    assert model.routes == 0
    coaching = Coaching.model_validate_json(response.content)
    assert coaching.receipt.routing == JsonDocument(
        {"mode": "review", "source": "template", "fallback_reason": None}
    )
