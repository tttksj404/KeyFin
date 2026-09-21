"""Freeze new held-out outcomes after the protocol, without exporting raw account IDs."""

import hashlib
import json
import sys
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Final

from pydantic import TypeAdapter

from benchmarks.forecast.public_bank.contracts import TrainingSeries, Truth
from benchmarks.forecast.public_bank.data import account_key, history, ledger_total, read_ledger, sha256

from .arithmetic import predict
from .contracts import Case, Inputs, Prediction, Split

CUTOFFS: Final[dict[Split, tuple[date, ...]]] = {
    "development": (date(1998, 1, 31), date(1998, 3, 31), date(1998, 5, 31)),
    "calibration": (date(1998, 6, 30),),
    "evaluation": (date(1998, 7, 31), date(1998, 9, 30), date(1998, 11, 30)),
}


def new_key(account: int) -> str:
    return hashlib.sha256(f"berka-r15-v1:{account}".encode("ascii")).hexdigest()


def prepare(source: Path, output: Path) -> None:
    """Only this preparation boundary reads the complete raw source for disjoint files."""
    protocol = Path(__file__).with_name("PROTOCOL.md")
    frozen_hash = sha256(protocol)
    output.mkdir(parents=True, exist_ok=False)
    _ = (output / "protocol.lock.json").write_text(json.dumps({
        "sha256": frozen_hash, "created_at": datetime.now(UTC).isoformat(),
    }), encoding="utf-8")
    _ = (output / "PROTOCOL.md").write_bytes(protocol.read_bytes())
    ledger = read_ledger(source)
    old_order = sorted((account for account, opened in ledger.opened.items()
                        if account not in ledger.unsupported_accounts and opened <= date(1997, 1, 1)),
                       key=account_key)
    pool = sorted(old_order[300:], key=new_key)
    if len(pool) < 801:
        raise ValueError("Not enough accounts outside the previous development/evaluation")
    splits: dict[Split, list[int]] = {
        "development": pool[:200], "calibration": pool[200:400], "evaluation": pool[400:800],
    }
    training = tuple(TrainingSeries(account=new_key(account),
                                   daily=history(ledger.daily_cents.get(account, {}), date(1997, 12, 31)))
                     for account in pool[800:])
    cases: list[Case] = []
    forecasts: list[Prediction] = []
    truth: dict[Split, list[Truth]] = {name: [] for name in CUTOFFS}
    for split, accounts in splits.items():
        for account in accounts:
            key = new_key(account)
            raw = ledger.daily_cents.get(account, {})
            for cutoff in CUTOFFS[split]:
                for horizon in (7, 30):
                    row = Case(case_id=f"{key}:{cutoff}:{horizon}", account=key, split=split,
                               cutoff=cutoff, first_date=cutoff - timedelta(days=364),
                               end_date=cutoff + timedelta(days=horizon), horizon=horizon,
                               history=history(raw, cutoff))
                    cases.append(row)
                    forecasts.extend(predict(row))
                    truth[split].append(Truth(case_id=row.case_id, actual=ledger_total(raw, cutoff, horizon)))
    bundle = Inputs(protocol_sha256=frozen_hash, training=training, cases=tuple(cases))
    _ = (output / "model_inputs.json").write_text(bundle.model_dump_json(), encoding="utf-8")
    _ = (output / "arithmetic.json").write_bytes(TypeAdapter(list[Prediction]).dump_json(forecasts))
    for split, rows in truth.items():
        _ = (output / f"{split}_truth.json").write_bytes(TypeAdapter(list[Truth]).dump_json(rows))
    manifest = {
        "protocol_sha256": frozen_hash, "training_accounts": len(training),
        "accounts_by_split": {key: len(value) for key, value in splits.items()},
        "cases_by_split": dict(Counter(row.split for row in cases)),
        "previous_eval_dev_accounts_excluded": 300,
        "evaluation_future_used_in_r12": False, "old_training_history_overlap": True,
        "source_files": {name: sha256(source / name) for name in ("trans.asc", "account.asc")},
        "files": {path.name: sha256(path) for path in output.glob("*.json")},
    }
    if sha256(protocol) != frozen_hash:
        raise ValueError("Protocol changed during preparation")
    _ = (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    _ = sys.stdout.write(json.dumps({key: value for key, value in manifest.items() if key != "files"}) + "\n")
    _ = sys.stdout.write("AGGREGATE_PREPARED\n")


if __name__ == "__main__":
    prepare(Path(sys.argv[1]), Path(sys.argv[2]))
