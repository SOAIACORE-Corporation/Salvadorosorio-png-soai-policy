from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any

from psycopg import Connection
from psycopg.types.json import Jsonb

from .config import RuntimeSettings
from .context_graph import edge_to_schema
from .database import Database
from .errors import RuntimeContractError, contract_error
from .hashing import sha256_json
from .identifiers import deterministic_id
from .migrations import verify_migrations
from .mock import deterministic_embedding, load_mock_fixture
from .operations import claim_to_schema
from .policy import data_minimization_decision, review_policy_decision
from .schemas import validate_payload


EVIDENCE_RANK = {
    "REFERENCED": 1,
    "INVENTORIED": 2,
    "ACQUIRED": 3,
    "FIXITY_VERIFIED": 4,
    "PROCESSED": 5,
    "VERIFIED": 6,
    "ADMISSIBLE": 7,
}


@dataclass(frozen=True)
class WorkerResult:
    exit_code: int
    job_id: str | None
    run_id: str | None
    status: str
    receipt_id: str | None = None
    blocker: str | None = None


def claim_one_job(database: Database) -> dict[str, Any] | None:
    with database.transaction() as connection:
        row = connection.execute(
            """
            SELECT job_id,run_id,job_type,status,attempts,payload
            FROM soa_ops.jobs
            WHERE status='QUEUED'
            ORDER BY created_at,job_id
            FOR UPDATE SKIP LOCKED
            LIMIT 1
            """
        ).fetchone()
        if not row:
            return None
        updated = connection.execute(
            """
            UPDATE soa_ops.jobs
            SET status='RUNNING',attempts=attempts+1,started_at=COALESCE(started_at,now())
            WHERE job_id=%s
            RETURNING job_id,run_id,job_type,status,attempts,payload
            """,
            (row["job_id"],),
        ).fetchone()
        connection.execute(
            "UPDATE soa_intelligence.runs SET status='RUNNING' WHERE run_id=%s",
            (row["run_id"],),
        )
        return dict(updated)


def _load_metadata(connection: Connection, run_id: str) -> dict[str, Any]:
    row = connection.execute(
        "SELECT metadata FROM soa_intelligence.runs WHERE run_id=%s", (run_id,)
    ).fetchone()
    if not row:
        raise contract_error(
            "RESOURCE_NOT_FOUND", "Run does not exist", "CONTEXT", status_code=404, run_id=run_id
        )
    return dict(row["metadata"])


def _write_metadata(connection: Connection, run_id: str, metadata: dict[str, Any]) -> None:
    connection.execute(
        "UPDATE soa_intelligence.runs SET metadata=%s WHERE run_id=%s",
        (Jsonb(metadata), run_id),
    )


def _mark_stage(
    connection: Connection,
    run_id: str,
    stage: str,
    status: str,
    details: dict[str, Any] | None = None,
) -> None:
    metadata = _load_metadata(connection, run_id)
    lifecycle = dict(metadata.get("lifecycle", {}))
    lifecycle[stage] = status
    metadata["lifecycle"] = lifecycle
    if details is not None:
        stage_results = dict(metadata.get("stage_results", {}))
        stage_results[stage] = details
        metadata["stage_results"] = stage_results
    _write_metadata(connection, run_id, metadata)


