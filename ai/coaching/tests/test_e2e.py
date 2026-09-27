# ruff: noqa: INP001
"""Real TCP contract tests; the generation endpoint is synthetic and never uses a GPU."""

import hashlib
import json
from collections import Counter
from datetime import date
from pathlib import Path
from zipfile import ZipFile

import httpx2
import pytest
from pydantic import TypeAdapter, ValidationError

from benchmarks.coaching.e2e.e2e import ROOT, load_cases, run_suite
from benchmarks.coaching.e2e.e2e_auth import worker_token
from benchmarks.coaching.e2e.e2e_bundle import build_bundle
from benchmarks.coaching.e2e.e2e_contracts import CaseOutcome, E2ECase, Report, RunConfig
from benchmarks.coaching.e2e.e2e_observation import observe_model
from benchmarks.coaching.e2e.e2e_package import (
    build_evidence,
    restore_archive,
    verified_payloads,
    write_archive,
)
from benchmarks.coaching.e2e.e2e_runtime import Gateway, GenerationRequest, PromptMessage, serve
from benchmarks.coaching.e2e.e2e_tokenizer import synthetic_budget
from coaching_service.llm_contract import EvidenceInput
from coaching_service.llm_prompt import system_prompt, user_payload
from coaching_service.schemas import JsonDocument
from coaching_service.token_budget import TokenBudget


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
@pytest.mark.parametrize("evidence_as_object", [False, True])
async def test_fake_gateway_attests_exact_bytes_before_generation(
    tmp_path: Path, evidence_as_object: bool
) -> None:
    gateway = Gateway(RunConfig(output=tmp_path))
    gateway.active_case = load_cases()[0]
    evidence = EvidenceInput(facts_json='{"synthetic":true}')
    payload = JsonDocument.model_validate_json(user_payload(evidence))
    payload.root["evidence_json"] = (
        JsonDocument.model_validate_json(evidence.facts_json).root
        if evidence_as_object
        else evidence.facts_json
    )
    body = {
        "model": "synthetic",
        "messages": [
            {"role": "system", "content": system_prompt("write")},
            {"role": "user", "content": payload.model_dump_json()},
        ],
        "temperature": 0,
        "max_tokens": 256,
        "stream": False,
    }
    raw = json.dumps(body, ensure_ascii=False, indent=2).encode("utf-8")
    async with gateway.client, serve(gateway.app) as base, httpx2.AsyncClient(trust_env=False) as client:
        response = await client.post(base + "/v1/tokenize", content=raw)
        assert response.status_code == 200
        budget = TokenBudget.model_validate_json(response.content)
        assert budget.request_sha256 == hashlib.sha256(raw).hexdigest()
        assert len(gateway.generations) == 0
        generated = await client.post(
            base + "/v1/chat/completions",
            content=raw,
            headers={"X-Coaching-Prompt-Sha256": budget.prompt_sha256},
        )
        assert generated.status_code == 200
        changed = await client.post(
            base + "/v1/chat/completions",
            content=raw + b"\n",
            headers={"X-Coaching-Prompt-Sha256": budget.prompt_sha256},
        )
        assert changed.status_code == 409
        stale = await client.post(
            base + "/v1/chat/completions", content=raw, headers={"X-Coaching-Prompt-Sha256": "0" * 64}
        )
        assert stale.status_code == 409
        missing = await client.post(base + "/v1/chat/completions", content=raw)
        assert missing.status_code == 409
    assert len(gateway.generations) == 1
    assert gateway.preflights[0].tokenizer == "synthetic_utf8_bytes_standin"


def test_catalog_has_independent_users_and_required_paths() -> None:
    cases = load_cases()
    assert len(cases) == 24
    assert len({case.case_id for case in cases}) == 24
    assert len({case.owner for case in cases}) == 24
    assert {case.expected_route for case in cases if case.expected_route} == {"review", "risk", "forecast"}
    modes = {
        mode for case in cases for request in case.analyses if isinstance(mode := request.root["mode"], str)
    }
    assert modes == {"forecast", "what_if", "goal", "risk", "optimize"}
    assert {
        "cancel",
        "bootstrap_cancel",
        "duplicate_key",
        "duplicate_event",
        "conflict",
        "isolation",
        "ack",
    } <= {case.action for case in cases}


