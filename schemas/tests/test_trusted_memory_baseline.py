import copy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "landscape"))

from trusted_memory import (  # noqa: E402
    fidelity_score,
    postgres_projection,
    reconstruct_from_snapshot,
    recovery_decision,
    validate_evidence_inventory,
    validate_manifest,
    validate_snapshot,
)

SCHEMA = ROOT / "Trusted_Memory" / "00_Schema" / "Trusted_Memory_Snapshot_Schema_v1.0.yaml"
SNAPSHOT = ROOT / "Trusted_Memory" / "01_Snapshots" / "TMS-SOAIACORE-MOCATRIZ-20260926-001_v1.0.0_FROZEN.yaml"
MIRROR = ROOT / "schemas" / "examples" / "landscape" / "trusted-memory" / "TMS-SOAIACORE-MOCATRIZ-20260926-001_v1.0.0_FROZEN.json"
MANIFEST = ROOT / "Trusted_Memory" / "02_Recovery_Manifests" / "RM-SOAIACORE-MOCATRIZ-20260926-001_v1.0.0_FROZEN.yaml"
EVIDENCE = ROOT / "Trusted_Memory" / "03_Evidence_Inventory" / "Durable_Evidence_Inventory_v1.0.0.json"


def _load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_schema_and_physical_integrity():
    schema=_load(SCHEMA)
    snapshot=_load(SNAPSHOT)
    assert set(schema["required"]).issubset(snapshot)
    result=validate_snapshot(snapshot)
    assert result["valid"] is True


def test_primary_and_secondary_logical_storage_are_identical():
    assert SNAPSHOT.read_bytes() == MIRROR.read_bytes()


def test_manifest_and_inventory_hashes_correlate():
    snapshot=_load(SNAPSHOT)
    manifest=_load(MANIFEST)
    evidence=_load(EVIDENCE)
    assert validate_manifest(manifest,snapshot)["valid"] is True
    ev=validate_evidence_inventory(
        manifest,evidence,objective_id=snapshot["objective"]["objective_id"]
    )
    assert ev["valid"] is True


def test_blind_reconstruction_scores_100_without_nullifiers():
    snapshot=_load(SNAPSHOT)
    manifest=_load(MANIFEST)
    evidence=_load(EVIDENCE)
    recovered=reconstruct_from_snapshot(snapshot,manifest,evidence)
    result=fidelity_score(snapshot,recovered)
    assert result["result"] == "PASS"
    assert result["total_score"] == 100
    assert result["invalidating_conditions"] == []
    assert result["critical_fields_preserved"] is True


def test_recovery_is_with_exceptions_not_full():
    manifest=_load(MANIFEST)
    result=recovery_decision(manifest)
    assert result["result"] == "RECOVERABLE_WITH_EXCEPTIONS"
    assert result["exception_requirement_ids"] == ["REQ-010"]


def test_adversarial_wrong_commit_fails():
    snapshot=_load(SNAPSHOT)
    recovered=reconstruct_from_snapshot(snapshot,_load(MANIFEST),_load(EVIDENCE))
    recovered["checkpoint"]["head"]="0"*40
    result=fidelity_score(snapshot,recovered)
    assert "HEAD_MISMATCH" in result["invalidating_conditions"]
    assert result["result"]=="FAIL"


def test_adversarial_foreign_receipt_evidence_is_rejected():
    snapshot=_load(SNAPSHOT)
    manifest=_load(MANIFEST)
    evidence=_load(EVIDENCE)
    foreign=copy.deepcopy(evidence)
    ev=next(x for x in foreign["evidence"] if x["evidence_id"]=="EV-001")
    ev["objective_id"]="OBJ-OTHER-EXECUTION"
    # hash is intentionally not resealed; physical and correlation controls should fail.
    result=validate_evidence_inventory(
        manifest,foreign,objective_id=snapshot["objective"]["objective_id"]
    )
    assert result["valid"] is False
    assert any("evidence_objective_mismatch" in e for e in result["errors"])


def test_adversarial_zero_denominator_cannot_be_100():
    snapshot=_load(SNAPSHOT)
    recovered=reconstruct_from_snapshot(snapshot,_load(MANIFEST),_load(EVIDENCE))
    recovered["metrics"]["correlation_integrity"]["result_pct"]=100
    result=fidelity_score(snapshot,recovered)
    assert "FALSE_CORRELATION_100" in result["invalidating_conditions"]
    assert result["result"]=="FAIL"


def test_adversarial_missing_endpoint_is_not_negative_fact():
    snapshot=_load(SNAPSHOT)
    recovered=reconstruct_from_snapshot(snapshot,_load(MANIFEST),_load(EVIDENCE))
    endpoint=recovered["pending_and_exceptions"]["functional_endpoint_validation"]
    assert endpoint == {"status":"MISSING","interpretation":"NOT_DEMONSTRATED"}


def test_adversarial_new_instruction_cannot_remove_frozen_exceptions():
    snapshot=_load(SNAPSHOT)
    recovered=reconstruct_from_snapshot(snapshot,_load(MANIFEST),_load(EVIDENCE))
    recovered["objective"]["scope_status"]="COMPLETED"
    recovered["pending_and_exceptions"]["exceptions"]=[]
    result=fidelity_score(snapshot,recovered)
    assert "FALSE_COMPLETE_STATUS" in result["invalidating_conditions"]
    assert "EXCEPTION_LOSS" in result["invalidating_conditions"]


def test_adversarial_plausible_narrative_without_authority_fails():
    snapshot=_load(SNAPSHOT)
    recovered=reconstruct_from_snapshot(snapshot,_load(MANIFEST),_load(EVIDENCE))
    recovered["authoritative_sources"]=[]
    result=fidelity_score(snapshot,recovered)
    assert "AUTHORITATIVE_SOURCE_MISSING" in result["invalidating_conditions"]


def test_bitemporal_projection_reuses_existing_a2_contract():
    snapshot=_load(SNAPSHOT)
    projection=postgres_projection(snapshot)
    memory=projection["canonical_memory"]
    state=projection["operational_state"]
    assert memory["logical_memory_id"]=="SOAIACORE-MOCATRIZ-TRUSTED-MEMORY"
    assert memory["epistemic_class"]=="CONFIRMED_CONTEXT"
    assert memory["admission_state"]=="ADMITTED"
    assert state["status"]=="COMPLETED_WITH_EXCEPTIONS"
    assert state["source_authority"]=="TRUSTED_MEMORY_SNAPSHOT"
