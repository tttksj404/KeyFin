from pydantic import JsonValue

from .model import Twin

class Coach:
    def __init__(self, twin: Twin) -> None: ...
    def review(self, request: dict[str, JsonValue]) -> dict[str, JsonValue]: ...
