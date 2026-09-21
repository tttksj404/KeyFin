"""Deterministic synthetic generation fixtures; never records model-quality evidence."""

import json

from benchmarks.coaching.e2e.e2e_contracts import E2ECase
from coaching_service.llm_contract import Operation
from coaching_service.llm_prompt import TEMPLATE_TEXT


def fake_completion(case: E2ECase, operation: Operation, model: str) -> tuple[int, str]:
    if operation == "write" and case.fake_fault == "write_http_503":
        return 503, '{"error":"synthetic generation unavailable"}'
    if operation == "write":
        content = "확인할 지출이 3건 있어요." if case.fake_fault == "write_numeric" else TEMPLATE_TEXT
    elif operation == "judge":
        reasons = {
            "coach": "context_concern",
            "skip": "no_additional_concern",
            "needs_data": "insufficient_context",
        }
        content = json.dumps(
            {
                "decision": case.fake_decision,
                "reason_code": reasons[case.fake_decision],
                "confidence": case.fake_confidence,
            }
        )
        if case.fake_fault == "judge_schema":
            content = '{"decision":"coach","amount":123}'
    else:
        content = json.dumps({"mode": case.expected_route or "review"})
    return 200, json.dumps(
        {
            "model": model,
            "choices": [
                {"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}
            ],
        },
        ensure_ascii=False,
    )
