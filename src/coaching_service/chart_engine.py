"""Capture daily means from the same pinned-engine simulation as its P50 result."""

from typing import TYPE_CHECKING

import numpy as np
from fdt import Engine, Twin
from fdt.simulation import RandomBundle, Simulation
from pydantic import JsonValue
from typing_extensions import override

from coaching_service.chart_contract import DailyForecast, DailyPoint
from coaching_service.errors import ServiceError

if TYPE_CHECKING:
    from numpy.typing import NDArray


def daily_forecast(sim: Simulation, paths: int) -> DailyForecast:
    """같은 시뮬레이션의 날짜별 7개 봉투 평균을 원 단위 일별 막대로 옮긴다.

    0원인 날도 보존하며 Python round의 짝수 쪽 반올림을 적용한다.
    평균의 합과 누적 분포의 P50은 다른 통계이므로 서로 맞추어 보정하지 않는다.
    """
    days = len(sim.dates)
    if (
        paths < 1
        or days < 1
        or sim.by_envelope.shape != (paths, days, 7)
        or sim.consumption.shape != (paths, days)
        or sim.pending.shape != (paths, days)
    ):
        raise ServiceError("chart_daily_shape_mismatch", 502)
    if any(
        not np.isfinite(values).all() or (values < 0).any()
        for values in (sim.by_envelope, sim.consumption, sim.pending)
    ):
        raise ServiceError("chart_daily_invalid_amount", 502)
    # 미분류 pending은 총소비에는 있지만 7개 봉투에는 없다. 그 차이만 허용하고
    # 모양·음수·비유한 수·금액 보존이 깨지면 임의로 메우지 않고 502로 중단한다.
    difference: NDArray[np.int64] = sim.by_envelope.sum(axis=2) + sim.pending - sim.consumption
    if difference.any():
        raise ServiceError("chart_daily_consumption_mismatch", 502)
    means: NDArray[np.float64] = sim.by_envelope.mean(axis=0)
    return DailyForecast(
        points=tuple(
            DailyPoint(date=day, amounts_krw=tuple(round(means.item(i, j)) for j in range(7)))
            for i, day in enumerate(sim.dates)
        )
    )


class ChartEngine(Engine):
    """고정된 FDT의 _base에서 사용한 Simulation을 읽는 차트 어댑터.

    상위 구현이 만든 결과와 검증은 그대로 반환하고 일별 평균만 함께 보관한다.
    이 연결 지점의 호환성은 엔진 원본 해시와 계약 테스트로 확인한다.
    """

    def __init__(self, twin: Twin) -> None:
        super().__init__(twin)
        self.daily: DailyForecast | None = None

    @override
    def _base(self, req: dict[str, JsonValue], bundle: RandomBundle, sim: Simulation) -> dict[str, JsonValue]:
        result = super()._base(req, bundle, sim)
        self.daily = daily_forecast(sim, bundle.paths)
        return result
