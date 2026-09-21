"""Deterministic injected model for transport tests; never evidence of GPU quality."""

from typing import Final

from fastapi import FastAPI

from coaching_service.api import create_app
from coaching_service.finance_knowledge import selected_finance_wording
from coaching_service.llm_contract import EvidenceInput, Judgment, Mode, Routing, Wording
from coaching_service.settings import Settings

QUESTIONS: Final[dict[str, Mode]] = {
    "복리가 뭐야?": "finance",
    "이번 달 말까지 잔액 예측해줘": "forecast",
    "이번 달 위험을 알려줘": "risk",
    "이번 달 내 지출은 얼마야?": "history",
    "취소한 결제 이후 이번 달 위험을 알려줘": "risk",
}


class SyntheticModel:
    async def route(self, evidence: EvidenceInput) -> Routing:
        return Routing(mode=QUESTIONS[evidence.question], source="llm")

    async def judge(self, evidence: EvidenceInput) -> Judgment:
        _ = evidence
        return Judgment(decision="coach", reason_code="context_concern", confidence=0.9, source="llm")

    async def write(self, evidence: EvidenceInput) -> Wording:
        if evidence.purpose == "finance":
            return selected_finance_wording(
                '{"status":"answered","fact_ids":["compound_interest"]}',
                "synthetic-flow-model",
            )
        return Wording(
            text="확인된 내역과 예상 흐름을 함께 살펴보세요.", source="llm", model="synthetic-flow-model"
        )


def from_environment() -> FastAPI:
    return create_app(Settings(), SyntheticModel())
