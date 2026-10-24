from __future__ import annotations

from datetime import datetime, timezone
from inspect import signature
import json
import sys
from pathlib import Path

import psycopg
import pytest

from soaiacore_runtime.a2_persistence import (
    _require_scope,
    apply_a2_persistence,
    canonical_memory_as_of,
    load_human_task_bundle,
    persist_human_response,
    persist_human_task,
    persist_human_task_lifecycle_event,
    verify_a2_persistence,
)


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "landscape"))
from trusted_memory import postgres_projection  # noqa: E402
from mocatriz_execution import create_human_task, correlate_human_response  # noqa: E402
A2_MIGRATION = ROOT / "db" / "a2_migrations" / "1001_memory_decision_bitemporal.sql"
A2_HUMAN_TASK_MIGRATION = ROOT / "db" / "a2_migrations" / "1002_mocatriz_human_task_resume.sql"
A2_HUMAN_RESPONSE_GUARD_MIGRATION = ROOT / "db" / "a2_migrations" / "1003_mocatriz_human_response_replay_guard.sql"
A2_HUMAN_TASK_LIFECYCLE_MIGRATION = ROOT / "db" / "a2_migrations" / "1004_mocatriz_human_task_lifecycle_guard.sql"
A2_HUMAN_TASK_SCOPE_MIGRATION = ROOT / "db" / "a2_migrations" / "1005_mocatriz_human_task_project_scope_guard.sql"
A2_HUMAN_TASK_AUTHORITY_MIGRATION = ROOT / "db" / "a2_migrations" / "1006_mocatriz_human_task_authority_asof.sql"
A2_RUNNER = ROOT / "packages" / "python-runtime" / "src" / "soaiacore_runtime" / "a2_persistence.py"
WORKER_MAIN = ROOT / "apps" / "worker" / "src" / "soaiacore_worker" / "__main__.py"
WORKER_DOCKERFILE = ROOT / "apps" / "worker" / "Dockerfile"


def _sql() -> str:
    return A2_MIGRATION.read_text(encoding="utf-8")


def test_a2_overlay_is_separate_from_p0_migration_directory() -> None:
    assert A2_MIGRATION.is_file()
    assert A2_HUMAN_TASK_MIGRATION.is_file()
    assert A2_HUMAN_RESPONSE_GUARD_MIGRATION.is_file()
    assert A2_HUMAN_TASK_LIFECYCLE_MIGRATION.is_file()
    assert A2_HUMAN_TASK_SCOPE_MIGRATION.is_file()
    assert A2_HUMAN_TASK_AUTHORITY_MIGRATION.is_file()
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
    assert "if _migration_objects_present(connection, path):" in runner
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


