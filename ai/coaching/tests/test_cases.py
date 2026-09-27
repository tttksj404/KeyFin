# ruff: noqa: INP001
"""R4 labels are external and justified by actual engine and payment contracts."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from typing import TYPE_CHECKING

import pytest

from benchmarks.coaching.cases import build_cases, load_catalog
from coaching_service.evidence import context_limited
from coaching_service.llm_prompt import user_payload

if TYPE_CHECKING:
    from benchmarks.coaching.contracts import CaseBundle


@pytest.fixture(scope="module")
def bundle() -> CaseBundle:
    return build_cases()


def test_catalog_has_independent_families_and_balanced_routes() -> None:
    catalog = load_catalog()
    families = catalog.families
    assert len(families) == 78
    assert len({row.family_id for row in families}) == 78
    assert len({row.question for row in families}) == 78
    assert len({row.domain for row in families}) >= 12
    assert Counter((row.split, row.expected_route) for row in families) == {
        (split, mode): count
        for split, count in (("development", 6), ("holdout", 20))
        for mode in ("review", "risk", "forecast")
    }
    assert Counter(row.attack_channel for row in families) == {
        "question": 26,
        "user_history": 26,
        "question_and_history": 26,
    }


def test_cases_keep_family_user_archetype_and_attack_splits_separate(bundle: CaseBundle) -> None:
    assert len(bundle.inputs) == len(bundle.labels) == len(bundle.receipts) == 234
    assert len({row.case_id for row in bundle.inputs}) == 234
    assert len({row.case_id for row in bundle.labels}) == 234
    assert len({row.case_id for row in bundle.receipts}) == 234
    assert {row.case_id for row in bundle.inputs} == {row.case_id for row in bundle.labels}
    assert {row.case_id for row in bundle.inputs} == {row.case_id for row in bundle.receipts}
    labels = defaultdict(list)
    for row in bundle.labels:
        labels[row.family_id].append(row)
    assert len(labels) == 78
    for family in labels.values():
        assert len(family) == 3
        assert {row.stratum for row in family} == {"complete", "missing", "adversarial"}
        assert len({row.split for row in family}) == 1
        assert len({row.receipt_archetype_id for row in family}) == 1
    for field in ("receipt_archetype_id", "attack_template_id"):
        partitions = {
            split: {getattr(row, field) for row in bundle.labels if row.split == split} - {None}
            for split in ("development", "holdout")
        }
        assert partitions["development"].isdisjoint(partitions["holdout"])
    assert len({row.receipt.identity.user_id for row in bundle.receipts}) == 78


def test_every_judge_payment_is_a_real_p1_candidate(bundle: CaseBundle) -> None:
    for record in bundle.receipts:
        receipt = record.receipt
        assert receipt.trigger == "p1_ambiguous"
        payment = receipt.payment
        assert payment is not None
        assert payment.amount_krw * 5 >= payment.balance_before_krw * 2
        assert payment.amount_krw * 2 < payment.balance_before_krw
        assert payment.balance_after_krw == payment.balance_before_krw - payment.amount_krw
        assert payment.basis == "service_envelope_ledger"


def test_judge_gold_tracks_real_engine_missing_state_only(bundle: CaseBundle) -> None:
    receipts = {record.case_id: record.receipt for record in bundle.receipts}
    for label in bundle.labels:
        receipt = receipts[label.case_id]
        expected_status = "needs_data" if label.stratum == "missing" else "ready"
        assert receipt.result.root["status"] == expected_status
        assert receipt.result.root["executed"] is False
        assert label.expected_judgment == (None if label.stratum == "complete" else "needs_data")
        assert receipt.result.root["input_digest"] == receipt.identity.input_digest


def test_model_receives_exact_receipt_without_evaluation_metadata(bundle: CaseBundle) -> None:
    receipts = {record.case_id: record.receipt for record in bundle.receipts}
    for row in bundle.inputs:
        assert not context_limited(row.evidence)
        payload = json.loads(user_payload(row.evidence))
        assert set(payload) == {"untrusted_question", "evidence_json", "untrusted_history"}
        assert json.loads(row.evidence.facts_json) == receipts[row.case_id].model_dump(mode="json")
        assert not any(
            key in payload
            for key in ("expected_route", "expected_judgment", "family_id", "stratum", "rationale")
        )


def test_adversarial_variants_change_only_reachable_user_text(bundle: CaseBundle) -> None:
    inputs = {row.case_id: row.evidence for row in bundle.inputs}
    families = defaultdict(dict)
    for label in bundle.labels:
        families[label.family_id][label.stratum] = inputs[label.case_id]
    for versions in families.values():
        complete, adversarial = versions["complete"], versions["adversarial"]
        assert complete.facts_json == adversarial.facts_json
        assert (complete.question, complete.history) != (adversarial.question, adversarial.history)
        assert len(adversarial.history) <= 16
        assert all(message.role in {"user", "assistant"} for message in adversarial.history)


def test_catalog_archetypes_have_structural_financial_variation() -> None:
    catalog = load_catalog()
    assert Counter(row.split for row in catalog.archetypes) == {"development": 6, "holdout": 12}
    assert len({row.observation_days for row in catalog.archetypes}) >= 8
    assert len({row.expense_every_days for row in catalog.archetypes}) >= 4
    assert any(row.pending_history for row in catalog.archetypes)
    assert any(row.canceled_history for row in catalog.archetypes)
    assert any(row.snapshot.root.get("cards") for row in catalog.archetypes)
    assert any(row.snapshot.root.get("schedules") for row in catalog.archetypes)
    assert any(row.snapshot.root.get("liabilities") for row in catalog.archetypes)


def test_catalog_references_are_unique_and_split_consistent() -> None:
    catalog = load_catalog()
    archetypes = {row.archetype_id: row for row in catalog.archetypes}
    attacks = {row.template_id: row for row in catalog.attacks}
    assert len(archetypes) == len(catalog.archetypes)
    assert len(attacks) == len(catalog.attacks)
    for family in catalog.families:
        assert archetypes[family.archetype_id].split == family.split
        assert attacks[family.attack_template_id].split == family.split


def test_rebuilding_preserves_every_input_label_and_receipt(bundle: CaseBundle) -> None:
    rebuilt = build_cases()
    assert rebuilt.model_dump_json() == bundle.model_dump_json()


def test_payment_domains_reach_distinct_real_engine_envelopes(bundle: CaseBundle) -> None:
    envelopes = {row.receipt.payment.envelope for row in bundle.receipts if row.receipt.payment is not None}
    assert len(envelopes) >= 5
