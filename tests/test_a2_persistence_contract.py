from __future__ import annotations

from inspect import signature
from pathlib import Path

import pytest

from soaiacore_runtime.a2_persistence import _require_scope, canonical_memory_as_of


ROOT = Path(__file__).resolve().parents[1]
A2_MIGRATION = ROOT / "db" / "a2_migrations" / "1001_memory_decision_bitemporal.sql"
A2_RUNNER = ROOT / "packages" / "python-runtime" / "src" / "soaiacore_runtime" / "a2_persistence.py"


def _sql() -> str:
    return A2_MIGRATION.read_text(encoding="utf-8")


def test_a2_overlay_is_separate_from_p0_migration_directory() -> None:
    assert A2_MIGRATION.is_file()
    assert A2_MIGRATION.parent.name == "a2_migrations"
    assert A2_MIGRATION.parent != ROOT / "db" / "migrations"


def test_four_active_persistence_cores_are_materialized() -> None:
    sql = _sql()
    assert "CREATE TABLE soa_memory.canonical_memory" in sql
    assert "CREATE TABLE soa_memory.episodic_temporal_memory" in sql
    assert "CREATE TABLE soa_memory.operational_state" in sql
    assert "CREATE TABLE soa_decision.decision_ledger" in sql


def test_project_scope_is_mandatory_and_t2_to_t1_guard_is_structural() -> None:
    sql = _sql()
    assert sql.count("project_scope text NOT NULL") >= 4
    assert sql.count("recorded_time <= p_recorded_at") == 4
    assert sql.count("project_scope = p_project_scope") == 4


def test_temporal_dimensions_are_preserved() -> None:
    sql = _sql()
    for field in ("event_time", "observed_time", "recorded_time", "valid_from", "valid_until"):
        assert field in sql


def test_epistemic_classes_include_working_assumption_without_auto_fact_promotion() -> None:
    sql = _sql()
    for label in (
        "DOCUMENTED_FACT",
        "CONFIRMED_CONTEXT",
        "INFERENCE",
        "HYPOTHESIS",
        "WORKING_ASSUMPTION",
        "STALE_INFORMATION",
    ):
        assert f"'{label}'" in sql
    assert "admission_state = 'ADMITTED'" in sql


def test_decisionos_states_and_r3_human_authorization_guard() -> None:
    sql = _sql()
    for state in (
        "PROPOSED",
        "APPROVED",
        "EXECUTED",
        "VALIDATED",
        "SUPERSEDED",
        "REVOKED",
        "FAILED",
    ):
        assert f"'{state}'" in sql
    assert "authority_level <> 'R3' OR human_authorization_ref IS NOT NULL" in sql


def test_source_claim_memory_lineage_is_explicit() -> None:
    sql = _sql()
    assert "CREATE TABLE soa_memory.memory_claim_lineage" in sql
    assert "claim_id text NOT NULL REFERENCES soa_core.claims(claim_id)" in sql
    assert "evidence_ref_id text REFERENCES soa_evidence.evidence_references(evidence_ref_id)" in sql


def test_canonical_histories_are_append_only() -> None:
    sql = _sql()
    assert sql.count("BEFORE UPDATE OR DELETE") == 4
    assert "insert a new version/event instead" in sql


def test_application_read_contract_requires_recorded_at_and_project_scope() -> None:
    params = signature(canonical_memory_as_of).parameters
    assert "project_scope" in params
    assert "valid_at" in params
    assert "recorded_at" in params

    with pytest.raises(ValueError):
        _require_scope("   ")
    assert _require_scope("project-a") == "project-a"


def test_overlay_runner_is_crash_safe_between_sql_commit_and_registry_receipt() -> None:
    runner = A2_RUNNER.read_text(encoding="utf-8")
    assert "if _overlay_objects_present(connection):" in runner
    assert ":BASELINED" in runner
    assert "baselined=True" in runner