def test_tms002_round_trips_through_ephemeral_bitemporal_postgres(database) -> None:
    """Persist TMS-001 -> TMS-002 in CI Postgres and read TMS-002 back bitemporally.

    This is intentionally limited to the disposable GitHub Actions service database.
    It demonstrates real SQL write/read-back without mutating Azure or any live database.
    """
    apply_a2_persistence(
        database,
        base_migration_dir=ROOT / "db" / "migrations",
        a2_migration_dir=ROOT / "db" / "a2_migrations",
    )

    tms1_path = (
        ROOT
        / "Trusted_Memory"
        / "01_Snapshots"
        / "TMS-SOAIACORE-MOCATRIZ-20260926-001_v1.0.0_FROZEN.yaml"
    )
    tms2_path = (
        ROOT
        / "Trusted_Memory"
        / "01_Snapshots"
        / "TMS-SOAIACORE-MOCATRIZ-20260928-002_v1.1.0_FROZEN.yaml"
    )
    tms1 = json.loads(tms1_path.read_text(encoding="utf-8"))
    tms2 = json.loads(tms2_path.read_text(encoding="utf-8"))
    p1 = postgres_projection(tms1)["canonical_memory"]
    p2 = postgres_projection(tms2)["canonical_memory"]

    with database.connect(autocommit=True) as connection:
        connection.execute(
            "TRUNCATE soa_memory.memory_claim_lineage, soa_memory.canonical_memory, "
            "soa_memory.episodic_temporal_memory, soa_memory.operational_state, "
            "soa_decision.decision_ledger RESTART IDENTITY CASCADE",
            prepare=False,
        )
        for row in (p1, p2):
            connection.execute(
                """
                INSERT INTO soa_memory.canonical_memory(
                  memory_id, logical_memory_id, version_no, project_scope, subject_ref,
                  content, epistemic_class, admission_state, observed_time, valid_from,
                  valid_until, supersedes_memory_id, receipt_ref, metadata
                ) VALUES (
                  %s, %s, %s, %s, %s,
                  %s::jsonb, %s, %s, %s, %s,
                  %s, %s, %s, %s::jsonb
                )
                """,
                (
                    row["memory_id"],
                    row["logical_memory_id"],
                    row["version_no"],
                    row["project_scope"],
                    row["subject_ref"],
                    json.dumps(row["content"], ensure_ascii=False),
                    row["epistemic_class"],
                    row["admission_state"],
                    row["observed_time"],
                    row["valid_from"],
                    row["valid_until"],
                    row["supersedes_memory_id"],
                    row["receipt_ref"],
                    json.dumps(row["metadata"], ensure_ascii=False),
                ),
                prepare=False,
            )

    recovered = canonical_memory_as_of(
        database,
        project_scope=tms2["project"]["name"],
        valid_at=datetime.fromisoformat(tms2["valid_from"].replace("Z", "+00:00")),
        recorded_at=datetime.now(timezone.utc),
    )

    assert len(recovered) == 1
    row = recovered[0]
    assert row["memory_id"] == tms2["snapshot_id"]
    assert row["logical_memory_id"] == tms2["logical_snapshot_id"]
    assert row["version_no"] == 2
    assert row["content"] == p2["content"]
    assert row["metadata"]["content_sha256"] == tms2["content_sha256"]
    assert row["content"]["resume_point"]["next_objective"].startswith("Ejecutar PostgreSQL")


def test_overlay_runner_verifies_each_migration_semantically() -> None:
    runner = A2_RUNNER.read_text(encoding="utf-8")
    assert "_migration_objects_present(connection, path)" in runner
    assert 'path.name.startswith("1002_")' in runner
    assert 'path.name.startswith("1003_")' in runner
    assert 'path.name.startswith("1004_")' in runner
    assert 'path.name.startswith("1005_")' in runner
    assert 'path.name.startswith("1006_")' in runner
    assert "A2_HUMAN_TASK_RELATIONS" in runner
    assert "A2_HUMAN_TASK_TRIGGERS" in runner
    assert "A2_HUMAN_TASK_RESPONSE_INDEXES" in runner


