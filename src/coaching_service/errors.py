"""Stable service errors without request or credential reflection."""


class ServiceError(Exception):
    def __init__(self, code: str, status: int = 422) -> None:
        super().__init__(code)
        self.code: str = code
        self.status: int = status
