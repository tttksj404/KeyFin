"""Check source-answer links independently of the product's Message model."""

from coaching_service.schemas import JsonDocument


def exact_references(session: JsonDocument, answers: tuple[JsonDocument, ...]) -> bool:
    """Each new assistant turn must identify the exact answer whose GET body was checked."""
    raw = session.root.get("messages")
    if not isinstance(raw, list) or len(raw) != 2 * len(answers):
        return False
    for index, answer in enumerate(answers):
        user, assistant = raw[index * 2 : index * 2 + 2]
        if not isinstance(user, dict) or not isinstance(assistant, dict):
            return False
        expected = {"kind": "coaching" if "receipt" in answer.root else "chat", "id": answer.root["id"]}
        if (
            user.get("role") != "user"
            or user.get("response") is not None
            or assistant.get("role") != "assistant"
            or assistant.get("response") != expected
            or assistant.get("content") != answer.root.get("text")
        ):
            return False
    return True