def test_human_task_cross_session_persists_correlates_and_resumes(database) -> None:
    """SCN-030 / MOCATRIZ Test 03: durable Human Task across session boundaries."""
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
    assert "soa_memory.human_tasks" in verification.relations
    assert "soa_memory.human_task_responses" in verification.relations

    task = create_human_task(
        objective_id="OBJ-MOCATRIZ-002",
        execution_id="EXE-MOCATRIZ-002-01",
        human_task_id="HT-MOCATRIZ-002-01",
        correlation_id="CORR-MOCATRIZ-002-01",
        reason="Material human authority is required before continuing the selected branch.",
        question="Authorize or reject continuation of the authority-bound branch?",
        evidence=["TMS-002", "RM-TMS-002", "SCN-029"],
        resume_from="RESOLVE-AUTHORITY-GATE",
    )

    persist_human_task(
        database,
        project_scope="SOAiaCore",
        task=task,
        observed_time=datetime(2026, 10, 17, 23, 45, tzinfo=timezone.utc),
    )

    # Simulated later session: recover only from durable PostgreSQL state.
    recovered_before = load_human_task_bundle(
        database,
        project_scope="SOAiaCore",
        human_task_id=task["human_task_id"],
    )
    assert recovered_before["task"]["status"] == "WAITING_HUMAN"
    assert recovered_before["response"] is None
    assert recovered_before["task"]["resume_from"] == "RESOLVE-AUTHORITY-GATE"

    response = {
        "objective_id": "OBJ-MOCATRIZ-002",
        "execution_id": "EXE-MOCATRIZ-002-01",
        "human_task_id": "HT-MOCATRIZ-002-01",
        "correlation_id": "CORR-MOCATRIZ-002-01",
        "answer": {"decision": "AUTHORIZED_FOR_TEST_ONLY"},
    }
    persist_human_response(
        database,
        project_scope="SOAiaCore",
        response_id="HR-MOCATRIZ-002-01",
        response=response,
        received_time=datetime(2026, 10, 17, 23, 50, tzinfo=timezone.utc),
    )

    # Another simulated later session: reload and correlate from durable state.
    recovered_after = load_human_task_bundle(
        database,
        project_scope="SOAiaCore",
        human_task_id=task["human_task_id"],
    )
    result = correlate_human_response(
        recovered_after["task"],
        recovered_after["response"],
    )
    assert result["correlation_status"] == "MATCHED"
    assert result["resume_from"] == "RESOLVE-AUTHORITY-GATE"
    assert result["recommended_phase"] == "UNDERSTAND"

    with database.connect(autocommit=True) as connection:
        connection.execute(
            """
            INSERT INTO soa_memory.operational_state(
              state_id,state_key,version_no,project_scope,status,phase,decision,
              source_authority,source_ref,observed_time,valid_from
            ) VALUES
              ('OBJ-MOCATRIZ-002:state:v1','OBJ-MOCATRIZ-002',1,'SOAiaCore',
               'WAITING_HUMAN','RESOLVE','awaiting authority-bound response',
               'MOCATRIZ','HT-MOCATRIZ-002-01',now(),now()),
              ('OBJ-MOCATRIZ-002:state:v2','OBJ-MOCATRIZ-002',2,'SOAiaCore',
               'RUNNING','UNDERSTAND','human response correlated; reinterpret before resume',
               'HUMAN','HR-MOCATRIZ-002-01',now(),now())
            """,
            prepare=False,
        )
        latest = connection.execute(
            """
            SELECT status,phase,source_ref
            FROM soa_memory.operational_state
            WHERE project_scope='SOAiaCore' AND state_key='OBJ-MOCATRIZ-002'
            ORDER BY version_no DESC LIMIT 1
            """
        ).fetchone()
    assert latest["status"] == "RUNNING"
    assert latest["phase"] == "UNDERSTAND"
    assert latest["source_ref"] == "HR-MOCATRIZ-002-01"

    bad = {
        "objective_id": "OBJ-MOCATRIZ-002",
        "execution_id": "EXE-WRONG",
        "human_task_id": "HT-MOCATRIZ-002-01",
        "correlation_id": "CORR-MOCATRIZ-002-01",
        "answer": {"decision": "SHOULD_NOT_BIND"},
    }
    with pytest.raises(psycopg.Error):
        persist_human_response(
            database,
            project_scope="SOAiaCore",
            response_id="HR-MOCATRIZ-002-BAD",
            response=bad,
            received_time=datetime(2026, 10, 17, 23, 51, tzinfo=timezone.utc),
        )


def test_human_task_rejects_replay_or_conflicting_second_response(database) -> None:
    """SCN-031: one durable Human Task accepts one authoritative response."""
    apply_a2_persistence(
        database,
        base_migration_dir=ROOT / "db" / "migrations",
        a2_migration_dir=ROOT / "db" / "a2_migrations",
    )

    task = create_human_task(
        objective_id="OBJ-MOCATRIZ-003",
        execution_id="EXE-MOCATRIZ-003-01",
        human_task_id="HT-MOCATRIZ-003-01",
        correlation_id="CORR-MOCATRIZ-003-01",
        reason="A single authority-bound decision is required.",
        question="Authorize or reject this test branch?",
        evidence=["SCN-031"],
        resume_from="UNDERSTAND-AUTHORITY-RESULT",
    )
    persist_human_task(
        database,
        project_scope="SOAiaCore",
        task=task,
        observed_time=datetime(2026, 10, 24, 12, 0, tzinfo=timezone.utc),
    )

    base_response = {
        "objective_id": task["objective_id"],
        "execution_id": task["execution_id"],
        "human_task_id": task["human_task_id"],
        "correlation_id": task["correlation_id"],
        "answer": {"decision": "AUTHORIZED_FOR_TEST_ONLY"},
    }
    persist_human_response(
        database,
        project_scope="SOAiaCore",
        response_id="HR-MOCATRIZ-003-01",
        response=base_response,
        received_time=datetime(2026, 10, 24, 12, 1, tzinfo=timezone.utc),
    )

    conflicting = dict(base_response)
    conflicting["answer"] = {"decision": "REJECTED_AFTER_THE_FACT"}
    with pytest.raises(psycopg.Error):
        persist_human_response(
            database,
            project_scope="SOAiaCore",
            response_id="HR-MOCATRIZ-003-02",
            response=conflicting,
            received_time=datetime(2026, 10, 24, 12, 2, tzinfo=timezone.utc),
        )

    recovered = load_human_task_bundle(
        database,
        project_scope="SOAiaCore",
        human_task_id=task["human_task_id"],
    )
    assert recovered["response"]["answer"]["decision"] == "AUTHORIZED_FOR_TEST_ONLY"


