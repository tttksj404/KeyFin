from pydantic import JsonValue

class FDTError(Exception):
    code: str
    def as_dict(self) -> dict[str, JsonValue]: ...
