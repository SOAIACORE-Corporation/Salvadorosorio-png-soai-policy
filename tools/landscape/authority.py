"""Global authority policy for SOAiaCore Landscape Intelligence.

Exception authority is explicit and singular. This module does not authenticate
a person; it validates whether a declared authority string matches the canonical
exception authority configured by governance.
"""

from __future__ import annotations

CANONICAL_EXCEPTION_AUTHORITY = "Salvador Osorio Ayala"
CANONICAL_EXCEPTION_ALIAS = "SOA"


def is_exception_authority(authority: str | None) -> bool:
    if not authority:
        return False
    normalized = authority.strip().casefold()
    return normalized in {
        CANONICAL_EXCEPTION_AUTHORITY.casefold(),
        CANONICAL_EXCEPTION_ALIAS.casefold(),
    }


def require_exception_authority(authority: str | None) -> None:
    if not is_exception_authority(authority):
        raise PermissionError(
            "Exception requires explicit authority: SOA / Salvador Osorio Ayala"
        )


def exception_gate(*, authority: str | None, reason: str | None) -> dict[str, object]:
    if not reason or not reason.strip():
        return {
            "allowed": False,
            "state": "REJECTED",
            "reason": "Exception reason is required.",
            "required_authority": CANONICAL_EXCEPTION_AUTHORITY,
        }
    if not is_exception_authority(authority):
        return {
            "allowed": False,
            "state": "REJECTED",
            "reason": "Declared authority is not the canonical exception authority.",
            "required_authority": CANONICAL_EXCEPTION_AUTHORITY,
        }
    return {
        "allowed": True,
        "state": "AUTHORIZED_EXCEPTION",
        "reason": reason.strip(),
        "authority": CANONICAL_EXCEPTION_AUTHORITY,
    }
