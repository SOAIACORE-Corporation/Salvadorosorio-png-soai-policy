from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RuntimeContractError(Exception):
    code: str
    message: str
    stage: str
    status_code: int = 422
    retryable: bool = False
    details: dict[str, Any] = field(default_factory=dict)
    run_id: str | None = None

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"

    def envelope(self, correlation_id: str) -> dict[str, Any]:
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "stage": self.stage,
                "correlation_id": correlation_id,
                "run_id": self.run_id,
                "retryable": self.retryable,
                "details": self.details,
            }
        }


def contract_error(
    code: str,
    message: str,
    stage: str,
    *,
    status_code: int = 422,
    retryable: bool = False,
    details: dict[str, Any] | None = None,
    run_id: str | None = None,
) -> RuntimeContractError:
    return RuntimeContractError(
        code=code,
        message=message,
        stage=stage,
        status_code=status_code,
        retryable=retryable,
        details=details or {},
        run_id=run_id,
    )

