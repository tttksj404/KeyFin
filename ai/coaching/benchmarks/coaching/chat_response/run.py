"""Run the fixed natural-chat suite against an isolated API and save raw artifacts."""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import time
import urllib.parse
import uuid
from datetime import date, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, final

import httpx2

if TYPE_CHECKING:
    from pydantic import JsonValue

from benchmarks.coaching.chat_response.cases import CASES, ChatCase
from benchmarks.coaching.chat_response.contracts import CaseResult, HttpResult, HttpStage, RunReport
from coaching_service.chat_answers import ChatAnswer
from coaching_service.schemas import (
    Bootstrap,
    Coaching,
    Frozen,
    JsonDocument,
    Message,
    ReviewRequest,
    Session,
    SessionRequest,
    TurnRequest,
)

TOKEN_KEY = re.compile(r"token|auth|secret|password|credential|api.?key", re.IGNORECASE)


class CliArguments(Frozen):
    api_url: str
    fixture: Path
    output: Path
    token_env: str
    timeout_seconds: float


def safe_output(path: Path) -> Path:
    resolved = path.resolve()
    if "artifacts" not in {part.casefold() for part in resolved.parts}:
        raise ValueError("Raw responses must be written below an artifacts directory")
    _ = resolved.mkdir(parents=True, exist_ok=False)
    return resolved


def api_origin(value: str) -> str:
    parsed = urllib.parse.urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username is not None:
        raise ValueError("API URL must be an HTTP(S) origin without credentials")
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise ValueError("API URL must not include a path, query, or fragment")
    return value.rstrip("/")


def contains_secret_key(value: JsonValue) -> bool:
    if isinstance(value, dict):
        return any(
            TOKEN_KEY.search(key) is not None or contains_secret_key(child)
            for key, child in value.items()
        )
    return isinstance(value, list) and any(contains_secret_key(child) for child in value)


def twin_payload(path: Path) -> Bootstrap:
    loaded = JsonDocument.model_validate_json(path.read_bytes())
    if contains_secret_key(loaded.root):
        raise ValueError("Fixture must not contain credential fields")
    request = loaded.root.get("request")
    nested = request.get("data") if isinstance(request, dict) else None
    twin = nested if isinstance(nested, dict) else loaded.root.get("twin", loaded.root)
    return Bootstrap.model_validate(twin)


@final
class Client:
    def __init__(self, base_url: str, token: str, timeout: float) -> None:
        self.base_url: str = base_url
        self.token: str = token
        self.client: httpx2.Client = httpx2.Client(timeout=timeout)

    def close(self) -> None:
        self.client.close()

    def request(self, method: str, path: str, body: JsonDocument | None = None) -> HttpResult:
        headers = {"Authorization": "Bearer " + self.token, "Idempotency-Key": uuid.uuid4().hex}
        started = time.perf_counter()
        response = self.client.request(
            method,
            self.base_url + path,
            json=body.root if body is not None else None,
            headers=headers,
            follow_redirects=False,
        )
        return HttpResult(
            status=response.status_code,
            latency_ms=round((time.perf_counter() - started) * 1000, 3),
            body=JsonDocument.model_validate_json(response.content),
        )


def document(value: Frozen) -> JsonDocument:
    return JsonDocument.model_validate_json(value.model_dump_json())


def request_artifact(
    review: ReviewRequest | None,
    session: SessionRequest,
    message: TurnRequest,
) -> JsonDocument:
    value: dict[str, JsonValue] = {
        "session": session.model_dump(mode="json"),
        "message": message.model_dump(mode="json"),
    }
    if review is not None:
        value["review"] = review.model_dump(mode="json")
    return JsonDocument(value)


def incomplete(
    case: ChatCase,
    request: JsonDocument,
    stages: dict[str, HttpStage],
    body: JsonDocument,
) -> CaseResult:
    return CaseResult(
        id=case.id,
        question=case.question,
        setup=case.setup,
        expected_kind=case.expected_kind,
        expected_status=case.expected_status,
        reference_id=case.reference_id,
        request=request,
        http=stages,
        response=body,
    )


