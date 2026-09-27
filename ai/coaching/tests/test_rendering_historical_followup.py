"""A historical coaching follow-up must render the preserved historical result.

``authoritative_text`` must never present the live (current-Twin-revision) result as
the next action / warnings for a ``historical_coaching_followup`` trigger. It must
read ``receipt.historical.engine_result`` instead. This discriminates the fix in
``coaching_service.rendering.authoritative_text`` from the prior, unconditional
``action = receipt.result.root.get("next_action")``.
"""

# ruff: noqa: INP001

from coaching_service.rendering import authoritative_text
from coaching_service.schemas import Receipt


def receipt_for_followup() -> Receipt:
    return Receipt.model_validate(
        {
            "engine_commit": "pinned-engine",
            "identity": {
                "user_id": "user",
                "twin_id": "twin",
                "revision": 4,
                "input_digest": "digest",
                "as_of": "2026-09-09",
            },
            "request": {"on_date": "2026-09-09", "through_date": "2026-09-16"},
            # The live result for the CURRENT Twin revision: must NOT be rendered.
            "result": {
                "next_action": {
                    "title": "live-title-must-not-appear",
                    "detail": "live-detail-must-not-appear",
                },
                "warnings": [
                    {"severity": "user", "detail": "live-warning-must-not-appear"},
                ],
            },
            "trigger": "historical_coaching_followup",
            "historical": {
                "coaching_id": "past-coaching",
                "created_at": 1_700_000_000.0,
                "payment": None,
                "trigger": "p0_half_balance",
                "transaction_status": "active",
                "engine_result": {
                    "next_action": {
                        "title": "historical-title-must-appear",
                        "detail": "historical-detail-must-appear",
                    },
                    "warnings": [
                        {"severity": "user", "detail": "historical-warning-must-appear"},
                    ],
                },
            },
        }
    )


def test_historical_followup_renders_historical_result_not_live_result() -> None:
    # Given a session-bound historical follow-up whose live result differs from the
    # preserved historical engine result.
    text = authoritative_text(receipt_for_followup())

    # Then the rendered text carries the historical next_action/warnings.
    assert "historical-title-must-appear. historical-detail-must-appear" in text
    assert "historical-warning-must-appear" in text

    # And it must never present the live result as the current one.
    assert "live-title-must-not-appear" not in text
    assert "live-detail-must-not-appear" not in text
    assert "live-warning-must-not-appear" not in text