def test_gpu_requires_explicit_primary_completion_gate(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="primary"):
        _ = RunConfig(output=tmp_path, backend="gpu", model="base27")
    with pytest.raises(ValidationError, match="token file"):
        _ = RunConfig(output=tmp_path, backend="gpu", primary_completed=True, allow_gpu=True)
    config = RunConfig(
        output=tmp_path,
        backend="gpu",
        model="base27",
        primary_completed=True,
        allow_gpu=True,
        upstream_token_file=tmp_path / "worker.token",
    )
    assert config.upstream_url == "http://127.0.0.1:18745/v1/chat/completions"


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://example.invalid:18745",
        "https://127.0.0.1:18745",
        "http://user:pass@127.0.0.1:18745",
        "http://127.0.0.1:18745/v1/tokenize",
        "http://127.0.0.1:18745?query=value",
    ],
)
def test_upstream_worker_endpoint_stays_on_explicit_loopback(tmp_path: Path, endpoint: str) -> None:
    with pytest.raises(ValidationError, match="loopback"):
        _ = RunConfig(output=tmp_path, upstream_url=endpoint)


@pytest.mark.anyio
async def test_real_uvicorn_http_runs_all_cases_and_preserves_receipts(tmp_path: Path) -> None:
    report = await run_suite(RunConfig(output=tmp_path / "fake", backend="fake", model="synthetic"))
    assert len(report.cases) == 24
    failures = [
        (case.case_id, check.name, check.detail)
        for case in report.cases
        for check in case.checks
        if not check.passed
    ]
    assert failures == []
    assert report.gpu_calls == 0
    assert report.transport == "uvicorn_tcp_http"
    assert report.generation_backend == "fake"
    assert report.experiment == "r5_20260910_e2e_compat"
    assert len(report.preflights) == len(report.generations)
    for preflight, generation in zip(report.preflights, report.generations, strict=True):
        assert preflight.tokenizer == "synthetic_utf8_bytes_standin"
        assert preflight.status_code == 200
        assert preflight.budget is not None
        assert preflight.budget.request_sha256 == generation.request_sha256
        assert preflight.budget.prompt_sha256 == generation.prompt_sha256
        assert (preflight.case_id, preflight.operation, preflight.evidence) == (
            generation.case_id,
            generation.operation,
            generation.evidence,
        )
    observations = report.model_observation
    assert observations.gpu_connection_verified is None
    assert observations.generation_attempts == len(report.generations)
    assert sum(row.observed_results for row in observations.operation_results) >= len(report.generations)
    assert all(
        row.observed_results == row.accepted_llm + row.template_results + row.other_sources
        for row in observations.operation_results
    )
    assert observations.http_status_counts == {"200": len(report.generations) - 1, "503": 1}
    assert report.api_base_url.startswith("http://127.0.0.1:")
    assert report.gateway_base_url != report.api_base_url
    assert {row.operation for row in report.generations} == {"write", "judge", "route"}
    assert all(row.request_body.root["model"] == "synthetic" for row in report.generations)
    checks = Counter(check.name for case in report.cases for check in case.checks)
    assert checks["stored_receipt_exact"] >= 20
    # A complete numerical/review receipt is intentionally a template result with no writer call.
    assert (
        checks["writer_projection_exact"] + checks["authoritative_receipt_no_writer"]
        == checks["stored_receipt_exact"]
    )
    assert checks["judge_projection_exact"] >= 5
    assert checks["route_projection_exact"] >= 2
    assert checks["projection_original_receipt_preserved"] == len(report.preflights)
    assert (
        checks["original_engine_review_exact"] + checks["original_engine_review_not_run"]
        == checks["stored_receipt_exact"]
    )
    assert checks["numeric_engine_result_exact"] >= 7
    assert checks["dialogue_authoritative_receipt_no_writer"] >= 7
    assert sum(case.deterministic_routes for case in report.cases) == (
        checks["explicit_analysis_exact"] + checks["natural_routing_provenance"]
    )
    assert checks["duplicate_no_generation"] >= 2
    assert checks["duplicate_no_tokenization"] == checks["duplicate_no_generation"]
    assert checks["owner_isolation"] >= 3
    assert checks["p1_conditional_coaching"] >= 5
    assert checks["cancellation_historical_separation"] == 1
    assert all(row.status_code != 500 for row in report.http)
    assert any(row.status_code == 409 for row in report.http)
    assert any(row.status_code == 404 for row in report.http)
    assert any(row.status_code == 401 for row in report.http)
    assert {
        "numeric_output",
        "http_status_503",
        "invalid_schema",
        "structured_numeric",
    } <= {reason for case in report.cases for reason in case.fallback_reasons}
    paths = sorted((tmp_path / "fake").glob("*.json"))
    assert {path.name for path in paths} >= {"report.json", "freeze.json"}
    stored = Report.model_validate_json((tmp_path / "fake" / "report.json").read_bytes())
    assert stored.gpu_calls == 0
    freeze = JsonDocument.model_validate_json((tmp_path / "fake" / "freeze.json").read_bytes())
    assert freeze.root["role"] == "prospective_e2e_source_and_synthetic_input_freeze"
    source_root = ROOT
    expected_files = {path.name for path in source_root.glob("e2e*.py")} | {"e2e_cases.json"}
    sources = TypeAdapter(dict[str, str]).validate_python(freeze.root["source_sha256"])
    assert {Path(name).name for name in sources if "/e2e" in name} == expected_files
    verified = JsonDocument.model_validate_json((tmp_path / "fake" / "verification.json").read_bytes())
    assert verified.root["source_hashes_unchanged"] is True
    assert (
        verified.root["report_sha256"]
        == hashlib.sha256((tmp_path / "fake" / "report.json").read_bytes()).hexdigest()
    )
    serialized = stored.model_dump_json().lower()
    assert "authorization" not in serialized
    assert "bearer " not in serialized
    assert "secretstr" not in serialized
    archive = tmp_path / "r5_evidence.zip"
    manifest = build_evidence(tmp_path / "fake", archive)
    assert {entry.path for entry in manifest.entries} == {"report.json", "freeze.json", "verification.json"}
    with ZipFile(archive) as packaged:
        assert packaged.read("report.json") == (tmp_path / "fake" / "report.json").read_bytes()


