BEGIN;

-- SOA Intelligence A2 persistence overlay.
-- This migration is intentionally isolated from db/migrations (P0 baseline).
-- It must only be executed against the dedicated A2 database after the base
-- migrations have installed pgvector and the shared evidence/claim schemas.

CREATE SCHEMA IF NOT EXISTS soa_memory;
CREATE SCHEMA IF NOT EXISTS soa_decision;

CREATE TABLE soa_memory.canonical_memory (
    memory_id text PRIMARY KEY,
    logical_memory_id text NOT NULL,
    version_no integer NOT NULL CHECK (version_no > 0),
    project_scope text NOT NULL CHECK (btrim(project_scope) <> ''),
    subject_ref text,
    content jsonb NOT NULL,
    epistemic_class text NOT NULL CHECK (epistemic_class IN (
        'DOCUMENTED_FACT',
        'CONFIRMED_CONTEXT',
        'INFERENCE',
        'HYPOTHESIS',
        'WORKING_ASSUMPTION',
        'STALE_INFORMATION'
    )),
    admission_state text NOT NULL CHECK (admission_state IN (
        'PROPOSED','ADMITTED','REJECTED','SUPERSEDED','REVOKED'
    )),
    source_claim_id text REFERENCES soa_core.claims(claim_id),
    event_time timestamptz,
    observed_time timestamptz NOT NULL,
    recorded_time timestamptz NOT NULL DEFAULT now(),
    valid_from timestamptz NOT NULL,
    valid_until timestamptz,
    supersedes_memory_id text REFERENCES soa_memory.canonical_memory(memory_id),
    sensitivity text NOT NULL DEFAULT 'STANDARD' CHECK (sensitivity IN (
        'STANDARD','HIGH','RESTRICTED'
    )),
    receipt_ref text,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (project_scope, logical_memory_id, version_no),
    CHECK (valid_until IS NULL OR valid_until > valid_from)
);

CREATE TABLE soa_memory.episodic_temporal_memory (
    episode_id text PRIMARY KEY,
    logical_episode_id text NOT NULL,
    version_no integer NOT NULL CHECK (version_no > 0),
    project_scope text NOT NULL CHECK (btrim(project_scope) <> ''),
    session_id text,
    subject_ref text,
    payload jsonb NOT NULL,
    source_claim_id text REFERENCES soa_core.claims(claim_id),
    event_time timestamptz,
    observed_time timestamptz NOT NULL,
    recorded_time timestamptz NOT NULL DEFAULT now(),
    valid_from timestamptz NOT NULL,
    valid_until timestamptz,
    supersedes_episode_id text REFERENCES soa_memory.episodic_temporal_memory(episode_id),
    sensitivity text NOT NULL DEFAULT 'STANDARD' CHECK (sensitivity IN (
        'STANDARD','HIGH','RESTRICTED'
    )),
    receipt_ref text,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (project_scope, logical_episode_id, version_no),
    CHECK (valid_until IS NULL OR valid_until > valid_from)
);

CREATE TABLE soa_memory.operational_state (
    state_id text PRIMARY KEY,
    state_key text NOT NULL,
    version_no integer NOT NULL CHECK (version_no > 0),
    project_scope text NOT NULL CHECK (btrim(project_scope) <> ''),
    status text NOT NULL,
    phase text,
    decision text,
    source_authority text NOT NULL,
    source_ref text,
    event_time timestamptz,
    observed_time timestamptz NOT NULL,
    recorded_time timestamptz NOT NULL DEFAULT now(),
    valid_from timestamptz NOT NULL,
    valid_until timestamptz,
    supersedes_state_id text REFERENCES soa_memory.operational_state(state_id),
    receipt_ref text,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (project_scope, state_key, version_no),
    CHECK (valid_until IS NULL OR valid_until > valid_from)
);

CREATE TABLE soa_decision.decision_ledger (
    decision_event_id text PRIMARY KEY,
    decision_id text NOT NULL,
    event_seq integer NOT NULL CHECK (event_seq > 0),
    project_scope text NOT NULL CHECK (btrim(project_scope) <> ''),
    state text NOT NULL CHECK (state IN (
        'PROPOSED','APPROVED','EXECUTED','VALIDATED','SUPERSEDED','REVOKED','FAILED'
    )),
    authority_level text NOT NULL CHECK (authority_level IN ('R1','R2','R3')),
    human_authorization_ref text,
    proposal jsonb NOT NULL DEFAULT '{}'::jsonb,
    evidence_refs jsonb NOT NULL DEFAULT '[]'::jsonb,
    reason text,
    event_time timestamptz,
    observed_time timestamptz NOT NULL,
    recorded_time timestamptz NOT NULL DEFAULT now(),
    valid_from timestamptz NOT NULL,
    valid_until timestamptz,
    previous_event_id text REFERENCES soa_decision.decision_ledger(decision_event_id),
    receipt_ref text,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (project_scope, decision_id, event_seq),
    CHECK (valid_until IS NULL OR valid_until > valid_from),
    CHECK (authority_level <> 'R3' OR human_authorization_ref IS NOT NULL)
);

CREATE TABLE soa_memory.memory_claim_lineage (
    memory_id text NOT NULL REFERENCES soa_memory.canonical_memory(memory_id),
    claim_id text NOT NULL REFERENCES soa_core.claims(claim_id),
    evidence_ref_id text REFERENCES soa_evidence.evidence_references(evidence_ref_id),
    lineage_role text NOT NULL CHECK (lineage_role IN (
        'SOURCE','SUPPORT','CONTRADICTION','ADMISSION_BASIS'
    )),
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (memory_id, claim_id, lineage_role)
);

