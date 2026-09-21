"""Authenticated JSON and HTML views of the same saved chart result."""

from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.responses import HTMLResponse

from coaching_service.auth import Authenticate
from coaching_service.chart_contract import ChartRequest, ChartResponse
from coaching_service.chart_rendering import render_chart
from coaching_service.charts import Charts
from coaching_service.coaching import CoachingCore
from coaching_service.http_contracts import RequestKey, operation
from coaching_service.repository import document
from coaching_service.schemas import Identifier


def register_charts(app: FastAPI, core: CoachingCore, auth: Authenticate) -> None:
    charts = Charts(core)

    async def forecast(
        body: ChartRequest, key: RequestKey, owner: Annotated[str, Depends(auth.backend)]
    ) -> ChartResponse:
        result = await charts.forecast(operation(owner, "budget-chart", key, document(body)), body)
        return ChartResponse.model_validate(result.root)

    async def saved(chart_id: Identifier, owner: Annotated[str, Depends(auth.user)]) -> ChartResponse:
        return ChartResponse.model_validate_json(await core.repository.load(owner, "chart/" + chart_id))

    async def html(chart_id: Identifier, owner: Annotated[str, Depends(auth.user)]) -> HTMLResponse:
        chart = await saved(chart_id, owner)
        return HTMLResponse(
            render_chart(chart.chart),
            headers={
                "Content-Security-Policy": "default-src 'none'; script-src 'unsafe-inline'; "
                "style-src 'unsafe-inline'; img-src data:; frame-ancestors 'none'; base-uri 'none'",
            },
        )

    # Reading/retrying a prior receipt must not add newly introduced default metadata.
    app.add_api_route(
        "/v1/charts/budget-forecast",
        forecast,
        methods=["POST"],
        response_model=ChartResponse,
        response_model_exclude_unset=True,
    )
    app.add_api_route(
        "/v1/charts/{chart_id}",
        saved,
        methods=["GET"],
        response_model=ChartResponse,
        response_model_exclude_unset=True,
    )
    app.add_api_route("/v1/charts/{chart_id}/html", html, methods=["GET"], response_class=HTMLResponse)
