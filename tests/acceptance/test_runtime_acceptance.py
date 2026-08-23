from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
from typing import Any

import pytest
from jsonschema import Draft202012Validator
from psycopg.errors import RaiseException, UniqueViolation

from soaiacore_runtime.context_graph import edge_to_schema
from soaiacore_runtime.database import Database
from soaiacore_runtime.lifecycle import claim_one_job, execute_claimed_job, run_one
from soaiacore_runtime.mock import deterministic_embedding, load_mock_fixture
from soaiacore_runtime.schemas import validate_payload


ROOT = Path(__file__).resolve().parents[2]


def idem(name: str) -> dict[str, str]:
    return {"Idempotency-Key": f"acceptance-{name}"}


def profile_payload(mode: str = "NONE", *, restricted: bool = False) -> dict[str, Any]:
    return {
        "analysis_profile_id": "AP-101",
        "version": "1.0.0",
        "name": f"P0 Acceptance {mode}",
        "method_families": ["EXTRACTION"],
        "human_review_mode": mode,
        "restricted_workflow": restricted,
        "inference_regime": "LOW",
        "evidence_requirements": {
            "minimum_state": "ADMISSIBLE",
            "counterevidence_required": False,
            "negative_audit_sample": "NOT_REQUIRED",
            "provenance_required": True,
        },
        "output_semantics": ["OBSERVATION"],
        "authorization_tier": "T0_STANDARD",
        "metadata": {"synthetic_only": True},
    }


def bootstrap(
    client,
    *,
    suffix: str = "base",
    review_mode: str = "NONE",
    fixture_id: str = "documented-observation",
    synthetic_only: bool = True,
    evidence_state: str = "ADMISSIBLE",
    run_key: str | None = None,
) -> dict[str, Any]:
    project_id = f"prj_{suffix}"
    corpus_id = f"cor_{suffix}"
    context_id = f"ctx_{suffix}"
    capsule_id = f"cap_{suffix}"
    subject_id = f"sub_{suffix}"
    evidence_ref_id = f"evref_{suffix}"
    content = f"SOAIACORE deterministic synthetic evidence {suffix}".encode()
    content_hash = hashlib.sha256(content).hexdigest()

    assert client.put(
        f"/v1/projects/{project_id}",
        json={"name": f"Project {suffix}", "metadata": {"synthetic": True}},
        headers=idem(f"project-{suffix}"),
    ).status_code == 200
    assert client.put(
        f"/v1/projects/{project_id}/corpora/{corpus_id}",
        json={"name": f"Corpus {suffix}", "metadata": {"synthetic": True}},
        headers=idem(f"corpus-{suffix}"),
    ).status_code == 200
    profile = profile_payload(review_mode)
    assert client.put(
        "/v1/analysis-profiles/AP-101/versions/1.0.0",
        json=profile,
        headers=idem(f"profile-{suffix}"),
    ).status_code == 200
    identity_response = client.post(
        "/v1/identity/resolve",
        json={
            "observed_actor_id": f"act_{suffix}",
            "corpus_id": corpus_id,
            "source_local_ref": f"fixture://actor/{suffix}",
            "display_label": "Synthetic actor",
            "canonical_subject_id": subject_id,
            "identity_resolution_status": "ADJUDICATED",
            "identity_claim_id": f"idc_{suffix}",
            "identity_decision_id": f"idd_{suffix}",
            "decision_type": "LINK",
            "evidence_refs": [evidence_ref_id],
        },
        headers=idem(f"identity-{suffix}"),
    )
    assert identity_response.status_code == 200, identity_response.text
    evidence_response = client.post(
        "/v1/evidence/register",
        json={
            "source_id": f"src_{suffix}",
            "corpus_id": corpus_id,
            "source_type": "TEXT",
            "source_locator": f"fixture://source/{suffix}",
            "content_sha256": content_hash,
            "byte_size": len(content),
            "evidence_id": f"ev_{suffix}",
            "evidence_state": evidence_state,
            "object_locator": f"fixture://object/{suffix}",
            "modality": "TEXT",
            "evidence_ref_id": evidence_ref_id,
            "locator": "bytes:0-*",
            "support_type": "DIRECT",
            "relationship": "SUPPORTS",
            "admissibility_scope": "AP-101",
        },
        headers=idem(f"evidence-{suffix}"),
    )
    assert evidence_response.status_code == 200, evidence_response.text
    assert client.post(
        "/v1/contexts",
        json={
            "context_id": context_id,
            "project_id": project_id,
            "context_type": "P0_SYNTHETIC",
            "dimensions": {"corpus_id": corpus_id, "synthetic": True},
        },
        headers=idem(f"context-{suffix}"),
    ).status_code == 200
    capsule_payload = {
        "project_id": project_id,
        "corpus_id": corpus_id,
        "context_id": context_id,
        "analysis_profile_id": "AP-101",
        "analysis_profile_version": "1.0.0",
        "identity_refs": [subject_id],
        "evidence_refs": [evidence_ref_id],
        "synthetic_only": synthetic_only,
        "purpose": "P0_ACCEPTANCE",
    }
    capsule_response = client.post(
        "/v1/context-capsules",
        json={
            "context_capsule_id": capsule_id,
            "context_id": context_id,
            "schema_version": "P0-RUNTIME-1",
            "payload": capsule_payload,
        },
        headers=idem(f"capsule-{suffix}"),
    )
    assert capsule_response.status_code == 200, capsule_response.text
    run_response = client.post(
        "/v1/runs",
        json={
            "context_capsule_id": capsule_id,
            "analysis_profile_id": "AP-101",
            "analysis_profile_version": "1.0.0",
            "purpose": "P0_ACCEPTANCE",
            "mode": "MOCK",
            "mock_fixture_id": fixture_id,
        },
        headers=idem(run_key or f"run-{suffix}"),
    )
    assert run_response.status_code == 202, run_response.text
    return {
        **run_response.json(),
        "project_id": project_id,
        "corpus_id": corpus_id,
        "context_id": context_id,
        "capsule_id": capsule_id,
        "subject_id": subject_id,
        "evidence_ref_id": evidence_ref_id,
        "profile": profile,
    }


