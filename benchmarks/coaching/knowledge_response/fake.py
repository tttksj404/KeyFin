"""Exact fixture decisions only; fake output cannot measure a language model."""

import json

from fastapi import FastAPI

from benchmarks.coaching.knowledge_response.cases import CONCEPTS, FOLLOWUP, PERSONAL, SCOPE, UNSUPPORTED
from coaching_service.api import create_app
from coaching_service.finance_knowledge import selected_finance_wording
from coaching_service.llm_contract import EvidenceInput, Judgment, Mode, Routing, Wording
from coaching_service.settings import Settings


class SyntheticModel:
    async def route(self, evidence: EvidenceInput) -> Routing:
        case = next(
            case
            for case in (*CONCEPTS, *SCOPE, FOLLOWUP, *PERSONAL, UNSUPPORTED)
            if case.question == evidence.question
        )
        mode: Mode = "finance"
        if case.personal_topic is not None:
            mode = "personal"
        elif case.expected_status == "out_of_scope":
            mode = "other"
        return Routing(mode=mode, source="llm")

    async def judge(self, evidence: EvidenceInput) -> Judgment:
        _ = evidence
        raise RuntimeError("knowledge_suite_does_not_judge_payments")

    async def write(self, evidence: EvidenceInput) -> Wording:
        case = next(case for case in (*CONCEPTS, *SCOPE, FOLLOWUP) if case.question == evidence.question)
        return selected_finance_wording(
            json.dumps(
                {"status": case.expected_status, "fact_ids": [case.reference_id] if case.reference_id else []}
            ),
            "synthetic-knowledge-model",
            evidence=evidence,
        )


def from_environment() -> FastAPI:
    return create_app(Settings(), SyntheticModel())
