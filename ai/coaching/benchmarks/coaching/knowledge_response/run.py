"""Execute a new synthetic knowledge and personal-context coverage suite over TCP."""

import argparse
import hashlib
import json
import os
import secrets
import sys
import uuid
from importlib.resources import files
from pathlib import Path
from typing import Literal

import httpx2
from pydantic import ValidationError

from benchmarks.coaching.chat_response.run import safe_output
from benchmarks.coaching.flow.client import Flow
from benchmarks.coaching.flow.contracts import Backend, Check, Exchange, ModelObservation, RoutingObservation
from benchmarks.coaching.flow.process import OwnedApi
from benchmarks.coaching.flow.references import exact_references
from benchmarks.coaching.flow.scenario import saved_answer
from benchmarks.coaching.knowledge_response.cases import (
    CONCEPTS,
    FOLLOWUP,
    PERSONAL,
    SCOPE,
    UNSUPPORTED,
    Case,
)
from benchmarks.coaching.knowledge_response.fixtures import personal, twin
from benchmarks.coaching.knowledge_response.score import evaluate
from coaching_service.llm_contract import ModelConfig
from coaching_service.schemas import Frozen, JsonDocument, Session

Group = Literal["concept", "scope", "followup", "personal", "filter"]


class CaseResult(Frozen):
    group: Group
    case: Case
    response_stage: str
    passed: bool


class Report(Frozen):
    version: Literal["knowledge-personal-coverage/3"] = "knowledge-personal-coverage/3"
    backend: Backend
    catalog_sha256: str
    cases: tuple[CaseResult, ...]
    checks: tuple[Check, ...]
    exchanges: tuple[Exchange, ...]
    model_observations: tuple[ModelObservation, ...]
    routing_observations: tuple[RoutingObservation, ...]
    followup_text_changed: bool | None
    api_process_id: int
    api_process_stopped: bool
    completed: bool
    error_type: str | None


class Arguments(Frozen):
    output: Path
    backend: Backend


def session(flow: Flow, key: str) -> str:
    return Session.model_validate(
        flow.request(key + "-session", "POST", "/v1/sessions", JsonDocument({})).root
    ).id


def exercise(flow: Flow, case: Case, group: Group, session_id: str) -> CaseResult:
    stage = group + "-" + case.id
    response = flow.turn(stage, session_id, case.question)
    _ = saved_answer(flow, stage, response)
    history_doc = flow.request(stage + "-history", "GET", "/v1/sessions/" + session_id)
    history = Session.model_validate(history_doc.root)
    raw_messages = history_doc.root.get("messages")
    tail = JsonDocument({"messages": raw_messages[-2:] if isinstance(raw_messages, list) else []})
    flow.check(stage + ":answer_reference", passed=exact_references(tail, (response,)))
    flow.check(
        stage + ":appended_messages",
        passed=len(history.messages) >= 2
        and history.messages[-2].role == "user"
        and history.messages[-2].content == case.question
        and history.messages[-1].role == "assistant"
        and history.messages[-1].content == response.root.get("text"),
    )
    passed = evaluate(case, response)
    flow.check(stage + ":coverage", passed=passed)
    return CaseResult(group=group, case=case, response_stage=stage, passed=passed)


