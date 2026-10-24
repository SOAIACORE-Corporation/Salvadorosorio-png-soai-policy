from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "landscape"))

from authority import (  # noqa: E402
    CANONICAL_EXCEPTION_AUTHORITY_REF,
    exception_gate,
    has_exception_authority_provenance,
    is_exception_authority,
    require_exception_authority,
)


def test_soa_alias_is_canonical_exception_authority():
    assert is_exception_authority("SOA") is True


def test_full_name_is_canonical_exception_authority():
    assert is_exception_authority("Salvador Osorio Ayala") is True


def test_other_authority_cannot_grant_exception():
    assert is_exception_authority("Architecture / Owner") is False


def test_exception_requires_reason():
    result=exception_gate(authority="SOA",reason="")
    assert result["allowed"] is False
    assert result["state"]=="REJECTED"


def test_exception_alias_without_authentication_provenance_fails_closed():
    result=exception_gate(authority="SOA",reason="Approved controlled exception")
    assert result["allowed"] is False
    assert result["state"]=="REJECTED"


def test_full_name_without_authentication_provenance_fails_closed():
    result=exception_gate(
        authority="Salvador Osorio Ayala",
        reason="Approved controlled exception",
    )
    assert result["allowed"] is False


def test_wrong_actor_with_apparent_provenance_still_fails_closed():
    result=exception_gate(
        authority="Committee",
        reason="Attempted exception",
        authority_ref=CANONICAL_EXCEPTION_AUTHORITY_REF,
        authentication_ref="authn:upstream:committee",
    )
    assert result["allowed"] is False


def test_valid_exception_requires_canonical_ref_and_authentication_provenance():
    result=exception_gate(
        authority="SOA",
        reason="Approved controlled exception",
        authority_ref=CANONICAL_EXCEPTION_AUTHORITY_REF,
        authentication_ref="authn:upstream:soa",
    )
    assert result["allowed"] is True
    assert result["authority"]=="Salvador Osorio Ayala"
    assert result["authority_ref"]==CANONICAL_EXCEPTION_AUTHORITY_REF
    assert result["authentication_ref"]=="authn:upstream:soa"
    assert has_exception_authority_provenance(
        authority="SOA",
        authority_ref=CANONICAL_EXCEPTION_AUTHORITY_REF,
        authentication_ref="authn:upstream:soa",
    ) is True


def test_require_exception_authority_rejects_noncanonical_actor():
    try:
        require_exception_authority(
            "Committee",
            authority_ref=CANONICAL_EXCEPTION_AUTHORITY_REF,
            authentication_ref="authn:upstream:committee",
        )
    except PermissionError as exc:
        assert "authentication provenance" in str(exc)
    else:
        raise AssertionError("noncanonical exception authority must be rejected")