CREATE INDEX idx_a2_canonical_memory_asof
    ON soa_memory.canonical_memory(project_scope, logical_memory_id, recorded_time DESC, valid_from, valid_until);
CREATE INDEX idx_a2_episode_asof
    ON soa_memory.episodic_temporal_memory(project_scope, logical_episode_id, recorded_time DESC, valid_from, valid_until);
CREATE INDEX idx_a2_operational_state_asof
    ON soa_memory.operational_state(project_scope, state_key, recorded_time DESC, valid_from, valid_until);
CREATE INDEX idx_a2_decision_asof
    ON soa_decision.decision_ledger(project_scope, decision_id, recorded_time DESC, valid_from, valid_until);
CREATE INDEX idx_a2_memory_claim_lineage_claim
    ON soa_memory.memory_claim_lineage(claim_id, memory_id);

-- Bitemporal read functions. Callers MUST provide both valid-time and
-- recorded-time cutoffs. The recorded-time predicate is the T2 -> T1 leak guard.
CREATE OR REPLACE FUNCTION soa_memory.canonical_memory_as_of(
    p_project_scope text,
    p_valid_at timestamptz,
    p_recorded_at timestamptz
)
RETURNS SETOF soa_memory.canonical_memory
LANGUAGE sql
STABLE
AS $$
    SELECT DISTINCT ON (cm.logical_memory_id) cm.*
    FROM soa_memory.canonical_memory cm
    WHERE cm.project_scope = p_project_scope
      AND cm.recorded_time <= p_recorded_at
      AND cm.valid_from <= p_valid_at
      AND (cm.valid_until IS NULL OR p_valid_at < cm.valid_until)
      AND cm.admission_state = 'ADMITTED'
    ORDER BY cm.logical_memory_id, cm.recorded_time DESC, cm.version_no DESC;
$$;

CREATE OR REPLACE FUNCTION soa_memory.episodic_memory_as_of(
    p_project_scope text,
    p_valid_at timestamptz,
    p_recorded_at timestamptz
)
RETURNS SETOF soa_memory.episodic_temporal_memory
LANGUAGE sql
STABLE
AS $$
    SELECT DISTINCT ON (em.logical_episode_id) em.*
    FROM soa_memory.episodic_temporal_memory em
    WHERE em.project_scope = p_project_scope
      AND em.recorded_time <= p_recorded_at
      AND em.valid_from <= p_valid_at
      AND (em.valid_until IS NULL OR p_valid_at < em.valid_until)
    ORDER BY em.logical_episode_id, em.recorded_time DESC, em.version_no DESC;
$$;

CREATE OR REPLACE FUNCTION soa_memory.operational_state_as_of(
    p_project_scope text,
    p_valid_at timestamptz,
    p_recorded_at timestamptz
)
RETURNS SETOF soa_memory.operational_state
LANGUAGE sql
STABLE
AS $$
    SELECT DISTINCT ON (os.state_key) os.*
    FROM soa_memory.operational_state os
    WHERE os.project_scope = p_project_scope
      AND os.recorded_time <= p_recorded_at
      AND os.valid_from <= p_valid_at
      AND (os.valid_until IS NULL OR p_valid_at < os.valid_until)
    ORDER BY os.state_key, os.recorded_time DESC, os.version_no DESC;
$$;

CREATE OR REPLACE FUNCTION soa_decision.decision_state_as_of(
    p_project_scope text,
    p_valid_at timestamptz,
    p_recorded_at timestamptz
)
RETURNS SETOF soa_decision.decision_ledger
LANGUAGE sql
STABLE
AS $$
    SELECT DISTINCT ON (dl.decision_id) dl.*
    FROM soa_decision.decision_ledger dl
    WHERE dl.project_scope = p_project_scope
      AND dl.recorded_time <= p_recorded_at
      AND dl.valid_from <= p_valid_at
      AND (dl.valid_until IS NULL OR p_valid_at < dl.valid_until)
    ORDER BY dl.decision_id, dl.recorded_time DESC, dl.event_seq DESC;
$$;

-- Canonical history is append-only. State changes are represented by new
-- versions/events rather than in-place mutation.
CREATE OR REPLACE FUNCTION soa_memory.reject_history_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'A2 canonical history is append-only; insert a new version/event instead';
END;
$$;

CREATE TRIGGER trg_a2_canonical_memory_append_only
    BEFORE UPDATE OR DELETE ON soa_memory.canonical_memory
    FOR EACH ROW EXECUTE FUNCTION soa_memory.reject_history_mutation();

CREATE TRIGGER trg_a2_episode_append_only
    BEFORE UPDATE OR DELETE ON soa_memory.episodic_temporal_memory
    FOR EACH ROW EXECUTE FUNCTION soa_memory.reject_history_mutation();

CREATE TRIGGER trg_a2_operational_state_append_only
    BEFORE UPDATE OR DELETE ON soa_memory.operational_state
    FOR EACH ROW EXECUTE FUNCTION soa_memory.reject_history_mutation();

CREATE TRIGGER trg_a2_decision_ledger_append_only
    BEFORE UPDATE OR DELETE ON soa_decision.decision_ledger
    FOR EACH ROW EXECUTE FUNCTION soa_memory.reject_history_mutation();

COMMIT;
