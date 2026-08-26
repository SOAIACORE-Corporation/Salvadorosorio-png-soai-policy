from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from psycopg import Connection
from psycopg.types.json import Jsonb

from .errors import contract_error
from .hashing import sha256_json, sha256_text
from .identifiers import deterministic_id


LIFECYCLE_STAGES = (
    "CONTEXT",
    "SYNC",
    "PRECHECK",
    "EXECUTION",
    "AUTOMATED_VALIDATION",
    "REVIEW_POLICY",
    "RECEIPT",
)

_SENSITIVE_KEY_FRAGMENTS = (
    "password",
    "secret",
    "token",
    "credential",
    "authorization",
    "connectionstring",
    "accountkey",
    "apikey",
    "accesskey",
    "privatekey",
    "saskey",
)


def utc_iso(value: datetime | None = None) -> str:
    active = value or datetime.now(timezone.utc)
    return active.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def upsert_project(connection: Connection, project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    connection.execute(
        """
        INSERT INTO soa_core.projects(project_id,name,status,metadata)
        VALUES (%s,%s,%s,%s)
        ON CONFLICT (project_id) DO UPDATE
        SET name=EXCLUDED.name,status=EXCLUDED.status,metadata=EXCLUDED.metadata
        """,
        (
            project_id,
            payload["name"],
            payload.get("status", "ACTIVE"),
            Jsonb(payload.get("metadata", {})),
        ),
    )
    row = connection.execute(
        "SELECT project_id,name,status,metadata,created_at FROM soa_core.projects WHERE project_id=%s",
        (project_id,),
    ).fetchone()
    return {**row, "created_at": utc_iso(row["created_at"])}


def upsert_corpus(
    connection: Connection, project_id: str, corpus_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    connection.execute(
        """
        INSERT INTO soa_core.corpora(corpus_id,project_id,name,metadata)
        VALUES (%s,%s,%s,%s)
        ON CONFLICT (corpus_id) DO UPDATE
        SET project_id=EXCLUDED.project_id,name=EXCLUDED.name,metadata=EXCLUDED.metadata
        """,
        (corpus_id, project_id, payload["name"], Jsonb(payload.get("metadata", {}))),
    )
    row = connection.execute(
        "SELECT corpus_id,project_id,name,metadata,created_at FROM soa_core.corpora WHERE corpus_id=%s",
        (corpus_id,),
    ).fetchone()
    return {**row, "created_at": utc_iso(row["created_at"])}


def put_analysis_profile(connection: Connection, payload: dict[str, Any]) -> dict[str, Any]:
    profile_id = payload["analysis_profile_id"]
    version = payload["version"]
    existing = connection.execute(
        """
        SELECT config FROM soa_intelligence.analysis_profiles
        WHERE analysis_profile_id=%s AND version=%s
        """,
        (profile_id, version),
    ).fetchone()
    if existing and sha256_json(existing["config"]) != sha256_json(payload):
        raise contract_error(
            "PROFILE_VERSION_CONFLICT",
            "An immutable AnalysisProfile version already exists with different content",
            "CORE_API",
            status_code=409,
        )
    if not existing:
        connection.execute(
            """
            INSERT INTO soa_intelligence.analysis_profiles(
              analysis_profile_id,version,name,human_review_mode,restricted_workflow,config,maturity
            ) VALUES (%s,%s,%s,%s,%s,%s,'M1')
            """,
            (
                profile_id,
                version,
                payload.get("name"),
                payload["human_review_mode"],
                payload["restricted_workflow"],
                Jsonb(payload),
            ),
        )
    return payload


def resolve_identity(connection: Connection, payload: dict[str, Any]) -> dict[str, Any]:
    connection.execute(
        """
        INSERT INTO soa_identity.observed_actors(
          observed_actor_id,corpus_id,source_local_ref,display_label,metadata,observed_at
        ) VALUES (%s,%s,%s,%s,%s,%s)
        ON CONFLICT (observed_actor_id) DO NOTHING
        """,
        (
            payload["observed_actor_id"],
            payload["corpus_id"],
            payload.get("source_local_ref"),
            payload.get("display_label"),
            Jsonb(payload.get("metadata", {})),
            payload.get("observed_at"),
        ),
    )
    connection.execute(
        """
        INSERT INTO soa_identity.canonical_subjects(
          canonical_subject_id,status,identity_resolution_status,metadata
        ) VALUES (%s,'ACTIVE',%s,%s)
        ON CONFLICT (canonical_subject_id) DO NOTHING
        """,
        (
            payload["canonical_subject_id"],
            payload.get("identity_resolution_status", "ADJUDICATED"),
            Jsonb(payload.get("subject_metadata", {})),
        ),
    )
    connection.execute(
        """
        INSERT INTO soa_identity.identity_claims(
          identity_claim_id,observed_actor_id,candidate_subject_id,claim_type,
          confidence_class,evidence_refs,status
        ) VALUES (%s,%s,%s,%s,%s,%s,'OPEN')
        ON CONFLICT (identity_claim_id) DO NOTHING
        """,
        (
            payload["identity_claim_id"],
            payload["observed_actor_id"],
            payload["canonical_subject_id"],
            payload.get("claim_type", "LINK_CANDIDATE"),
            payload.get("confidence_class", "HIGH"),
            Jsonb(payload.get("evidence_refs", [])),
        ),
    )
    connection.execute(
        """
        INSERT INTO soa_identity.identity_decisions(
          identity_decision_id,decision_type,observed_actor_id,canonical_subject_id,
          decided_by,rationale_summary,evidence_refs
        ) VALUES (%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (identity_decision_id) DO NOTHING
        """,
        (
            payload["identity_decision_id"],
            payload.get("decision_type", "LINK"),
            payload["observed_actor_id"],
            payload["canonical_subject_id"],
            payload.get("decided_by", "P0_MOCK"),
            payload.get("rationale_summary", "Deterministic P0 identity resolution"),
            Jsonb(payload.get("evidence_refs", [])),
        ),
    )
    return {
        "observed_actor_id": payload["observed_actor_id"],
        "canonical_subject_id": payload["canonical_subject_id"],
        "identity_claim_id": payload["identity_claim_id"],
        "identity_decision_id": payload["identity_decision_id"],
        "identity_resolution_status": payload.get("identity_resolution_status", "ADJUDICATED"),
    }


def register_evidence(connection: Connection, payload: dict[str, Any]) -> dict[str, Any]:
    connection.execute(
        """
        INSERT INTO soa_evidence.source_artifacts(
          source_id,corpus_id,source_type,source_locator,content_sha256,byte_size,metadata
        ) VALUES (%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (source_id) DO NOTHING
        """,
        (
            payload["source_id"],
            payload["corpus_id"],
            payload["source_type"],
            payload.get("source_locator"),
            payload["content_sha256"],
            payload.get("byte_size"),
            Jsonb(payload.get("source_metadata", {})),
        ),
    )
    connection.execute(
        """
        INSERT INTO soa_evidence.evidence_objects(
          evidence_id,source_id,evidence_state,object_locator,content_sha256,modality,metadata
        ) VALUES (%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (evidence_id) DO NOTHING
        """,
        (
            payload["evidence_id"],
            payload["source_id"],
            payload["evidence_state"],
            payload.get("object_locator"),
            payload["content_sha256"],
            payload.get("modality", "TEXT"),
            Jsonb(payload.get("evidence_metadata", {})),
        ),
    )
    connection.execute(
        """
        INSERT INTO soa_evidence.evidence_references(
          evidence_ref_id,evidence_id,source_id,locator,support_type,relationship,
          evidence_state_snapshot,admissibility_scope,excerpt_hash,provenance_chain_ref
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (evidence_ref_id) DO NOTHING
        """,
        (
            payload["evidence_ref_id"],
            payload["evidence_id"],
            payload["source_id"],
            payload.get("locator"),
            payload.get("support_type", "DIRECT"),
            payload.get("relationship", "SUPPORTS"),
            payload["evidence_state"],
            payload.get("admissibility_scope", "P0_MOCK"),
            payload.get("excerpt_hash"),
            payload.get("provenance_chain_ref"),
        ),
    )
    return {
        "source_id": payload["source_id"],
        "evidence_id": payload["evidence_id"],
        "evidence_ref_id": payload["evidence_ref_id"],
        "content_sha256": payload["content_sha256"],
        "evidence_state": payload["evidence_state"],
    }


def create_context(connection: Connection, payload: dict[str, Any]) -> dict[str, Any]:
    connection.execute(
        """
        INSERT INTO soa_core.contexts(
          context_id,project_id,context_type,valid_from,valid_until,dimensions
        ) VALUES (%s,%s,%s,%s,%s,%s)
        ON CONFLICT (context_id) DO NOTHING
        """,
        (
            payload["context_id"],
            payload["project_id"],
            payload["context_type"],
            payload.get("valid_from"),
            payload.get("valid_until"),
            Jsonb(payload.get("dimensions", {})),
        ),
    )
    row = connection.execute(
        "SELECT * FROM soa_core.contexts WHERE context_id=%s", (payload["context_id"],)
    ).fetchone()
    return {
        **row,
        "valid_from": utc_iso(row["valid_from"]) if row["valid_from"] else None,
        "valid_until": utc_iso(row["valid_until"]) if row["valid_until"] else None,
        "created_at": utc_iso(row["created_at"]),
    }


def create_context_capsule(connection: Connection, payload: dict[str, Any]) -> dict[str, Any]:
    input_hash = sha256_json(payload["payload"])
    existing = connection.execute(
        "SELECT * FROM soa_core.context_capsules WHERE context_capsule_id=%s",
        (payload["context_capsule_id"],),
    ).fetchone()
    if existing and (
        existing["input_hash"] != input_hash
        or existing["schema_version"] != payload.get("schema_version", "P0-RUNTIME-1")
    ):
        raise contract_error(
            "CONTEXT_CAPSULE_CONFLICT",
            "ContextCapsule IDs are immutable",
            "CORE_API",
            status_code=409,
        )
    if not existing:
        connection.execute(
            """
            INSERT INTO soa_core.context_capsules(
              context_capsule_id,context_id,schema_version,payload,input_hash
            ) VALUES (%s,%s,%s,%s,%s)
            """,
            (
                payload["context_capsule_id"],
                payload["context_id"],
                payload.get("schema_version", "P0-RUNTIME-1"),
                Jsonb(payload["payload"]),
                input_hash,
            ),
        )
    row = connection.execute(
        "SELECT * FROM soa_core.context_capsules WHERE context_capsule_id=%s",
        (payload["context_capsule_id"],),
    ).fetchone()
    return {**row, "created_at": utc_iso(row["created_at"])}


def create_run_job(
    connection: Connection,
    payload: dict[str, Any],
    *,
    idempotency_key: str,
) -> dict[str, Any]:
    if payload["mode"] != "MOCK":
        raise contract_error(
            "MODE_NOT_IMPLEMENTED",
            "P0-06A implements MOCK only; LIVE and REPLAY are rejected",
            "PRECHECK",
            status_code=422,
        )
    capsule = connection.execute(
        "SELECT context_id,input_hash FROM soa_core.context_capsules WHERE context_capsule_id=%s",
        (payload["context_capsule_id"],),
    ).fetchone()
    if not capsule:
        raise contract_error(
            "RESOURCE_NOT_FOUND",
            "ContextCapsule does not exist",
            "CORE_API",
            status_code=404,
        )
    profile = connection.execute(
        """
        SELECT 1 FROM soa_intelligence.analysis_profiles
        WHERE analysis_profile_id=%s AND version=%s
        """,
        (payload["analysis_profile_id"], payload["analysis_profile_version"]),
    ).fetchone()
    if not profile:
        raise contract_error(
            "ANALYSIS_PROFILE_NOT_FOUND",
            "Requested AnalysisProfile version does not exist",
            "CORE_API",
            status_code=404,
        )

    request_hash = sha256_json(payload)
    run_id = deterministic_id("run", idempotency_key, request_hash)
    job_id = deterministic_id("job", run_id)
    lifecycle = {stage: "PENDING" for stage in LIFECYCLE_STAGES}
    metadata = {
        "mock_fixture_id": payload["mock_fixture_id"],
        "request_hash": request_hash,
        "idempotency_key_hash": sha256_text(idempotency_key),
        "lifecycle": lifecycle,
    }
    connection.execute(
        """
        INSERT INTO soa_intelligence.runs(
          run_id,project_id,analysis_profile_id,analysis_profile_version,purpose,status,
          mode,metadata,context_capsule_id
        )
        SELECT %s,c.project_id,%s,%s,%s,'QUEUED','MOCK',%s,%s
        FROM soa_core.contexts c
        WHERE c.context_id=%s
        """,
        (
            run_id,
            payload["analysis_profile_id"],
            payload["analysis_profile_version"],
            payload["purpose"],
            Jsonb(metadata),
            payload["context_capsule_id"],
            capsule["context_id"],
        ),
    )
    connection.execute(
        """
        INSERT INTO soa_ops.jobs(job_id,run_id,job_type,status,payload)
        VALUES (%s,%s,'MOCK_LIFECYCLE','QUEUED',%s)
        """,
        (
            job_id,
            run_id,
            Jsonb(
                {
                    "run_id": run_id,
                    "context_capsule_id": payload["context_capsule_id"],
                    "mock_fixture_id": payload["mock_fixture_id"],
                }
            ),
        ),
    )
    return {"run_id": run_id, "job_id": job_id, "status": "QUEUED", "mode": "MOCK"}


def get_run(connection: Connection, run_id: str) -> dict[str, Any] | None:
    row = connection.execute(
        """
        SELECT r.*,j.job_id,j.status AS job_status,j.attempts
        FROM soa_intelligence.runs r
        LEFT JOIN soa_ops.jobs j ON j.run_id=r.run_id
        WHERE r.run_id=%s
        """,
        (run_id,),
    ).fetchone()
    if not row:
        return None
    result = dict(row)
    result["started_at"] = utc_iso(result["started_at"])
    result["completed_at"] = utc_iso(result["completed_at"]) if result["completed_at"] else None
    return result


def _sanitize_read_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _sanitize_read_value(item)
            for key, item in value.items()
            if not any(
                fragment in "".join(character for character in str(key).lower() if character.isalnum())
                for fragment in _SENSITIVE_KEY_FRAGMENTS
            )
        }
    if isinstance(value, list):
        return [_sanitize_read_value(item) for item in value]
    if isinstance(value, tuple):
        return [_sanitize_read_value(item) for item in value]
    if isinstance(value, str) and "://" in value:
        parsed = urlsplit(value)
        safe_netloc = parsed.netloc.rsplit("@", 1)[-1]
        return urlunsplit((parsed.scheme, safe_netloc, parsed.path, "", ""))
    return value


def _rows_with_times(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for row in rows:
        item = _sanitize_read_value(dict(row))
        for field in ("created_at", "started_at", "completed_at", "valid_from", "valid_until"):
            if item.get(field) is not None:
                item[field] = utc_iso(item[field])
        result.append(item)
    return result


def list_projects(
    connection: Connection, limit: int, *, project_id: str | None = None
) -> list[dict[str, Any]]:
    if project_id:
        rows = connection.execute(
            "SELECT project_id,name,status,metadata,created_at FROM soa_core.projects WHERE project_id=%s ORDER BY created_at DESC,project_id LIMIT %s",
            (project_id, limit),
        ).fetchall()
    else:
        rows = connection.execute(
            "SELECT project_id,name,status,metadata,created_at FROM soa_core.projects ORDER BY created_at DESC,project_id LIMIT %s",
            (limit,),
        ).fetchall()
    return _rows_with_times(rows)


def list_corpora(
    connection: Connection, project_id: str, limit: int, *, corpus_id: str | None = None
) -> list[dict[str, Any]]:
    if corpus_id:
        rows = connection.execute(
            "SELECT corpus_id,project_id,name,metadata,created_at FROM soa_core.corpora WHERE project_id=%s AND corpus_id=%s ORDER BY created_at DESC,corpus_id LIMIT %s",
            (project_id, corpus_id, limit),
        ).fetchall()
    else:
        rows = connection.execute(
            "SELECT corpus_id,project_id,name,metadata,created_at FROM soa_core.corpora WHERE project_id=%s ORDER BY created_at DESC,corpus_id LIMIT %s",
            (project_id, limit),
        ).fetchall()
    return _rows_with_times(rows)


def list_contexts(
    connection: Connection,
    project_id: str | None,
    corpus_id: str | None,
    limit: int,
    *,
    context_id: str | None = None,
) -> list[dict[str, Any]]:
    if context_id:
        rows = connection.execute(
            "SELECT context_id,project_id,context_type,valid_from,valid_until,dimensions,created_at FROM soa_core.contexts WHERE context_id=%s ORDER BY created_at DESC,context_id LIMIT %s",
            (context_id, limit),
        ).fetchall()
    elif project_id and corpus_id:
        rows = connection.execute(
            "SELECT context_id,project_id,context_type,valid_from,valid_until,dimensions,created_at FROM soa_core.contexts WHERE project_id=%s AND dimensions->>'corpus_id'=%s ORDER BY created_at DESC,context_id LIMIT %s",
            (project_id, corpus_id, limit),
        ).fetchall()
    elif project_id:
        rows = connection.execute(
            "SELECT context_id,project_id,context_type,valid_from,valid_until,dimensions,created_at FROM soa_core.contexts WHERE project_id=%s ORDER BY created_at DESC,context_id LIMIT %s",
            (project_id, limit),
        ).fetchall()
    elif corpus_id:
        rows = connection.execute(
            "SELECT context_id,project_id,context_type,valid_from,valid_until,dimensions,created_at FROM soa_core.contexts WHERE dimensions->>'corpus_id'=%s ORDER BY created_at DESC,context_id LIMIT %s",
            (corpus_id, limit),
        ).fetchall()
    else:
        rows = connection.execute(
            "SELECT context_id,project_id,context_type,valid_from,valid_until,dimensions,created_at FROM soa_core.contexts ORDER BY created_at DESC,context_id LIMIT %s",
            (limit,),
        ).fetchall()
    return _rows_with_times(rows)


def list_context_capsules(
    connection: Connection, context_id: str | None, limit: int, *, context_capsule_id: str | None = None
) -> list[dict[str, Any]]:
    if context_capsule_id:
        rows = connection.execute(
            "SELECT context_capsule_id,context_id,schema_version,input_hash,created_at FROM soa_core.context_capsules WHERE context_capsule_id=%s ORDER BY created_at DESC,context_capsule_id LIMIT %s",
            (context_capsule_id, limit),
        ).fetchall()
    elif context_id:
        rows = connection.execute(
            "SELECT context_capsule_id,context_id,schema_version,input_hash,created_at FROM soa_core.context_capsules WHERE context_id=%s ORDER BY created_at DESC,context_capsule_id LIMIT %s",
            (context_id, limit),
        ).fetchall()
    else:
        rows = connection.execute(
            "SELECT context_capsule_id,context_id,schema_version,input_hash,created_at FROM soa_core.context_capsules ORDER BY created_at DESC,context_capsule_id LIMIT %s",
            (limit,),
        ).fetchall()
    return _rows_with_times(rows)


def get_context_capsule(connection: Connection, context_capsule_id: str) -> dict[str, Any] | None:
    row = connection.execute(
        "SELECT context_capsule_id,context_id,schema_version,payload,input_hash,created_at FROM soa_core.context_capsules WHERE context_capsule_id=%s",
        (context_capsule_id,),
    ).fetchone()
    if not row:
        return None
    return _rows_with_times([row])[0]


def list_analysis_profiles(connection: Connection, limit: int) -> list[dict[str, Any]]:
    rows = connection.execute(
        "SELECT config FROM soa_intelligence.analysis_profiles ORDER BY analysis_profile_id,version LIMIT %s",
        (limit,),
    ).fetchall()
    return [_sanitize_read_value(dict(row["config"])) for row in rows]


def list_runs(
    connection: Connection, project_id: str | None, status: str | None, limit: int
) -> list[dict[str, Any]]:
    clauses = []
    params: list[Any] = []
    if project_id:
        clauses.append("r.project_id=%s")
        params.append(project_id)
    if status:
        clauses.append("r.status=%s")
        params.append(status)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(limit)
    rows = connection.execute(
        """
        SELECT r.run_id,r.project_id,r.context_capsule_id,r.analysis_profile_id,
               r.analysis_profile_version,r.purpose,r.status,r.mode,r.started_at,r.completed_at
        FROM soa_intelligence.runs r
        """ + where + " ORDER BY r.started_at DESC,r.run_id LIMIT %s",
        params,
    ).fetchall()
    return _rows_with_times(rows)


def evidence_metadata(connection: Connection, evidence_ref_id: str) -> dict[str, Any] | None:
    row = connection.execute(
        """
        SELECT er.evidence_ref_id,er.locator,er.support_type,er.relationship,
               er.evidence_state_snapshot,er.admissibility_scope,er.excerpt_hash,
               er.provenance_chain_ref,er.created_at AS reference_created_at,
               eo.evidence_id,eo.evidence_state,eo.object_locator,eo.content_sha256,
               eo.modality,eo.metadata AS evidence_metadata,eo.created_at AS evidence_created_at,
               sa.source_id,sa.corpus_id,sa.source_type,sa.source_locator,sa.byte_size,
               sa.metadata AS source_metadata,sa.created_at AS source_created_at
        FROM soa_evidence.evidence_references er
        JOIN soa_evidence.evidence_objects eo ON eo.evidence_id=er.evidence_id
        LEFT JOIN soa_evidence.source_artifacts sa ON sa.source_id=er.source_id
        WHERE er.evidence_ref_id=%s
        """,
        (evidence_ref_id,),
    ).fetchone()
    if not row:
        return None
    result = dict(row)
    for field in ("reference_created_at", "evidence_created_at", "source_created_at"):
        result[field] = utc_iso(result[field]) if result[field] else None
    result["content_availability"] = "METADATA_ONLY_BLOB_OBJECT_CONTENT_NOT_IMPLEMENTED"
    return _sanitize_read_value(result)


def claim_to_schema(connection: Connection, claim_id: str) -> dict[str, Any]:
    row = connection.execute("SELECT * FROM soa_core.claims WHERE claim_id=%s", (claim_id,)).fetchone()
    if not row:
        raise contract_error(
            "RESOURCE_NOT_FOUND", "Claim does not exist", "CORE_API", status_code=404
        )
    evidence = connection.execute(
        "SELECT evidence_ref_id,evidence_role FROM soa_core.claim_evidence WHERE claim_id=%s",
        (claim_id,),
    ).fetchall()
    alternatives = connection.execute(
        """
        SELECT target_claim_id FROM soa_core.claim_relations
        WHERE source_claim_id=%s AND relation_type='ALTERNATIVE'
        """,
        (claim_id,),
    ).fetchall()
    payload = {
        "claim_id": row["claim_id"],
        "subject_id": row["subject_id"],
        "statement": row["statement"],
        "claim_kind": row["claim_kind"],
        "epistemic_class": row["epistemic_class"],
        "analysis_profile_id": row["analysis_profile_id"],
        "methodology_ref": row["methodology_ref"],
        "supporting_evidence_refs": sorted(
            item["evidence_ref_id"] for item in evidence if item["evidence_role"] == "SUPPORTING"
        ),
        "contradicting_evidence_refs": sorted(
            item["evidence_ref_id"]
            for item in evidence
            if item["evidence_role"] == "CONTRADICTING"
        ),
        "assumptions": row["assumptions"],
        "alternative_claim_refs": sorted(item["target_claim_id"] for item in alternatives),
        "falsifiers": row["falsifiers"],
        "scope_boundary": row["scope_boundary"],
        "confidence_score": row["confidence_score"],
        "confidence_semantics": row["confidence_semantics"],
        "probability_estimate": row["probability_estimate"],
        "calibration_ref": row["calibration_ref"],
        "status": row["status"],
        "created_at": utc_iso(row["created_at"]),
        "metadata": row["metadata"],
    }
    return payload
