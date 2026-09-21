from pathlib import Path

import httpx2
import pytest
from test_api import TestModel
from test_engine import fixture

from coaching_service.api import create_app
from coaching_service.settings import Client, Settings

BACKEND_TOKEN = "test-only-backend-svc-token-0000000000"
DEMO_BACKEND_TOKEN = "test-only-backend-demo-token-000000000"
ALPHA_USER_TOKEN = "test-only-user-alpha-token-0000000000"
BETA_USER_TOKEN = "test-only-user-beta-token-00000000000"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def setup(path: Path, model: TestModel) -> object:
    return create_app(
        Settings(
            database=path,
            clients=(
                Client(user_id="svc", token=BACKEND_TOKEN, role="backend"),
                Client(user_id="demo", token=DEMO_BACKEND_TOKEN, role="backend"),
                Client(user_id="alpha", token=ALPHA_USER_TOKEN, role="user"),
                Client(user_id="beta", token=BETA_USER_TOKEN, role="user"),
            ),
        ),
        model,
    )


@pytest.mark.anyio
async def test_backend_header_targets_user(tmp_path: Path) -> None:
    model = TestModel()
    app = setup(tmp_path / "targets.sqlite3", model)
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": "Bearer " + BACKEND_TOKEN},
    ) as client:
        created_alpha = await client.post(
            "/v1/twin",
            json=fixture("alpha").model_dump(mode="json"),
            headers={"Idempotency-Key": "b-alpha", "X-Coaching-User": "alpha"},
        )
        assert created_alpha.status_code == 200, created_alpha.text

        created_beta = await client.post(
            "/v1/twin",
            json=fixture("beta").model_dump(mode="json"),
            headers={"Idempotency-Key": "b-beta", "X-Coaching-User": "beta"},
        )
        assert created_beta.status_code == 200, created_beta.text

        twin_alpha = await client.get("/v1/twin", headers={"X-Coaching-User": "alpha"})
        twin_beta = await client.get("/v1/twin", headers={"X-Coaching-User": "beta"})
        assert twin_alpha.status_code == 200
        assert twin_beta.status_code == 200
        assert twin_alpha.json() != twin_beta.json()


@pytest.mark.anyio
async def test_backend_no_header_uses_token_user(tmp_path: Path) -> None:
    model = TestModel()
    app = setup(tmp_path / "nohead.sqlite3", model)
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": "Bearer " + DEMO_BACKEND_TOKEN},
    ) as client:
        created = await client.post(
            "/v1/twin", json=fixture("demo").model_dump(mode="json"), headers={"Idempotency-Key": "b1"}
        )
        assert created.status_code == 200, created.text


@pytest.mark.anyio
async def test_header_user_id_mismatch_rejected(tmp_path: Path) -> None:
    model = TestModel()
    app = setup(tmp_path / "mismatch.sqlite3", model)
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": "Bearer " + BACKEND_TOKEN},
    ) as client:
        result = await client.post(
            "/v1/twin",
            json=fixture("beta").model_dump(mode="json"),
            headers={"Idempotency-Key": "b1", "X-Coaching-User": "alpha"},
        )
        assert result.status_code == 403, result.text
        assert result.json()["error"] == "user_mismatch"


@pytest.mark.anyio
async def test_user_role_ignores_header(tmp_path: Path) -> None:
    model = TestModel()
    app = setup(tmp_path / "ignore.sqlite3", model)
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=app), base_url="http://test"
    ) as client:
        for user, key in (("alpha", "b-alpha"), ("beta", "b-beta")):
            bootstrapped = await client.post(
                "/v1/twin",
                json=fixture(user).model_dump(mode="json"),
                headers={
                    "Authorization": "Bearer " + BACKEND_TOKEN,
                    "Idempotency-Key": key,
                    "X-Coaching-User": user,
                },
            )
            assert bootstrapped.status_code == 200, bootstrapped.text

        review_body = {"on_date": "2026-09-09", "through_date": "2026-09-16", "paths": 20}
        review_alpha = await client.post(
            "/v1/coaching/reviews",
            json=review_body,
            headers={"Authorization": "Bearer " + ALPHA_USER_TOKEN, "Idempotency-Key": "review-alpha"},
        )
        assert review_alpha.status_code == 200, review_alpha.text
        coaching_alpha = review_alpha.json()["id"]

        review_beta = await client.post(
            "/v1/coaching/reviews",
            json=review_body,
            headers={"Authorization": "Bearer " + BETA_USER_TOKEN, "Idempotency-Key": "review-beta"},
        )
        assert review_beta.status_code == 200, review_beta.text
        coaching_beta = review_beta.json()["id"]

        own_via_other_header = await client.get(
            "/v1/coaching/" + coaching_alpha,
            headers={"Authorization": "Bearer " + ALPHA_USER_TOKEN, "X-Coaching-User": "beta"},
        )
        assert own_via_other_header.status_code == 200
        assert own_via_other_header.json()["id"] == coaching_alpha

        cross_via_header = await client.get(
            "/v1/coaching/" + coaching_beta,
            headers={"Authorization": "Bearer " + ALPHA_USER_TOKEN, "X-Coaching-User": "beta"},
        )
        assert cross_via_header.status_code == 404


@pytest.mark.anyio
async def test_blank_header_rejected(tmp_path: Path) -> None:
    model = TestModel()
    app = setup(tmp_path / "blank.sqlite3", model)
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": "Bearer " + BACKEND_TOKEN},
    ) as client:
        result = await client.post(
            "/v1/twin",
            json=fixture("alpha").model_dump(mode="json"),
            headers={"Idempotency-Key": "b1", "X-Coaching-User": ""},
        )
        assert result.status_code == 400, result.text
        assert result.json()["error"] == "invalid_target_user"
