import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "landscape"))

from trusted_memory import (  # noqa: E402
    compare_snapshot_versions,
    fidelity_score,
    persist_dual,
    postgres_projection,
    reconstruct_from_snapshot,
    recovery_decision,
    validate_evidence_inventory,
    seal_snapshot,
    sha256_hex,
    validate_manifest,
    validate_snapshot,
)


def _snapshot():
    return seal_snapshot({
        "snapshot_id":"TMS-TEST-001",
        "schema_version":"1.0",
        "snapshot_version":"1.0.0",
        "version_no":1,
        "created_at":"2026-09-26T12:24:00Z",
        "valid_from":"2026-09-26T12:24:00Z",
        "valid_until":None,
        "previous_snapshot_id":None,
        "logical_snapshot_id":"SOAIACORE-MOCATRIZ",
        "status":"FROZEN",
        "project":{"name":"SOAiaCore","capability":"Landscape Intelligence + Memory Integrity","methodology":"MOCATRIZ"},
        "objective":{
            "objective_id":"OBJ-1",
            "statement":"Validate continuity",
            "scope_status":"COMPLETED_WITH_EXCEPTIONS",
            "scope":["continuity"],
            "exclusions":["functional endpoint"],
        },
        "checkpoint":{"branch":"feat/x","head":"a"*40,"writes_frozen":True},
        "continuity":{"result":"PASS","score":30,"maximum_score":30,"invalidating_conditions":0},
        "error_matrix":{"total":27,"controlled":25,"accepted_gaps":2,"open":0},
        "metrics":{
            "correlation_integrity":{"numerator":0,"denominator":0,"result_pct":None,"status":"NOT_EXERCISED"},
        },
        "rules":[{"rule_id":"R1","statement":"Do not infer functional success"}],
        "authoritative_sources":[{"source_id":"git","authority":"PRIMARY_AUTHORITATIVE","ref":"a"*40}],
        "evidence_inventory_ref":"evidence.json",
        "decisions":[{"decision_id":"D1","decision":"COMPLETED_WITH_EXCEPTIONS"}],
        "pending_and_exceptions":{
            "exceptions":["functional endpoint not demonstrated"],
            "functional_endpoint_validation":{"status":"MISSING","interpretation":"NOT_DEMONSTRATED"},
        },
        "resume_point":{"phase":"OBSERVE","next_objective":"Trusted Memory Snapshot"},
        "metadata":{"receipt_ref":"receipt.md"},
    })


def _evidence_inventory():
    inventory = {
        "inventory_id":"EV-TEST-001",
        "evidence":[
            {"evidence_id":"EV-1","objective_id":"OBJ-1","quality":"CONFIRMED","freshness":"CURRENT"},
            {"evidence_id":"EV-2","objective_id":"OBJ-1","quality":"MISSING","freshness":"UNKNOWN"},
        ],
    }
    inventory["content_sha256"] = sha256_hex(inventory)
    return inventory


def _manifest(snapshot):
    inventory = _evidence_inventory()
    manifest = {
        "manifest_id":"RM-1",
        "manifest_version":"1.0.0",
        "schema_version":"1.0",
        "status":"FROZEN",
        "target_snapshot":{
            "snapshot_id":snapshot["snapshot_id"],
            "snapshot_version":snapshot["snapshot_version"],
            "expected_hash":snapshot["content_sha256"],
        },
        "evidence_inventory":{
            "inventory_id":inventory["inventory_id"],
            "expected_hash":inventory["content_sha256"],
        },
        "requirements":[
            {"requirement_id":"REQ-1","criticality":"critical","status":"CONFIRMED","evidence_ids":["EV-1"]},
            {"requirement_id":"REQ-2","criticality":"necessary","status":"MISSING","evidence_ids":["EV-2"]},
        ],
    }
    manifest["content_sha256"] = sha256_hex(manifest)
    return manifest


def test_snapshot_seal_and_validate():
    snapshot=_snapshot()
    result=validate_snapshot(snapshot)
    assert result["valid"] is True
    assert result["actual_content_sha256"] == snapshot["content_sha256"]


def test_hash_mismatch_fails_validation():
    snapshot=_snapshot()
    snapshot["objective"]["statement"]="tampered"
    result=validate_snapshot(snapshot)
    assert result["valid"] is False
    assert "content_hash_mismatch" in result["errors"]


def test_manifest_targets_exact_snapshot_hash():
    snapshot=_snapshot()
    manifest=_manifest(snapshot)
    assert validate_manifest(manifest,snapshot)["valid"] is True
    manifest["target_snapshot"]["expected_hash"]="0"*64
    assert "snapshot_hash_mismatch" in validate_manifest(manifest,snapshot)["errors"]


def test_missing_necessary_requirement_is_recoverable_with_exceptions():
    result=recovery_decision(_manifest(_snapshot()))
    assert result["result"]=="RECOVERABLE_WITH_EXCEPTIONS"
    assert result["blocking_requirement_ids"]==[]


def test_missing_critical_requirement_blocks_recovery():
    manifest=_manifest(_snapshot())
    manifest["requirements"][0]["status"]="MISSING"
    result=recovery_decision(manifest)
    assert result["result"]=="RECOVERY_BLOCKED"