@pytest.mark.anyio
async def test_existing_output_is_never_overwritten(tmp_path: Path) -> None:
    output = tmp_path / "existing"
    output.mkdir()
    marker = output / "report.json"
    _ = marker.write_text("original", encoding="utf-8")
    with pytest.raises(FileExistsError):
        _ = await run_suite(RunConfig(output=output))
    assert marker.read_text(encoding="utf-8") == "original"


def test_remote_bundle_has_inputs_without_labels_or_previous_results(tmp_path: Path) -> None:
    target = tmp_path / "runtime.zip"
    manifest = build_bundle(target)
    assert manifest.archive_sha256 == hashlib.sha256(target.read_bytes()).hexdigest()
    forbidden_fields = {
        "purpose",
        "expected_detection",
        "expected_route",
        "fake_decision",
        "fake_confidence",
        "fake_fault",
    }
    with ZipFile(target) as archive:
        names = archive.namelist()
        assert "CHART_MANIFEST.json" in names
        assert "vendor/keyfin_chart/forecast-template.html" in names
        assert "vendor/keyfin_chart/design-tokens.json" in names
        assert not any(
            name.endswith(("labels.jsonl", "inputs.jsonl", "case_catalog.json", "report.json"))
            for name in names
        )
        assert not any("fake_v1" in name or "fake_v2" in name or "results" in name for name in names)
        catalog = TypeAdapter(tuple[JsonDocument, ...]).validate_json(
            archive.read("benchmarks/coaching/e2e/e2e_cases.json")
        )
        runtime_cases = TypeAdapter(tuple[E2ECase, ...]).validate_json(
            archive.read("benchmarks/coaching/e2e/e2e_cases.json")
        )
        assert len(catalog) == 24
        assert all(not forbidden_fields.intersection(row.root) for row in catalog)
        assert all(case.expected_route is None and case.expected_detection is None for case in runtime_cases)
        assert [case.contract_detection for case in runtime_cases] == [
            case.contract_detection for case in load_cases()
        ]
        assert all(
            row.root["question"] == original.question
            for row, original in zip(catalog, load_cases(), strict=True)
        )
        assert {case.case_id for case in runtime_cases} == {case.case_id for case in load_cases()}
        for entry in manifest.entries:
            assert hashlib.sha256(archive.read(entry.path)).hexdigest() == entry.sha256
    with pytest.raises(FileExistsError):
        _ = build_bundle(target)


