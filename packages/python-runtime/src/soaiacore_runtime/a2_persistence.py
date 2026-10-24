from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import hashlib
from pathlib import Path
from typing import Any

from .database import Database
from .errors import contract_error
from .migrations import apply_migrations, verify_migrations


A2_REQUIRED_RELATIONS = (
    "soa_memory.canonical_memory",
    "soa_memory.episodic_temporal_memory",
    "soa_memory.operational_state",
    "soa_memory.memory_claim_lineage",
    "soa_decision.decision_ledger",
)

A2_HUMAN_TASK_RELATIONS = (
    "soa_memory.human_tasks",
    "soa_memory.human_task_responses",
)

A2_HUMAN_TASK_LIFECYCLE_RELATIONS = (
    "soa_memory.human_task_lifecycle",
)

A2_REQUIRED_FUNCTIONS = (
    "soa_memory.canonical_memory_as_of(text,timestamp with time zone,timestamp with time zone)",
    "soa_memory.episodic_memory_as_of(text,timestamp with time zone,timestamp with time zone)",
    "soa_memory.operational_state_as_of(text,timestamp with time zone,timestamp with time zone)",
    "soa_decision.decision_state_as_of(text,timestamp with time zone,timestamp with time zone)",
    "soa_memory.reject_history_mutation()",
    "soa_decision.enforce_decision_transition()",
)

A2_REQUIRED_TRIGGERS = (
    ("soa_memory", "canonical_memory", "trg_a2_canonical_memory_append_only"),
    ("soa_memory", "episodic_temporal_memory", "trg_a2_episode_append_only"),
    ("soa_memory", "operational_state", "trg_a2_operational_state_append_only"),
    ("soa_decision", "decision_ledger", "trg_a2_decision_transition"),
    ("soa_decision", "decision_ledger", "trg_a2_decision_ledger_append_only"),
)

A2_HUMAN_TASK_TRIGGERS = (
    ("soa_memory", "human_tasks", "trg_a2_human_tasks_append_only"),
    ("soa_memory", "human_task_responses", "trg_a2_human_task_responses_append_only"),
)

A2_HUMAN_TASK_RESPONSE_INDEXES = (
    ("soa_memory", "human_task_responses", "uq_a2_human_task_single_authoritative_response"),
)

A2_HUMAN_TASK_LIFECYCLE_TRIGGERS = (
    ("soa_memory", "human_task_lifecycle", "trg_a2_human_task_lifecycle_append_only"),
    ("soa_memory", "human_task_responses", "trg_a2_reject_stale_human_response"),
)

A2_HUMAN_TASK_LIFECYCLE_FUNCTIONS = (
    "soa_memory.reject_stale_human_response()",
)

A2_HUMAN_TASK_AUTHORITY_FUNCTIONS = (
    "soa_memory.human_task_response_authority(text,text,timestamp with time zone)",
)

A2_HUMAN_TASK_SCOPE_CONSTRAINTS = (
    ("soa_memory", "human_task_responses", "fk_a2_human_response_project_scope"),
    ("soa_memory", "human_task_lifecycle", "fk_a2_human_lifecycle_project_scope"),
)


@dataclass(frozen=True)
class A2PersistenceVerification:
    vector_installed: bool
    base_migrations: dict[str, str]
    overlay_migrations: dict[str, str]
    relations: tuple[str, ...]
    functions: tuple[str, ...]
    triggers: tuple[tuple[str, str, str], ...]
    working_assumption_enabled: bool


def _overlay_files(migration_dir: Path) -> list[Path]:
    return sorted(migration_dir.glob("[0-9][0-9][0-9][0-9]_*.sql"))


def _checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _relation_exists(connection, qualified_name: str) -> bool:
    row = connection.execute(
        "SELECT to_regclass(%s) IS NOT NULL AS present", (qualified_name,)
    ).fetchone()
    return bool(row and row["present"])


def _function_exists(connection, signature: str) -> bool:
    row = connection.execute(
        "SELECT to_regprocedure(%s) IS NOT NULL AS present", (signature,)
    ).fetchone()
    return bool(row and row["present"])


