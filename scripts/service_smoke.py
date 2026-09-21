"""Run a real HTTP API process against a configured local GPU worker or explicit disabled profile.

Run with the locked COACHING_SERVICE project environment. Credentials stay in child environment variables.
"""

import hashlib
import importlib.metadata
import json
import os
import secrets
import subprocess
import sys
import time
from pathlib import Path

import anyio
import httpx2
from pydantic import SecretStr

from coaching_service.engine import ENGINE_COMMIT
from coaching_service.llm import create_http_client
from coaching_service.llm_contract import ModelConfig
from coaching_service.schemas import Bootstrap, Coaching, EventResult, JsonDocument, Session
from coaching_service.settings import Client, Settings

ROOT = Path(__file__).resolve().parents[1]


def fixture() -> Bootstrap:
    row = {
        "user_id": "smoke",
        "transaction_id": "old",
        "source": "LIVE",
        "transaction_type": "WITHDRAW",
        "transaction_date": "2026-07-01",
        "transaction_time": "12:00",
        "category": "기타",
        "subcategory": "기타",
        "merchant": "SYNTHETIC",
        "merchant_id": "synthetic",
        "amount_krw": 10000,
        "account_id": "a",
        "card_id": "",
        "confirm_status": "CONFIRMED",
        "status": "NORMAL",
    }
    return Bootstrap.model_validate(
        {
            "as_of": "2026-09-09",
            "transactions": [row],
            "envelopes": [{"envelope": "기타", "balance_krw": 100000}],
            "snapshot": {
                "as_of": "2026-09-09",
                "source": "USER_ASSUMPTION",
                "accounts": [{"account_id": "a", "balance_krw": 1000000}],
                "cards": [],
                "known_bills": [],
                "reserve_krw": 100000,
                "budgets": {"기타": 100000},
            },
        }
    )