def _stage_context(connection: Connection, run_id: str) -> dict[str, Any]:
    bundle = connection.execute(
        """
        SELECT r.run_id,r.project_id,r.analysis_profile_id,r.analysis_profile_version,
               r.purpose,r.mode,r.context_capsule_id,r.metadata AS run_metadata,
               cc.context_id,cc.payload AS capsule_payload,cc.input_hash,cc.schema_version,
               c.context_type,c.dimensions
        FROM soa_intelligence.runs r
        JOIN soa_core.context_capsules cc ON cc.context_capsule_id=r.context_capsule_id
        JOIN soa_core.contexts c ON c.context_id=cc.context_id
        WHERE r.run_id=%s
        """,
        (run_id,),
    ).fetchone()
    if not bundle:
        raise contract_error(
            "CONTEXT_NOT_RESOLVED",
            "Run does not resolve to a ContextCapsule and Context",
            "CONTEXT",
            run_id=run_id,
        )
    payload = dict(bundle["capsule_payload"])
    required = {
        "project_id",
        "corpus_id",
        "context_id",
        "analysis_profile_id",
        "analysis_profile_version",
        "identity_refs",
        "evidence_refs",
        "synthetic_only",
    }
    missing = sorted(required.difference(payload))
    if missing:
        raise contract_error(
            "CONTEXT_CAPSULE_INVALID",
            "ContextCapsule is missing required runtime references",
            "CONTEXT",
            details={"missing": missing},
            run_id=run_id,
        )
    if (
        payload["project_id"] != bundle["project_id"]
        or payload["context_id"] != bundle["context_id"]
        or payload["analysis_profile_id"] != bundle["analysis_profile_id"]
        or payload["analysis_profile_version"] != bundle["analysis_profile_version"]
    ):
        raise contract_error(
            "CONTEXT_CAPSULE_MISMATCH",
            "Run and ContextCapsule references disagree",
            "CONTEXT",
            run_id=run_id,
        )
    project = connection.execute(
        "SELECT 1 FROM soa_core.projects WHERE project_id=%s", (payload["project_id"],)
    ).fetchone()
    corpus = connection.execute(
        "SELECT 1 FROM soa_core.corpora WHERE corpus_id=%s AND project_id=%s",
        (payload["corpus_id"], payload["project_id"]),
    ).fetchone()
    if not project or not corpus:
        raise contract_error(
            "CONTEXT_NOT_RESOLVED",
            "Project or Corpus referenced by the capsule is absent",
            "CONTEXT",
            run_id=run_id,
        )
    result = dict(bundle)
    result["capsule_payload"] = payload
    _mark_stage(connection, run_id, "CONTEXT", "PASS", {"context_id": bundle["context_id"]})
    return result


def _stage_sync(connection: Connection, run_id: str, context: dict[str, Any]) -> dict[str, Any]:
    payload = context["capsule_payload"]
    if sha256_json(payload) != context["input_hash"]:
        raise contract_error(
            "CONTEXT_HASH_MISMATCH",
            "ContextCapsule payload no longer matches input_hash",
            "SYNC",
            run_id=run_id,
        )
    evidence_rows = connection.execute(
        """
        SELECT er.evidence_ref_id,er.evidence_state_snapshot,eo.evidence_state,
               eo.content_sha256,sa.content_sha256 AS source_sha256
        FROM soa_evidence.evidence_references er
        JOIN soa_evidence.evidence_objects eo ON eo.evidence_id=er.evidence_id
        JOIN soa_evidence.source_artifacts sa ON sa.source_id=er.source_id
        WHERE er.evidence_ref_id=ANY(%s)
        ORDER BY er.evidence_ref_id
        """,
        (payload["evidence_refs"],),
    ).fetchall()
    if len(evidence_rows) != len(set(payload["evidence_refs"])):
        raise contract_error(
            "EVIDENCE_REFERENCE_MISSING",
            "One or more ContextCapsule evidence references are unresolved",
            "SYNC",
            run_id=run_id,
        )
    for row in evidence_rows:
        if row["evidence_state_snapshot"] != row["evidence_state"]:
            raise contract_error(
                "EVIDENCE_SNAPSHOT_STALE",
                "Evidence state differs from its synchronized snapshot",
                "SYNC",
                details={"evidence_ref_id": row["evidence_ref_id"]},
                run_id=run_id,
            )
        if row["content_sha256"] != row["source_sha256"]:
            raise contract_error(
                "EVIDENCE_HASH_MISMATCH",
                "Evidence object and source artifact hashes differ",
                "SYNC",
                details={"evidence_ref_id": row["evidence_ref_id"]},
                run_id=run_id,
            )
    _mark_stage(
        connection,
        run_id,
        "SYNC",
        "PASS",
        {"evidence_refs": [row["evidence_ref_id"] for row in evidence_rows]},
    )
    return {"evidence_rows": [dict(row) for row in evidence_rows]}


