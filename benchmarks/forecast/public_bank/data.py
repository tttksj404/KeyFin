"""Read only permitted columns and aggregate currency in integer minor units."""

import csv
import hashlib
from collections import Counter, defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Final

EXPECTED: Final = {
    "trans.asc": "75ab2f39df9d79d79c5c900de90ddd28248b689f214598ac9fa2ff0f574a70d2",
    "account.asc": "58d7f50abd72e9b1a5568346f74bb54cd71224ee1db9f09a27d7cac563f38cc6",
}


@dataclass(frozen=True, slots=True)
class Ledger:
    opened: Mapping[int, date]
    daily_cents: Mapping[int, Mapping[date, int]]
    unsupported_accounts: frozenset[int]
    type_counts: Mapping[str, int]


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def source_date(value: str) -> date:
    return date(1900 + int(value[:2]), int(value[2:4]), int(value[4:6]))


def read_ledger(directory: Path) -> Ledger:
    for name, expected in EXPECTED.items():
        if sha256(directory / name) != expected:
            raise ValueError("Source does not match the frozen protocol hash")
    with (directory / "account.asc").open(encoding="ascii", newline="") as stream:
        accounts = [(int(row["account_id"]), source_date(row["date"]))
                    for row in csv.DictReader(stream, delimiter=";")]
    if len(dict(accounts)) != len(accounts):
        raise ValueError("Duplicate account in source")
    opened = dict(accounts)
    daily: defaultdict[int, defaultdict[date, int]] = defaultdict(lambda: defaultdict(int))
    unsupported: set[int] = set()
    counts: Counter[str] = Counter()
    with (directory / "trans.asc").open(encoding="ascii", newline="") as stream:
        for row in csv.DictReader(stream, delimiter=";"):
            account = int(row["account_id"])
            observed = source_date(row["date"])
            kind = row["type"]
            amount = Decimal(row["amount"]) * 100
            if not amount.is_finite() or amount < 0 or amount != amount.to_integral_value():
                raise ValueError("Invalid source amount")
            if account not in opened or observed < opened[account]:
                raise ValueError("Transaction precedes account opening or has unknown account")
            counts[kind] += 1
            if kind not in {"PRIJEM", "VYDAJ"}:
                unsupported.add(account)
            if kind == "VYDAJ":
                daily[account][observed] += int(amount)
    return Ledger(opened, dict(daily), frozenset(unsupported), dict(counts))


def ledger_total(ledger: Mapping[date, int], cutoff: date, horizon: int) -> float:
    """Independent raw-ledger target; does not call a forecasting function."""
    end = cutoff + timedelta(days=horizon)
    return sum(cents for day, cents in ledger.items() if cutoff < day <= end) / 100


def history(ledger: Mapping[date, int], cutoff: date) -> tuple[float, ...]:
    first = cutoff - timedelta(days=364)
    return tuple(ledger.get(first + timedelta(days=index), 0) / 100 for index in range(365))


def account_key(account: int) -> str:
    return hashlib.sha256(f"berka-r12-v1:{account}".encode("ascii")).hexdigest()