def _trigger_exists(connection, schema: str, table: str, trigger: str) -> bool:
    row = connection.execute(
        """
        SELECT EXISTS (
          SELECT 1
          FROM pg_trigger t
          JOIN pg_class c ON c.oid=t.tgrelid
          JOIN pg_namespace n ON n.oid=c.relnamespace
          WHERE NOT t.tgisinternal
            AND n.nspname=%s AND c.relname=%s AND t.tgname=%s
        ) AS present
        """,
        (schema, table, trigger),
    ).fetchone()
    return bool(row and row["present"])


def _index_exists(connection, schema: str, table: str, index: str) -> bool:
    row = connection.execute(
        """
        SELECT EXISTS (
          SELECT 1
          FROM pg_indexes
          WHERE schemaname=%s AND tablename=%s AND indexname=%s
        ) AS present
        """,
        (schema, table, index),
    ).fetchone()
    return bool(row and row["present"])


def _constraint_exists(connection, schema: str, table: str, constraint: str) -> bool:
    row = connection.execute(
        """
        SELECT EXISTS (
          SELECT 1
          FROM pg_constraint c
          JOIN pg_class r ON r.oid = c.conrelid
          JOIN pg_namespace n ON n.oid = r.relnamespace
          WHERE n.nspname=%s AND r.relname=%s AND c.conname=%s
        ) AS present
        """,
        (schema, table, constraint),
    ).fetchone()
    return bool(row and row["present"])


def _working_assumption_enabled(connection) -> bool:
    row = connection.execute(
        """
        SELECT pg_get_constraintdef(c.oid) AS definition
        FROM pg_constraint c
        JOIN pg_class r ON r.oid=c.conrelid
        JOIN pg_namespace n ON n.oid=r.relnamespace
        WHERE n.nspname='soa_core'
          AND r.relname='claims'
          AND c.conname='claims_epistemic_class_check'
        """
    ).fetchone()
    return bool(row and "WORKING_ASSUMPTION" in row["definition"])


def _vector_installed(connection) -> bool:
    row = connection.execute(
        "SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname='vector') AS present"
    ).fetchone()
    return bool(row and row["present"])


def _overlay_objects_present(connection) -> bool:
    return (
        all(_relation_exists(connection, name) for name in A2_REQUIRED_RELATIONS)
        and all(_function_exists(connection, signature) for signature in A2_REQUIRED_FUNCTIONS)
        and all(_trigger_exists(connection, *spec) for spec in A2_REQUIRED_TRIGGERS)
        and _working_assumption_enabled(connection)
    )


def _human_task_objects_present(connection) -> bool:
    return (
        all(_relation_exists(connection, name) for name in A2_HUMAN_TASK_RELATIONS)
        and all(_trigger_exists(connection, *spec) for spec in A2_HUMAN_TASK_TRIGGERS)
    )


def _human_response_guard_present(connection) -> bool:
    return all(_index_exists(connection, *spec) for spec in A2_HUMAN_TASK_RESPONSE_INDEXES)


def _human_task_lifecycle_present(connection) -> bool:
    return (
        all(_relation_exists(connection, name) for name in A2_HUMAN_TASK_LIFECYCLE_RELATIONS)
        and all(_function_exists(connection, signature) for signature in A2_HUMAN_TASK_LIFECYCLE_FUNCTIONS)
        and all(_trigger_exists(connection, *spec) for spec in A2_HUMAN_TASK_LIFECYCLE_TRIGGERS)
    )


def _human_task_scope_guards_present(connection) -> bool:
    return all(_constraint_exists(connection, *spec) for spec in A2_HUMAN_TASK_SCOPE_CONSTRAINTS)


def _human_task_authority_function_present(connection) -> bool:
    return all(_function_exists(connection, signature) for signature in A2_HUMAN_TASK_AUTHORITY_FUNCTIONS)


def _migration_objects_present(connection, path: Path) -> bool:
    if path.name.startswith("1001_"):
        return _overlay_objects_present(connection)
    if path.name.startswith("1002_"):
        return _human_task_objects_present(connection)
    if path.name.startswith("1003_"):
        return _human_response_guard_present(connection)
    if path.name.startswith("1004_"):
        return _human_task_lifecycle_present(connection)
    if path.name.startswith("1005_"):
        return _human_task_scope_guards_present(connection)
    if path.name.startswith("1006_"):
        return _human_task_authority_function_present(connection)
    return False


