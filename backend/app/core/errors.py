from typing import Any


class DomainError(Exception):
    def __init__(self, code: str, message: str, status: int = 409, **context: Any):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.context = context
