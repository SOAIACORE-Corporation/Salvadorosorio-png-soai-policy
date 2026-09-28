from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "landscape"))

from context_integrity import assess_context_integrity  # noqa: E402


def test_complete_evidence_yields_verified_continuity():
    result = assess_context_integrity(
        evidence_confirmed=10,
        evidence_expected=10,
        causal_links_confirmed=8,
        causal_links_expected=8,
        authority_confirmed=3,
        authority_expected=3,
        fresh_sources=5,
        required_sources=5,
        receipts_confirmed=4,
        receipts_expected=4,
    )
    assert result["claimable_score_pct"] == 100
    assert result["confidence_band"] == "VERIFIED_CONTINUITY"
    assert result["gates"] == []


def test_missing_verbatim_dialogue_does_not_fake_state_loss():
    result = assess_context_integrity(
        evidence_confirmed=10,
        evidence_expected=10,
        causal_links_confirmed=8,
        causal_links_expected=8,
        authority_confirmed=3,
        authority_expected=3,
        fresh_sources=5,
        required_sources=5,
        receipts_confirmed=4,
        receipts_expected=4,
        unrecovered_verbatim_dialogue=True,
    )
    assert result["claimable_score_pct"] == 100
    assert "VERBATIM_DIALOGUE_UNRECOVERED" in result["gates"]


def test_missing_authority_caps_claimable_confidence():
    result = assess_context_integrity(
        evidence_confirmed=10,
        evidence_expected=10,
        causal_links_confirmed=8,
        causal_links_expected=8,
        authority_confirmed=2,
        authority_expected=3,
        fresh_sources=5,
        required_sources=5,
        receipts_confirmed=4,
        receipts_expected=4,
        missing_required_authority=True,
    )
    assert result["raw_score_pct"] > 84
    assert result["claimable_score_pct"] == 84
    assert result["confidence_band"] == "PARTIAL_CONTINUITY"


def test_missing_material_primary_evidence_caps_at_69():
    result = assess_context_integrity(
        evidence_confirmed=9,
        evidence_expected=10,
        causal_links_confirmed=8,
        causal_links_expected=8,
        authority_confirmed=3,
        authority_expected=3,
        fresh_sources=5,
        required_sources=5,
        receipts_confirmed=4,
        receipts_expected=4,
        missing_material_primary_evidence=True,
    )
    assert result["raw_score_pct"] > 69
    assert result["claimable_score_pct"] == 69
    assert result["confidence_band"] == "DEGRADED_CONTINUITY"


def test_unknown_required_dimension_is_not_silently_zeroed():
    result = assess_context_integrity(
        evidence_confirmed=0,
        evidence_expected=0,
        causal_links_confirmed=0,
        causal_links_expected=0,
        authority_confirmed=0,
        authority_expected=0,
        fresh_sources=0,
        required_sources=0,
        receipts_confirmed=0,
        receipts_expected=0,
    )
    assert result["claimable_score_pct"] == 100


def test_invalid_counts_fail_closed():
    try:
        assess_context_integrity(
            evidence_confirmed=2,
            evidence_expected=1,
            causal_links_confirmed=0,
            causal_links_expected=0,
            authority_confirmed=0,
            authority_expected=0,
            fresh_sources=0,
            required_sources=0,
            receipts_confirmed=0,
            receipts_expected=0,
        )
    except ValueError:
        pass
    else:
        raise AssertionError("invalid counts must fail closed")