def _stage_precheck(
    connection: Connection,
    run_id: str,
    context: dict[str, Any],
    settings: RuntimeSettings,
) -> dict[str, Any]:
    if settings.provider_mode != "MOCK" or context["mode"] != "MOCK":
        raise contract_error(
            "LIVE_PROVIDER_FORBIDDEN",
            "P0-06A rejects LIVE and REPLAY provider modes",
            "PRECHECK",
            run_id=run_id,
        )
    profile = connection.execute(
        """
        SELECT analysis_profile_id,version,human_review_mode,restricted_workflow,config
        FROM soa_intelligence.analysis_profiles
        WHERE analysis_profile_id=%s AND version=%s
        """,
        (context["analysis_profile_id"], context["analysis_profile_version"]),
    ).fetchone()
    if not profile:
        raise contract_error(
            "ANALYSIS_PROFILE_NOT_FOUND",
            "AnalysisProfile disappeared before execution",
            "PRECHECK",
            run_id=run_id,
        )
    validate_payload(
        "analysis-profile-v0.3.schema.json", dict(profile["config"]), stage="PRECHECK"
    )
    minimum = profile["config"]["evidence_requirements"]["minimum_state"]
    required_rank = EVIDENCE_RANK[minimum]
    evidence = connection.execute(
        """
        SELECT er.evidence_ref_id,eo.evidence_state
        FROM soa_evidence.evidence_references er
        JOIN soa_evidence.evidence_objects eo ON eo.evidence_id=er.evidence_id
        WHERE er.evidence_ref_id=ANY(%s)
        """,
        (context["capsule_payload"]["evidence_refs"],),
    ).fetchall()
    insufficient = [
        row["evidence_ref_id"]
        for row in evidence
        if EVIDENCE_RANK.get(row["evidence_state"], 0) < required_rank
    ]
    if insufficient:
        raise contract_error(
            "EVIDENCE_STATE_INSUFFICIENT",
            "Evidence does not satisfy the AnalysisProfile minimum state",
            "PRECHECK",
            details={"evidence_refs": insufficient, "minimum_state": minimum},
            run_id=run_id,
        )

    identity_refs = context["capsule_payload"]["identity_refs"]
    identities = connection.execute(
        """
        SELECT cs.canonical_subject_id,cs.identity_resolution_status,
               EXISTS (
                 SELECT 1 FROM soa_identity.identity_decisions id
                 WHERE id.canonical_subject_id=cs.canonical_subject_id
                   AND id.decision_type IN ('LINK','MERGE')
               ) AS has_final_link
        FROM soa_identity.canonical_subjects cs
        WHERE cs.canonical_subject_id=ANY(%s)
        """,
        (identity_refs,),
    ).fetchall()
    identity_uncertainty = len(identities) != len(set(identity_refs)) or any(
        row["identity_resolution_status"] != "ADJUDICATED" or not row["has_final_link"]
        for row in identities
    )
    created_at = context["run_metadata"].get("mock_created_at", "2026-08-23T00:00:00Z")
    minimization = data_minimization_decision(
        run_id=run_id,
        purpose=context["purpose"],
        synthetic_only=bool(context["capsule_payload"]["synthetic_only"]),
        created_at=created_at,
    )
    authorization = "ALLOW" if minimization["action"] == "ALLOW" else "DENY"
    authorization_id = deterministic_id("authz", run_id)
    connection.execute(
        """
        INSERT INTO soa_intelligence.authorization_decisions(
          authorization_decision_id,analysis_profile_id,analysis_profile_version,
          purpose,tier,decision,reason_codes,created_at
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (authorization_decision_id) DO NOTHING
        """,
        (
            authorization_id,
            profile["analysis_profile_id"],
            profile["version"],
            context["purpose"],
            profile["config"].get("authorization_tier", "T0_STANDARD"),
            authorization,
            Jsonb(minimization["reason_codes"]),
            created_at,
        ),
    )
    metadata = _load_metadata(connection, run_id)
    metadata["data_minimization_decision"] = minimization
    metadata["authorization_decision"] = authorization
    metadata["identity_uncertainty"] = identity_uncertainty
    _write_metadata(connection, run_id, metadata)
    if authorization == "DENY":
        raise contract_error(
            "DATA_MINIMIZATION_DENIED",
            "P0 accepts synthetic data only",
            "PRECHECK",
            run_id=run_id,
        )
    _mark_stage(
        connection,
        run_id,
        "PRECHECK",
        "PASS",
        {
            "authorization_decision_id": authorization_id,
            "minimum_evidence_state": minimum,
            "identity_uncertainty": identity_uncertainty,
        },
    )
    return {
        "profile": dict(profile),
        "identity_uncertainty": identity_uncertainty,
        "authorization": authorization,
        "minimization": minimization,
    }