def test_stale_human_authority_is_rejected_after_task_supersession(database) -> None:
    """SCN-032: correct correlation is insufficient once the Human Task is stale."""
    apply_a2_persistence(
        database,
        base_migration_dir=ROOT / "db" / "migrations",
        a2_migration_dir=ROOT / "db" / "a2_migrations",
    )

    task = create_human_task(
        objective_id="OBJ-MOCATRIZ-004",
        execution_id="EXE-MOCATRIZ-004-01",
        human_task_id="HT-MOCATRIZ-004-01",
        correlation_id="CORR-MOCATRIZ-004-01",
        reason="Authority is required against checkpoint A.",
        question="Authorize continuation against checkpoint A?",
        evidence=["checkpoint:A", "SCN-032"],
        resume_from="UNDERSTAND-CHECKPOINT-A",
    )
    persist_human_task(
        database,
        project_scope="SOAiaCore",
        task=task,
        observed_time=datetime(2026, 10, 24, 13, 0, tzinfo=timezone.utc),
    )

    persist_human_task_lifecycle_event(
        database,
        project_scope="SOAiaCore",
        event_id="HTLE-MOCATRIZ-004-01",
        task=task,
        lifecycle_state="SUPERSEDED",
        effective_time=datetime(2026, 10, 24, 13, 5, tzinfo=timezone.utc),
        reason="Checkpoint A was superseded by checkpoint B before the human answer arrived.",
    )

    stale_but_correlated = {
        "objective_id": task["objective_id"],
        "execution_id": task["execution_id"],
        "human_task_id": task["human_task_id"],
        "correlation_id": task["correlation_id"],
        "answer": {"decision": "AUTHORIZED_FOR_CHECKPOINT_A"},
    }
    with pytest.raises(psycopg.Error):
        persist_human_response(
            database,
            project_scope="SOAiaCore",
            response_id="HR-MOCATRIZ-004-LATE",
            response=stale_but_correlated,
            received_time=datetime(2026, 10, 24, 13, 10, tzinfo=timezone.utc),
        )

    recovered = load_human_task_bundle(
        database,
        project_scope="SOAiaCore",
        human_task_id=task["human_task_id"],
    )
    assert recovered["response"] is None