def _overlay_registry_row(connection, path: Path):
    return connection.execute(
        """
        SELECT schema_name, version, checksum_sha256
        FROM soa_ops.schema_registry
        WHERE schema_name=%s
        """,
        (f"a2-migration:{path.name}",),
    ).fetchone()


def _record_overlay(connection, path: Path, checksum: str, *, baselined: bool) -> None:
    metadata = (
        '{"runner":"soa-intelligence-a2","overlay":true,"baselined":%s}'
        % ("true" if baselined else "false")
    )
    connection.execute(
        """
        INSERT INTO soa_ops.schema_registry(schema_name,version,maturity,checksum_sha256,metadata)
        VALUES (%s,%s,'M1',%s,%s::jsonb)
        ON CONFLICT (schema_name) DO NOTHING
        """,
        (
            f"a2-migration:{path.name}",
            path.stem.split("_", 1)[0],
            checksum,
            metadata,
        ),
    )


def apply_a2_persistence(
    database: Database,
    *,
    base_migration_dir: Path,
    a2_migration_dir: Path,
) -> dict[str, list[str]]:
    """Apply shared migrations, then the isolated A2 overlay.

    This mutates only the target database. It never changes networking, IAM or
    Azure resources and must be called only after the environment execution gate.
    """

    base_applied = apply_migrations(database, base_migration_dir)
    overlay_applied: list[str] = []
    files = _overlay_files(a2_migration_dir)
    if not files:
        raise contract_error(
            "A2_MIGRATIONS_NOT_FOUND",
            "No SOA Intelligence A2 overlay migrations were found",
            "MIGRATE",
            status_code=500,
        )

    with database.connect(autocommit=True) as connection:
        if not _vector_installed(connection):
            raise contract_error(
                "A2_VECTOR_EXTENSION_MISSING",
                "Base migration did not install pgvector before the A2 overlay",
                "MIGRATE",
                status_code=503,
            )

        for path in files:
            checksum = _checksum(path)
            registered = _overlay_registry_row(connection, path)
            if registered:
                if registered["checksum_sha256"] != checksum:
                    raise contract_error(
                        "A2_MIGRATION_CHECKSUM_MISMATCH",
                        f"Checksum mismatch for {path.name}",
                        "MIGRATE",
                        status_code=500,
                    )
                if not _migration_objects_present(connection, path):
                    raise contract_error(
                        "A2_MIGRATION_OBJECTS_MISSING",
                        f"Registered A2 migration {path.name} is incomplete",
                        "MIGRATE",
                        status_code=500,
                    )
                continue

            if _migration_objects_present(connection, path):
                _record_overlay(connection, path, checksum, baselined=True)
                overlay_applied.append(f"{path.name}:BASELINED")
                continue

            sql = path.read_text(encoding="utf-8")
            connection.execute(sql, prepare=False)
            if not _migration_objects_present(connection, path):
                raise contract_error(
                    "A2_MIGRATION_VERIFICATION_FAILED",
                    f"A2 migration {path.name} did not create required objects",
                    "MIGRATE",
                    status_code=500,
                )
            _record_overlay(connection, path, checksum, baselined=False)
            overlay_applied.append(f"{path.name}:APPLIED")

    return {"base": base_applied, "a2_overlay": overlay_applied}