def _stage_execution(
    connection: Connection,
    run_id: str,
    context: dict[str, Any],
    settings: RuntimeSettings,
) -> dict[str, Any]:
    fixture_id = context["run_metadata"]["mock_fixture_id"]
    fixture = load_mock_fixture(settings.fixture_dir, fixture_id)
    created_at = fixture["created_at"]
    claim_template = fixture["claim"]
    statement = claim_template["statement_template"].format(
        run_id=run_id,
        context_id=context["context_id"],
        evidence_ref_id=context["capsule_payload"]["evidence_refs"][0],
    )
    subject_id = context["capsule_payload"]["identity_refs"][0]
    evidence_ref_id = context["capsule_payload"]["evidence_refs"][0]
    claim_id = deterministic_id("clm", run_id, fixture["fixture_hash"])
    edge_id = deterministic_id("edge", run_id, claim_id)
    model_run_id = deterministic_id("modelrun", run_id)
    tool_run_id = deterministic_id("toolrun", run_id, fixture["tool_name"])
    model_output = {
        "statement": statement,
        "claim_kind": claim_template["claim_kind"],
        "epistemic_class": claim_template["epistemic_class"],
        "evidence_ref_id": evidence_ref_id,
        "graph_relation_type": fixture["graph_relation_type"],
    }
    response_hash = sha256_json(model_output)
    connection.execute(
        """
        INSERT INTO soa_intelligence.model_runs(
          model_run_id,run_id,mode,provider,model_id,model_version,input_hash,
          toolset_hash,response_hash,captured_at,usage_metadata,created_at
        ) VALUES (%s,%s,'MOCK','MOCK',%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (model_run_id) DO NOTHING
        """,
        (
            model_run_id,
            run_id,
            fixture["model_id"],
            fixture["fixture_version"],
            context["input_hash"],
            sha256_json([fixture["tool_name"]]),
            response_hash,
            created_at,
            Jsonb({"external_calls": 0, "fixture_hash": fixture["fixture_hash"]}),
            created_at,
        ),
    )
    connection.execute(
        """
        INSERT INTO soa_intelligence.tool_runs(
          tool_run_id,run_id,tool_provider,tool_name,request_hash,response_hash,status,metadata,created_at
        ) VALUES (%s,%s,'INTERNAL',%s,%s,%s,'PASS',%s,%s)
        ON CONFLICT (tool_run_id) DO NOTHING
        """,
        (
            tool_run_id,
            run_id,
            fixture["tool_name"],
            context["input_hash"],
            response_hash,
            Jsonb({"network_calls": 0}),
            created_at,
        ),
    )
    connection.execute(
        """
        INSERT INTO soa_core.claims(
          claim_id,run_id,subject_id,statement,claim_kind,epistemic_class,
          analysis_profile_id,analysis_profile_version,methodology_ref,assumptions,
          falsifiers,scope_boundary,confidence_score,confidence_semantics,status,metadata,created_at
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'ACTIVE',%s,%s)
        ON CONFLICT (claim_id) DO NOTHING
        """,
        (
            claim_id,
            run_id,
            subject_id,
            statement,
            claim_template["claim_kind"],
            claim_template["epistemic_class"],
            context["analysis_profile_id"],
            context["analysis_profile_version"],
            claim_template.get("methodology_ref"),
            Jsonb(claim_template.get("assumptions", [])),
            Jsonb(claim_template.get("falsifiers", [])),
            claim_template.get("scope_boundary", "P0 synthetic fixture"),
            claim_template.get("confidence_score"),
            claim_template.get("confidence_semantics"),
            Jsonb({"fixture_id": fixture_id, "fixture_hash": fixture["fixture_hash"]}),
            created_at,
        ),
    )
    connection.execute(
        """
        INSERT INTO soa_core.claim_evidence(claim_id,evidence_ref_id,evidence_role)
        VALUES (%s,%s,'SUPPORTING')
        ON CONFLICT DO NOTHING
        """,
        (claim_id, evidence_ref_id),
    )
    connection.execute(
        """
        INSERT INTO soa_core.context_graph_edges(
          edge_id,from_ref,to_ref,relation_type,directed,valid_from,evidence_ref_id,metadata,created_at
        ) VALUES (%s,%s,%s,%s,true,%s,%s,%s,%s)
        ON CONFLICT (edge_id) DO NOTHING
        """,
        (
            edge_id,
            subject_id,
            context["context_id"],
            fixture["graph_relation_type"],
            created_at,
            evidence_ref_id,
            Jsonb({"run_id": run_id, "claim_id": claim_id}),
            created_at,
        ),
    )
    embedding = deterministic_embedding(response_hash)
    connection.execute(
        """
        INSERT INTO soa_intelligence.embeddings(
          embedding_id,owner_type,owner_id,model_id,model_version,embedding,
          evidence_ref_id,metadata,created_at
        ) VALUES (%s,'CLAIM',%s,%s,%s,%s::vector,%s,%s,%s)
        ON CONFLICT (embedding_id) DO NOTHING
        """,
        (
            deterministic_id("emb", claim_id),
            claim_id,
            "mock-hash-vector",
            "1",
            "[" + ",".join(str(value) for value in embedding) + "]",
            evidence_ref_id,
            Jsonb({"deterministic": True, "dimensions": len(embedding)}),
            created_at,
        ),
    )
    result = {
        "fixture": fixture,
        "created_at": created_at,
        "claim_id": claim_id,
        "edge_id": edge_id,
        "model_run_id": model_run_id,
        "tool_run_id": tool_run_id,
        "response_hash": response_hash,
        "embedding": embedding,
    }
    _mark_stage(
        connection,
        run_id,
        "EXECUTION",
        "PASS",
        {key: result[key] for key in ("claim_id", "edge_id", "model_run_id", "tool_run_id")},
    )
    return result


