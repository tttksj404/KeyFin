import json

import httpx2
import pytest
from test_llm import completion

from coaching_service.chart_wording import ChartFact, ChartFacts
from coaching_service.llm import OpenAICompatibleCoachModel
from coaching_service.llm_contract import EvidenceInput, ModelConfig


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("raw", "source"),
    [
        ('{"selected_fact_ids":["period","total","category:외식"]}', "llm"),
        ("차트에서 각 항목의 예상 소비 흐름을 어떻게 보고 싶으신지 알려 주세요.", "template"),
        ('{"selected_fact_ids":["period","total","invented:투자"]}', "template"),
        ('{"selected_fact_ids":["period","total","total"]}', "template"),
        ('{"selected_fact_ids":["period","total","category:외식"],"amount":999999}', "template"),
    ],
)
async def test_chart_fact_selection_rejects_generic_questions_and_invented_claims(
    raw: str, source: str
) -> None:
    # Given independently specified facts; model output is never a source of amounts.
    facts = ChartFacts(
        facts=(
            ChartFact(id="period", text="예산 기간은 2026-09-01부터 2026-09-30까지입니다."),
            ChartFact(id="total", text="현재 소비는 10,000원, 예상 총소비는 50,000원입니다."),
            ChartFact(id="category:외식", text="외식은 예산 대비 5,000원 초과 예측입니다."),
        ),
    )
    evidence = EvidenceInput(
        purpose="chart", question="이 차트를 설명해줘", facts_json=facts.model_dump_json()
    )
    seen: list[dict] = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        seen.append(json.loads(request.content))
        return httpx2.Response(200, content=completion(raw), request=request)

    # When the real gateway processes the proposed selection.
    async with httpx2.AsyncClient(transport=httpx2.MockTransport(respond)) as client:
        model = OpenAICompatibleCoachModel(
            ModelConfig(endpoint_url="http://127.0.0.1:18743", token_preflight=False), client=client
        )
        result = await model.write(evidence)
    # Then malformed/re-questioning outputs fall back explicitly to known facts.
    assert result.source == source
    assert result.text == " ".join(fact.text for fact in facts.facts)
    assert (result.fallback_reason is None) == (source == "llm")
    assert seen[0]["response_format"]["json_schema"]["name"] == "chart_facts"
    assert "새 질문이나 문장을 만들지" in seen[0]["messages"][0]["content"]
