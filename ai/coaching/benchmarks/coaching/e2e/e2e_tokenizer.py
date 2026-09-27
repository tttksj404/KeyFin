"""Synthetic byte tokenizer for protocol tests; never reports serving-model token counts."""

import hashlib
import json

from coaching_service.schemas import JsonDocument
from coaching_service.token_budget import TokenBudget


def synthetic_budget(raw: bytes) -> TokenBudget:
    """Treat each canonical prompt UTF-8 byte as a synthetic token, including schema framing."""
    body = JsonDocument.model_validate_json(raw).root
    prompt = json.dumps(
        {"messages": body["messages"], "response_format": body.get("response_format")},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return TokenBudget(
        prompt_tokens=len(prompt),
        max_input_tokens=65536,
        max_output_tokens=1536,
        request_sha256=hashlib.sha256(raw).hexdigest(),
        prompt_sha256=hashlib.sha256(prompt).hexdigest(),
    )
