from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "landscape"))

from recovery_manifest_builder import CANONICAL_REQUIREMENTS, build_recovery_manifest  # noqa: E402
from memory_cycle import run_memory_cycle_from_evidence  # noqa: E402


def _complete_evidence():
    return [
        {"evidence_id":"commit:state","requirement_id":"primary-state","available":True,"validation_status":"CONFIRMED","source_ref":"git:abc"},
        {"evidence_id":"receipt:causal","requirement_id":"causal-link","available":True,"validation_status":"CONFIRMED","source_ref":"receipt:memory"},
        {"evidence_id":"receipt:authority","requirement_id":"decision-authority","available":True,"validation_status":"CONFIRMED","source_ref":"receipt:approval"},
        {"evidence_id":"ci:fresh","requirement_id":"source-freshness","available":True,"validation_status":"CONFIRMED","fresh":True,"source_ref":"ci:112"},
        {"evidence_id":"receipt:validation","requirement_id":"validation-receipt","available":True,"validation_status":"CONFIRMED","source_ref":"receipt:validation"},
    ]


def test_builder_generates_confirmed_manifest_from_durable_evidence():
    manifest = build_recovery_manifest(_complete_evidence())
    assert manifest["generated_from_durable_evidence"] is True
    assert all(r["status"] == "CONFIRMED" for r in manifest["requirements"])
    assert manifest["evidence_inventory_count"] == 5


def test_missing_evidence_becomes_missing_not_healthy():
    evidence = [e for e in _complete_evidence() if e["requirement_id"] != "decision-authority"]
    manifest = build_recovery_manifest(evidence)
    authority = next(r for r in manifest["requirements"] if r["requirement_id"] == "decision-authority")
    assert authority["status"] == "MISSING"
    assert authority["evidence_ids"] == []


def test_stale_freshness_stays_stale():
    evidence = _complete_evidence()
    fresh = next(e for e in evidence if e["requirement_id"] == "source-freshness")
    fresh["fresh"] = False
    manifest = build_recovery_manifest(evidence)
    item = next(r for r in manifest["requirements"] if r["requirement_id"] == "source-freshness")
    assert item["status"] == "STALE"


def test_partial_evidence_is_not_promoted_to_confirmed():
    evidence = _complete_evidence()
    causal = next(e for e in evidence if e["requirement_id"] == "causal-link")
    causal["validation_status"] = "PARTIAL"
    manifest = build_recovery_manifest(evidence)
    item = next(r for r in manifest["requirements"] if r["requirement_id"] == "causal-link")
    assert item["status"] == "PARTIAL"


def test_generated_manifest_flows_directly_into_memory_cycle():
    result = run_memory_cycle_from_evidence(_complete_evidence())
    assert result["resolve"]["canonicalization_status"] == "ELIGIBLE"
    assert result["understand"]["context_integrity_score_pct"] == 100
    assert result["generated_manifest"]["recovery_manifest_version"] == "0.2"


def test_missing_authority_from_inventory_blocks_cycle():
    evidence = [e for e in _complete_evidence() if e["requirement_id"] != "decision-authority"]
    result = run_memory_cycle_from_evidence(evidence)
    assert result["resolve"]["canonicalization_status"] == "BLOCKED"
    assert "MISSING_REQUIRED_AUTHORITY" in result["understand"]["critical_gates"]


def test_evidence_cannot_target_undeclared_obligation():
    evidence = _complete_evidence() + [
        {"evidence_id":"x","requirement_id":"invented","available":True,"validation_status":"CONFIRMED"}
    ]
    try:
        build_recovery_manifest(evidence, requirements=CANONICAL_REQUIREMENTS)
    except ValueError:
        pass
    else:
        raise AssertionError("evidence must not create undeclared requirements")
