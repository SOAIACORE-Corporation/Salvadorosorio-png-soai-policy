from __future__ import annotations

from datetime import datetime
import uuid
from typing import Any

from fastapi import Body, Depends, FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse
from psycopg import Error as PsycopgError

from soaiacore_runtime.config import RuntimeSettings
from soaiacore_runtime.context_graph import (
    insert_edge,
    neighbors,
    path_between,
    relation_history,
    supersede_edge,
    traverse,
)
from soaiacore_runtime.database import Database
from soaiacore_runtime.errors import RuntimeContractError, contract_error
from soaiacore_runtime.idempotency import execute_idempotent
from soaiacore_runtime.migrations import verify_migrations
from soaiacore_runtime.operations import (
    claim_to_schema,
    create_context,
    create_context_capsule,
    create_run_job,
    get_run,
    evidence_metadata,
    get_context_capsule,
    list_analysis_profiles,
    list_context_capsules,
    list_contexts,
    list_corpora,
    list_projects,
    list_runs,
    put_analysis_profile,
    register_evidence,
    resolve_identity,
    upsert_corpus,
    upsert_project,
    utc_iso,
)
from soaiacore_runtime.schemas import validate_payload

from .models import (
    ContextCapsuleRequest,
    ContextRequest,
    CorpusRequest,
    EvidenceRegisterRequest,
    IdentityResolveRequest,
    ProjectRequest,
    RunRequest,
    TraverseRequest,
)


_RUN_STATUS_PATTERN = (
    r"^(QUEUED|RUNNING|COMPLETED|REVIEW_REQUIRED|FAILED_PRECHECK|DENIED|"
    r"FAILED_EXECUTION|FAILED_VALIDATION|FAILED_RECEIPT)$"
)


def require_idempotency_key(
    value: str = Header(..., alias="Idempotency-Key", min_length=1, max_length=200),
) -> str:
    return value


def _correlation_id(request: Request) -> str:
    supplied = request.headers.get("X-Correlation-ID", "").strip()
    if supplied and len(supplied) <= 100 and all(ch.isalnum() or ch in "_-" for ch in supplied):
        return supplied
    return f"corr_{uuid.uuid4().hex}"


def _receipt_payload(row: dict[str, Any]) -> dict[str, Any]:
    result = dict(row)
    result["created_at"] = utc_iso(result["created_at"])
    return result