@pytest.mark.anyio
async def test_gateway_reads_worker_token_without_logging_it(tmp_path: Path) -> None:
    secret = "synthetic-worker-credential-for-test"
    token_file = tmp_path / "worker.token"
    _ = token_file.write_text(secret, encoding="ascii")
    token_file.chmod(0o600)
    observed: list[httpx2.Request] = []

    async def authenticated_worker(request: httpx2.Request) -> httpx2.Response:
        observed.append(request)
        if request.headers.get("Authorization") != "Bearer " + secret:
            return httpx2.Response(401, json={"detail": "unauthorized"})
        if request.url.path == "/v1/tokenize":
            return httpx2.Response(200, content=synthetic_budget(request.content).model_dump_json())
        return httpx2.Response(
            200, json={"choices": [{"message": {"content": "확인할 자료를 알려 주세요."}}]}
        )

    upstream = httpx2.AsyncClient(transport=httpx2.MockTransport(authenticated_worker), trust_env=False)
    config = RunConfig(
        output=tmp_path,
        backend="gpu",
        model="base27",
        primary_completed=True,
        allow_gpu=True,
        upstream_token_file=token_file,
        upstream_url="http://127.0.0.1:18746",
    )
    gateway = Gateway(config, client=upstream)
    gateway.active_case = load_cases()[0]
    evidence = EvidenceInput(facts_json='{"synthetic":true}')
    body = {
        "model": "base27",
        "messages": [
            {"role": "system", "content": system_prompt("write")},
            {"role": "user", "content": user_payload(evidence)},
        ],
        "temperature": 0.0,
        "max_tokens": 256,
        "stream": False,
    }
    raw = json.dumps(body, ensure_ascii=False, indent=2).encode("utf-8")
    async with (
        upstream,
        httpx2.AsyncClient(
            transport=httpx2.ASGITransport(app=gateway.app), base_url="http://synthetic-gateway"
        ) as client,
    ):
        preflight = await client.post("/v1/tokenize", content=raw)
        assert preflight.status_code == 200
        budget = TokenBudget.model_validate_json(preflight.content)
        response = await client.post(
            "/v1/chat/completions",
            content=raw,
            headers={"X-Coaching-Prompt-Sha256": budget.prompt_sha256},
        )
    assert response.status_code == 200
    assert len(observed) == 2
    assert str(observed[0].url) == "http://127.0.0.1:18746/v1/tokenize"
    assert str(observed[1].url) == "http://127.0.0.1:18746/v1/chat/completions"
    assert observed[0].content == observed[1].content == raw
    assert observed[1].headers["X-Coaching-Prompt-Sha256"] == budget.prompt_sha256
    recorded = gateway.generations[0].model_dump_json()
    assert secret not in recorded
    assert "Authorization" not in recorded


@pytest.mark.parametrize("data", [b"", b"x" * 8193, b"a\rb", b"a\nb", b"a b", b"\xff"])
def test_worker_token_rejects_unsafe_file_without_revealing_data(tmp_path: Path, data: bytes) -> None:
    path = tmp_path / "worker.token"
    _ = path.write_bytes(data)
    path.chmod(0o600)
    config = RunConfig(
        output=tmp_path, backend="gpu", primary_completed=True, allow_gpu=True, upstream_token_file=path
    )
    with pytest.raises(ValueError, match="Worker credential"):
        _ = worker_token(config)


