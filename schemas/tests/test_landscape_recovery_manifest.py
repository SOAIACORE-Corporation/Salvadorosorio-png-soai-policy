from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "landscape"))

from recovery_manifest import assess_recovery_manifest  # noqa: E402


def _base_manifest():
    return {
        "recovery_manifest_version": "0.1",
        "requirements": [
            {"requirement_id":"e1","dimension":"evidence_coverage","status":"CONFIRMED","required":True,"material_primary":True},
            {"requirement_id":"c1","dimension":"causal_continuity","status":"CONFIRMED","required":True},
            {"requirement_id":"a1","dimension":"authority_integrity","status":"CONFIRMED","required":True,"required_authority":True},
            {"requirement_id":"f1","dimension":"freshness","status":"CONFIRMED","required":True},
            {"requirement_id":"r1","dimension":"receipt_integrity","status":"CONFIRMED","required":True},
        ],
    }


def test_manifest_derives_complete_score_without_manual_counts():
    result = assess_recovery_manifest(_base_manifest())
    assert result["claimable_score_pct"] == 100
    assert result["unconfirmed_requirement_ids"] == []


def test_manifest_missing_primary_evidence_activates_ceiling():
    m = _base_manifest()
    m["requirements"][0]["status"] = "MISSING"
    result = assess_recovery_manifest(m)
    assert "MISSING_MATERIAL_PRIMARY_EVIDENCE" in result["gates"]
    assert result["claimable_score_pct"] <= 69
    assert result["unconfirmed_requirement_ids"] == ["e1"]


def test_manifest_missing_authority_activates_authority_gate():
    m = _base_manifest()
    m["requirements"][2]["status"] = "PARTIAL"
    result = assess_recovery_manifest(m)
    assert "MISSING_REQUIRED_AUTHORITY" in result["gates"]
    assert result["claimable_score_pct"] <= 84