def test_cross_project_human_authority_is_rejected(database) -> None:
    """SCN-033: Human Task authority cannot cross project_scope boundaries."""
    apply_a2_persistence(
        database,
        base_migration_dir=ROOT / "db" / "migrations",
        a2_migration_dir=ROOT / "db" / "a2_migrations",
    )

    task = create_human_task(
        objective_id="OBJ-MOCATRIZ-005",
        execution_id="EXE-MOCATRIZ-005-01",
        human_task_id="HT-MOCATRIZ-005-01",
        correlation_id="CORR-MOCATRIZ-005-01",
        reason="Human authority is required inside Project-A only.",
        question="Authorize Project-A branch?",
        evidence=["SCN-033"],
        resume_from="UNDERSTAND-PROJECT-A",
    )
    persist_human_task(
        database,
        project_scope="Project-A",
        task=task,
        observed_time=datetime(2026, 10, 24, 14, 0, tzinfo=timezone.utc),
    )

    cross_scope_response = {
        "objective_id": task["objective_id"],
        "execution_id": task["execution_id"],
        "human_task_id": task["human_task_id"],
        "correlation_id": task["correlation_id"],
        "answer": {"decision": "AUTHORIZED_BUT_WRONG_SCOPE"},
    }
    with pytest.raises(psycopg.Error):
        persist_human_response(
            database,
            project_scope="Project-B",
            response_id="HR-MOCATRIZ-005-CROSS-SCOPE",
            response=cross_scope_response,
            received_time=datetime(2026, 10, 24, 14, 1, tzinfo=timezone.utc),
        )

    with pytest.raises(psycopg.Error):
        persist_human_task_lifecycle_event(
            database,
            project_scope="Project-B",
            event_id="HTLE-MOCATRIZ-005-CROSS-SCOPE",
            task=task,
            lifecycle_state="REVOKED",
            effective_time=datetime(2026, 10, 24, 14, 2, tzinfo=timezone.utc),
            reason="Wrong project must not revoke Project-A Human Task.",
        )

    recovered = load_human_task_bundle(
        database,
        project_scope="Project-A",
        human_task_id=task["human_task_id"],
    )
    assert recovered["response"] is None


def test_late_recorded_backdated_revocation_invalidates_prior_response(database) -> None:
    """SCN-034: later knowledge can invalidate an earlier response without deleting history."""
    apply_a2_persistence(
        database,
        base_migration_dir=ROOT / "db" / "migrations",
        a2_migration_dir=ROOT / "db" / "a2_migrations",
    )

    task = create_human_task(
        objective_id="OBJ-MOCATRIZ-006",
        execution_id="EXE-MOCATRIZ-006-01",
        human_task_id="HT-MOCATRIZ-006-01",
        correlation_id="CORR-MOCATRIZ-006-01",
        reason="Authority is requested while checkpoint A appears current.",
        question="Authorize checkpoint A?",
        evidence=["SCN-034", "checkpoint:A"],
        resume_from="UNDERSTAND-CHECKPOINT-A",
    )
    persist_human_task(
        database,
        project_scope="SOAiaCore",
        task=task,
        observed_time=datetime(2026, 10, 24, 15, 0, tzinfo=timezone.utc),
    )
    response = {
        "objective_id": task["objective_id"],
        "execution_id": task["execution_id"],
        "human_task_id": task["human_task_id"],
        "correlation_id": task["correlation_id"],
        "answer": {"decision": "AUTHORIZED_FOR_CHECKPOINT_A"},
    }
    persist_human_response(
        database,
        project_scope="SOAiaCore",
        response_id="HR-MOCATRIZ-006-01",
        response=response,
        received_time=datetime(2026, 10, 24, 15, 10, tzinfo=timezone.utc),
    )

    with database.connect(autocommit=True) as connection:
        response_recorded = connection.execute(
            """
            SELECT recorded_time
            FROM soa_memory.human_task_responses
            WHERE response_id='HR-MOCATRIZ-006-01'
            """
        ).fetchone()["recorded_time"]

    before_new_evidence = load_human_task_bundle(
        database,
        project_scope="SOAiaCore",
        human_task_id=task["human_task_id"],
        recorded_at=response_recorded,
    )
    assert before_new_evidence["authority_state"] == "AUTHORITATIVE"
    assert before_new_evidence["response"] is not None

    # Later we learn that checkpoint A had already been superseded before the answer arrived.
    persist_human_task_lifecycle_event(
        database,
        project_scope="SOAiaCore",
        event_id="HTLE-MOCATRIZ-006-LATE-FACT",
        task=task,
        lifecycle_state="SUPERSEDED",
        effective_time=datetime(2026, 10, 24, 15, 5, tzinfo=timezone.utc),
        reason="Late-arriving evidence shows checkpoint B superseded A at 15:05.",
    )

    after_new_evidence = load_human_task_bundle(
        database,
        project_scope="SOAiaCore",
        human_task_id=task["human_task_id"],
    )
    assert after_new_evidence["authority_state"] == "INVALIDATED"
    assert after_new_evidence["response"] is None
    assert after_new_evidence["invalidated_response"]["answer"]["decision"] == "AUTHORIZED_FOR_CHECKPOINT_A"
    assert after_new_evidence["invalidating_lifecycle"]["lifecycle_state"] == "SUPERSEDED"

    with database.connect(autocommit=True) as connection:
        stored = connection.execute(
            "SELECT count(*) AS n FROM soa_memory.human_task_responses WHERE response_id='HR-MOCATRIZ-006-01'"
        ).fetchone()["n"]
    assert stored == 1