def test_reconstruction_preserves_frozen_state():
    snapshot=_snapshot()
    recovered=reconstruct_from_snapshot(snapshot,_manifest(snapshot))
    result=fidelity_score(snapshot,recovered)
    assert result["result"]=="PASS"
    assert result["total_score"]==100
    assert result["invalidating_conditions"]==[]


def test_wrong_head_nullifies_fidelity():
    snapshot=_snapshot()
    recovered=reconstruct_from_snapshot(snapshot,_manifest(snapshot))
    recovered["checkpoint"]["head"]="b"*40
    result=fidelity_score(snapshot,recovered)
    assert result["result"]=="FAIL"
    assert "HEAD_MISMATCH" in result["invalidating_conditions"]


def test_endpoint_missing_remains_not_demonstrated():
    snapshot=_snapshot()
    recovered=reconstruct_from_snapshot(snapshot,_manifest(snapshot))
    assert recovered["pending_and_exceptions"]["functional_endpoint_validation"]["status"]=="MISSING"
    assert "FALSE_FUNCTIONAL_SUCCESS" not in fidelity_score(snapshot,recovered)["invalidating_conditions"]


def test_zero_denominator_is_not_exercised_not_100_percent():
    snapshot=_snapshot()
    recovered=reconstruct_from_snapshot(snapshot,_manifest(snapshot))
    metric=recovered["metrics"]["correlation_integrity"]
    assert metric["denominator"]==0
    assert metric["result_pct"] is None
    assert metric["status"]=="NOT_EXERCISED"


def test_frozen_exception_cannot_be_silently_removed():
    snapshot=_snapshot()
    recovered=reconstruct_from_snapshot(snapshot,_manifest(snapshot))
    recovered["pending_and_exceptions"]["exceptions"]=[]
    result=fidelity_score(snapshot,recovered)
    assert "EXCEPTION_LOSS" in result["invalidating_conditions"]
    assert result["result"]=="FAIL"


def test_complete_cannot_replace_completed_with_exceptions():
    snapshot=_snapshot()
    recovered=reconstruct_from_snapshot(snapshot,_manifest(snapshot))
    recovered["objective"]["scope_status"]="COMPLETED"
    result=fidelity_score(snapshot,recovered)
    assert "FALSE_COMPLETE_STATUS" in result["invalidating_conditions"]


def test_snapshot_diff_requires_lineage():
    previous=_snapshot()
    current=seal_snapshot({
        **{k:v for k,v in previous.items() if k!="content_sha256"},
        "snapshot_id":"TMS-TEST-002",
        "snapshot_version":"1.1.0",
        "version_no":2,
        "previous_snapshot_id":previous["snapshot_id"],
        "resume_point":{"phase":"RESOLVE","next_objective":"Versioning"},
    })
    diff=compare_snapshot_versions(previous,current)
    assert "resume_point" in diff["changed_fields"]
    assert diff["previous_snapshot_id"]==previous["snapshot_id"]


def test_dual_persistence_writes_identical_immutable_copies(tmp_path):
    snapshot=_snapshot()
    p1=tmp_path/"primary"/"snapshot.yaml"
    p2=tmp_path/"secondary"/"snapshot.yaml"
    result=persist_dual(snapshot,p1,p2)
    assert result["same_content"] is True
    try:
        persist_dual(snapshot,p1,p2)
    except FileExistsError:
        pass
    else:
        raise AssertionError("trusted persistence must be append-only")


def test_postgres_projection_reuses_existing_bitemporal_model():
    snapshot=_snapshot()
    projection=postgres_projection(snapshot)
    assert projection["canonical_memory"]["epistemic_class"]=="CONFIRMED_CONTEXT"
    assert projection["canonical_memory"]["admission_state"]=="ADMITTED"
    assert projection["operational_state"]["source_authority"]=="TRUSTED_MEMORY_SNAPSHOT"


def test_evidence_inventory_requires_confirmed_fresh_matching_evidence():
    snapshot=_snapshot()
    manifest=_manifest(snapshot)
    inventory=_evidence_inventory()
    result=validate_evidence_inventory(manifest,inventory,objective_id="OBJ-1")
    assert result["valid"] is True


def test_evidence_inventory_rejects_stale_as_confirmed():
    snapshot=_snapshot()
    manifest=_manifest(snapshot)
    inventory=_evidence_inventory()
    inventory["evidence"][0]["freshness"]="STALE"
    result=validate_evidence_inventory(manifest,inventory,objective_id="OBJ-1")
    assert result["valid"] is False
    assert any("stale_evidence_as_current" in e for e in result["errors"])


def test_evidence_inventory_rejects_wrong_objective_correlation():
    snapshot=_snapshot()
    manifest=_manifest(snapshot)
    inventory=_evidence_inventory()
    inventory["evidence"][0]["objective_id"]="OBJ-OTHER"
    result=validate_evidence_inventory(manifest,inventory,objective_id="OBJ-1")
    assert result["valid"] is False
    assert any("evidence_objective_mismatch" in e for e in result["errors"])


def test_blind_reconstruction_requires_manifest_and_evidence_to_agree():
    snapshot=_snapshot()
    manifest=_manifest(snapshot)
    recovered=reconstruct_from_snapshot(snapshot,manifest,_evidence_inventory())
    assert recovered["objective"]["objective_id"]=="OBJ-1"


def test_canonical_hash_is_stable_for_integral_float_representation():
    assert sha256_hex({"value":100}) == sha256_hex({"value":100.0})
