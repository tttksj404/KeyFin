"""Materialize an observed-only input bundle and physically separate target files."""

import json
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Final

from pydantic import TypeAdapter

from .baselines import BASELINES, predict
from .contracts import Case, Inputs, Prediction, Split, TrainingSeries, Truth
from .data import account_key, history, ledger_total, read_ledger, sha256

CUTOFFS: Final[dict[Split, tuple[date, ...]]] = {
    "development": (date(1998, 1, 31), date(1998, 3, 31), date(1998, 5, 31)),
    "evaluation": (date(1998, 7, 31), date(1998, 9, 30), date(1998, 11, 30)),
}


def prepare(source: Path, output: Path) -> None:
    """Freeze the protocol before targets exist; raw account IDs never leave parsing."""
    protocol = Path(__file__).with_name("PROTOCOL.md")
    frozen_hash = sha256(protocol)
    output.mkdir(parents=True, exist_ok=False)
    frozen_at = datetime.now(UTC).isoformat()
    (output / "protocol.lock.json").write_text(json.dumps({
        "protocol_sha256": frozen_hash, "created_at": frozen_at}), encoding="utf-8")
    ledger = read_ledger(source)
    eligible = sorted((account for account, opened in ledger.opened.items()
                       if account not in ledger.unsupported_accounts and opened <= date(1997, 1, 1)),
                      key=account_key)
    if len(eligible) < 301:
        raise ValueError("Insufficient eligible accounts for the frozen split")
    splits: dict[Split, list[int]] = {"evaluation": eligible[:200], "development": eligible[200:300]}
    training = tuple(TrainingSeries(account=account_key(account),
                                   daily=history(ledger.daily_cents.get(account, {}), date(1997, 12, 31)))
                     for account in eligible[300:])
    cases = []
    targets: dict[Split, list[Truth]] = {"development": [], "evaluation": []}
    for split, accounts in splits.items():
        for account in accounts:
            key = account_key(account)
            raw = ledger.daily_cents.get(account, {})
            for cutoff in CUTOFFS[split]:
                for horizon in (7, 30):
                    case_id = f"{key}:{cutoff}:{horizon}"
                    cases.append(Case(case_id=case_id, account=key, split=split, cutoff=cutoff,
                                      first_date=cutoff - timedelta(days=364),
                                      end_date=cutoff + timedelta(days=horizon), horizon=horizon,
                                      history=history(raw, cutoff)))
                    targets[split].append(Truth(case_id=case_id, actual=ledger_total(raw, cutoff, horizon)))
    bundle = Inputs(protocol_sha256=frozen_hash, training=training, cases=tuple(cases))
    (output / "model_inputs.json").write_bytes(bundle.model_dump_json().encode())
    for split, rows in targets.items():
        (output / f"{split}_truth.json").write_bytes(TypeAdapter(list[Truth]).dump_json(rows))
    predictions = output / "predictions"
    predictions.mkdir()
    baselines = [row for case in cases for row in predict(case)]
    for name in BASELINES:
        (predictions / f"{name}.predictions.json").write_bytes(TypeAdapter(list[Prediction]).dump_json(
            [row for row in baselines if row.model == name]))
    manifest = {
        "protocol_sha256": frozen_hash, "created_at": frozen_at, "source_accounts": len(ledger.opened),
        "transaction_type_counts": dict(ledger.type_counts),
        "excluded_unsupported_accounts": len(ledger.unsupported_accounts),
        "eligible_accounts": len(eligible), "training_accounts": len(training),
        "cases_by_split": dict(Counter(case.split for case in cases)),
        "currency": "CZK", "target": "gross_account_outflow", "data_provenance": "historical_bank_ledger",
        "files": {path.name: sha256(path) for path in sorted(output.glob("*.json"))},
        "source_files": {name: sha256(source / name) for name in ("trans.asc", "account.asc")},
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    if sha256(protocol) != frozen_hash:
        raise ValueError("Protocol changed while preparing data")
