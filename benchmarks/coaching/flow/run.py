"""Run a synthetic financial lifecycle over TCP, including a genuine process restart."""

import argparse
import json
import os
import secrets
import sys
import uuid
from datetime import date
from pathlib import Path

import httpx2
from pydantic import ValidationError

from benchmarks.coaching.chat_response.run import safe_output
from benchmarks.coaching.flow.client import Flow
from benchmarks.coaching.flow.contracts import Backend, FlowReport
from benchmarks.coaching.flow.fixtures import scenario
from benchmarks.coaching.flow.process import OwnedApi
from benchmarks.coaching.flow.scenario import after_restart, before_restart
from coaching_service.llm_contract import ModelConfig
from coaching_service.schemas import Frozen, JsonDocument


class Arguments(Frozen):
    output: Path
    backend: Backend
    as_of: date


def run(output: Path, backend: Backend, day: date) -> FlowReport:
    """Create isolated credentials and DB; inherit only the configured inference endpoint."""
    target = safe_output(output)
    owner = "flow-" + uuid.uuid4().hex
    token = secrets.token_urlsafe(32)
    data = scenario(owner, day)
    model = ModelConfig.model_validate_json(os.environ.get("COACHING_MODEL", "{}"))
    if backend == "gpu" and model.endpoint_url is None:
        raise RuntimeError("gpu_backend_requires_configured_model")
    env = {
        **os.environ,
        "CUDA_VISIBLE_DEVICES": "",
        "COACHING_DATABASE": str(target / "state.sqlite3"),
        "COACHING_CLIENTS": json.dumps([{"user_id": owner, "token": token, "role": "backend"}]),
        "COACHING_MODEL": model.model_dump_json(),
        "PYTHONUTF8": "1",
    }
    # SecretStr serializes as a mask; retain the original private model configuration for the child.
    if "COACHING_MODEL" in os.environ:
        env["COACHING_MODEL"] = os.environ["COACHING_MODEL"]
    api = OwnedApi(target, backend, env)
    process_ids = [0, 0]
    original_exit = 0
    error_type: str | None = None
    with httpx2.Client(
        base_url=api.origin, timeout=120, trust_env=False, headers={"Authorization": "Bearer " + token}
    ) as client:
        flow = Flow(client)
        try:
            process_ids[0] = api.start()
            saved = before_restart(flow, data)
            original_exit = api.stop()
            process_ids[1] = api.start()
            flow.check("restart:process_changed", passed=process_ids[0] != process_ids[1])
            after_restart(flow, saved)
        except (RuntimeError, OSError, httpx2.HTTPError, ValidationError) as error:
            error_type = type(error).__name__
            flow.check("flow:completed", passed=False)
        finally:
            _ = api.stop()
    report = FlowReport(
        backend=backend,
        fixture=JsonDocument.model_validate_json(data.model_dump_json()),
        process_ids=(process_ids[0], process_ids[1]),
        original_process_exit_code=original_exit,
        final_process_stopped=api.process is None,
        checks=tuple(flow.checks),
        exchanges=tuple(flow.exchanges),
        model_observations=tuple(flow.observations),
        routing_observations=tuple(flow.routes),
        completed=error_type is None and bool(flow.checks) and all(check.passed for check in flow.checks),
        error_type=error_type,
    )
    raw = report.model_dump_json(indent=2).encode()
    if token.encode() in raw:
        raise RuntimeError("credential_reached_flow_artifact")
    _ = (target / "report.json").write_bytes(raw)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument("--output", type=Path, required=True)
    _ = parser.add_argument("--backend", choices=("fake", "gpu"), default="fake")
    _ = parser.add_argument("--as-of", type=date.fromisoformat, default=date(2026, 9, 3))
    args = Arguments.model_validate(vars(parser.parse_args()))
    report = run(args.output, args.backend, args.as_of)
    _ = sys.stdout.write(
        json.dumps(
            {
                "completed": report.completed,
                "backend": report.backend,
                "checks_passed": sum(check.passed for check in report.checks),
                "checks_total": len(report.checks),
                "failed_checks": [check.name for check in report.checks if not check.passed],
                "http_exchanges": len(report.exchanges),
                "actual_process_restart": report.process_ids[1] > 0
                and report.process_ids[0] != report.process_ids[1],
                "error_type": report.error_type,
            }
        )
        + "\n"
    )
    return 0 if report.completed else 1


if __name__ == "__main__":
    raise SystemExit(main())