def _stage_validation(
    connection: Connection,
    run_id: str,
    execution: dict[str, Any],
) -> dict[str, Any]:
    claim = claim_to_schema(connection, execution["claim_id"])
    validate_payload("claim-v0.2.schema.json", claim, stage="AUTOMATED_VALIDATION")
    edge_row = connection.execute(
        "SELECT * FROM soa_core.context_graph_edges WHERE edge_id=%s", (execution["edge_id"],)
    ).fetchone()
    edge = edge_to_schema(edge_row)
    checks = {
        "claim_schema": True,
        "edge_schema": True,
        "claim_evidence": bool(
            connection.execute(
                "SELECT 1 FROM soa_core.claim_evidence WHERE claim_id=%s",
                (execution["claim_id"],),
            ).fetchone()
        ),
        "model_mode_mock": bool(
            connection.execute(
                "SELECT 1 FROM soa_intelligence.model_runs WHERE run_id=%s AND mode='MOCK'",
                (run_id,),
            ).fetchone()
        ),
        "tool_run": bool(
            connection.execute(
                "SELECT 1 FROM soa_intelligence.tool_runs WHERE run_id=%s AND status='PASS'",
                (run_id,),
            ).fetchone()
        ),
        "pgvector_embedding": bool(
            connection.execute(
                "SELECT 1 FROM soa_intelligence.embeddings WHERE owner_id=%s AND embedding IS NOT NULL",
                (execution["claim_id"],),
            ).fetchone()
        ),
    }
    if not all(checks.values()):
        raise contract_error(
            "AUTOMATED_VALIDATION_FAILED",
            "One or more runtime invariants failed",
            "AUTOMATED_VALIDATION",
            details={"checks": checks},
            run_id=run_id,
        )
    validation_tool_id = deterministic_id("toolrun", run_id, "automated-validation")
    validation_hash = sha256_json({"claim": claim, "edge": edge, "checks": checks})
    connection.execute(
        """
        INSERT INTO soa_intelligence.tool_runs(
          tool_run_id,run_id,tool_provider,tool_name,request_hash,response_hash,status,metadata,created_at
        ) VALUES (%s,%s,'INTERNAL','automated-validation',%s,%s,'PASS',%s,%s)
        ON CONFLICT (tool_run_id) DO NOTHING
        """,
        (
            validation_tool_id,
            run_id,
            execution["response_hash"],
            validation_hash,
            Jsonb({"checks": checks}),
            execution["created_at"],
        ),
    )
    metadata = _load_metadata(connection, run_id)
    metadata["automated_validation"] = {"status": "PASS", "checks": checks}
    _write_metadata(connection, run_id, metadata)
    _mark_stage(
        connection,
        run_id,
        "AUTOMATED_VALIDATION",
        "PASS",
        {"validation_hash": validation_hash},
    )
    return {"claim": claim, "edge": edge, "checks": checks, "validation_hash": validation_hash}