def complete_run(client, database: Database, settings, **kwargs):
    resources = bootstrap(client, **kwargs)
    result = run_one(database, settings)
    return resources, result


def test_SCHEMAS_authoritative_documents_are_valid():
    schemas = sorted((ROOT / "schemas").glob("*.json"))
    assert schemas
    for path in schemas:
        Draft202012Validator.check_schema(json.loads(path.read_text(encoding="utf-8")))


def test_CORE_API_exposes_required_openapi_operations(client):
    openapi = client.get("/openapi.json").json()
    required = {
        "/health/live",
        "/health/ready",
        "/v1/projects/{project_id}",
        "/v1/projects/{project_id}/corpora/{corpus_id}",
        "/v1/analysis-profiles/{profile_id}/versions/{version}",
        "/v1/identity/resolve",
        "/v1/evidence/register",
        "/v1/contexts",
        "/v1/context-capsules",
        "/v1/runs",
        "/v1/runs/{run_id}/claims",
        "/v1/runs/{run_id}/receipt",
        "/v1/context-graph/edges",
        "/v1/context-graph/traverse",
    }
    assert required.issubset(openapi["paths"])


def test_IDEMPOTENCY_replays_same_request_and_rejects_conflict(client):
    headers = idem("idempotency")
    first = client.put(
        "/v1/projects/prj_idempotent", json={"name": "One"}, headers=headers
    )
    second = client.put(
        "/v1/projects/prj_idempotent", json={"name": "One"}, headers=headers
    )
    conflict = client.put(
        "/v1/projects/prj_idempotent", json={"name": "Different"}, headers=headers
    )
    assert first.status_code == 200
    assert second.headers["Idempotency-Replayed"] == "true"
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"


def test_PERSISTENCE_runtime_relations_and_append_only_receipt(client, database, settings):
    resources, result = complete_run(client, database, settings, suffix="persistence")
    assert result.exit_code == 0
    with database.connect(autocommit=True) as connection:
        relation = connection.execute(
            """
            SELECT r.context_capsule_id,c.run_id,cr.context_receipt_id
            FROM soa_intelligence.runs r
            JOIN soa_core.claims c ON c.run_id=r.run_id
            JOIN soa_ops.context_receipts cr ON cr.run_id=r.run_id
            WHERE r.run_id=%s
            """,
            (resources["run_id"],),
        ).fetchone()
        assert relation["context_capsule_id"] == resources["capsule_id"]
        with pytest.raises(RaiseException):
            connection.execute(
                "UPDATE soa_ops.context_receipts SET output_status='MUTATED' WHERE run_id=%s",
                (resources["run_id"],),
            )
    with database.connect() as connection:
        with pytest.raises(UniqueViolation):
            connection.execute(
                """
                INSERT INTO soa_ops.context_receipts(context_receipt_id,run_id,output_status)
                VALUES ('cr_duplicate',%s,'COMPLETED')
                """,
                (resources["run_id"],),
            )


