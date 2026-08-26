from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Iterable

from psycopg import Connection

from .database import Database
from .errors import contract_error


def migration_files(migration_dir: Path) -> list[Path]:
    return sorted(migration_dir.glob("[0-9][0-9][0-9][0-9]_*.sql"))


def migration_checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _relation_exists(connection: Connection, qualified_name: str) -> bool:
    row = connection.execute(
        "SELECT to_regclass(%s) IS NOT NULL AS present", (qualified_name,)
    ).fetchone()
    return bool(row and row["present"])


def _column_exists(connection: Connection, schema: str, table: str, column: str) -> bool:
    row = connection.execute(
        """
        SELECT EXISTS (
          SELECT 1 FROM information_schema.columns
          WHERE table_schema=%s AND table_name=%s AND column_name=%s
        ) AS present
        """,
        (schema, table, column),
    ).fetchone()
    return bool(row and row["present"])


def _migration_objects_present(connection: Connection, version: str) -> bool:
    expected_relations: dict[str, Iterable[str]] = {
        "0001": ("soa_ops.schema_registry",),
        "0002": (
            "soa_core.projects",
            "soa_core.corpora",
            "soa_identity.observed_actors",
            "soa_identity.canonical_subjects",
            "soa_identity.identity_claims",
            "soa_identity.identity_decisions",
            "soa_evidence.source_artifacts",
            "soa_evidence.evidence_objects",
            "soa_evidence.evidence_references",
        ),
        "0003": (
            "soa_intelligence.analysis_profiles",
            "soa_intelligence.authorization_decisions",
            "soa_intelligence.runs",
            "soa_intelligence.model_runs",
            "soa_intelligence.tool_runs",
            "soa_intelligence.embeddings",
        ),
        "0004": (
            "soa_core.contexts",
            "soa_core.context_capsules",
            "soa_core.claims",
            "soa_core.claim_evidence",
        ),
        "0005": ("soa_core.context_graph_edges",),
        "0006": ("soa_ops.jobs", "soa_ops.context_receipts"),
        "0007": (),
        "0008": ("soa_ops.idempotency_keys",),
    }
    if not all(_relation_exists(connection, relation) for relation in expected_relations[version]):
        return False
    if version == "0001":
        row = connection.execute(
            "SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname='vector') AS present"
        ).fetchone()
        return bool(row and row["present"])
    if version == "0007":
        row = connection.execute(
            "SELECT to_regclass('soa_ops.idx_receipt_run') IS NOT NULL AS present"
        ).fetchone()
        return bool(row and row["present"])
    if version == "0008":
        return _column_exists(connection, "soa_intelligence", "runs", "context_capsule_id") and _column_exists(
            connection, "soa_core", "claims", "run_id"
        )
    return True


def _registry_row(connection: Connection, schema_name: str):
    if not _relation_exists(connection, "soa_ops.schema_registry"):
        return None
    return connection.execute(
        "SELECT schema_name, version, checksum_sha256 FROM soa_ops.schema_registry WHERE schema_name=%s",
        (schema_name,),
    ).fetchone()


def _record_migration(connection: Connection, path: Path, checksum: str, *, baselined: bool) -> None:
    connection.execute(
        """
        INSERT INTO soa_ops.schema_registry(schema_name,version,maturity,checksum_sha256,metadata)
        VALUES (%s,%s,'M1',%s,%s::jsonb)
        ON CONFLICT (schema_name) DO NOTHING
        """,
        (
            f"migration:{path.name}",
            path.stem.split("_", 1)[0],
            checksum,
            '{"runner":"soaiacore-worker","baselined":%s}'
            % ("true" if baselined else "false"),
        ),
    )


def apply_migrations(database: Database, migration_dir: Path) -> list[str]:
    applied: list[str] = []
    files = migration_files(migration_dir)
    if not files:
        raise contract_error(
            "MIGRATIONS_NOT_FOUND",
            "No numbered migrations were found",
            "MIGRATE",
            status_code=500,
        )

    with database.connect(autocommit=True) as connection:
        for path in files:
            version = path.stem.split("_", 1)[0]
            checksum = migration_checksum(path)
            registry_name = f"migration:{path.name}"
            registered = _registry_row(connection, registry_name)
            if registered:
                if registered["checksum_sha256"] != checksum:
                    raise contract_error(
                        "MIGRATION_CHECKSUM_MISMATCH",
                        f"Checksum mismatch for {path.name}",
                        "MIGRATE",
                        status_code=500,
                    )
                if not _migration_objects_present(connection, version):
                    raise contract_error(
                        "MIGRATION_OBJECTS_MISSING",
                        f"Registered migration {path.name} is incomplete",
                        "MIGRATE",
                        status_code=500,
                    )
                continue

            if _migration_objects_present(connection, version):
                _record_migration(connection, path, checksum, baselined=True)
                applied.append(f"{path.name}:BASELINED")
                continue

            sql = path.read_text(encoding="utf-8")
            connection.execute(sql, prepare=False)
            if not _migration_objects_present(connection, version):
                raise contract_error(
                    "MIGRATION_VERIFICATION_FAILED",
                    f"Migration {path.name} did not create its required objects",
                    "MIGRATE",
                    status_code=500,
                )
            _record_migration(connection, path, checksum, baselined=False)
            applied.append(f"{path.name}:APPLIED")
    return applied


def verify_migrations(database: Database, migration_dir: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    with database.connect(autocommit=True) as connection:
        for path in migration_files(migration_dir):
            version = path.stem.split("_", 1)[0]
            checksum = migration_checksum(path)
            row = _registry_row(connection, f"migration:{path.name}")
            if not row or row["checksum_sha256"] != checksum:
                raise contract_error(
                    "MIGRATION_CHECKSUM_MISMATCH",
                    f"Migration registry is missing or mismatched for {path.name}",
                    "PRECHECK",
                    status_code=503,
                    retryable=False,
                )
            if not _migration_objects_present(connection, version):
                raise contract_error(
                    "MIGRATION_OBJECTS_MISSING",
                    f"Expected objects for {path.name} are absent",
                    "PRECHECK",
                    status_code=503,
                )
            result[path.name] = checksum
    return result