def _stage_review(
    connection: Connection,
    run_id: str,
    context: dict[str, Any],
    precheck: dict[str, Any],
    execution: dict[str, Any],
) -> dict[str, Any]:
    profile = precheck["profile"]
    decision = review_policy_decision(
        run_id=run_id,
        analysis_profile_id=profile["analysis_profile_id"],
        profile_mode=profile["human_review_mode"],
        restricted_workflow=profile["restricted_workflow"],
        identity_uncertainty=precheck["identity_uncertainty"],
        authorization_decision=precheck["authorization"],
        created_at=execution["created_at"],
    )
    metadata = _load_metadata(connection, run_id)
    metadata["review_policy_decision"] = decision
    _write_metadata(connection, run_id, metadata)
    _mark_stage(
        connection,
        run_id,
        "REVIEW_POLICY",
        "PASS",
        {"mode": decision["mode"], "reason_codes": decision["reason_codes"]},
    )
    return decision


def _stage_receipt(
    connection: Connection,
    job: dict[str, Any],
    context: dict[str, Any],
    execution: dict[str, Any],
    validation: dict[str, Any],
    review: dict[str, Any],
) -> tuple[str, str]:
    run_id = job["run_id"]
    receipt_id = deterministic_id("cr", run_id)
    output_status = "REVIEW_REQUIRED" if review["mode"] == "REQUIRED" else "COMPLETED"
    output_hash = sha256_json(
        {
            "claim": validation["claim"],
            "edge": validation["edge"],
            "model_response_hash": execution["response_hash"],
            "review": review,
        }
    )
    limitations = [
        {
            "type": "MODEL_MODE",
            "mode": "MOCK",
            "reason_codes": ["NO_EXTERNAL_PROVIDER_CALL"],
        },
        {
            "type": "REVIEW_POLICY",
            "mode": review["mode"],
            "reason_codes": review["reason_codes"],
        },
    ]
    connection.execute(
        """
        INSERT INTO soa_ops.context_receipts(
          context_receipt_id,run_id,context_id,analysis_profile_id,purpose_class,
          precheck_status,review_mode,identity_summary,evidence_refs,claims_created,
          limitations,input_hash,context_hash,output_hash,output_status,cost_observation,created_at
        ) VALUES (%s,%s,%s,%s,%s,'PASS',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (context_receipt_id) DO NOTHING
        """,
        (
            receipt_id,
            run_id,
            context["context_id"],
            context["analysis_profile_id"],
            context["purpose"],
            review["mode"],
            Jsonb(
                {
                    "identity_refs": context["capsule_payload"]["identity_refs"],
                    "resolution_status": "UNCERTAIN"
                    if review["identity_uncertainty"]
                    else "SUFFICIENT",
                }
            ),
            Jsonb(context["capsule_payload"]["evidence_refs"]),
            Jsonb([execution["claim_id"]]),
            Jsonb(limitations),
            context["input_hash"],
            sha256_json(context["capsule_payload"]),
            output_hash,
            output_status,
            Jsonb({"provider_mode": "MOCK", "external_provider_calls": 0}),
            execution["created_at"],
        ),
    )
    _mark_stage(
        connection,
        run_id,
        "RECEIPT",
        "PASS",
        {"context_receipt_id": receipt_id, "output_status": output_status},
    )
    connection.execute(
        "UPDATE soa_intelligence.runs SET status=%s,completed_at=%s WHERE run_id=%s",
        (output_status, execution["created_at"], run_id),
    )
    connection.execute(
        "UPDATE soa_ops.jobs SET status='COMPLETED',completed_at=%s WHERE job_id=%s",
        (execution["created_at"], job["job_id"]),
    )
    return receipt_id, output_status


