from pydantic import JsonValue

from .model import Twin

def apply_events(twin: Twin, events: list[dict[str, JsonValue]]) -> Twin: ...