def verify_a2_persistence(
    database: Database,
    *,
    base_migration_dir: Path,
    a2_migration_dir: Path,
) -> A2PersistenceVerification:
    base = verify_migrations(database, base_migration_dir)
    overlay: dict[str, str] = {}
    files = _overlay_files(a2_migration_dir)
    if not files:
        raise contract_error(
            "A2_MIGRATIONS_NOT_FOUND",
            "No SOA Intelligence A2 overlay migrations were found",
            "PRECHECK",
            status_code=503,
        )

    with database.connect(autocommit=True) as connection:
        if not _vector_installed(connection):
            raise contract_error(
                "A2_VECTOR_EXTENSION_MISSING",
                "pgvector is not installed in the A2 database",
                "PRECHECK",
                status_code=503,
            )
        if not _overlay_objects_present(connection):
            raise contract_error(
                "A2_PERSISTENCE_OBJECTS_MISSING",
                "One or more A2 persistence invariants are absent",
                "PRECHECK",
                status_code=503,
            )
        if not _human_task_objects_present(connection):
            raise contract_error(
                "A2_HUMAN_TASK_OBJECTS_MISSING",
                "Durable Human Task persistence objects are absent",
                "PRECHECK",
                status_code=503,
            )
        if not _human_response_guard_present(connection):
            raise contract_error(
                "A2_HUMAN_RESPONSE_GUARD_MISSING",
                "Human Task single-authoritative-response guard is absent",
                "PRECHECK",
                status_code=503,
            )
        if not _human_task_lifecycle_present(connection):
            raise contract_error(
                "A2_HUMAN_TASK_LIFECYCLE_GUARD_MISSING",
                "Human Task lifecycle / stale-authority guard is absent",
                "PRECHECK",
                status_code=503,
            )
        if not _human_task_scope_guards_present(connection):
            raise contract_error(
                "A2_HUMAN_TASK_SCOPE_GUARD_MISSING",
                "Human Task project-scope correlation guard is absent",
                "PRECHECK",
                status_code=503,
            )
        if not _human_task_authority_function_present(connection):
            raise contract_error(
                "A2_HUMAN_TASK_AUTHORITY_RESOLVER_MISSING",
                "Bitemporal Human Task authority resolver is absent",
                "PRECHECK",
                status_code=503,
            )
        for path in files:
            checksum = _checksum(path)
            row = _overlay_registry_row(connection, path)
            if not row or row["checksum_sha256"] != checksum:
                raise contract_error(
                    "A2_MIGRATION_CHECKSUM_MISMATCH",
                    f"A2 migration registry is missing or mismatched for {path.name}",
                    "PRECHECK",
                    status_code=503,
                )
            overlay[path.name] = checksum

    return A2PersistenceVerification(
        vector_installed=True,
        base_migrations=base,
        overlay_migrations=overlay,
        relations=A2_REQUIRED_RELATIONS + A2_HUMAN_TASK_RELATIONS + A2_HUMAN_TASK_LIFECYCLE_RELATIONS,
        functions=A2_REQUIRED_FUNCTIONS + A2_HUMAN_TASK_LIFECYCLE_FUNCTIONS + A2_HUMAN_TASK_AUTHORITY_FUNCTIONS,
        triggers=A2_REQUIRED_TRIGGERS + A2_HUMAN_TASK_TRIGGERS + A2_HUMAN_TASK_LIFECYCLE_TRIGGERS,
        working_assumption_enabled=True,
    )


def _require_scope(project_scope: str) -> str:
    scope = project_scope.strip()
    if not scope:
        raise ValueError("project_scope is mandatory for A2 persistence reads")
    return scope


def canonical_memory_as_of(
    database: Database,
    *,
    project_scope: str,
    valid_at: datetime,
    recorded_at: datetime,
) -> list[dict[str, Any]]:
    scope = _require_scope(project_scope)
    with database.connect(autocommit=True) as connection:
        rows = connection.execute(
            "SELECT * FROM soa_memory.canonical_memory_as_of(%s,%s,%s)",
            (scope, valid_at, recorded_at),
        ).fetchall()
    return [dict(row) for row in rows]


def decision_state_as_of(
    database: Database,
    *,
    project_scope: str,
    valid_at: datetime,
    recorded_at: datetime,
) -> list[dict[str, Any]]:
    scope = _require_scope(project_scope)
    with database.connect(autocommit=True) as connection:
        rows = connection.execute(
            "SELECT * FROM soa_decision.decision_state_as_of(%s,%s,%s)",
            (scope, valid_at, recorded_at),
        ).fetchall()
    return [dict(row) for row in rows]


def persist_human_task(
    database: Database,
    *,
    project_scope: str,
    task: dict[str, Any],
    observed_time: datetime,
) -> None:
    """Persist a WAITING_HUMAN task durably without changing its authority semantics."""
    scope = _require_scope(project_scope)
    if task.get("status") != "WAITING_HUMAN":
        raise ValueError("only WAITING_HUMAN tasks may be persisted by this contract")
    with database.connect(autocommit=True) as connection:
        connection.execute(
            """
            INSERT INTO soa_memory.human_tasks(
              human_task_id, objective_id, execution_id, correlation_id, project_scope,
              status, reason, question, evidence_refs, resume_from, observed_time
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s)
            """,
            (
                task["human_task_id"], task["objective_id"], task["execution_id"],
                task["correlation_id"], scope, task["status"], task["reason"],
                task["question"], json.dumps(task.get("evidence", [])),
                task["resume_from"], observed_time,
            ),
            prepare=False,
        )