def _persist_failure_receipt(
    database: Database,
    job: dict[str, Any],
    error: RuntimeContractError,
) -> str | None:
    run_id = job["run_id"]
    receipt_id = deterministic_id("cr", run_id)
    status_by_stage = {
        "CONTEXT": "FAILED_PRECHECK",
        "SYNC": "FAILED_PRECHECK",
        "PRECHECK": "DENIED" if error.code == "DATA_MINIMIZATION_DENIED" else "FAILED_PRECHECK",
        "EXECUTION": "FAILED_EXECUTION",
        "AUTOMATED_VALIDATION": "FAILED_VALIDATION",
        "REVIEW_POLICY": "FAILED_VALIDATION",
        "RECEIPT": "FAILED_RECEIPT",
    }
    output_status = status_by_stage.get(error.stage, "FAILED_EXECUTION")
    try:
        with database.transaction() as connection:
            row = connection.execute(
                """
                SELECT r.analysis_profile_id,r.purpose,r.context_capsule_id,r.metadata,
                       cc.context_id,cc.input_hash,cc.payload
                FROM soa_intelligence.runs r
                LEFT JOIN soa_core.context_capsules cc ON cc.context_capsule_id=r.context_capsule_id
                WHERE r.run_id=%s
                """,
                (run_id,),
            ).fetchone()
            if not row:
                return None
            connection.execute(
                """
                INSERT INTO soa_ops.context_receipts(
                  context_receipt_id,run_id,context_id,analysis_profile_id,purpose_class,
                  precheck_status,review_mode,identity_summary,evidence_refs,claims_created,
                  limitations,input_hash,context_hash,output_hash,output_status,cost_observation
                ) VALUES (%s,%s,%s,%s,%s,%s,NULL,%s,%s,'[]'::jsonb,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (context_receipt_id) DO NOTHING
                """,
                (
                    receipt_id,
                    run_id,
                    row["context_id"],
                    row["analysis_profile_id"],
                    row["purpose"],
                    "FAIL",
                    Jsonb({}),
                    Jsonb((row["payload"] or {}).get("evidence_refs", [])),
                    Jsonb(
                        [
                            {
                                "type": "TERMINAL_ERROR",
                                "stage": error.stage,
                                "code": error.code,
                                "retryable": error.retryable,
                            }
                        ]
                    ),
                    row["input_hash"],
                    sha256_json(row["payload"] or {}),
                    sha256_json({"error_code": error.code, "stage": error.stage}),
                    output_status,
                    Jsonb({"provider_mode": "MOCK", "external_provider_calls": 0}),
                ),
            )
            _mark_stage(
                connection,
                run_id,
                error.stage if error.stage in {
                    "CONTEXT",
                    "SYNC",
                    "PRECHECK",
                    "EXECUTION",
                    "AUTOMATED_VALIDATION",
                    "REVIEW_POLICY",
                    "RECEIPT",
                } else "EXECUTION",
                "FAIL",
                {"code": error.code},
            )
            if error.stage != "RECEIPT":
                _mark_stage(
                    connection,
                    run_id,
                    "RECEIPT",
                    "PASS",
                    {"context_receipt_id": receipt_id, "output_status": output_status},
                )
            connection.execute(
                "UPDATE soa_intelligence.runs SET status=%s,completed_at=now() WHERE run_id=%s",
                (output_status, run_id),
            )
            connection.execute(
                "UPDATE soa_ops.jobs SET status='FAILED',completed_at=now() WHERE job_id=%s",
                (job["job_id"],),
            )
        return receipt_id
    except Exception:
        return None


