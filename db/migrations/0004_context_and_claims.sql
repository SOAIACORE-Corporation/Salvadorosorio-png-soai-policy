BEGIN;

CREATE TABLE soa_core.contexts (
    context_id text PRIMARY KEY,
    project_id text REFERENCES soa_core.projects(project_id),
    context_type text NOT NULL,
    valid_from timestamptz,
    valid_until timestamptz,
    dimensions jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE soa_core.context_capsules (
    context_capsule_id text PRIMARY KEY,
    context_id text NOT NULL REFERENCES soa_core.contexts(context_id),
    schema_version text NOT NULL,
    payload jsonb NOT NULL,
    input_hash text,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE soa_core.relationships (
    relationship_id text PRIMARY KEY,
    from_ref text NOT NULL,
    to_ref text NOT NULL,
    relationship_type text NOT NULL,
    valid_from timestamptz,
    valid_until timestamptz,
    evidence_ref_id text REFERENCES soa_evidence.evidence_references(evidence_ref_id),
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE soa_core.claims (
    claim_id text PRIMARY KEY,
    subject_id text,
    statement text NOT NULL,
    claim_kind text NOT NULL CHECK (claim_kind IN (
        'OBSERVATION','SIGNAL','PATTERN','RELATION','EVENT','ESTIMATE','FORECAST','SCENARIO'
    )),
    epistemic_class text NOT NULL CHECK (epistemic_class IN (
        'DOCUMENTED_FACT','CONFIRMED_CONTEXT','INFERENCE','HYPOTHESIS','CONTRADICTION','UNKNOWN','STALE'
    )),
    analysis_profile_id text,
    analysis_profile_version text,
    methodology_ref text,
    assumptions jsonb NOT NULL DEFAULT '[]'::jsonb,
    falsifiers jsonb NOT NULL DEFAULT '[]'::jsonb,
    scope_boundary text,
    confidence_score double precision CHECK (confidence_score IS NULL OR (confidence_score BETWEEN 0 AND 1)),
    confidence_semantics text,
    probability_estimate double precision CHECK (probability_estimate IS NULL OR (probability_estimate BETWEEN 0 AND 1)),
    calibration_ref text REFERENCES soa_intelligence.calibration_registry(calibration_id),
    status text NOT NULL DEFAULT 'DRAFT',
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK (
      probability_estimate IS NULL
      OR (methodology_ref IS NOT NULL AND calibration_ref IS NOT NULL)
    )
);

CREATE TABLE soa_core.claim_relations (
    claim_relation_id text PRIMARY KEY,
    source_claim_id text NOT NULL REFERENCES soa_core.claims(claim_id),
    target_claim_id text NOT NULL REFERENCES soa_core.claims(claim_id),
    relation_type text NOT NULL CHECK (relation_type IN ('ALTERNATIVE','CONTRADICTS','SUPPORTS','SUPERSEDES','REFINES')),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE soa_core.claim_evidence (
    claim_id text NOT NULL REFERENCES soa_core.claims(claim_id),
    evidence_ref_id text NOT NULL REFERENCES soa_evidence.evidence_references(evidence_ref_id),
    evidence_role text NOT NULL CHECK (evidence_role IN ('SUPPORTING','CONTRADICTING','CONTEXT')),
    PRIMARY KEY (claim_id, evidence_ref_id, evidence_role)
);

COMMIT;
