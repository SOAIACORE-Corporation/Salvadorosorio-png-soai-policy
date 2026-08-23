BEGIN;

CREATE TABLE soa_core.projects (
    project_id text PRIMARY KEY,
    name text NOT NULL,
    status text NOT NULL DEFAULT 'ACTIVE',
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE soa_core.corpora (
    corpus_id text PRIMARY KEY,
    project_id text NOT NULL REFERENCES soa_core.projects(project_id),
    name text NOT NULL,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE soa_identity.observed_actors (
    observed_actor_id text PRIMARY KEY,
    corpus_id text REFERENCES soa_core.corpora(corpus_id),
    source_local_ref text,
    display_label text,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    observed_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE soa_identity.canonical_subjects (
    canonical_subject_id text PRIMARY KEY,
    status text NOT NULL DEFAULT 'ACTIVE',
    identity_resolution_status text NOT NULL DEFAULT 'PROVISIONAL',
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE soa_identity.aliases (
    alias_id text PRIMARY KEY,
    canonical_subject_id text NOT NULL REFERENCES soa_identity.canonical_subjects(canonical_subject_id),
    alias_value text NOT NULL,
    valid_from timestamptz,
    valid_until timestamptz,
    source_ref text,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE soa_identity.identity_claims (
    identity_claim_id text PRIMARY KEY,
    observed_actor_id text NOT NULL REFERENCES soa_identity.observed_actors(observed_actor_id),
    candidate_subject_id text REFERENCES soa_identity.canonical_subjects(canonical_subject_id),
    claim_type text NOT NULL,
    confidence_class text,
    evidence_refs jsonb NOT NULL DEFAULT '[]'::jsonb,
    status text NOT NULL DEFAULT 'OPEN',
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE soa_identity.identity_decisions (
    identity_decision_id text PRIMARY KEY,
    decision_type text NOT NULL CHECK (decision_type IN (
        'MERGE','SPLIT','LINK','UNLINK','KEEP_SEPARATE','NEVER_MERGE','PROVISIONAL_LINK','REJECT_LINK'
    )),
    observed_actor_id text REFERENCES soa_identity.observed_actors(observed_actor_id),
    canonical_subject_id text REFERENCES soa_identity.canonical_subjects(canonical_subject_id),
    supersedes_decision_id text REFERENCES soa_identity.identity_decisions(identity_decision_id),
    decided_by text,
    rationale_summary text,
    evidence_refs jsonb NOT NULL DEFAULT '[]'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE soa_evidence.source_artifacts (
    source_id text PRIMARY KEY,
    corpus_id text REFERENCES soa_core.corpora(corpus_id),
    source_type text NOT NULL,
    source_locator text,
    content_sha256 text,
    byte_size bigint,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE soa_evidence.evidence_objects (
    evidence_id text PRIMARY KEY,
    source_id text REFERENCES soa_evidence.source_artifacts(source_id),
    evidence_state text NOT NULL CHECK (evidence_state IN (
        'REFERENCED','INVENTORIED','ACQUIRED','FIXITY_VERIFIED','PROCESSED','VERIFIED','ADMISSIBLE',
        'QUARANTINED','SUPERSEDED','REJECTED'
    )),
    object_locator text,
    content_sha256 text,
    modality text,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE soa_evidence.evidence_transforms (
    transform_id text PRIMARY KEY,
    input_evidence_id text NOT NULL REFERENCES soa_evidence.evidence_objects(evidence_id),
    output_evidence_id text REFERENCES soa_evidence.evidence_objects(evidence_id),
    transform_type text NOT NULL,
    tool_or_model_ref text,
    parameters jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE soa_evidence.evidence_references (
    evidence_ref_id text PRIMARY KEY,
    evidence_id text NOT NULL REFERENCES soa_evidence.evidence_objects(evidence_id),
    source_id text REFERENCES soa_evidence.source_artifacts(source_id),
    locator text,
    support_type text NOT NULL,
    relationship text NOT NULL,
    evidence_state_snapshot text NOT NULL,
    admissibility_scope text NOT NULL,
    excerpt_hash text,
    provenance_chain_ref text,
    created_at timestamptz NOT NULL DEFAULT now()
);

COMMIT;