def execute(flow: Flow, owner: str, results: list[CaseResult]) -> bool:
    """Append each observed case immediately so a later HTTP failure preserves earlier results."""
    results.extend(exercise(flow, case, "concept", session(flow, "concept-" + case.id)) for case in CONCEPTS)
    results.extend(exercise(flow, case, "scope", session(flow, "scope-" + case.id)) for case in SCOPE)
    followup_session = session(flow, "followup")
    results.append(exercise(flow, CONCEPTS[0], "followup", followup_session))
    results.append(exercise(flow, FOLLOWUP, "followup", followup_session))
    followup_history = Session.model_validate(
        flow.request("followup-final", "GET", "/v1/sessions/" + followup_session).root
    )
    flow.check("followup:four_messages", passed=len(followup_history.messages) == 4)
    text_changed = followup_history.messages[1].content != followup_history.messages[3].content
    _ = flow.request("bootstrap", "POST", "/v1/twin", twin(owner))
    context = flow.request("personal-context", "POST", "/v1/personal/context", personal())
    flow.check(
        "personal:context_persisted",
        passed=flow.request("personal-context-get", "GET", "/v1/personal/context") == context,
    )
    personal_session = session(flow, "personal")
    results.extend(exercise(flow, case, "personal", personal_session) for case in PERSONAL)
    results.append(exercise(flow, UNSUPPORTED, "filter", personal_session))
    personal_history = Session.model_validate(
        flow.request("personal-final", "GET", "/v1/sessions/" + personal_session).root
    )
    flow.check("personal:eighteen_messages", passed=len(personal_history.messages) == 18)
    return text_changed


def run(output: Path, backend: Backend) -> Report:
    target = safe_output(output)
    owner = "knowledge-" + uuid.uuid4().hex
    token = secrets.token_urlsafe(32)
    raw_model = os.environ.get("COACHING_MODEL", "{}")
    model = ModelConfig.model_validate_json(raw_model)
    if backend == "gpu" and model.endpoint_url is None:
        raise RuntimeError("gpu_backend_requires_configured_model")
    env = {
        **os.environ,
        "CUDA_VISIBLE_DEVICES": "",
        "COACHING_DATABASE": str(target / "state.sqlite3"),
        "COACHING_MODEL": raw_model,
        "COACHING_CLIENTS": json.dumps([{"user_id": owner, "token": token, "role": "backend"}]),
        "PYTHONUTF8": "1",
    }
    api = OwnedApi(
        target, backend, env, fake_factory="benchmarks.coaching.knowledge_response.fake:from_environment"
    )
    cases: list[CaseResult] = []
    error_type: str | None = None
    process_id = 0
    changed: bool | None = None
    with httpx2.Client(
        base_url=api.origin, timeout=120, trust_env=False, headers={"Authorization": "Bearer " + token}
    ) as client:
        flow = Flow(client)
        try:
            process_id = api.start()
            changed = execute(flow, owner, cases)
        except (RuntimeError, OSError, httpx2.HTTPError, ValidationError) as error:
            error_type = type(error).__name__
            flow.check("suite:completed", passed=False)
        finally:
            _ = api.stop()
    report = Report(
        backend=backend,
        catalog_sha256=hashlib.sha256(
            files("coaching_service").joinpath("knowledge/finance.json").read_bytes()
        ).hexdigest(),
        cases=tuple(cases),
        checks=tuple(flow.checks),
        exchanges=tuple(flow.exchanges),
        model_observations=tuple(flow.observations),
        routing_observations=tuple(flow.routes),
        followup_text_changed=changed,
        api_process_id=process_id,
        api_process_stopped=api.process is None,
        completed=error_type is None and len(cases) == 41 and all(check.passed for check in flow.checks),
        error_type=error_type,
    )
    raw = report.model_dump_json(indent=2).encode()
    if token.encode() in raw:
        raise RuntimeError("credential_reached_knowledge_artifact")
    _ = (target / "report.json").write_bytes(raw)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument("--output", type=Path, required=True)
    _ = parser.add_argument("--backend", choices=("fake", "gpu"), default="fake")
    args = Arguments.model_validate(vars(parser.parse_args()))
    result = run(args.output, args.backend)
    _ = sys.stdout.write(
        json.dumps(
            {
                "completed": result.completed,
                "backend": result.backend,
                "cases_passed": sum(case.passed for case in result.cases),
                "cases_total": len(result.cases),
                "checks_passed": sum(check.passed for check in result.checks),
                "checks_total": len(result.checks),
                "failed_checks": [check.name for check in result.checks if not check.passed],
                "followup_text_changed": result.followup_text_changed,
                "error_type": result.error_type,
            }
        )
        + "\n"
    )
    return 0 if result.completed else 1


if __name__ == "__main__":
    raise SystemExit(main())
