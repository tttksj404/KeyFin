"""Merge gate for the finance knowledge catalog: run before adding entries.

Validates an arbitrary catalog JSON file (the live corpus, or a candidate/pending
file) against the same invariants tests/test_catalog_integrity.py enforces for
the live catalog:

  (1a) schema shape: unique ids, required fields present & well-typed,
       a plausible https source_url, and reviewed_on/review_due present and
       ordered. Most of this is already enforced by ``KnowledgeCatalog``'s own
       pydantic validators (see coaching_service/knowledge_catalog.py); this
       script surfaces the same failure as a clear, scriptable exit code
       instead of a raised ValidationError traceback.

  (1b) no two distinct entries may declare the identical alias string (after
       ``compact()``, length >= 2). This is the exact collision rule derived
       from finance_knowledge.py's ``_ALIAS_OWNERS``/``_anchor_terms``: a
       deterministic fast path only trusts an alias once it can prove that
       alias names exactly one catalog subject. A duplicated alias silently
       disables that subject match for every fact that declares it (see the
       long-form rationale in tests/test_catalog_integrity.py). Word-level
       overlap between different facts' TITLES (e.g. "ETF" appearing in both
       ``etf`` and ``fund_fees``) is a separate, intentionally tolerated
       signal handled elsewhere in the selection code and is NOT flagged here.

Usage:
    uv run --project . python scripts/validate_finance_catalog.py <path-to-catalog.json>

Exits 0 and prints "OK" on success; exits 1 with a clear message per violation
otherwise. Never mutates the file it validates.
"""

from __future__ import annotations

import sys
from pathlib import Path

from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coaching_service.finance_knowledge import _anchor_terms
from coaching_service.knowledge_catalog import KnowledgeCatalog


def collect_alias_collisions(catalog: KnowledgeCatalog) -> dict[str, tuple[str, ...]]:
    """Reproduce finance_knowledge._ALIAS_OWNERS for an arbitrary candidate catalog."""
    owners: dict[str, set[str]] = {}
    for fact in catalog.facts:
        for term in _anchor_terms(fact):
            owners.setdefault(term, set()).add(fact.id)
    return {term: tuple(sorted(ids)) for term, ids in owners.items() if len(ids) > 1}


def validate(path: Path) -> list[str]:
    """Return a list of violation messages; an empty list means the file passes."""
    try:
        raw = path.read_bytes()
    except OSError as error:
        return [f"cannot read {path}: {error}"]

    try:
        catalog = KnowledgeCatalog.model_validate_json(raw)
    except ValidationError as error:
        return [f"schema validation failed for {path}:\n{error}"]

    errors: list[str] = []

    ids = [fact.id for fact in catalog.facts]
    if len(set(ids)) != len(ids):
        duplicates = sorted({fid for fid in ids if ids.count(fid) > 1})
        errors.append(f"duplicate ids: {duplicates}")

    collisions = collect_alias_collisions(catalog)
    if collisions:
        for term, owners in sorted(collisions.items()):
            errors.append(f"alias collision: {term!r} is declared by more than one entry: {owners}")

    return errors


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: validate_finance_catalog.py <path-to-catalog.json>", file=sys.stderr)
        return 2
    path = Path(argv[1])
    errors = validate(path)
    if errors:
        print(f"FAIL: {path} violates {len(errors)} invariant(s):", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1
    entry_count = len(KnowledgeCatalog.model_validate_json(path.read_bytes()).facts)
    print(f"OK: {path} passes all catalog invariants ({entry_count} entries)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