def test_IDENTITY_is_resolved_and_persisted(client, database):
    resources = bootstrap(client, suffix="identity")
    with database.connect(autocommit=True) as connection:
        row = connection.execute(
            """
            SELECT cs.identity_resolution_status,id.decision_type
            FROM soa_identity.canonical_subjects cs
            JOIN soa_identity.identity_decisions id
              ON id.canonical_subject_id=cs.canonical_subject_id
            WHERE cs.canonical_subject_id=%s
            """,
            (resources["subject_id"],),
        ).fetchone()
    assert row == {"identity_resolution_status": "ADJUDICATED", "decision_type": "LINK"}


def test_EVIDENCE_has_real_hash_and_provenance_chain(client, database):
    resources = bootstrap(client, suffix="evidence")
    with database.connect(autocommit=True) as connection:
        row = connection.execute(
            """
            SELECT er.evidence_ref_id,eo.content_sha256,
                   sa.content_sha256 AS source_sha256
            FROM soa_evidence.evidence_references er
            JOIN soa_evidence.evidence_objects eo ON eo.evidence_id=er.evidence_id
            JOIN soa_evidence.source_artifacts sa ON sa.source_id=er.source_id
            WHERE er.evidence_ref_id=%s
            """,
            (resources["evidence_ref_id"],),
        ).fetchone()
    assert row["content_sha256"] == row["source_sha256"]
    assert len(row["content_sha256"]) == 64


def test_WORKER_SINGLE_JOB_CLAIM_uses_skip_locked(client, database):
    first = bootstrap(client, suffix="claimone", run_key="claim-one")
    second = client.post(
        "/v1/runs",
        json={
            "context_capsule_id": first["capsule_id"],
            "analysis_profile_id": "AP-101",
            "analysis_profile_version": "1.0.0",
            "purpose": "P0_ACCEPTANCE",
            "mode": "MOCK",
            "mock_fixture_id": "documented-observation",
        },
        headers=idem("claim-two"),
    ).json()
    locking = database.connect()
    transaction = locking.transaction()
    transaction.__enter__()
    locked = locking.execute(
        """
        SELECT job_id FROM soa_ops.jobs WHERE status='QUEUED'
        ORDER BY created_at,job_id FOR UPDATE SKIP LOCKED LIMIT 1
        """
    ).fetchone()
    claimed = claim_one_job(database)
    transaction.__exit__(None, None, None)
    locking.close()
    assert claimed is not None
    assert claimed["job_id"] != locked["job_id"]
    remaining = claim_one_job(database)
    assert remaining is not None
    assert {claimed["run_id"], remaining["run_id"]} == {first["run_id"], second["run_id"]}
    assert claim_one_job(database) is None


def test_MOCK_ZERO_EXTERNAL_CALLS(client, database, settings, monkeypatch):
    bootstrap(client, suffix="nonetwork")
    original = socket.create_connection
    calls = []
    def forbidden(*args, **kwargs):
        calls.append(args)
        raise AssertionError("external network call attempted")
    monkeypatch.setattr(socket, "create_connection", forbidden)
    result = run_one(database, settings)
    monkeypatch.setattr(socket, "create_connection", original)
    assert result.exit_code == 0
    assert calls == []
    with database.connect(autocommit=True) as connection:
        usage = connection.execute(
            "SELECT usage_metadata FROM soa_intelligence.model_runs"
        ).fetchone()["usage_metadata"]
    assert usage["external_calls"] == 0


def test_MOCK_DETERMINISM_produces_same_semantics(client, database, settings):
    first = bootstrap(client, suffix="determinism", run_key="determinism-one")
    assert run_one(database, settings).exit_code == 0
    second_response = client.post(
        "/v1/runs",
        json={
            "context_capsule_id": first["capsule_id"],
            "analysis_profile_id": "AP-101",
            "analysis_profile_version": "1.0.0",
            "purpose": "P0_ACCEPTANCE",
            "mode": "MOCK",
            "mock_fixture_id": "documented-observation",
        },
        headers=idem("determinism-two"),
    )
    assert second_response.status_code == 202
    assert run_one(database, settings).exit_code == 0
    with database.connect(autocommit=True) as connection:
        rows = connection.execute(
            """
            SELECT c.statement,m.response_hash,e.embedding::text
            FROM soa_core.claims c
            JOIN soa_intelligence.model_runs m ON m.run_id=c.run_id
            JOIN soa_intelligence.embeddings e ON e.owner_id=c.claim_id
            ORDER BY c.run_id
            """
        ).fetchall()
    assert len(rows) == 2
    assert rows[0]["statement"] == rows[1]["statement"]
    assert rows[0]["response_hash"] == rows[1]["response_hash"]
    assert rows[0]["embedding"] == rows[1]["embedding"]


