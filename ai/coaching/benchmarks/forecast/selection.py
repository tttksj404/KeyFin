"""Selection and calibration read other users' July outcomes only."""

from collections.abc import Mapping, Sequence
from math import inf

from .contracts import Calibration, Family, Forecast, ForecastCase
from .scoring import excess, radius, summarize


def choose(candidates: Mapping[str, Sequence[Forecast]], truth: Mapping[str, float]) -> str:
    """개발 오차로 후보를 고르며 FDT와 전체 평균 기준선의 상한을 모두 지킨다.

    실제 소비 합계가 0이면 WAPE는 정의되지 않으므로 null을 유지한 채 선택에만 MAE를 쓴다.
    0원 자료를 빈 자료로 간주하지 않으며, 실제로 빈 입력이나 다른 분모 경계의 혼합은 거절한다.
    """
    if not candidates or any(not rows for rows in candidates.values()):
        raise ValueError("Model selection requires nonempty candidate prediction rows")
    if not {"fdt", "all_mean"} <= candidates.keys():
        raise ValueError("Model selection requires both fdt and all_mean baselines")
    scores = {name: summarize(rows, truth) for name, rows in candidates.items()}
    zero_actual = all(score.wape is None for score in scores.values())
    errors: dict[str, float] = {}
    for name, score in scores.items():
        if zero_actual:
            errors[name] = score.mae
        elif score.wape is not None:
            errors[name] = score.wape
        else:
            raise ValueError("Candidate outcomes must share the same zero-spending boundary")
    ceiling = min(errors["fdt"], errors["all_mean"])
    eligible = [name for name, error in errors.items() if error <= ceiling]
    return min(eligible, key=lambda name: (
        errors[name], scores[name].wis if scores[name].wis is not None else inf, name,
    ))


def calibrate(
    fold: str, family: Family, rows: Sequence[Forecast],
    cases: Mapping[str, ForecastCase], truth: Mapping[str, float],
) -> Calibration:
    if not rows or any(cases[row.case_id].user == fold or cases[row.case_id].split != "development"
                       for row in rows):
        raise ValueError("Calibration requires other users' development cases")
    scores = [excess(row, cases[row.case_id], truth[row.case_id]) for row in rows]
    return Calibration(fold=fold, model=rows[0].model, family=family, count=len(rows),
                       radius=radius(scores), score_case_ids=tuple(row.case_id for row in rows))
