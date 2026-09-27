"""The chart forecast path must record a real ``fdt`` Server-Timing operation.

Matching the dialogue trace path, the chart request wraps its FDT computation with
``measure_fdt`` so a caller who opts into ``X-Coaching-Trace`` sees an ``fdt;dur=``
entry distinct from ``api;dur=``. This discriminates the instrumentation added in
``coaching_service.charts.Charts.forecast`` from a plain, unmeasured
``anyio.to_thread.run_sync(self.core.engine.chart_numeric, ...)`` call.
"""


from pathlib import Path

from fastapi.testclient import TestClient
from test_api import TOKEN, TestModel, setup
from test_chart_api import chart_request, headers


def test_chart_forecast_records_fdt_server_timing(tmp_path: Path) -> None:
    # Given a chart request whose budget period has not yet ended, so the numeric
    # FDT computation actually runs.
    with TestClient(setup(tmp_path / "chart-timing.sqlite", TestModel())) as client:
        # When the caller opts into the safe latency trace.
        response = client.post(
            "/v1/charts/budget-forecast",
            json=chart_request(),
            headers={**headers("timing"), "X-Coaching-Trace": "1"},
        )
    assert response.status_code == 200, response.text
    timing = response.headers["server-timing"]
    # Then the response carries a distinct fdt timing phase, not just the total.
    assert "api;dur=" in timing
    assert "fdt;dur=" in timing
    assert TOKEN not in timing