def run_case(client: Client, case: ChatCase, as_of: date) -> CaseResult:
    stages: dict[str, HttpStage] = {}
    review_request: ReviewRequest | None = None
    coaching_id: str | None = None
    if case.setup == "with_twin":
        review_request = ReviewRequest(
            on_date=as_of, through_date=as_of + timedelta(days=7), replay=True
        )
        review = client.request("POST", "/v1/coaching/reviews", document(review_request))
        stages["review"] = HttpStage(status=review.status, latency_ms=review.latency_ms)
        if review.status != 200:
            request = request_artifact(
                review_request,
                SessionRequest(),
                TurnRequest(question=case.question),
            )
            return incomplete(case, request, stages, review.body)
        coaching_id = Coaching.model_validate(review.body.root).id
    session_request = SessionRequest(coaching_id=coaching_id)
    turn_request = TurnRequest(question=case.question)
    request = request_artifact(review_request, session_request, turn_request)
    session_http = client.request("POST", "/v1/sessions", document(session_request))
    stages["session"] = HttpStage(status=session_http.status, latency_ms=session_http.latency_ms)
    if session_http.status != 200:
        return incomplete(case, request, stages, session_http.body)
    session = Session.model_validate(session_http.body.root)
    before_http = client.request("GET", "/v1/sessions/" + session.id)
    stages["history_before"] = HttpStage(status=before_http.status, latency_ms=before_http.latency_ms)
    message_http = client.request(
        "POST", "/v1/sessions/" + session.id + "/messages", document(turn_request)
    )
    stages["message"] = HttpStage(status=message_http.status, latency_ms=message_http.latency_ms)
    if message_http.status != 200:
        return incomplete(case, request, stages, message_http.body)
    answer: Coaching | ChatAnswer = (
        ChatAnswer.model_validate(message_http.body.root)
        if "answer_type" in message_http.body.root
        else Coaching.model_validate(message_http.body.root)
    )
    stored_kind = "answers" if isinstance(answer, ChatAnswer) else "coaching"
    stored_http = client.request("GET", f"/v1/{stored_kind}/" + answer.id)
    stages["stored"] = HttpStage(status=stored_http.status, latency_ms=stored_http.latency_ms)
    after_http = client.request("GET", "/v1/sessions/" + session.id)
    stages["history_after"] = HttpStage(status=after_http.status, latency_ms=after_http.latency_ms)
    before = Session.model_validate(before_http.body.root) if before_http.status == 200 else None
    after = Session.model_validate(after_http.body.root) if after_http.status == 200 else None
    return CaseResult(
        id=case.id,
        question=case.question,
        setup=case.setup,
        expected_kind=case.expected_kind,
        expected_status=case.expected_status,
        reference_id=case.reference_id,
        request=request,
        http=stages,
        response=answer,
        stored_exact=stored_http.status == 200 and stored_http.body == document(answer),
        history_isolated=(
            before is not None
            and before.messages == ()
            and after is not None
            and after.messages
            == (
                Message(role="user", content=case.question),
                Message(role="assistant", content=answer.text),
            )
        ),
    )


def write_report(path: Path, report: RunReport, token: str) -> None:
    raw = report.model_dump_json(indent=2).encode()
    if token.encode() in raw:
        raise RuntimeError("Credential material unexpectedly reached the artifact")
    _ = path.write_bytes(raw)


def arguments() -> CliArguments:
    parser = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument("--api-url", required=True, help="Isolated API origin")
    _ = parser.add_argument("--fixture", type=Path, required=True, help="Credential-free Twin bootstrap JSON")
    _ = parser.add_argument("--output", type=Path, required=True, help="New directory below artifacts/")
    _ = parser.add_argument("--token-env", default="COACHING_CHAT_TOKEN")
    _ = parser.add_argument("--timeout-seconds", type=float, default=180.0)
    return CliArguments.model_validate(vars(parser.parse_args()))


def main() -> None:
    options = arguments()
    token = os.environ.get(options.token_env)
    if not token:
        raise SystemExit("The configured token environment variable is empty")
    base = api_origin(options.api_url)
    payload = twin_payload(options.fixture)
    output = safe_output(options.output)
    client = Client(base, token, options.timeout_seconds)
    try:
        initial = client.request("GET", "/v1/twin")
        if initial.status != 404:
            raise SystemExit("This suite requires an isolated credential with no existing Twin")
        results = tuple(
            run_case(client, case, payload.as_of) for case in CASES if case.setup == "without_twin"
        )
        bootstrap = client.request("POST", "/v1/twin", document(payload))
        if bootstrap.status != 200:
            raise SystemExit("Twin fixture bootstrap failed")
        results += tuple(
            run_case(client, case, payload.as_of) for case in CASES if case.setup == "with_twin"
        )
    finally:
        client.close()
    report = RunReport(
        api_origin_sha256=hashlib.sha256(base.encode()).hexdigest(),
        fixture_sha256=hashlib.sha256(options.fixture.read_bytes()).hexdigest(),
        as_of=payload.as_of.isoformat(),
        cases=results,
    )
    write_report(output / "responses.json", report, token)
    message_ok = sum(
        case.http.get("message", HttpStage(status=0, latency_ms=0)).status == 200 for case in results
    )
    print(f"HTTP message responses: {message_ok}/{len(results)}")  # noqa: T201


if __name__ == "__main__":
    main()