def test_CLAIMS_conform_to_authoritative_schema(client, database, settings):
    resources, result = complete_run(client, database, settings, suffix="claims")
    assert result.exit_code == 0
    response = client.get(f"/v1/runs/{resources['run_id']}/claims")
    assert response.status_code == 200
    claims = response.json()
    assert len(claims) == 1
    validate_payload("claim-v0.2.schema.json", claims[0], settings=settings)


def test_CLAIM_EVIDENCE_is_relational(client, database, settings):
    resources, result = complete_run(client, database, settings, suffix="claimevidence")
    assert result.exit_code == 0
    with database.connect(autocommit=True) as connection:
        row = connection.execute(
            """
            SELECT c.run_id,ce.evidence_role,er.evidence_ref_id
            FROM soa_core.claims c
            JOIN soa_core.claim_evidence ce ON ce.claim_id=c.claim_id
            JOIN soa_evidence.evidence_references er ON er.evidence_ref_id=ce.evidence_ref_id
            WHERE c.run_id=%s
            """,
            (resources["run_id"],),
        ).fetchone()
    assert row["evidence_role"] == "SUPPORTING"
    assert row["evidence_ref_id"] == resources["evidence_ref_id"]


def test_CONTEXT_GRAPH_operations_are_persisted(client, database, settings):
    resources, result = complete_run(client, database, settings, suffix="graph")
    assert result.exit_code == 0
    with database.connect(autocommit=True) as connection:
        edge = connection.execute(
            "SELECT * FROM soa_core.context_graph_edges WHERE metadata->>'run_id'=%s",
            (resources["run_id"],),
        ).fetchone()
        edge_payload = edge_to_schema(edge)
    neighbors_response = client.get(
        "/v1/context-graph/neighbors",
        params={"ref": resources["subject_id"], "direction": "OUT"},
    )
    traversal = client.post(
        "/v1/context-graph/traverse",
        json={"start_ref": resources["subject_id"], "max_depth": 4},
    )
    path_response = client.get(
        "/v1/context-graph/path",
        params={"from_ref": resources["subject_id"], "to_ref": resources["context_id"]},
    )
    replacement = {
        **edge_payload,
        "edge_id": "edge_graph_replacement",
        "relation_type": "SYNCHRONIZED_WITH",
    }
    superseded = client.post(
        f"/v1/context-graph/edges/{edge_payload['edge_id']}:supersede",
        json=replacement,
        headers=idem("graph-supersede"),
    )
    history = client.get(
        f"/v1/context-graph/edges/{edge_payload['edge_id']}/history"
    )
    assert neighbors_response.status_code == 200 and len(neighbors_response.json()) == 1
    assert traversal.status_code == 200 and traversal.json()[0]["depth"] == 1
    assert path_response.json()["path"] == [resources["subject_id"], resources["context_id"]]
    assert superseded.status_code == 200
    assert len(history.json()) == 2


def test_PGVECTOR_persists_selective_deterministic_embedding(client, database, settings):
    resources, result = complete_run(client, database, settings, suffix="vector")
    assert result.exit_code == 0
    with database.connect(autocommit=True) as connection:
        row = connection.execute(
            """
            SELECT vector_dims(e.embedding) AS dimensions,e.evidence_ref_id
            FROM soa_intelligence.embeddings e
            JOIN soa_core.claims c ON c.claim_id=e.owner_id
            WHERE c.run_id=%s
            """,
            (resources["run_id"],),
        ).fetchone()
    assert row == {"dimensions": 8, "evidence_ref_id": resources["evidence_ref_id"]}


def test_AUTOMATED_VALIDATION_records_real_checks(client, database, settings):
    resources, result = complete_run(client, database, settings, suffix="validation")
    assert result.exit_code == 0
    run = client.get(f"/v1/runs/{resources['run_id']}").json()
    checks = run["metadata"]["automated_validation"]["checks"]
    assert checks and all(checks.values())
    assert run["metadata"]["lifecycle"]["AUTOMATED_VALIDATION"] == "PASS"


@pytest.mark.parametrize("mode", ["NONE", "OPTIONAL"])
def test_REVIEW_POLICY_NON_REQUIRED_modes(client, database, settings, mode):
    resources, result = complete_run(
        client, database, settings, suffix=f"review{mode.lower()}", review_mode=mode
    )
    assert result.exit_code == 0
    receipt = client.get(f"/v1/runs/{resources['run_id']}/receipt").json()
    assert receipt["review_mode"] == mode
    assert receipt["output_status"] == "COMPLETED"


