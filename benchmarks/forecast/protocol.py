"""Required prediction keys for the fixed R7 common and held-out-user candidate protocol."""

from collections.abc import Sequence
from typing import Final

from .contracts import Forecast, ForecastCase

BASELINES: Final = ("fdt", "all_mean", "recent28", "weekday_shrink")
COMMON_MODELS: Final = (
    "chronos_base_daily", "chronos_base_cumulative", "chronos_previous_daily",
    "chronos_previous_cumulative", "timesfm_cumulative",
)
TUNED_MODELS: Final = ("chronos_ft64", "chronos_ft128")


def validate_prediction_grid(cases: Sequence[ForecastCase], forecasts: Sequence[Forecast]) -> None:
    """R7에서 사전에 고정한 후보마다 필요한 모델·fold·case 키를 모두 확인한다.

    공통 5개 신경망과 4개 기준선은 모든 case가 필요하다. 추가 학습 2개는 각 제외 사용자
    fold마다 다른 사용자의 개발 case와 제외 사용자의 평가 case가 필요하다. 이 목록은
    비교 대상의 계약이며 예측값·선택 결과·점수를 고정하지 않는다. 누락·추가·중복은 오류다.
    """
    if not cases:
        raise ValueError("The R7 protocol requires nonempty forecast cases")
    actual = {(row.model, row.fold, row.case_id) for row in forecasts}
    if len(actual) != len(forecasts):
        raise ValueError("Duplicate prediction key")
    expected = {(name, "common", case.case_id) for name in (*BASELINES, *COMMON_MODELS) for case in cases}
    users = {case.user for case in cases}
    expected.update(
        (name, heldout, case.case_id)
        for name in TUNED_MODELS for heldout in users for case in cases
        if (case.split == "development" and case.user != heldout)
        or (case.split == "evaluation" and case.user == heldout)
    )
    missing, unexpected = expected - actual, actual - expected
    if missing or unexpected:
        message = (
            f"Incomplete R7 prediction grid: {len(missing)} missing and {len(unexpected)} unexpected keys"
        )
        raise ValueError(message)
