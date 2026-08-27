from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import re
import time


_OPERATOR_ID_PATTERN = re.compile(r"^op_[a-f0-9]{24}$")
_VALID_ROLES = {"OPERATOR", "ADMIN"}


class OperatorAuthError(ValueError):
    def __init__(self, code: str, message: str, status_code: int) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code


@dataclass(frozen=True)
class OperatorContext:
    operator_id: str
    role: str
    correlation_id: str


def signature_payload(
    *,
    method: str,
    path: str,
    timestamp: str,
    correlation_id: str,
    operator_id: str,
    role: str,
    content_sha256: str,
) -> bytes:
    return "\n".join(
        (method.upper(), path, timestamp, correlation_id, operator_id, role, content_sha256)
    ).encode("utf-8")


def sign_operator_context(
    secret: str,
    *,
    method: str,
    path: str,
    timestamp: str,
    correlation_id: str,
    operator_id: str,
    role: str,
    content_sha256: str,
) -> str:
    return hmac.new(
        secret.encode("utf-8"),
        signature_payload(
            method=method,
            path=path,
            timestamp=timestamp,
            correlation_id=correlation_id,
            operator_id=operator_id,
            role=role,
            content_sha256=content_sha256,
        ),
        hashlib.sha256,
    ).hexdigest()


def verify_operator_context(
    secret: str | None,
    *,
    method: str,
    path: str,
    timestamp: str | None,
    correlation_id: str | None,
    operator_id: str | None,
    role: str | None,
    signature: str | None,
    content_sha256: str | None,
    actual_content_sha256: str,
    now: int | None = None,
    max_clock_skew_seconds: int = 120,
) -> OperatorContext:
    if not secret or len(secret.encode("utf-8")) < 32:
        raise OperatorAuthError(
            "INTERNAL_AUTH_NOT_CONFIGURED",
            "The internal authorization boundary is unavailable",
            503,
        )
    if not all((timestamp, correlation_id, operator_id, role, signature, content_sha256)):
        raise OperatorAuthError(
            "OPERATOR_AUTH_REQUIRED", "Authenticated operator context is required", 401
        )
    if not _OPERATOR_ID_PATTERN.fullmatch(operator_id or ""):
        raise OperatorAuthError("OPERATOR_AUTH_INVALID", "Operator context is invalid", 401)
    normalized_role = (role or "").upper()
    if normalized_role not in _VALID_ROLES:
        raise OperatorAuthError("OPERATOR_ROLE_FORBIDDEN", "Operator role is not allowed", 403)
    if not correlation_id or len(correlation_id) > 100 or not all(
        character.isalnum() or character in "_-" for character in correlation_id
    ):
        raise OperatorAuthError("OPERATOR_AUTH_INVALID", "Operator context is invalid", 401)
    if not re.fullmatch(r"[a-f0-9]{64}", content_sha256 or "") or not hmac.compare_digest(
        content_sha256 or "", actual_content_sha256
    ):
        raise OperatorAuthError("OPERATOR_AUTH_INVALID", "Operator context is invalid", 401)
    try:
        signed_at = int(timestamp or "")
    except ValueError as exc:
        raise OperatorAuthError("OPERATOR_AUTH_INVALID", "Operator context is invalid", 401) from exc
    current = int(time.time()) if now is None else now
    if abs(current - signed_at) > max_clock_skew_seconds:
        raise OperatorAuthError("OPERATOR_AUTH_EXPIRED", "Operator context has expired", 401)
    expected = sign_operator_context(
        secret,
        method=method,
        path=path,
        timestamp=str(signed_at),
        correlation_id=correlation_id,
        operator_id=operator_id,
        role=normalized_role,
        content_sha256=content_sha256 or "",
    )
    if not hmac.compare_digest(expected, signature or ""):
        raise OperatorAuthError("OPERATOR_AUTH_INVALID", "Operator context is invalid", 401)
    return OperatorContext(
        operator_id=operator_id,
        role=normalized_role,
        correlation_id=correlation_id,
    )