async def exercise(settings: Settings, output: Path) -> None:  # noqa: C901, PLR0912, PLR0915 - linear scenario audit
    port = int(os.environ.get("COACHING_SMOKE_PORT", "18744"))
    base = f"http://127.0.0.1:{port}"
    environment = {
        **os.environ,
        "COACHING_DATABASE": str(settings.database),
        "COACHING_CLIENTS": json.dumps(
            [{"user_id": "smoke", "token": settings.clients[0].token.get_secret_value()}]
        ),
        "COACHING_MODEL": settings.model.model_dump_json(),
        "PYTHONUTF8": "1",
    }
    # SecretStr deliberately masks exports: inject the real secret only into the child environment.
    model_settings = json.loads(settings.model.model_dump_json())
    if settings.model.token is not None:
        model_settings["token"] = settings.model.token.get_secret_value()
    environment["COACHING_MODEL"] = json.dumps(model_settings)
    log = output / "server.log"
    trace: list[dict] = []
    with (
        log.open("wb") as stdout,
        subprocess.Popen(  # noqa: ASYNC220, S603 - isolated smoke runner starts its own fixed API process
            [
                sys.executable,
                "-m",
                "uvicorn",
                "coaching_service.api:from_environment",
                "--factory",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--no-access-log",
            ],
            env=environment,
            stdout=stdout,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        ) as process,
    ):
        try:
            async with create_http_client(ModelConfig(read_timeout_seconds=120.0)) as client:
                headers = {"Authorization": "Bearer " + settings.clients[0].token.get_secret_value()}
                for _ in range(80):
                    if process.poll() is not None:
                        raise RuntimeError("api_process_failed_see_server_log")
                    try:
                        response = await client.get(base + "/healthz")
                        if response.status_code == 200:
                            break
                    except OSError:
                        pass
                    except httpx2.ConnectError:
                        pass
                    await anyio.sleep(0.25)
                else:
                    raise RuntimeError("api_startup_deadline")

                async def call(method: str, path: str, body: dict | None = None, key: str = "read") -> dict:
                    started = time.perf_counter()
                    response = await client.request(
                        method, base + path, json=body, headers={**headers, "Idempotency-Key": key}
                    )
                    value = JsonDocument.model_validate_json(response.content).root
                    trace.append(
                        {
                            "method": method,
                            "path": path,
                            "status": response.status_code,
                            "seconds": time.perf_counter() - started,
                            "response": value,
                        }
                    )
                    if response.status_code != 200:
                        message = f"http_smoke_status_{response.status_code}"
                        raise RuntimeError(message)
                    return value

                initial = fixture()
                await call("POST", "/v1/twin", initial.model_dump(mode="json"), "init")
                row = {
                    **initial.transactions[0].root,
                    "transaction_id": "pay",
                    "transaction_date": "2026-09-09",
                    "amount_krw": 50000,
                }
                event = {
                    "expected_revision": 0,
                    "event": {
                        "type": "transaction",
                        "event_id": "pay",
                        "user_id": "smoke",
                        "transaction": row,
                    },
                }
                paid = EventResult.model_validate(await call("POST", "/v1/events", event, "pay"))
                if paid.coaching is None or paid.payment is None or paid.payment.balance_before_krw != 100000:
                    raise RuntimeError("p0_detection_failed")
                repeat = EventResult.model_validate(await call("POST", "/v1/events", event, "pay"))
                if paid != repeat:
                    raise RuntimeError("idempotency_failed")
                snapshot = initial.snapshot
                if snapshot is None:
                    raise RuntimeError("fixture_snapshot_missing")
                p1 = {
                    "expected_revision": 1,
                    "event": {
                        "type": "transaction",
                        "event_id": "p1",
                        "user_id": "smoke",
                        "transaction": {
                            **row,
                            "transaction_id": "p1",
                            "transaction_time": "13:00",
                            "amount_krw": 22500,
                        },
                    },
                    "snapshot_event": {
                        "type": "snapshot",
                        "event_id": "snapshot",
                        "user_id": "smoke",
                        "snapshot": {
                            **snapshot.root,
                            "source": "LIVE",
                            "accounts": [{"account_id": "a", "balance_krw": 927500}],
                        },
                    },
                }
                ambiguous = EventResult.model_validate(await call("POST", "/v1/events", p1, "p1"))
                if ambiguous.detection != "p1_ambiguous" or ambiguous.judgment is None:
                    raise RuntimeError("p1_judgment_missing")
                session = Session.model_validate(
                    await call("POST", "/v1/sessions", {"coaching_id": paid.coaching.id}, "session")
                )
                chat = Coaching.model_validate(
                    await call(
                        "POST",
                        f"/v1/sessions/{session.id}/messages",
                        {
                            "question": "왜 코칭이 나왔고 앞으로 현금이 부족할 위험은 어떻게 확인해?",
                            "analysis": {"mode": "risk", "horizon_days": 7, "paths": 20, "seed": 42},
                        },
                        "chat",
                    )
                )
                if chat.receipt.numeric_result is None or chat.receipt.historical is None:
                    raise RuntimeError("real_engine_dialogue_missing")
                await call("GET", "/v1/coaching/" + paid.coaching.id)
                await call("GET", f"/v1/sessions/{session.id}")
                notifications = await call("GET", "/v1/notifications")
                for item in notifications["items"]:
                    await call("POST", "/v1/notifications/" + item["event_id"] + "/ack", key=item["event_id"])
                remaining = await call("GET", "/v1/notifications")
                if remaining["items"]:
                    raise RuntimeError("notification_ack_failed")
                if settings.model.endpoint_url is not None and ambiguous.judgment.root.get("source") != "llm":
                    raise RuntimeError("gpu_judgment_not_executed")
                result = {
                    "status": "pass",
                    "real_http": True,
                    "real_engine": ENGINE_COMMIT,
                    "gpu_model_configured": settings.model.endpoint_url is not None,
                    "data": "synthetic contract scenarios, no customer accuracy estimate",
                    "p0_wording_source": paid.coaching.wording_source,
                    "p0_fallback_reason": paid.coaching.fallback_reason,
                    "p1_judgment": ambiguous.judgment.root,
                    "dialogue_wording_source": chat.wording_source,
                    "dialogue_fallback_reason": chat.fallback_reason,
                    "dialogue_routing": chat.receipt.routing.root if chat.receipt.routing else None,
                    "numeric_mode": chat.receipt.numeric_result.root.get("mode"),
                    "python": sys.version.split()[0],
                    "versions": {
                        name: importlib.metadata.version(name)
                        for name in ("pydantic", "fastapi", "uvicorn", "anyio", "httpx2")
                    },
                    "call_count": len(trace),
                }
                (output / "result.json").write_text(
                    json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
                )
        finally:
            (output / "trace.json").write_text(
                json.dumps(trace, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


def main() -> None:
    output = Path(os.environ.get("COACHING_SMOKE_OUTPUT", str(ROOT / "artifacts" / "http_smoke"))).resolve()
    output.mkdir(parents=True, exist_ok=True)
    endpoint = os.environ.get("COACHING_SMOKE_MODEL_ENDPOINT")
    token_file = os.environ.get("COACHING_SMOKE_MODEL_TOKEN_FILE")
    model_token = SecretStr(Path(token_file).read_text().strip()) if token_file else None
    model = ModelConfig(
        endpoint_url=endpoint,
        token=model_token,
        model="latest27_nf4",
        timeout_seconds=60.0,
        read_timeout_seconds=60.0,
    )
    settings = Settings(
        database=output / ("state-" + secrets.token_hex(8) + ".sqlite3"),
        clients=(Client(user_id="smoke", token=SecretStr(secrets.token_urlsafe(32))),),
        model=model,
    )
    anyio.run(exercise, settings, output)
    hashes = {
        name: hashlib.sha256((output / name).read_bytes()).hexdigest()
        for name in ("result.json", "trace.json", "server.log")
    }
    (output / "manifest.json").write_text(json.dumps(hashes, indent=2), encoding="utf-8")
    print("REAL_HTTP_SMOKE_PASS", json.dumps(hashes))


if __name__ == "__main__":
    main()
