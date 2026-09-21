"""One-way model selection: this module receives development observations only."""

from collections.abc import Mapping
from dataclasses import dataclass

from benchmarks.forecast.public_bank.baselines import BASELINES
from benchmarks.forecast.public_bank.contracts import Frozen, Truth

from .arithmetic import EXTRA, NEURAL
from .contracts import Case, Prediction


@dataclass(frozen=True, slots=True)
class Bank:
    """Complete named model forecasts over the same case IDs."""

    rows: Mapping[str, Mapping[str, Prediction]]


class Choice(Frozen):
    selected: str
    baseline: str
    development_mae: dict[str, float]


def candidate_bank(cases: tuple[Case, ...], forecasts: tuple[Prediction, ...]) -> Bank:
    """Reject missing/extra/duplicate predictions before adding the six frozen blends."""
    names = BASELINES + EXTRA + NEURAL
    expected = {row.case_id for row in cases}
    if not expected or len(expected) != len(cases):
        raise ValueError("Cases must be nonempty and unique")
    grouped: dict[str, dict[str, Prediction]] = {name: {} for name in names}
    for row in forecasts:
        if row.model not in grouped or row.case_id not in expected or row.case_id in grouped[row.model]:
            raise ValueError("Unexpected or duplicate candidate prediction")
        grouped[row.model][row.case_id] = row
    if any(set(rows) != expected for rows in grouped.values()):
        raise ValueError("Incomplete candidate predictions")
    for neural in NEURAL:
        for baseline in ("calendar_median", "recent90"):
            name = f"blend:{neural}:{baseline}"
            values = {}
            for case in cases:
                point = (grouped[neural][case.case_id].point + grouped[baseline][case.case_id].point) / 2
                values[case.case_id] = Prediction(case_id=case.case_id, model=name,
                                                  point=point, lower=point, upper=point)
            grouped[name] = values
    return Bank(grouped)


def choose(cases: tuple[Case, ...], outcomes: tuple[Truth, ...], bank: Bank) -> dict[int, Choice]:
    """Reject holdout cases even if the caller accidentally supplies their outcomes."""
    if not cases or any(case.split != "development" for case in cases):
        raise ValueError("Selection accepts development cases only")
    truth = {row.case_id: row.actual for row in outcomes}
    if len(truth) != len(outcomes) or set(truth) != {row.case_id for row in cases}:
        raise ValueError("Development targets are incomplete, duplicate, or unexpected")
    choices: dict[int, Choice] = {}
    for horizon in (7, 30):
        selected = [case for case in cases if case.horizon == horizon]
        if not selected:
            raise ValueError("Development must cover both horizons")
        scores = {name: sum(abs(rows[case.case_id].point - truth[case.case_id])
                            for case in selected) / len(selected) for name, rows in bank.rows.items()}
        choices[horizon] = Choice(selected=min(scores, key=lambda name: (scores[name], name)),
                                  baseline=min(BASELINES, key=lambda name: (scores[name], name)),
                                  development_mae=scores)
    return choices