def _exit_code_for(error: RuntimeContractError) -> int:
    return {
        "CONTEXT": 22,
        "SYNC": 22,
        "PRECHECK": 22,
        "EXECUTION": 23,
        "AUTOMATED_VALIDATION": 24,
        "REVIEW_POLICY": 24,
        "RECEIPT": 25,
    }.get(error.stage, 23)


def execute_claimed_job(
    database: Database,
    settings: RuntimeSettings,
    job: dict[str, Any],
) -> WorkerResult:
    run_id = job["run_id"]
    try:
        verify_migrations(database, settings.migration_dir)
        with database.transaction() as connection:
            context = _stage_context(connection, run_id)
        with database.transaction() as connection:
            _stage_sync(connection, run_id, context)
        with database.transaction() as connection:
            precheck = _stage_precheck(connection, run_id, context, settings)
        with database.transaction() as connection:
            execution = _stage_execution(connection, run_id, context, settings)
        with database.transaction() as connection:
            validation = _stage_validation(connection, run_id, execution)
        with database.transaction() as connection:
            review = _stage_review(connection, run_id, context, precheck, execution)
        with database.transaction() as connection:
            receipt_id, status = _stage_receipt(
                connection, job, context, execution, validation, review
            )
        return WorkerResult(
            exit_code=0,
            job_id=job["job_id"],
            run_id=run_id,
            status=status,
            receipt_id=receipt_id,
        )
    except RuntimeContractError as error:
        error.run_id = run_id
        receipt_id = _persist_failure_receipt(database, job, error)
        return WorkerResult(
            exit_code=_exit_code_for(error),
            job_id=job["job_id"],
            run_id=run_id,
            status="FAILED",
            receipt_id=receipt_id,
            blocker=error.code,
        )
    except Exception:
        error = contract_error(
            "INTERNAL_ERROR",
            "Worker encountered an unexpected internal error",
            "EXECUTION",
            status_code=500,
            run_id=run_id,
        )
        receipt_id = _persist_failure_receipt(database, job, error)
        return WorkerResult(
            exit_code=23,
            job_id=job["job_id"],
            run_id=run_id,
            status="FAILED",
            receipt_id=receipt_id,
            blocker="INTERNAL_ERROR",
        )


def run_one(database: Database, settings: RuntimeSettings) -> WorkerResult:
    job = claim_one_job(database)
    if not job:
        return WorkerResult(exit_code=10, job_id=None, run_id=None, status="NO_JOB")
    return execute_claimed_job(database, settings, job)
