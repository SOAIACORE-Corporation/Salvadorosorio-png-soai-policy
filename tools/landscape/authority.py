"""Global authority policy for SOAiaCore Landscape Intelligence.

Exception authority is explicit and singular. This module does not authenticate
a person; it validates whether a declared authority string matches the canonical
exception authority configured by governance.
"""

from __future__ import annotations

CANONICAL_EXCEPTION_AUTHORITY = "Salvador Osorio Ayala"
CANONICAL_EXCEPTION_ALIAS = "SOA"
CANONICAL_EXCEPTION_AUTHORITY_REF = "authority:soa:salvador-osorio-ayala"


def is_exception_authority(authority: str | None) -> bool:
    if not authority:
        return False
    normalized = authority.strip().casefold()
    return normalized in {
        CANONICAL_EXCEPTION_AUTHORITY.casefold(),
        CANONICAL_EXCEPTION_ALIAS.casefold(),
    }


def has_exception_authority_provenance(
    *,
    authority: str | None,
    authority_ref: str | None,
    authentication_ref: str | None,
) -> bool:
    return (
        is_exception_authority(authority)
        and authority_ref == CANONICAL_EXCEPTION_AUTHORITY_REF
        and isinstance(authentication_ref, str)
        and bool(authentication_ref.strip())
    )


def require_exception_authority(
    authority: str | None,
    *,
    authority_ref: str | None = None,
    authentication_ref: str | None = None,
) -> None:
    if not has_exception_authority_provenance(
        authority=authority,
        authority_ref=authority_ref,
        authentication_ref=authentication_ref,
    ):
        raise PermissionError(
            "Exception requires canonical authority plus durable authentication provenance"
        )


def exception_gate(
    *,
    authority: str | None,
    reason: str | None,
    authority_ref: str | None = None,
    authentication_ref: str | None = None,
) -> dict[str, object]:
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
            "required_authority_ref": CANONICAL_EXCEPTION_AUTHORITY_REF,
        }
    if not has_exception_authority_provenance(
        authority=authority,
        authority_ref=authority_ref,
        authentication_ref=authentication_ref,
    ):
        return {
            "allowed": False,
            "state": "REJECTED",
            "reason": "Canonical authority declaration lacks durable authentication provenance.",
            "required_authority": CANONICAL_EXCEPTION_AUTHORITY,
            "required_authority_ref": CANONICAL_EXCEPTION_AUTHORITY_REF,
        }
    return {
        "allowed": True,
        "state": "AUTHORIZED_EXCEPTION",
        "reason": reason.strip(),
        "authority": CANONICAL_EXCEPTION_AUTHORITY,
        "authority_ref": CANONICAL_EXCEPTION_AUTHORITY_REF,
        "authentication_ref": authentication_ref.strip(),
    }
