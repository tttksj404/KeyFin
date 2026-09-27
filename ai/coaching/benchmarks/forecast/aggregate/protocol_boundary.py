"""Enforce the frozen study at evaluation entry, independently of the preparation writer."""

from collections import Counter
from datetime import datetime
from typing import Final

from benchmarks.forecast.public_bank.contracts import Frozen
from benchmarks.forecast.public_bank.data import EXPECTED

from .contracts import Inputs
from .prepare import CUTOFFS

REQUIRED: Final = frozenset({
    "protocol.lock.json", "model_inputs.json", "arithmetic.json",
    "development_truth.json", "calibration_truth.json", "evaluation_truth.json",
})
ACCOUNTS: Final = {"development": 200, "calibration": 200, "evaluation": 400}
CASES: Final = {"development": 1200, "calibration": 400, "evaluation": 2400}


class Manifest(Frozen):
    protocol_sha256: str
    training_accounts: int
    accounts_by_split: dict[str, int]
    cases_by_split: dict[str, int]
    previous_eval_dev_accounts_excluded: int
    evaluation_future_used_in_r12: bool
    old_training_history_overlap: bool
    source_files: dict[str, str]
    files: dict[str, str]


class ProtocolLock(Frozen):
    sha256: str
    created_at: datetime


def validate_manifest(manifest: Manifest) -> None:
    """Reject omitted hashes even when the remaining declared files are unchanged."""
    if set(manifest.files) != REQUIRED or manifest.source_files != EXPECTED:
        raise ValueError("Frozen artifacts or original source hashes are incomplete")
    if (manifest.accounts_by_split != ACCOUNTS or manifest.cases_by_split != CASES
            or manifest.previous_eval_dev_accounts_excluded != 300
            or manifest.evaluation_future_used_in_r12 or not manifest.old_training_history_overlap):
        raise ValueError("Study partitions or prior evidence declarations differ from protocol")


def validate_inputs(inputs: Inputs, manifest: Manifest) -> None:
    """Reject relabeled future origins and missing per-account horizons before opening outcomes."""
    for row in inputs.cases:
        if row.cutoff not in CUTOFFS[row.split]:
            raise ValueError("Case date differs from its frozen partition")
    if (len(inputs.training) != manifest.training_accounts
            or Counter(row.split for row in inputs.cases) != CASES):
        raise ValueError("Input counts differ from frozen manifest")
    for split, dates in CUTOFFS.items():
        rows = tuple(row for row in inputs.cases if row.split == split)
        accounts = {row.account for row in rows}
        expected = {(account, day, h) for account in accounts for day in dates for h in (7, 30)}
        actual = {(row.account, row.cutoff, row.horizon) for row in rows}
        if len(accounts) != ACCOUNTS[split] or actual != expected or len(actual) != len(rows):
            raise ValueError("Account origins and horizons are incomplete or duplicated")