def persist_human_response(
    database: Database,
    *,
    project_scope: str,
    response_id: str,
    response: dict[str, Any],
    received_time: datetime,
) -> None:
    """Persist a human response only when its four-part correlation matches a durable task."""
    scope = _require_scope(project_scope)
    with database.connect(autocommit=True) as connection:
        connection.execute(
            """
            INSERT INTO soa_memory.human_task_responses(
              response_id, objective_id, execution_id, human_task_id, correlation_id,
              project_scope, answer, received_time
            ) VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s)
            """,
            (
                response_id, response["objective_id"], response["execution_id"],
                response["human_task_id"], response["correlation_id"], scope,
                json.dumps(response.get("answer")), received_time,
            ),
            prepare=False,
        )


def load_human_task_bundle(
    database: Database,
    *,
    project_scope: str,
    human_task_id: str,
    recorded_at: datetime | None = None,
) -> dict[str, Any]:
    """Recover a Human Task and resolve whether its persisted response is still authoritative.

    A later-recorded lifecycle fact may invalidate an earlier response without deleting
    that response from history. recorded_at preserves the bitemporal knowledge boundary.
    """
    scope = _require_scope(project_scope)
    at = recorded_at or datetime.now(timezone.utc)
    with database.connect(autocommit=True) as connection:
        task = connection.execute(
            """
            SELECT human_task_id, objective_id, execution_id, correlation_id, status,
                   reason, question, evidence_refs AS evidence, resume_from
            FROM soa_memory.human_tasks
            WHERE project_scope=%s AND human_task_id=%s
            """,
            (scope, human_task_id),
        ).fetchone()
        if not task:
            raise ValueError("human task not found")
        authority = connection.execute(
            "SELECT * FROM soa_memory.human_task_response_authority(%s,%s,%s)",
            (scope, human_task_id, at),
        ).fetchone()

    if not authority:
        return {
            "task": dict(task),
            "response": None,
            "invalidated_response": None,
            "authority_state": "WAITING_HUMAN",
            "invalidating_lifecycle": None,
        }

    row = dict(authority)
    response = {
        "objective_id": row["objective_id"],
        "execution_id": row["execution_id"],
        "human_task_id": row["human_task_id"],
        "correlation_id": row["correlation_id"],
        "answer": row["answer"],
    }
    invalidator = None
    if row["invalidating_lifecycle_event_id"]:
        invalidator = {
            "lifecycle_event_id": row["invalidating_lifecycle_event_id"],
            "lifecycle_state": row["invalidating_lifecycle_state"],
            "effective_time": row["invalidating_effective_time"],
            "recorded_time": row["invalidating_recorded_time"],
        }

    authoritative = bool(row["authoritative"])
    return {
        "task": dict(task),
        "response": response if authoritative else None,
        "invalidated_response": None if authoritative else response,
        "authority_state": "AUTHORITATIVE" if authoritative else "INVALIDATED",
        "invalidating_lifecycle": invalidator,
    }

def persist_human_task_lifecycle_event(
    database: Database,
    *,
    project_scope: str,
    event_id: str,
    task: dict[str, Any],
    lifecycle_state: str,
    effective_time: datetime,
    reason: str,
) -> None:
    """Append a lifecycle event that can invalidate later Human Task responses."""
    scope = _require_scope(project_scope)
    state = lifecycle_state.strip().upper()
    if state not in {"REVOKED", "SUPERSEDED", "EXPIRED"}:
        raise ValueError("lifecycle_state must be REVOKED, SUPERSEDED, or EXPIRED")
    if not reason.strip():
        raise ValueError("reason is required")
    with database.connect(autocommit=True) as connection:
        connection.execute(
            """
            INSERT INTO soa_memory.human_task_lifecycle(
              lifecycle_event_id, objective_id, execution_id, human_task_id,
              correlation_id, project_scope, lifecycle_state, effective_time, reason
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                event_id, task["objective_id"], task["execution_id"], task["human_task_id"],
                task["correlation_id"], scope, state, effective_time, reason.strip(),
            ),
            prepare=False,
        )
