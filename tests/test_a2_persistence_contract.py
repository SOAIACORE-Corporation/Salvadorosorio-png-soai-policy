from __future__ import annotations

from datetime import datetime, timezone
from inspect import signature
from pathlib import Path

import psycopg
import pytest

from soaiacore_runtime.a2_persistence import (
    _require_scope,
    apply_a2_persistence,
    canonical_memory_as_of,
    verify_a2_persistence,
)


ROOT = Path(__file__).resolve().parents[1]
A2_MIGRATION = ROOT / "db" / "a2_migrations" / "1001_memory_decision_bitemporal.sql"
A2_RUNNER = ROOT / "packages" / "python-runtime" / "src" / "soaiacore_runtime" / "a2_persistence.py"
WORKER_MAIN = ROOT / "apps" / "worker" / "src" / "soaiacore_worker" / "__main__.py"
WORKER_DOCKERFILE = ROOT / "apps" / "worker" / "Dockerfile"


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
    assert "claims_epistemic_class_check" in sql
    assert "admission_state = 'ADMITTED'" in sql


def test_decisionos_transition_and_authority_guards_are_materialized() -> None:
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
    assert "CREATE OR REPLACE FUNCTION soa_decision.enforce_decision_transition()" in sql
    assert "trg_a2_decision_transition" in sql
    assert "state requires R2 or R3 authority" in sql
    assert "first event must be PROPOSED at R1" in sql
    assert "authority_level <> 'R3' OR human_authorization_ref IS NOT NULL" in sql


def test_source_claim_memory_lineage_supports_multiple_evidence_links() -> None:
    sql = _sql()
    assert "CREATE TABLE soa_memory.memory_claim_lineage" in sql
    assert "lineage_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY" in sql
    assert "claim_id text NOT NULL REFERENCES soa_core.claims(claim_id)" in sql
    assert "evidence_ref_id text REFERENCES soa_evidence.evidence_references(evidence_ref_id)" in sql
    assert "UNIQUE NULLS NOT DISTINCT" in sql


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


def test_overlay_runner_is_crash_safe_and_verifies_semantic_guards() -> None:
    runner = A2_RUNNER.read_text(encoding="utf-8")
    assert "if _overlay_objects_present(connection):" in runner
    assert ":BASELINED" in runner
    assert "baselined=True" in runner
    assert "A2_REQUIRED_TRIGGERS" in runner
    assert "_working_assumption_enabled" in runner
    assert "soa_decision.enforce_decision_transition()" in runner


def test_worker_image_packages_a2_overlay_and_exposes_explicit_commands() -> None:
    dockerfile = WORKER_DOCKERFILE.read_text(encoding="utf-8")
    worker = WORKER_MAIN.read_text(encoding="utf-8")

    assert "COPY db/a2_migrations /app/db/a2_migrations" in dockerfile
    assert '"a2-migrate"' in worker
    assert '"a2-verify"' in worker
    assert '"a2-bootstrap"' in worker
    assert "apply_a2_persistence(" in worker
    assert "verify_a2_persistence(" in worker
    assert '"A2_MIGRATE_PASS"' in worker
    assert '"A2_VERIFY_PASS"' in worker
    assert '"A2_BOOTSTRAP_PASS"' in worker
    assert "project_scope_required=True" in worker
    assert "recorded_time_guard=True" in worker


