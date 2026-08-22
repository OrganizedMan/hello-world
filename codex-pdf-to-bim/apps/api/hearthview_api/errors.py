from dataclasses import dataclass


@dataclass(frozen=True)
class DomainError(Exception):
    status_code: int
    code: str
    message: str
    action: str