def test_REVIEW_POLICY_REQUIRED_blocks_downstream_without_worker_failure(client, database, settings):
    resources, result = complete_run(
        client, database, settings, suffix="reviewrequired", review_mode="REQUIRED"
    )
    assert result.exit_code == 0
    assert result.status == "REVIEW_REQUIRED"
    receipt = client.get(f"/v1/runs/{resources['run_id']}/receipt").json()
    assert receipt["review_mode"] == "REQUIRED"
    assert receipt["output_status"] == "REVIEW_REQUIRED"


def test_RECEIPT_SUCCESS_is_terminal_and_complete(client, database, settings):
    resources, result = complete_run(client, database, settings, suffix="receipt")
    assert result.receipt_id
    receipt = client.get(f"/v1/receipts/{result.receipt_id}").json()
    assert receipt["run_id"] == resources["run_id"]
    assert receipt["precheck_status"] == "PASS"
    assert len(receipt["claims_created"]) == 1
    assert len(receipt["input_hash"]) == len(receipt["context_hash"]) == len(receipt["output_hash"]) == 64


def test_RECEIPT_TERMINAL_FAILURES_are_persisted(client, database, settings):
    resources = bootstrap(client, suffix="terminalfailure", fixture_id="invalid-output")
    result = run_one(database, settings)
    assert result.exit_code == 24
    receipt = client.get(f"/v1/runs/{resources['run_id']}/receipt").json()
    assert receipt["output_status"] == "FAILED_VALIDATION"
    assert receipt["precheck_status"] == "FAIL"
    assert receipt["limitations"][0]["code"] == "SCHEMA_VALIDATION_FAILED"


def test_WEB_BFF_node_acceptance_suite_passes():
    npm = shutil.which("npm.cmd") or shutil.which("npm")
    assert npm, "npm is required"
    completed = subprocess.run(
        [npm, "test"],
        cwd=ROOT / "apps" / "web",
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_HEALTH_READINESS_distinguishes_live_and_ready(client):
    live = client.get("/health/live")
    ready = client.get("/health/ready")
    assert live.status_code == 200 and live.json()["status"] == "LIVE"
    assert ready.status_code == 200 and ready.json()["status"] == "READY"
    assert ready.json()["provider_mode"] == "MOCK"


def test_SECRET_LEAK_CHECK_new_source_has_no_hardcoded_secrets():
    roots = [ROOT / "apps", ROOT / "packages", ROOT / "tests"]
    forbidden = [
        "BEGIN " + "PRIVATE KEY",
        "AZURE_CLIENT_" + "SECRET=",
        "POSTGRES_" + "PASSWORD=",
        "gh" + "p_",
        "github_" + "pat_",
        "Account" + "Key=",
    ]
    for root in roots:
        for path in root.rglob("*"):
            if not path.is_file() or "node_modules" in path.parts or ".next" in path.parts:
                continue
            if path.suffix.lower() not in {".py", ".js", ".mjs", ".json", ".toml"}:
                continue
            content = path.read_text(encoding="utf-8", errors="ignore")
            assert not any(token in content for token in forbidden), path


def test_CONTAINER_CONTRACTS_are_pinned_non_root_and_finite():
    core = (ROOT / "apps/core/Dockerfile").read_text(encoding="utf-8")
    web = (ROOT / "apps/web/Dockerfile").read_text(encoding="utf-8")
    worker = (ROOT / "apps/worker/Dockerfile").read_text(encoding="utf-8")
    for content in (core, web, worker):
        assert "@sha256:" in content
        assert "USER 65532:65532" in content
        assert ":latest" not in content
        assert "--platform=linux/amd64" in content
    assert "EXPOSE 8000" in core
    assert "EXPOSE 3000" in web
    assert "run-one" in worker and "EXPOSE" not in worker


def test_E2E_LIFECYCLE_executes_every_stage_and_persists_receipt(client, database, settings):
    resources, result = complete_run(client, database, settings, suffix="e2e")
    assert result.exit_code == 0
    run = client.get(f"/v1/runs/{resources['run_id']}").json()
    expected = {
        "CONTEXT",
        "SYNC",
        "PRECHECK",
        "EXECUTION",
        "AUTOMATED_VALIDATION",
        "REVIEW_POLICY",
        "RECEIPT",
    }
    assert set(run["metadata"]["lifecycle"]) == expected
    assert set(run["metadata"]["lifecycle"].values()) == {"PASS"}
    assert run["status"] == "COMPLETED"
    assert result.receipt_id
