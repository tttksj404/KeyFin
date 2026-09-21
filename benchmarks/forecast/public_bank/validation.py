"""Reject partial or malformed prediction grids before computing a score."""

from pathlib import Path

from pydantic import TypeAdapter

from .contracts import Inputs, Prediction
from .prepare import CUTOFFS


def validate_frozen_grid(bundle: Inputs) -> None:
    if len(bundle.training) != 2374:
        raise ValueError("Frozen training account count differs")
    for split, count in (("development", 100), ("evaluation", 200)):
        cases = [case for case in bundle.cases if case.split == split]
        accounts = {case.account for case in cases}
        expected = {(account, cutoff, horizon) for account in accounts
                    for cutoff in CUTOFFS[split] for horizon in (7, 30)}
        actual = {(case.account, case.cutoff, case.horizon) for case in cases}
        if len(accounts) != count or actual != expected or len(cases) != count * 6:
            raise ValueError("Frozen forecast account/date/horizon grid differs")
        if any(case.case_id != f"{case.account}:{case.cutoff}:{case.horizon}" for case in cases):
            raise ValueError("Case identity differs from account/date/horizon")


def validate_predictions(rows: list[dict[str, str | float]], expected: set[str]) -> list[Prediction]:
    parsed = TypeAdapter(list[Prediction]).validate_python(rows)
    ids = [row.case_id for row in parsed]
    if len(ids) != len(set(ids)) or set(ids) != expected or len({row.model for row in parsed}) != 1:
        raise ValueError("Invalid prediction grid: duplicate, missing, extra or mixed model")
    return parsed


def read_predictions(path: Path, expected: set[str]) -> list[Prediction]:
    parsed = TypeAdapter(list[Prediction]).validate_json(path.read_bytes())
    ids = [row.case_id for row in parsed]
    if len(ids) != len(set(ids)) or set(ids) != expected or len({row.model for row in parsed}) != 1:
        raise ValueError("Invalid prediction grid: duplicate, missing, extra or mixed model")
    return parsed
