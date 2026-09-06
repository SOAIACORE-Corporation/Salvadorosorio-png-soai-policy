from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
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
                if not _overlay_objects_present(connection):
                    raise contract_error(
                        "A2_MIGRATION_OBJECTS_MISSING",
                        f"Registered A2 migration {path.name} is incomplete",
                        "MIGRATE",
                        status_code=500,
                    )
                continue

            if _overlay_objects_present(connection):
                _record_overlay(connection, path, checksum, baselined=True)
                overlay_applied.append(f"{path.name}:BASELINED")
                continue

            sql = path.read_text(encoding="utf-8")
            connection.execute(sql, prepare=False)
            if not _overlay_objects_present(connection):
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
        relations=A2_REQUIRED_RELATIONS,
        functions=A2_REQUIRED_FUNCTIONS,
        triggers=A2_REQUIRED_TRIGGERS,
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
