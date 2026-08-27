from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from soaiacore_core.main import create_app
from soaiacore_runtime.config import RuntimeSettings
from soaiacore_runtime.database import Database
from soaiacore_runtime.migrations import apply_migrations


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def settings() -> RuntimeSettings:
    database_url = os.getenv("SOAIACORE_TEST_DATABASE_URL")
    if not database_url:
        pytest.fail("SOAIACORE_TEST_DATABASE_URL is required for the acceptance matrix")
    return RuntimeSettings(
        database_url=database_url,
        provider_mode="MOCK",
        repo_root=ROOT,
        schema_dir=ROOT / "schemas",
        migration_dir=ROOT / "db" / "migrations",
        fixture_dir=ROOT / "packages" / "mock-fixtures" / "v1",
        storage_account_name=None,
        storage_container_name=None,
        internal_auth_required=False,
    )


@pytest.fixture(scope="session")
def database(settings: RuntimeSettings) -> Database:
    active = Database(settings.database_url)
    apply_migrations(active, settings.migration_dir)
    return active


@pytest.fixture(autouse=True)
def clean_runtime_tables(database: Database):
    with database.connect(autocommit=True) as connection:
        connection.execute(
            """
            TRUNCATE TABLE
              soa_ops.context_receipts,
              soa_ops.deployment_receipts,
              soa_ops.jobs,
              soa_ops.idempotency_keys,
              soa_adjudication.ground_truth_items,
              soa_adjudication.ground_truth_ledgers,
              soa_adjudication.adjudication_ratings,
              soa_adjudication.adjudications,
              soa_intelligence.embeddings,
              soa_core.context_graph_edges,
              soa_core.claim_evidence,
              soa_core.claim_relations,
              soa_core.claims,
              soa_core.relationships,
              soa_intelligence.tool_runs,
              soa_intelligence.model_runs,
              soa_intelligence.runs,
              soa_intelligence.authorization_decisions,
              soa_intelligence.external_source_registry,
              soa_intelligence.calibration_registry,
              soa_intelligence.analysis_profiles,
              soa_core.context_capsules,
              soa_core.contexts,
              soa_evidence.evidence_transforms,
              soa_evidence.evidence_references,
              soa_evidence.evidence_objects,
              soa_evidence.source_artifacts,
              soa_identity.identity_decisions,
              soa_identity.identity_claims,
              soa_identity.aliases,
              soa_identity.canonical_subjects,
              soa_identity.observed_actors,
              soa_core.corpora,
              soa_core.projects
            CASCADE
            """,
            prepare=False,
        )
    yield


@pytest.fixture
def client(settings: RuntimeSettings) -> TestClient:
    with TestClient(create_app(settings)) as active:
        yield active

