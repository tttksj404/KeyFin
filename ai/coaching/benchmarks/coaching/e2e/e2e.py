"""Run fixed synthetic cases through uvicorn TCP, the service, FDT, and a generation gateway."""

import argparse
import hashlib
import json
import secrets
from datetime import datetime
from pathlib import Path
from typing import Final
from zoneinfo import ZoneInfo

import anyio
import httpx2
from pydantic import SecretStr, TypeAdapter

from benchmarks.coaching.e2e.e2e_contracts import (
    CaseOutcome,
    E2ECase,
    HttpExchange,
    Report,
    RunConfig,
)
from benchmarks.coaching.e2e.e2e_observation import observe_model
from benchmarks.coaching.e2e.e2e_runtime import Gateway, serve
from benchmarks.coaching.e2e.e2e_scenarios import Scenario
from coaching_service.api import create_app
from coaching_service.engine import ENGINE_COMMIT
from coaching_service.llm import create_http_client
from coaching_service.llm_contract import ModelConfig
from coaching_service.settings import Client, Settings

ROOT: Final = Path(__file__).resolve().parent
_CASES: Final = TypeAdapter(tuple[E2ECase, ...])


def load_cases() -> tuple[E2ECase, ...]:
    return _CASES.validate_json((ROOT / "e2e_cases.json").read_text(encoding="utf-8"))


def source_hashes() -> dict[str, str]:
    service = ROOT.parents[2]
    paths = [*ROOT.glob("e2e*.py"), ROOT / "e2e_cases.json"]
    test_file = service / "tests" / "test_e2e.py"
    if test_file.exists():
        paths.append(test_file)
    paths.extend((service / "src" / "coaching_service").glob("*.py"))
    paths.append(service / "ENGINE_MANIFEST.json")
    return {
        path.relative_to(service).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(paths)
    }


async def run_suite(config: RunConfig, *, upstream_client: httpx2.AsyncClient | None = None) -> Report:
    if config.output.exists() and any(config.output.iterdir()):
        raise FileExistsError("Experiment output must be new or empty")
    config.output.mkdir(parents=True, exist_ok=True)
    cases = load_cases()
    credentials = tuple(
        Client(user_id=case.owner, token=SecretStr(secrets.token_urlsafe(36))) for case in cases
    )
    day = config.as_of or datetime.now(ZoneInfo("Asia/Seoul")).date()
    locked_sources = source_hashes()
    freeze = {
        "experiment": "r5_20260910_e2e_compat",
        "role": "prospective_e2e_source_and_synthetic_input_freeze",
        "source_sha256": locked_sources,
        "as_of": day.isoformat(),
        "backend": config.backend,
        "model": config.model,
        "case_count": len(cases),
        "primary_gate": "operator_acknowledgement; does not independently attest primary completion",
        "date_policy": "Resolve current Asia/Seoul date once; synthetic history uses fixed relative offsets",
        "interpretation": (
            "Synthetic HTTP contract verification; fake outputs are not model-quality evidence. "
            "Fake tokenization is a UTF-8 byte stand-in, not serving-tokenizer evidence. "
            "R4 frozen outputs remain historical; this run records current R5 source only. "
            "GPU source/fallback observations are separate from contract checks."
        ),
    }
    _ = (config.output / "freeze.json").write_text(
        json.dumps(freeze, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    gateway = Gateway(config.model_copy(update={"as_of": day}), client=upstream_client)
    outcomes: list[CaseOutcome] = []
    exchanges: list[HttpExchange] = []
    async with gateway.client, serve(gateway.app) as gateway_base:
        settings = Settings(
            database=config.output / "service.sqlite3",
            clients=credentials,
            model=ModelConfig(endpoint_url=gateway_base, model=config.model),
            persona="plain",
        )
        async with (
            serve(create_app(settings)) as api_base,
            create_http_client(ModelConfig(read_timeout_seconds=120.0)) as client,
        ):
            for case in cases:
                scenario = Scenario(case, client, api_base, credentials, gateway)
                outcomes.append(await scenario.run())
                exchanges.extend(scenario.http)
    report = Report(
        generation_backend=config.backend,
        model=config.model,
        as_of=day,
        api_base_url=api_base,
        gateway_base_url=gateway_base,
        engine_commit=ENGINE_COMMIT,
        gpu_calls=sum(row.backend == "gpu" for row in gateway.generations),
        model_observation=observe_model(
            config.backend, tuple(outcomes), tuple(gateway.generations), tuple(gateway.preflights)
        ),
        cases=tuple(outcomes),
        http=tuple(exchanges),
        generations=tuple(gateway.generations),
        preflights=tuple(gateway.preflights),
    )
    serialized = report.model_dump_json(indent=2)
    if gateway.contains_credential(serialized) or any(
        credential.token.get_secret_value() in serialized for credential in credentials
    ):
        raise ValueError("Credential material unexpectedly reached an artifact")
    report_bytes = serialized.encode("utf-8")
    _ = (config.output / "report.json").write_bytes(report_bytes)
    unchanged = source_hashes() == locked_sources
    verification = {
        "source_hashes_unchanged": unchanged,
        "report_sha256": hashlib.sha256(report_bytes).hexdigest(),
    }
    _ = (config.output / "verification.json").write_text(
        json.dumps(verification, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if not unchanged:
        raise ValueError(
            "Source or synthetic case catalog changed during execution; inspect preserved report"
        )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument("--output", type=Path, required=True)
    _ = parser.add_argument("--backend", choices=("fake", "gpu"), default="fake")
    _ = parser.add_argument("--model", default="synthetic")
    _ = parser.add_argument("--primary-completed", action="store_true")
    _ = parser.add_argument("--allow-gpu", action="store_true")
    _ = parser.add_argument("--upstream-token-file", type=Path)
    _ = parser.add_argument("--upstream-url", default="http://127.0.0.1:18745/v1/chat/completions")
    options = parser.parse_args()
    config = RunConfig.model_validate(vars(options))
    report = anyio.run(run_suite, config)
    failed = sum(not check.passed for case in report.cases for check in case.checks)
    print(  # noqa: T201 - CLI emits only aggregate counts, never credentials or raw bodies.
        json.dumps(
            {
                "cases": len(report.cases),
                "failed_checks": failed,
                "generation_calls": len(report.generations),
                "gpu_calls": report.gpu_calls,
                "model_observation": report.model_observation.model_dump(),
            }
        )
    )
    if failed:
        raise SystemExit(1)
    if report.model_observation.gpu_connection_verified is False:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