def test_postgres_semantics_block_t2_leak_and_illegal_decision_authority(database) -> None:
    apply_a2_persistence(
        database,
        base_migration_dir=ROOT / "db" / "migrations",
        a2_migration_dir=ROOT / "db" / "a2_migrations",
    )
    verification = verify_a2_persistence(
        database,
        base_migration_dir=ROOT / "db" / "migrations",
        a2_migration_dir=ROOT / "db" / "a2_migrations",
    )
    assert verification.vector_installed is True
    assert verification.working_assumption_enabled is True
    assert any(spec[2] == "trg_a2_decision_transition" for spec in verification.triggers)

    t1_valid = datetime(2026, 1, 15, tzinfo=timezone.utc)
    t1_recorded = datetime(2026, 1, 20, tzinfo=timezone.utc)
    t2_recorded = datetime(2026, 2, 20, tzinfo=timezone.utc)

    with database.connect(autocommit=True) as connection:
        connection.execute(
            "TRUNCATE soa_memory.memory_claim_lineage, soa_memory.canonical_memory, "
            "soa_memory.episodic_temporal_memory, soa_memory.operational_state, "
            "soa_decision.decision_ledger RESTART IDENTITY CASCADE",
            prepare=False,
        )
        connection.execute(
            """
            INSERT INTO soa_core.claims(claim_id,statement,claim_kind,epistemic_class)
            VALUES ('claim-working','working assumption','OBSERVATION','WORKING_ASSUMPTION')
            """,
            prepare=False,
        )
        connection.execute(
            """
            INSERT INTO soa_memory.canonical_memory(
              memory_id,logical_memory_id,version_no,project_scope,content,
              epistemic_class,admission_state,observed_time,recorded_time,valid_from
            ) VALUES
              ('mem-v1','logical-1',1,'project-a','{"value":"T1"}'::jsonb,
               'DOCUMENTED_FACT','ADMITTED','2026-01-01Z','2026-01-10Z','2026-01-01Z'),
              ('mem-v2','logical-1',2,'project-a','{"value":"T2"}'::jsonb,
               'DOCUMENTED_FACT','ADMITTED','2026-02-01Z','2026-02-10Z','2026-01-01Z')
            """,
            prepare=False,
        )

    at_t1 = canonical_memory_as_of(
        database,
        project_scope="project-a",
        valid_at=t1_valid,
        recorded_at=t1_recorded,
    )
    assert len(at_t1) == 1
    assert at_t1[0]["memory_id"] == "mem-v1"

    at_t2 = canonical_memory_as_of(
        database,
        project_scope="project-a",
        valid_at=t1_valid,
        recorded_at=t2_recorded,
    )
    assert len(at_t2) == 1
    assert at_t2[0]["memory_id"] == "mem-v2"

    with database.connect(autocommit=True) as connection:
        with pytest.raises(psycopg.Error):
            connection.execute(
                "UPDATE soa_memory.canonical_memory SET content='{}'::jsonb WHERE memory_id='mem-v1'"
            )

        connection.execute(
            """
            INSERT INTO soa_decision.decision_ledger(
              decision_event_id,decision_id,event_seq,project_scope,state,authority_level,
              observed_time,valid_from
            ) VALUES ('d1-e1','d1',1,'project-a','PROPOSED','R1',now(),now())
            """,
            prepare=False,
        )
        with pytest.raises(psycopg.Error):
            connection.execute(
                """
                INSERT INTO soa_decision.decision_ledger(
                  decision_event_id,decision_id,event_seq,project_scope,state,authority_level,
                  observed_time,valid_from,previous_event_id
                ) VALUES ('d1-e2-bad','d1',2,'project-a','APPROVED','R1',now(),now(),'d1-e1')
                """,
                prepare=False,
            )
        connection.execute(
            """
            INSERT INTO soa_decision.decision_ledger(
              decision_event_id,decision_id,event_seq,project_scope,state,authority_level,
              observed_time,valid_from,previous_event_id
            ) VALUES ('d1-e2','d1',2,'project-a','APPROVED','R2',now(),now(),'d1-e1')
            """,
            prepare=False,
        )
        count = connection.execute(
            "SELECT count(*) AS n FROM soa_decision.decision_ledger WHERE decision_id='d1'"
        ).fetchone()["n"]
        assert count == 2

        connection.execute(
            "TRUNCATE soa_memory.memory_claim_lineage, soa_memory.canonical_memory, "
            "soa_memory.episodic_temporal_memory, soa_memory.operational_state, "
            "soa_decision.decision_ledger RESTART IDENTITY CASCADE",
            prepare=False,
        )
