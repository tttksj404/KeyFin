from coaching_service.engine import EngineAdapter
from coaching_service.schemas import Bootstrap, JsonDocument


def fixture(user: str = "demo") -> Bootstrap:
    row = {
        "user_id": user,
        "transaction_id": "old",
        "source": "LIVE",
        "transaction_type": "WITHDRAW",
        "transaction_date": "2026-07-01",
        "transaction_time": "12:00",
        "category": "기타",
        "subcategory": "기타",
        "merchant": "synthetic",
        "merchant_id": "m",
        "amount_krw": 10000,
        "account_id": "a",
        "card_id": "",
        "confirm_status": "CONFIRMED",
        "status": "NORMAL",
    }
    return Bootstrap.model_validate(
        {
            "as_of": "2026-09-09",
            "transactions": [row],
            "snapshot": {
                "as_of": "2026-09-09",
                "source": "USER_ASSUMPTION",
                "accounts": [{"account_id": "a", "balance_krw": 1000000}],
                "cards": [],
                "known_bills": [],
                "reserve_krw": 100000,
                "budgets": {"기타": 100000},
            },
            "envelopes": [{"envelope": "기타", "balance_krw": 100000}],
        }
    )


def test_real_engine_roundtrip() -> None:
    engine = EngineAdapter()
    twin = engine.create(fixture(), "demo")
    result = engine.review(
        twin,
        JsonDocument.model_validate(
            {
                "on_date": "2026-09-09",
                "through_date": "2026-09-16",
                "paths": 20,
                "seed": 42,
            }
        ),
    )
    assert result.root["schema_version"] == "coaching/1.0"
    assert result.root["executed"] is False
    assert result.root["input_digest"] == engine.identity(twin).input_digest
    assert (
        engine.review(
            JsonDocument.model_validate_json(twin.model_dump_json()),
            JsonDocument.model_validate(
                {"on_date": "2026-09-09", "through_date": "2026-09-16", "paths": 20, "seed": 42}
            ),
        )
        == result
    )
