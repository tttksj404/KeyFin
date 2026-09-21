"""Keep model transport and accepted-result denominators separate from HTTP policy checks."""

from collections import Counter
from typing import TYPE_CHECKING, Literal

from benchmarks.coaching.e2e.e2e_contracts import (
    CaseOutcome,
    Generation,
    ModelObservation,
    OperationObservation,
    TokenPreflight,
)

if TYPE_CHECKING:
    from coaching_service.llm_contract import Operation


def observe_model(
    backend: Literal["fake", "gpu"],
    cases: tuple[CaseOutcome, ...],
    generations: tuple[Generation, ...],
    preflights: tuple[TokenPreflight, ...],
) -> ModelObservation:
    operations: tuple[Operation, ...] = ("write", "judge", "route")
    observations: list[OperationObservation] = []
    for operation in operations:
        calls = [row for row in generations if row.operation == operation]
        sources: list[str] = []
        for case in cases:
            values = {
                "write": case.wording_sources,
                "judge": case.judgment_sources,
                "route": case.routing_sources,
            }
            sources.extend(values[operation])
        observations.append(
            OperationObservation(
                operation=operation,
                generation_attempts=len(calls),
                upstream_http_200=sum(row.status_code == 200 for row in calls),
                upstream_non_200=sum(row.status_code not in {0, 200} for row in calls),
                pending=sum(row.status_code == 0 for row in calls),
                observed_results=len(sources),
                accepted_llm=sources.count("llm"),
                template_results=sources.count("template"),
                other_sources=sum(source not in {"llm", "template"} for source in sources),
            )
        )
    connected = (
        bool(generations)
        and bool(preflights)
        and all(row.status_code == 200 and row.budget is not None for row in preflights)
        and all(row.status_code == 200 for row in generations)
        and any(row.accepted_llm > 0 for row in observations)
    )
    return ModelObservation(
        backend=backend,
        generation_attempts=len(generations),
        http_status_counts=dict(sorted(Counter(str(row.status_code) for row in generations).items())),
        preflight_http_status_counts=dict(
            sorted(Counter(str(row.status_code) for row in preflights).items())
        ),
        operation_results=tuple(observations),
        fallback_counts=dict(
            sorted(Counter(reason for case in cases for reason in case.fallback_reasons).items())
        ),
        gpu_connection_verified=connected if backend == "gpu" else None,
        interpretation=(
            "Synthetic generation and byte-tokenizer stand-in only; accepted llm sources do not "
            "demonstrate GPU model use or serving-tokenizer measurements."
            if backend == "fake"
            else "Connection verified means all attempted requests returned HTTP 200 and at least one "
            "model result was accepted. This is not a model-quality score; inspect each operation's "
            "accepted and template result denominators and fallback reasons."
        ),
    )
