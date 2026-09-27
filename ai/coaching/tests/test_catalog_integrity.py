# ruff: noqa: INP001
"""Collision-guard invariants the LIVE finance catalog must hold for ANY future entry.

These invariants are derived from reading ``finance_knowledge.py``, not guessed:

* ``_ALIAS_OWNERS`` (built once from every fact's ``_anchor_terms``) is the single
  source of truth every deterministic/narrative shortcut relies on to prove an
  alias names exactly one catalog subject:

  - ``_unique_alias_matches`` only accepts an alias occurrence when
    ``_ALIAS_OWNERS.get(term) == frozenset({fact.id})``; a shared alias is
    dropped from *every* fact's candidate set, not just the new one.
  - ``deterministic_finance_wording``'s exact-definition fast path
    (``"제목이 뭐야?"`` style questions) adds a fact whenever one of its raw
    aliases prefixes the question; two facts sharing the identical alias text
    both get added, ``len(matched) != 1``, and the whole fast path silently
    stops answering a question it used to answer directly.
  - ``_subject_signal_score``'s two-character "paired alias" exception
    (``예금`` + ``적금`` style) only awards points for a short alias that is
    ``_ALIAS_OWNERS``-unique to that fact; a duplicated short alias goes dark
    for every fact that declares it.

  So the one concrete, code-verified collision rule is: **no two distinct
  facts may declare the identical alias string (after ``compact()``,
  length >= 2)**. This is exactly what ``_anchor_terms``/``_ALIAS_OWNERS``
  compute, so this test reuses those private helpers instead of re-deriving
  the normalization by hand.

* Word-level overlap in **titles** (for example ``ETF`` appearing inside both
  the ``etf`` and ``fund_fees``/``nav_market_price`` titles, or ``원리금``
  inside both ``amortization`` and ``loan_principal_interest``) is a SEPARATE,
  intentionally non-singleton signal (``_COMPONENT_OWNERS``). ``_unique_alias_anchor``
  explicitly resolves this category-vs-detail case with its own ranked
  ``component_hits`` comparison (see its docstring: "ETF + 비용" must reach the
  fee explanation, not a generic ETF description). Treating a
  ``_COMPONENT_OWNERS`` collision as a hard failure would flag *intended*
  behavior, so it is not part of the encoded invariant below (this is stated
  explicitly, per the task instructions, rather than silently ignored).

Finding on the current 27-entry catalog: **no (b) alias collision exists.**
``_ALIAS_OWNERS`` is a clean bijection (every anchor term maps to exactly one
fact) for all 27 live entries. The only non-singleton terms live in
``_COMPONENT_OWNERS`` (``etf``, ``원리금``), and those are the intentional
category/detail overlaps described above, not violations.
"""

from __future__ import annotations

from urllib.parse import urlsplit

import pytest

from coaching_service.finance_knowledge import (
    _ALIAS_OWNERS,
    FACTS,
    _anchor_terms,
    deterministic_finance_wording,
    finance_evidence,
)
from coaching_service.knowledge_catalog import load_catalog

_CATALOG = load_catalog()


# --- (a) schema invariants -------------------------------------------------


def test_catalog_has_the_expected_live_entry_count() -> None:
    assert len(FACTS) == 27


def test_all_ids_are_unique() -> None:
    ids = [fact.id for fact in FACTS]
    assert len(set(ids)) == len(ids)


@pytest.mark.parametrize("fact", FACTS, ids=[fact.id for fact in FACTS])
def test_required_fields_are_present_and_well_typed(fact: object) -> None:
    assert isinstance(fact.id, str)
    assert fact.id
    assert isinstance(fact.title, str)
    assert fact.title.strip()
    assert isinstance(fact.text, str)
    assert fact.text.strip()
    assert isinstance(fact.source_title, str)
    assert fact.source_title.strip()
    assert isinstance(fact.source_url, str)
    assert fact.source_url.strip()
    assert isinstance(fact.aliases, tuple)
    assert fact.aliases
    assert all(isinstance(alias, str) and alias.strip() for alias in fact.aliases)
    assert fact.jurisdiction.strip()


@pytest.mark.parametrize("fact", FACTS, ids=[fact.id for fact in FACTS])
def test_source_url_is_a_plausible_https_url(fact: object) -> None:
    parsed = urlsplit(fact.source_url)
    assert parsed.scheme == "https"
    assert parsed.hostname
    assert parsed.username is None
    assert parsed.password is None
    assert parsed.port is None
    assert not parsed.fragment


@pytest.mark.parametrize("fact", FACTS, ids=[fact.id for fact in FACTS])
def test_review_dates_are_present_and_ordered(fact: object) -> None:
    assert fact.reviewed_on is not None
    assert fact.review_due is not None
    assert fact.reviewed_on <= fact.review_due


# --- (b) alias/title collision guard ---------------------------------------


def test_no_alias_is_shared_between_two_distinct_facts() -> None:
    """The exact rule proven above: every ``_ALIAS_OWNERS`` term is a singleton.

    A shared alias silently disables the deterministic fast path for every
    fact that declares it (see module docstring). The current 27 entries do
    not violate this: this assertion should PASS today. If a future catalog
    addition breaks it, this test must fail loudly rather than be loosened.
    """
    collisions = {term: owners for term, owners in _ALIAS_OWNERS.items() if len(owners) > 1}
    assert collisions == {}, f"unsafe alias collisions (fast path silently disabled): {collisions}"


def test_anchor_terms_cover_every_declared_alias_of_length_two_or_more() -> None:
    """Sanity check that the reused helper actually inspects every fact's aliases."""
    for fact in FACTS:
        terms = _anchor_terms(fact)
        expected = {alias.strip() for alias in fact.aliases if len(alias.strip()) >= 2}
        # Every sufficiently long alias contributes at least one anchor term;
        # this only guards against an accidental empty-set regression in the
        # helper itself, not against catalog content.
        assert terms or not expected


# --- (c) reachability: every entry still routes to itself ------------------


@pytest.mark.parametrize("fact", FACTS, ids=[fact.id for fact in FACTS])
def test_every_entry_is_reachable_through_its_own_title(fact: object) -> None:
    """Canonical ``"<title> 뭐야?"`` probe must resolve to that exact entry.

    This proves the entry is actually reachable end-to-end (retrieval +
    deterministic selection), not merely present in the JSON file.
    """
    question = fact.title + " 뭐야?"
    evidence = finance_evidence(question)
    wording = deterministic_finance_wording(evidence)
    assert wording is not None, f"{fact.id} did not resolve deterministically for its own title probe"
    assert wording.reference_ids == (fact.id,)
    assert wording.answer_status == "answered"