@pytest.mark.anyio
@pytest.mark.parametrize("fault", ["request_hash", "budget_schema"])
async def test_gateway_rejects_unverifiable_upstream_token_budget(tmp_path: Path, fault: str) -> None:
    token_file = tmp_path / "worker.token"
    _ = token_file.write_text("synthetic-worker-token", encoding="ascii")
    token_file.chmod(0o600)

    async def invalid_tokenizer(request: httpx2.Request) -> httpx2.Response:
        budget = synthetic_budget(request.content).model_copy(update={"request_sha256": "0" * 64})
        return httpx2.Response(200, content=budget.model_dump_json() if fault == "request_hash" else "{}")

    upstream = httpx2.AsyncClient(transport=httpx2.MockTransport(invalid_tokenizer), trust_env=False)
    config = RunConfig(
        output=tmp_path,
        backend="gpu",
        primary_completed=True,
        allow_gpu=True,
        upstream_token_file=token_file,
    )
    gateway = Gateway(config, client=upstream)
    gateway.active_case = load_cases()[0]
    request = GenerationRequest(
        model="synthetic",
        messages=(
            PromptMessage(role="system", content=system_prompt("write")),
            PromptMessage(role="user", content=user_payload(EvidenceInput(facts_json='{"synthetic":true}'))),
        ),
        temperature=0,
        max_tokens=256,
        stream=False,
    )
    async with (
        upstream,
        httpx2.AsyncClient(
            transport=httpx2.ASGITransport(app=gateway.app), base_url="http://synthetic-gateway"
        ) as client,
    ):
        response = await client.post("/v1/tokenize", content=request.model_dump_json())
    assert response.status_code == 502
    assert gateway.preflights[0].budget is None
    assert gateway.generations == []


def test_fake_backend_never_reads_a_worker_credential(tmp_path: Path) -> None:
    assert worker_token(RunConfig(output=tmp_path, upstream_token_file=tmp_path / "absent")) is None


@pytest.mark.anyio
@pytest.mark.parametrize("status", [200, 401])
async def test_worker_auth_observation_is_separate_from_http_contract(tmp_path: Path, status: int) -> None:
    token_file = tmp_path / "worker.token"
    _ = token_file.write_text("synthetic-wrong-worker-credential", encoding="ascii")
    token_file.chmod(0o600)
    requests: list[httpx2.Request] = []

    async def authenticated_worker(request: httpx2.Request) -> httpx2.Response:
        requests.append(request)
        expected_token = "synthetic-wrong-worker-credential" if status == 200 else "other-synthetic-token"
        if request.headers.get("Authorization") != "Bearer " + expected_token:
            return httpx2.Response(401, json={"detail": "unauthorized"})
        if request.url.path == "/v1/tokenize":
            return httpx2.Response(200, content=synthetic_budget(request.content).model_dump_json())
        body = GenerationRequest.model_validate_json(request.content)
        # The schema name survives every route/judge prompt candidate (see
        # ``ModelConfig.route_prompt_version``); the raw system instruction text
        # does not, so it is not a stable way to recognize a route or judge call.
        schema_name = (
            body.response_format.root.get("json_schema", {}).get("name")
            if body.response_format is not None
            else None
        )
        if schema_name == "judge":
            content = '{"decision":"skip","reason_code":"no_additional_concern","confidence":0.9}'
        elif schema_name == "route":
            content = '{"mode":"review"}'
        else:
            content = "확인할 자료를 알려 주세요."
        return httpx2.Response(
            200, json={"choices": [{"message": {"content": content}, "finish_reason": "stop"}]}
        )

    config = RunConfig(
        output=tmp_path / "mocked_gpu",
        backend="gpu",
        model="synthetic",
        primary_completed=True,
        allow_gpu=True,
        upstream_token_file=token_file,
    )
    client = httpx2.AsyncClient(
        transport=httpx2.MockTransport(authenticated_worker), trust_env=False, follow_redirects=False
    )
    report = await run_suite(config, upstream_client=client)
    assert requests
    assert len(requests) == len(report.preflights) + len(report.generations)
    assert all(check.passed for case in report.cases for check in case.checks)
    observation = report.model_observation
    assert observation.gpu_connection_verified is (status == 200)
    assert observation.http_status_counts == ({"200": len(report.generations)} if status == 200 else {})
    assert observation.preflight_http_status_counts == {str(status): len(report.preflights)}
    assert sum(row.accepted_llm for row in observation.operation_results) == (
        len(report.generations) if status == 200 else 0
    )
    authoritative_templates = sum(
        check.name == "authoritative_receipt_no_writer" for case in report.cases for check in case.checks
    )
    assert authoritative_templates > 0
    assert sum(row.template_results for row in observation.operation_results) == (
        authoritative_templates if status == 200 else len(report.preflights) + authoritative_templates
    )
    assert observation.fallback_counts.get("token_preflight_http_status_401", 0) == (
        0 if status == 200 else len(report.preflights)
    )
    assert "synthetic-wrong-worker-credential" not in (config.output / "report.json").read_text(
        encoding="utf-8"
    )


