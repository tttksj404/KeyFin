# Finance knowledge catalog: contribution guide

The approved finance concept catalog lives at
`src/coaching_service/knowledge/finance.json`. It is the only source
`finance_knowledge.py` loads at runtime (`knowledge_catalog.load_catalog`), and
every entry is treated as a reviewed, cited fact — never a model-generated
statement. Do not fabricate facts or sources; every entry needs a real,
approved source.

## Entry schema

Each entry in `facts` is an object with:

| field         | type            | rule |
|---------------|-----------------|------|
| `id`          | string          | `^[a-z][a-z0-9_]{1,63}$`, unique across the catalog |
| `title`       | string          | 1–120 chars, the canonical concept name |
| `text`        | string          | 1–600 chars, the reviewed explanation |
| `source_title`| string          | 1–120 chars, human-readable source name |
| `source_url`  | string          | see **source_url rules** below |
| `aliases`     | array of string | 1–20 entries, each 1–80 chars; alternate names/synonyms used to match a question to this entry |
| `reviewed_on` | date (`YYYY-MM-DD`) | when the entry was last reviewed against its source |
| `review_due`  | date (`YYYY-MM-DD`) | must be `>= reviewed_on`; when it must be re-reviewed |
| `jurisdiction`| string          | 1–40 chars, e.g. `general_concept` |

### `source_url` rules

- Scheme must be `https`.
- Host must be one of the approved hosts in
  `coaching_service/knowledge_catalog.py` (`_APPROVED_HOSTS`) — currently
  `www.bok.or.kr`, `www.fsc.go.kr`, `www.fss.or.kr`, `www.investor.gov`,
  `www.consumerfinance.gov`, `www.finra.org`, `content.naic.org`.
- No embedded username/password, no port, no URL fragment (`#...`).

### `aliases` rules (the collision guard)

An alias should be a name a real question would use for this concept. Before
adding an entry, check that **no alias you are adding is already declared,
identically after normalization, by a different existing entry.** The
deterministic answer paths in `finance_knowledge.py`
(`_unique_alias_anchor`, `deterministic_finance_wording`,
`_subject_signal_score`) all rely on each alias uniquely identifying one
catalog subject. A duplicated alias does not make either entry answer
wrong — it silently disables the fast, template-only answer path for
*every* entry that declares that alias, forcing those questions through the
slower model-selection route instead. `scripts/validate_finance_catalog.py`
checks this automatically (see below); it is the same rule
`tests/test_catalog_integrity.py` enforces for the live catalog, with the
full reasoning documented in that test file's module docstring.

Word-level overlap between two entries' *titles* (for example "ETF" appearing
in both an `etf` entry's title and a `fund_fees` entry's title) is expected
and already handled by the selection code's category-vs-detail ranking; it is
not flagged by the validator.

## Running the validator

```
uv run --project . python scripts/validate_finance_catalog.py <path-to-catalog.json>
```

Run it against your candidate file before proposing a merge, and again
against `src/coaching_service/knowledge/finance.json` if you touch the live
file directly. It exits `0` and prints `OK` when every invariant holds, or
exits non-zero with one message per violation.

## Where new content goes first

New or edited entries do **not** go straight into `finance.json`. Add them to
`src/coaching_service/knowledge/finance_candidates.pending.json` first (same
shape as the live file: `{"version": ..., "facts": [...]}`,
starting empty). That file is never loaded by the live serving path —
`knowledge_catalog.load_catalog()` only reads `finance.json` by default (or an
explicitly configured, hash-pinned override), and
`tests/test_pending_catalog_not_served.py` proves the pending file is not
wired into any served answer.

Promotion flow:

1. Add the candidate entry to `finance_candidates.pending.json`.
2. Run `scripts/validate_finance_catalog.py` against the pending file.
3. Get human review of the entry's accuracy, source, and alias choices.
4. Only after review, move the entry from the pending file into
   `finance.json` and re-run the validator against `finance.json`, then the
   full test suite (`tests/test_catalog_integrity.py` in particular).
