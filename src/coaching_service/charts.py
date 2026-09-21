"""One owner-scoped input produces an auditable chart and GPU-backed wording."""

import time
from datetime import date
from typing import assert_never
from uuid import uuid4

import anyio

from coaching_service.chart_contract import ChartReceipt, ChartRequest, ChartResponse, budget_period
from coaching_service.chart_projection import Budgets, ChartInputs, project_chart
from coaching_service.chart_rendering import renderer_manifest
from coaching_service.chart_wording import chart_evidence
from coaching_service.coaching import CoachingCore
from coaching_service.engine import ENGINE_COMMIT
from coaching_service.llm_contract import Wording
from coaching_service.repository import Mutation, write
from coaching_service.request_timing import measure_fdt, run_measured_fdt
from coaching_service.schemas import JsonDocument
from coaching_service.store import Operation


class Charts:
    """소유자별 입력→FDT 수치→AI 설명→차트·계산 근거 저장을 묶는 호출 흐름."""

    def __init__(self, core: CoachingCore) -> None:
        self.core: CoachingCore = core

    async def forecast(self, operation: Operation, request: ChartRequest) -> JsonDocument:
        """인라인 또는 저장된 Twin에서 차트를 만들고 검증 완료 후에만 저장한다.

        종료된 기간은 관측값만 반환하며 엔진 예측·LLM을 호출하지 않는다. 계산·문장·
        렌더러 출처가 모두 준비되기 전의 422/502는 차트와 완료 응답을 남기지 않는다.
        """
        async def action() -> Mutation:
            twin = (
                await anyio.to_thread.run_sync(
                    self.core.engine.create, request.data, operation.owner, limiter=self.core.engine_limit
                )
                if request.data is not None
                else await self.core.twin(operation.owner)
            )
            identity = await anyio.to_thread.run_sync(self.core.engine.identity, twin)
            period = budget_period(request.period_start, date.fromisoformat(identity.as_of))
            transactions = await anyio.to_thread.run_sync(self.core.engine.transactions, twin)
            budgets = Budgets.model_validate(twin.root.get("snapshot") or {})
            numeric_request = None
            numeric_result = None
            daily_prediction = None
            observation_audit = None
            if period.as_of < period.horizon_end:
                numeric_request = JsonDocument(
                    {
                        "mode": "forecast",
                        "paths": request.paths,
                        "seed": request.seed,
                        "horizon_days": (period.horizon_end - period.as_of).days,
                    }
                )
                # Match dialogue traces: one chart forecast records its real FDT
                # operation separately from model generation and HTML rendering.
                with measure_fdt():
                    numeric_result, daily_prediction = await anyio.to_thread.run_sync(
                        run_measured_fdt,
                        lambda: self.core.engine.chart_numeric(twin, numeric_request),
                        limiter=self.core.engine_limit,
                    )
            else:
                observation_audit = await anyio.to_thread.run_sync(
                    self.core.engine.observation_audit, twin, limiter=self.core.engine_limit
                )
            inputs = ChartInputs(
                id=uuid4().hex,
                question=request.question,
                period=period,
                transactions=transactions,
                budgets=budgets,
                paths=request.paths,
                seed=request.seed,
                observation_audit=observation_audit,
            )
            chart = project_chart(inputs, numeric_result, daily_prediction)
            if numeric_result is None:
                wording = Wording(
                    text="예산 기간이 종료되어 입력에 기록된 소비를 표시합니다."
                    + (
                        " " + chart.meta.quality.summary
                        if chart.meta.quality and chart.meta.quality.summary
                        else ""
                    ),
                    source="template",
                    model="not_called",
                    fallback_reason="period_complete",
                )
            else:
                # 모델에는 선택 가능한 근거 ID를 보낸다. 원본 시계열은 receipt에 남기고
                # LLM이 금액·날짜를 새로 작성하거나 화면 수치를 바꾸지 못하게 한다.
                wording = await self.core.model.write(chart_evidence(chart))
            match wording.source:
                case "llm":
                    language = "AI 근거 선택 · 검증 문장"
                case "template":
                    language = "정형 안내 · AI 문장 미채택"
                case unreachable:
                    assert_never(unreachable)
            is_seed = bool(transactions) and all(row.source == "SEED" for row in transactions)
            source = "SEED 데이터" if is_seed else "입력 거래"
            meta = chart.meta.model_copy(update={"source_label": f"{source} · FDT 계산 · {language}"})
            chart = chart.model_copy(update={"answer": wording.text, "meta": meta})
            result = ChartResponse(
                id=chart.id,
                chart=chart,
                wording=wording,
                created_at=time.time(),
                receipt=ChartReceipt(
                    engine_commit=ENGINE_COMMIT,
                    renderer_commit=renderer_manifest().commit,
                    identity=identity,
                    numeric_request=numeric_request,
                    numeric_result=numeric_result,
                    daily_forecast=daily_prediction,
                    observation_audit=observation_audit,
                ),
            )
            return Mutation(
                result=JsonDocument.model_validate_json(result.model_dump_json(by_alias=True)),
                writes=(write("chart/" + result.id, result),),
            )

        return await self.core.repository.mutate(operation, action)