def test_evidence_archive_preserves_original_bytes_and_refuses_overwrite(tmp_path: Path) -> None:
    original = b'{\r\n  "original": true\r\n}'
    payloads = {"fake_v1/report.json": original, "verification_logs/check.log": b"synthetic test\n"}
    archive = tmp_path / "evidence.zip"
    manifest = write_archive(payloads, archive)
    verified, restored_bytes = verified_payloads(archive)
    assert verified == manifest
    assert restored_bytes == payloads
    destination = tmp_path / "restored"
    assert restore_archive(archive, destination) == manifest
    assert (destination / "fake_v1/report.json").read_bytes() == original
    with pytest.raises(FileExistsError, match="new"):
        _ = restore_archive(archive, destination)
    assert (destination / "fake_v1/report.json").read_bytes() == original
    with pytest.raises(FileExistsError, match="new"):
        _ = write_archive(payloads, archive)


@pytest.mark.parametrize(
    "name",
    [
        "../escape.json",
        "/absolute.json",
        "C:/drive.json",
        ".venv/lib.json",
        "store.sqlite3-wal",
        "worker.token",
        "nested/CON.log",
        "./value.json",
        "worker.token.",
        ".",
    ],
)
def test_evidence_archive_rejects_unsafe_or_private_paths(tmp_path: Path, name: str) -> None:
    with pytest.raises(ValueError, match="Unsafe"):
        _ = write_archive({name: b"never write"}, tmp_path / "bad.zip")
    assert not (tmp_path / "bad.zip").exists()


def test_evidence_archive_checks_payload_hash_before_restoring(tmp_path: Path) -> None:
    archive = tmp_path / "evidence.zip"
    manifest = write_archive({"payload.json": b"original"}, archive)
    corrupt = manifest.model_copy(
        update={"entries": (manifest.entries[0].model_copy(update={"sha256": "0" * 64}),)}
    )
    _ = archive.with_suffix(".manifest.json").write_bytes(corrupt.model_dump_json().encode("utf-8"))
    destination = tmp_path / "restored"
    with pytest.raises(ValueError, match="Archived file SHA-256"):
        _ = restore_archive(archive, destination)
    assert not destination.exists()


def test_evidence_archive_rejects_windows_filename_aliases(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unique"):
        _ = write_archive({"Report.json": b"first", "report.json": b"second"}, tmp_path / "bad.zip")
    assert not (tmp_path / "bad.zip").exists()


def report_with_cases(count: int) -> Report:
    cases = tuple(CaseOutcome(case_id=f"case-{index}", owner=f"owner-{index}", checks=(), generation_calls=0)
                  for index in range(count))
    return Report(generation_backend="fake", model="synthetic", as_of=date(2026, 9, 11),
                  api_base_url="http://127.0.0.1:1", gateway_base_url="http://127.0.0.1:2",
                  engine_commit="synthetic", gpu_calls=0,
                  model_observation=observe_model("fake", cases, (), ()), cases=cases,
                  http=(), generations=(), preflights=())


@pytest.mark.parametrize("count", [0, 1, 3])
def test_evidence_manifest_case_count_comes_from_the_report(tmp_path: Path, count: int) -> None:
    # Given an actual typed report with a variable number of recorded cases.
    report = report_with_cases(count)
    # When archiving its exact bytes.
    manifest = write_archive(
        {"report.json": report.model_dump_json().encode("utf-8")}, tmp_path / "evidence.zip",
    )
    # Then the metadata reports the case denominator in that report.
    assert manifest.case_count == count


def test_evidence_archive_rejects_manifest_report_case_count_mismatch(tmp_path: Path) -> None:
    # Given valid archive hashes but a sidecar with an incorrect case count.
    archive = tmp_path / "evidence.zip"
    manifest = write_archive({"report.json": report_with_cases(1).model_dump_json().encode("utf-8")}, archive)
    corrupt = manifest.model_copy(update={"case_count": 99})
    _ = archive.with_suffix(".manifest.json").write_text(corrupt.model_dump_json(), encoding="utf-8")
    # When verifying the evidence.
    # Then content-derived counts are checked in addition to file hashes.
    with pytest.raises(ValueError, match="case count"):
        _ = verified_payloads(archive)
