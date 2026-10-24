import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "landscape"))

from trusted_memory import (  # noqa: E402
    compare_snapshot_versions,
    fidelity_score,
    reconstruct_from_snapshot,
    recovery_decision,
    select_authoritative_snapshot,
    validate_evidence_inventory,
    validate_manifest,
    validate_snapshot,
)

TMS1 = ROOT / "Trusted_Memory" / "01_Snapshots" / "TMS-SOAIACORE-MOCATRIZ-20260926-001_v1.0.0_FROZEN.yaml"
TMS2 = ROOT / "Trusted_Memory" / "01_Snapshots" / "TMS-SOAIACORE-MOCATRIZ-20260928-002_v1.1.0_FROZEN.yaml"
M2 = ROOT / "Trusted_Memory" / "02_Recovery_Manifests" / "RM-SOAIACORE-MOCATRIZ-20260928-002_v1.1.0_FROZEN.yaml"
E2 = ROOT / "Trusted_Memory" / "03_Evidence_Inventory" / "Durable_Evidence_Inventory_v1.1.0.json"
D12 = ROOT / "Trusted_Memory" / "06_Diffs" / "Snapshot_Diff_001_to_002.json"


def _load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_tms2_is_new_append_only_version_of_tms1():
    t1, t2 = _load(TMS1), _load(TMS2)
    assert t1["status"] == "FROZEN"
    assert t2["status"] == "FROZEN"
    assert t2["previous_snapshot_id"] == t1["snapshot_id"]
    assert t2["version_no"] == t1["version_no"] + 1
    assert t2["snapshot_id"] != t1["snapshot_id"]
    assert t2["content_sha256"] != t1["content_sha256"]


def test_tms2_preserves_live_error_state_without_rewriting_tms1():
    t1, t2 = _load(TMS1), _load(TMS2)
    assert t1["error_matrix"]["total"] == 27
    assert t1["error_matrix"]["controlled"] == 25
    assert t2["error_matrix"]["total"] == 28
    assert t2["error_matrix"]["controlled"] == 26
    assert t2["error_matrix"]["accepted_gaps"] == 2
    assert t2["error_matrix"]["new_since_previous"] == ["ERR-20260926-028"]


def test_tms2_hash_manifest_and_evidence_are_valid():
    t2, m2, e2 = _load(TMS2), _load(M2), _load(E2)
    assert validate_snapshot(t2)["valid"] is True
    assert validate_manifest(m2, t2)["valid"] is True
    assert validate_evidence_inventory(
        m2, e2, objective_id=t2["objective"]["objective_id"]
    )["valid"] is True


def test_tms2_is_recoverable_with_postgres_exception():
    t2, m2, e2 = _load(TMS2), _load(M2), _load(E2)
    decision = recovery_decision(m2)
    assert decision["result"] == "RECOVERABLE_WITH_EXCEPTIONS"
    assert decision["exception_requirement_ids"] == ["REQ2-005"]
    recovered = reconstruct_from_snapshot(t2, m2, e2)
    assert recovered["recovery_status"] == "RECOVERABLE_WITH_EXCEPTIONS"
    assert recovered["resume_point"]["next_objective"].startswith("Ejecutar PostgreSQL")


def test_diff_records_first_real_temporal_evolution():
    t1, t2, diff = _load(TMS1), _load(TMS2), _load(D12)
    assert diff["previous_snapshot_id"] == t1["snapshot_id"]
    assert diff["current_snapshot_id"] == t2["snapshot_id"]
    assert diff["previous_hash"] == t1["content_sha256"]
    assert diff["current_hash"] == t2["content_sha256"]
    generated = compare_snapshot_versions(t1, t2)
    assert generated["previous_snapshot_id"] == t1["snapshot_id"]
    assert generated["current_snapshot_id"] == t2["snapshot_id"]
    assert "error_matrix" in generated["changed_fields"]


def test_tms2_blind_recovery_preserves_task_continuity_without_chat_context():
    """Recover only from frozen durable artifacts and preserve the resumable task."""
    t2, m2, e2 = _load(TMS2), _load(M2), _load(E2)
    recovered = reconstruct_from_snapshot(t2, m2, e2)
    result = fidelity_score(t2, recovered)

    assert result["result"] == "PASS"
    assert result["total_score"] == 100
    assert result["invalidating_conditions"] == []
    assert result["critical_fields_preserved"] is True

    assert recovered["objective"]["objective_id"] == t2["objective"]["objective_id"]
    assert recovered["objective"]["scope_status"] == "COMPLETED_WITH_EXCEPTIONS"
    assert recovered["checkpoint"]["head"] == t2["checkpoint"]["head"]
    assert recovered["error_matrix"]["accepted_gap_ids"] == t2["error_matrix"]["accepted_gap_ids"]
    assert recovered["pending_and_exceptions"] == t2["pending_and_exceptions"]
    assert recovered["resume_point"] == t2["resume_point"]
    assert recovered["recovery_status"] == "RECOVERABLE_WITH_EXCEPTIONS"


def test_real_trusted_snapshot_selection_is_historical_as_of_not_latest_file():
    t1, t2 = _load(TMS1), _load(TMS2)

    historical = select_authoritative_snapshot(
        [t1,t2],
        logical_snapshot_id=t1["logical_snapshot_id"],
        as_of="2026-09-27T00:00:00Z",
    )
    current = select_authoritative_snapshot(
        [t1,t2],
        logical_snapshot_id=t1["logical_snapshot_id"],
        as_of="2026-10-24T00:00:00Z",
    )

    assert historical["snapshot_id"] == t1["snapshot_id"]
    assert current["snapshot_id"] == t2["snapshot_id"]


def test_tms2_bitemporal_projection_links_only_real_trusted_memory_predecessors():
    t1, t2 = _load(TMS1), _load(TMS2)
    from trusted_memory import postgres_projection

    p1 = postgres_projection(t1)["canonical_memory"]
    p2 = postgres_projection(t2)["canonical_memory"]

    assert p1["supersedes_memory_id"] is None
    assert p1["metadata"]["source_predecessor_ref"] == "CHK-MOCATRIZ-02-CLOSURE-20260926"
    assert p2["supersedes_memory_id"] == t1["snapshot_id"]
