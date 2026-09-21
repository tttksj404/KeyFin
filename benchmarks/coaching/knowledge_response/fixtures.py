"""Independent small amounts for personal-source integration; not real customer data."""

from datetime import date

from benchmarks.coaching.flow.fixtures import scenario
from coaching_service.schemas import JsonDocument


def twin(owner: str) -> JsonDocument:
    initial = scenario(owner, date(2026, 9, 3)).bootstrap
    return JsonDocument(
        {
            **initial.model_dump(mode="json"),
            "snapshot": {
                "as_of": "2026-09-03",
                "source": "LIVE",
                "accounts": [
                    {"account_id": "cash-account", "balance_krw": 1320000},
                    {"account_id": "overdraft", "balance_krw": -20000},
                ],
                "assets": [{"asset_id": "fund", "kind": "investment", "value_krw": 250000}],
                "liabilities": [{"liability_id": "loan", "principal_krw": 410000}],
                "cards": [
                    {
                        "card_id": "credit",
                        "kind": "CREDIT",
                        "settlement_account_id": "cash-account",
                        "opening_payable_krw": 90000,
                        "payment_delay_days": 20,
                    }
                ],
                "known_bills": [
                    {
                        "bill_id": "tomorrow",
                        "card_id": "credit",
                        "due_date": "2026-09-04",
                        "amount_krw": 18000,
                    },
                    {"bill_id": "next", "card_id": "credit", "due_date": "2026-09-08", "amount_krw": 72000},
                ],
                "coverage": {"all_assets_reported": True, "all_liabilities_reported": True},
            },
        }
    )


def personal() -> JsonDocument:
    return JsonDocument(
        {
            "expected_revision": 0,
            "as_of": "2026-09-03",
            "source_system": "coverage-experiment",
            "source_record_id": "independent-synthetic-input",
            "provenance": "synthetic",
            "income": {
                "coverage": "complete",
                "items": [
                    {"id": "salary", "label": "급여", "monthly_amount_krw": 2800000},
                    {"id": "side", "label": "부수입", "monthly_amount_krw": 250000},
                ],
            },
            "fixed_costs": {
                "coverage": "partial",
                "items": [
                    {"id": "rent", "label": "월세", "monthly_amount_krw": 500000},
                    {"id": "phone", "label": "통신비", "monthly_amount_krw": 47000},
                ],
            },
            "insurance": {
                "coverage": "complete",
                "items": [
                    {
                        "id": "health",
                        "label": "건강보험",
                        "monthly_premium_krw": 25000,
                        "coverage_amount_krw": 30000000,
                    },
                    {
                        "id": "life",
                        "label": "생명보험",
                        "monthly_premium_krw": 40000,
                        "coverage_amount_krw": 80000000,
                    },
                ],
            },
            "goals": {
                "coverage": "complete",
                "items": [
                    {"id": "trip", "label": "여행", "target_krw": 700000, "saved_krw": 150000},
                    {"id": "emergency", "label": "비상금", "target_krw": 1500000, "saved_krw": 250000},
                ],
            },
        }
    )