def test_concurrent_human_tasks_remain_execution_isolated(database) -> None:
    """SCN-035: concurrent WAITING_HUMAN tasks must not cross-bind responses."""
    apply_a2_persistence(
        database,
        base_migration_dir=ROOT / "db" / "migrations",
        a2_migration_dir=ROOT / "db" / "a2_migrations",
    )

    task_a = create_human_task(
        objective_id="OBJ-MOCATRIZ-007",
        execution_id="EXE-MOCATRIZ-007-A",
        human_task_id="HT-MOCATRIZ-007-A",
        correlation_id="CORR-MOCATRIZ-007-A",
        reason="Execution A needs authority.",
        question="Authorize execution A?",
        evidence=["SCN-035", "execution:A"],
        resume_from="UNDERSTAND-A",
    )
    task_b = create_human_task(
        objective_id="OBJ-MOCATRIZ-007",
        execution_id="EXE-MOCATRIZ-007-B",
        human_task_id="HT-MOCATRIZ-007-B",
        correlation_id="CORR-MOCATRIZ-007-B",
        reason="Execution B needs independent authority.",
        question="Authorize execution B?",
        evidence=["SCN-035", "execution:B"],
        resume_from="UNDERSTAND-B",
    )
    persist_human_task(
        database,
        project_scope="SOAiaCore",
        task=task_a,
        observed_time=datetime(2026, 10, 24, 16, 0, tzinfo=timezone.utc),
    )
    persist_human_task(
        database,
        project_scope="SOAiaCore",
        task=task_b,
        observed_time=datetime(2026, 10, 24, 16, 0, tzinfo=timezone.utc),
    )

    response_b = {
        "objective_id": task_b["objective_id"],
        "execution_id": task_b["execution_id"],
        "human_task_id": task_b["human_task_id"],
        "correlation_id": task_b["correlation_id"],
        "answer": {"decision": "REJECT_B"},
    }
    response_a = {
        "objective_id": task_a["objective_id"],
        "execution_id": task_a["execution_id"],
        "human_task_id": task_a["human_task_id"],
        "correlation_id": task_a["correlation_id"],
        "answer": {"decision": "AUTHORIZE_A"},
    }

    # Deliberately persist B first to prove arrival order does not determine binding.
    persist_human_response(
        database,
        project_scope="SOAiaCore",
        response_id="HR-MOCATRIZ-007-B",
        response=response_b,
        received_time=datetime(2026, 10, 24, 16, 2, tzinfo=timezone.utc),
    )
    persist_human_response(
        database,
        project_scope="SOAiaCore",
        response_id="HR-MOCATRIZ-007-A",
        response=response_a,
        received_time=datetime(2026, 10, 24, 16, 3, tzinfo=timezone.utc),
    )

    recovered_a = load_human_task_bundle(
        database,
        project_scope="SOAiaCore",
        human_task_id=task_a["human_task_id"],
    )
    recovered_b = load_human_task_bundle(
        database,
        project_scope="SOAiaCore",
        human_task_id=task_b["human_task_id"],
    )

    assert recovered_a["authority_state"] == "AUTHORITATIVE"
    assert recovered_b["authority_state"] == "AUTHORITATIVE"
    assert recovered_a["response"]["answer"]["decision"] == "AUTHORIZE_A"
    assert recovered_b["response"]["answer"]["decision"] == "REJECT_B"
    assert recovered_a["task"]["execution_id"] == "EXE-MOCATRIZ-007-A"
    assert recovered_b["task"]["execution_id"] == "EXE-MOCATRIZ-007-B"