def create_app(settings: RuntimeSettings | None = None) -> FastAPI:
    active_settings = settings or RuntimeSettings.from_env()
    database = Database(active_settings.database_url)
    app = FastAPI(title="SOAIACORE Core", version="0.1.0")
    app.state.settings = active_settings
    app.state.database = database

    @app.exception_handler(RuntimeContractError)
    async def runtime_error_handler(request: Request, exc: RuntimeContractError):
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.envelope(_correlation_id(request)),
        )

    @app.exception_handler(PsycopgError)
    async def database_error_handler(request: Request, exc: PsycopgError):
        safe = contract_error(
            "DATABASE_OPERATION_FAILED",
            "The canonical database rejected the operation",
            "PERSISTENCE",
            status_code=503,
            retryable=True,
        )
        return JSONResponse(status_code=503, content=safe.envelope(_correlation_id(request)))

    @app.get("/health/live")
    def health_live() -> dict[str, Any]:
        return {"status": "LIVE", "service": "soaiacore-core", "version": "0.1.0"}

    @app.get("/health/ready")
    def health_ready() -> dict[str, Any]:
        if active_settings.provider_mode != "MOCK":
            raise contract_error(
                "LIVE_PROVIDER_FORBIDDEN",
                "P0-06A readiness requires SOAIACORE_PROVIDER_MODE=MOCK",
                "PRECHECK",
                status_code=503,
            )
        checksums = verify_migrations(database, active_settings.migration_dir)
        return {
            "status": "READY",
            "service": "soaiacore-core",
            "provider_mode": "MOCK",
            "database": "PASS",
            "migrations": len(checksums),
            "pgvector": "PASS",
        }

    @app.put("/v1/projects/{project_id}")
    def project_put(
        project_id: str,
        body: ProjectRequest,
        response: Response,
        key: str = Depends(require_idempotency_key),
    ) -> dict[str, Any]:
        payload = body.model_dump(mode="json")
        with database.transaction() as connection:
            result, replayed = execute_idempotent(
                connection,
                operation="PUT_PROJECT",
                key=key,
                request_payload={"project_id": project_id, **payload},
                resource_type="project",
                action=lambda: (project_id, upsert_project(connection, project_id, payload)),
            )
        response.headers["Idempotency-Replayed"] = str(replayed).lower()
        return result

    @app.get("/v1/projects")
    def projects_list(limit: int = Query(50, ge=1, le=100)) -> list[dict[str, Any]]:
        with database.connect(autocommit=True) as connection:
            return list_projects(connection, limit)

    @app.get("/v1/projects/{project_id}")
    def project_get(project_id: str) -> dict[str, Any]:
        with database.connect(autocommit=True) as connection:
            result = list_projects(connection, 1, project_id=project_id)
        if not result:
            raise contract_error("RESOURCE_NOT_FOUND", "Project does not exist", "CORE_API", status_code=404)
        return result[0]

    @app.put("/v1/projects/{project_id}/corpora/{corpus_id}")
    def corpus_put(
        project_id: str,
        corpus_id: str,
        body: CorpusRequest,
        response: Response,
        key: str = Depends(require_idempotency_key),
    ) -> dict[str, Any]:
        payload = body.model_dump(mode="json")
        with database.transaction() as connection:
            result, replayed = execute_idempotent(
                connection,
                operation="PUT_CORPUS",
                key=key,
                request_payload={"project_id": project_id, "corpus_id": corpus_id, **payload},
                resource_type="corpus",
                action=lambda: (
                    corpus_id,
                    upsert_corpus(connection, project_id, corpus_id, payload),
                ),
            )
        response.headers["Idempotency-Replayed"] = str(replayed).lower()
        return result

    @app.get("/v1/projects/{project_id}/corpora")
    def project_corpora_list(project_id: str, limit: int = Query(50, ge=1, le=100)) -> list[dict[str, Any]]:
        with database.connect(autocommit=True) as connection:
            return list_corpora(connection, project_id, limit)

    @app.get("/v1/projects/{project_id}/corpora/{corpus_id}")
    def corpus_get(project_id: str, corpus_id: str) -> dict[str, Any]:
        with database.connect(autocommit=True) as connection:
            result = list_corpora(connection, project_id, 1, corpus_id=corpus_id)
        if not result:
            raise contract_error("RESOURCE_NOT_FOUND", "Corpus does not exist", "CORE_API", status_code=404)
        return result[0]

    @app.put("/v1/analysis-profiles/{profile_id}/versions/{version}")
    def profile_put(
        profile_id: str,
        version: str,
        response: Response,
        body: dict[str, Any] = Body(...),
        key: str = Depends(require_idempotency_key),
    ) -> dict[str, Any]:
        validate_payload("analysis-profile-v0.3.schema.json", body, stage="CORE_API")
        if body["analysis_profile_id"] != profile_id or body["version"] != version:
            raise contract_error(
                "SCHEMA_VALIDATION_FAILED",
                "AnalysisProfile path and payload identifiers differ",
                "CORE_API",
                status_code=422,
            )
        with database.transaction() as connection:
            result, replayed = execute_idempotent(
                connection,
                operation="PUT_ANALYSIS_PROFILE",
                key=key,
                request_payload=body,
                resource_type="analysis_profile",
                action=lambda: (
                    f"{profile_id}:{version}",
                    put_analysis_profile(connection, body),
                ),
            )
        response.headers["Idempotency-Replayed"] = str(replayed).lower()
        return result

    @app.get("/v1/analysis-profiles")
    def profiles_list(limit: int = Query(50, ge=1, le=100)) -> list[dict[str, Any]]:
        with database.connect(autocommit=True) as connection:
            return list_analysis_profiles(connection, limit)

    @app.post("/v1/identity/resolve")
    def identity_resolve(
        body: IdentityResolveRequest,
        response: Response,
        key: str = Depends(require_idempotency_key),
    ) -> dict[str, Any]:
        payload = body.model_dump(mode="json")
        with database.transaction() as connection:
            result, replayed = execute_idempotent(
                connection,
                operation="RESOLVE_IDENTITY",
                key=key,
                request_payload=payload,
                resource_type="identity_decision",
                action=lambda: (
                    payload["identity_decision_id"],
                    resolve_identity(connection, payload),
                ),
            )
        response.headers["Idempotency-Replayed"] = str(replayed).lower()
        return result

    @app.post("/v1/evidence/register")
    def evidence_register(
        body: EvidenceRegisterRequest,
        response: Response,
        key: str = Depends(require_idempotency_key),
    ) -> dict[str, Any]:
        payload = body.model_dump(mode="json")
        with database.transaction() as connection:
            result, replayed = execute_idempotent(
                connection,
                operation="REGISTER_EVIDENCE",
                key=key,
                request_payload=payload,
                resource_type="evidence_reference",
                action=lambda: (
                    payload["evidence_ref_id"],
                    register_evidence(connection, payload),
                ),
            )
        response.headers["Idempotency-Replayed"] = str(replayed).lower()
        return result

    @app.post("/v1/contexts")
    def context_post(
        body: ContextRequest,
        response: Response,
        key: str = Depends(require_idempotency_key),
    ) -> dict[str, Any]:
        payload = body.model_dump(mode="json")
        with database.transaction() as connection:
            result, replayed = execute_idempotent(
                connection,
                operation="CREATE_CONTEXT",
                key=key,
                request_payload=payload,
                resource_type="context",
                action=lambda: (payload["context_id"], create_context(connection, payload)),
            )
        response.headers["Idempotency-Replayed"] = str(replayed).lower()
        return result

    @app.get("/v1/contexts")
    def contexts_list(
        project_id: str | None = Query(None, min_length=1),
        corpus_id: str | None = Query(None, min_length=1),
        limit: int = Query(50, ge=1, le=100),
    ) -> list[dict[str, Any]]:
        with database.connect(autocommit=True) as connection:
            return list_contexts(connection, project_id, corpus_id, limit)

    @app.get("/v1/contexts/{context_id}")
    def context_get(context_id: str) -> dict[str, Any]:
        with database.connect(autocommit=True) as connection:
            result = list_contexts(connection, None, None, 1, context_id=context_id)
        if not result:
            raise contract_error("RESOURCE_NOT_FOUND", "Context does not exist", "CORE_API", status_code=404)
        return result[0]

    @app.post("/v1/context-capsules")
    def capsule_post(
        body: ContextCapsuleRequest,
        response: Response,
        key: str = Depends(require_idempotency_key),
    ) -> dict[str, Any]:
        payload = body.model_dump(mode="json")
        with database.transaction() as connection:
            result, replayed = execute_idempotent(
                connection,
                operation="CREATE_CONTEXT_CAPSULE",
                key=key,
                request_payload=payload,
                resource_type="context_capsule",
                action=lambda: (
                    payload["context_capsule_id"],
                    create_context_capsule(connection, payload),
                ),
            )
        response.headers["Idempotency-Replayed"] = str(replayed).lower()
        return result

    @app.get("/v1/context-capsules")
    def capsules_list(
        context_id: str | None = Query(None, min_length=1),
        limit: int = Query(50, ge=1, le=100),
    ) -> list[dict[str, Any]]:
        with database.connect(autocommit=True) as connection:
            return list_context_capsules(connection, context_id, limit)

    @app.get("/v1/context-capsules/{context_capsule_id}")
    def capsule_get(context_capsule_id: str) -> dict[str, Any]:
        with database.connect(autocommit=True) as connection:
            result = get_context_capsule(connection, context_capsule_id)
        if not result:
            raise contract_error("RESOURCE_NOT_FOUND", "ContextCapsule does not exist", "CORE_API", status_code=404)
        return result

    @app.post("/v1/runs", status_code=202)
    def run_post(
        body: RunRequest,
        response: Response,
        key: str = Depends(require_idempotency_key),
    ) -> dict[str, Any]:
        payload = body.model_dump(mode="json")
        with database.transaction() as connection:
            result, replayed = execute_idempotent(
                connection,
                operation="CREATE_RUN",
                key=key,
                request_payload=payload,
                resource_type="run",
                action=lambda: (
                    (created := create_run_job(connection, payload, idempotency_key=key))["run_id"],
                    created,
                ),
            )
        response.headers["Idempotency-Replayed"] = str(replayed).lower()
        return result

    @app.get("/v1/runs")
    def runs_list(
        project_id: str | None = Query(None, min_length=1),
        status: str | None = Query(None, min_length=1, max_length=40, pattern=_RUN_STATUS_PATTERN),
        limit: int = Query(50, ge=1, le=100),
    ) -> list[dict[str, Any]]:
        with database.connect(autocommit=True) as connection:
            return list_runs(connection, project_id, status, limit)

    @app.get("/v1/runs/{run_id}")
    def run_get(run_id: str) -> dict[str, Any]:
        with database.connect(autocommit=True) as connection:
            result = get_run(connection, run_id)
        if not result:
            raise contract_error("RESOURCE_NOT_FOUND", "Run does not exist", "CORE_API", status_code=404)
        return result

    @app.get("/v1/runs/{run_id}/claims")
    def run_claims(run_id: str) -> list[dict[str, Any]]:
        with database.connect(autocommit=True) as connection:
            ids = connection.execute(
                "SELECT claim_id FROM soa_core.claims WHERE run_id=%s ORDER BY claim_id", (run_id,)
            ).fetchall()
            claims = [claim_to_schema(connection, row["claim_id"]) for row in ids]
        for claim in claims:
            validate_payload("claim-v0.2.schema.json", claim, stage="CORE_API")
        return claims

    @app.get("/v1/claims/{claim_id}")
    def claim_get(claim_id: str) -> dict[str, Any]:
        with database.connect(autocommit=True) as connection:
            claim = claim_to_schema(connection, claim_id)
        validate_payload("claim-v0.2.schema.json", claim, stage="CORE_API")
        return claim

    @app.get("/v1/evidence/{evidence_ref_id}")
    def evidence_reference_get(evidence_ref_id: str) -> dict[str, Any]:
        with database.connect(autocommit=True) as connection:
            result = evidence_metadata(connection, evidence_ref_id)
        if not result:
            raise contract_error("RESOURCE_NOT_FOUND", "Evidence reference does not exist", "CORE_API", status_code=404)
        return result

    @app.get("/v1/runs/{run_id}/receipt")
    def run_receipt(run_id: str) -> dict[str, Any]:
        with database.connect(autocommit=True) as connection:
            row = connection.execute(
                "SELECT * FROM soa_ops.context_receipts WHERE run_id=%s", (run_id,)
            ).fetchone()
        if not row:
            raise contract_error("RESOURCE_NOT_FOUND", "Run receipt does not exist", "CORE_API", status_code=404)
        return _receipt_payload(row)

    @app.get("/v1/receipts/{receipt_id}")
    def receipt_get(receipt_id: str) -> dict[str, Any]:
        with database.connect(autocommit=True) as connection:
            row = connection.execute(
                "SELECT * FROM soa_ops.context_receipts WHERE context_receipt_id=%s",
                (receipt_id,),
            ).fetchone()
        if not row:
            raise contract_error("RESOURCE_NOT_FOUND", "Receipt does not exist", "CORE_API", status_code=404)
        return _receipt_payload(row)

    @app.post("/v1/context-graph/edges")
    def graph_edge_post(
        response: Response,
        body: dict[str, Any] = Body(...),
        key: str = Depends(require_idempotency_key),
    ) -> dict[str, Any]:
        validate_payload("context-graph-edge-v0.1.schema.json", body, stage="CONTEXT_GRAPH")
        with database.transaction() as connection:
            result, replayed = execute_idempotent(
                connection,
                operation="ADD_CONTEXT_GRAPH_EDGE",
                key=key,
                request_payload=body,
                resource_type="context_graph_edge",
                action=lambda: (body["edge_id"], insert_edge(connection, body)),
            )
        response.headers["Idempotency-Replayed"] = str(replayed).lower()
        return result

    @app.post("/v1/context-graph/edges/{edge_id}:supersede")
    def graph_edge_supersede(
        edge_id: str,
        response: Response,
        body: dict[str, Any] = Body(...),
        key: str = Depends(require_idempotency_key),
    ) -> dict[str, Any]:
        validate_payload("context-graph-edge-v0.1.schema.json", body, stage="CONTEXT_GRAPH")
        with database.transaction() as connection:
            result, replayed = execute_idempotent(
                connection,
                operation="SUPERSEDE_CONTEXT_GRAPH_EDGE",
                key=key,
                request_payload={"old_edge_id": edge_id, "replacement": body},
                resource_type="context_graph_edge",
                action=lambda: (body["edge_id"], supersede_edge(connection, edge_id, body)),
            )
        response.headers["Idempotency-Replayed"] = str(replayed).lower()
        return result

    @app.get("/v1/context-graph/neighbors")
    def graph_neighbors(
        reference: str = Query(..., alias="ref"),
        direction: str = Query("BOTH"),
        at: datetime | None = Query(None),
    ) -> list[dict[str, Any]]:
        with database.connect(autocommit=True) as connection:
            return neighbors(connection, reference=reference, direction=direction, at=at)

    @app.post("/v1/context-graph/traverse")
    def graph_traverse(body: TraverseRequest) -> list[dict[str, Any]]:
        with database.connect(autocommit=True) as connection:
            return traverse(connection, start_ref=body.start_ref, max_depth=body.max_depth)

    @app.get("/v1/context-graph/path")
    def graph_path(
        from_ref: str,
        to_ref: str,
        max_depth: int = Query(4, ge=1, le=10),
    ) -> dict[str, Any]:
        with database.connect(autocommit=True) as connection:
            result = path_between(
                connection, from_ref=from_ref, to_ref=to_ref, max_depth=max_depth
            )
        return {"from_ref": from_ref, "to_ref": to_ref, "path": result}

    @app.get("/v1/context-graph/edges/{edge_id}/history")
    def graph_history(edge_id: str) -> list[dict[str, Any]]:
        with database.connect(autocommit=True) as connection:
            return relation_history(connection, edge_id)

    return app


app = create_app()
