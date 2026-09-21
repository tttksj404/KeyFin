from pydantic import JsonValue

from .model import Twin as Twin
from .simulation import RandomBundle, Simulation

class Engine:
    def __init__(self, twin: Twin) -> None: ...
    def run(self, request: dict[str, JsonValue]) -> dict[str, JsonValue]: ...
    def _base(self, req: dict[str, JsonValue], bundle: RandomBundle,
              sim: Simulation) -> dict[str, JsonValue]: ...
