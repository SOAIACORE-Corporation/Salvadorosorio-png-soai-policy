from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "landscape"))

from authority import exception_gate, is_exception_authority, require_exception_authority  # noqa: E402


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


def test_valid_exception_is_normalized_to_full_canonical_name():
    result=exception_gate(authority="SOA",reason="Approved controlled exception")
    assert result["allowed"] is True
    assert result["authority"]=="Salvador Osorio Ayala"


def test_require_exception_authority_rejects_noncanonical_actor():
    try:
        require_exception_authority("Committee")
    except PermissionError as exc:
        assert "Salvador Osorio Ayala" in str(exc)
    else:
        raise AssertionError("noncanonical exception authority must be rejected")
