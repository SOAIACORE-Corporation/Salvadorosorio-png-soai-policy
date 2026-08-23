BEGIN;

CREATE TABLE soa_intelligence.analysis_profiles (
    analysis_profile_id text NOT NULL,
    version text NOT NULL,
    name text,
    human_review_mode text NOT NULL CHECK (human_review_mode IN ('NONE','OPTIONAL','REQUIRED')),
    restricted_workflow boolean NOT NULL DEFAULT false,
    config jsonb NOT NULL,
    maturity text NOT NULL DEFAULT 'M1' CHECK (maturity IN ('M0','M1','M2','M3')),
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (analysis_profile_id, version)
);

CREATE TABLE soa_intelligence.authorization_decisions (
    authorization_decision_id text PRIMARY KEY,
    analysis_profile_id text,
    analysis_profile_version text,
    purpose text NOT NULL,
    tier text NOT NULL,
    decision text NOT NULL CHECK (decision IN ('ALLOW','DENY','CONDITIONAL')),
    reason_codes jsonb NOT NULL DEFAULT '[]'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE soa_intelligence.calibration_registry (
    calibration_id text PRIMARY KEY,
    analysis_profile_id text NOT NULL,
    methodology_ref text NOT NULL,
    model_id text,
    model_version text,
    dataset_or_outcome text,
    evaluation_window text,
    temporal_horizon text,
    metric_name text NOT NULL,
    metric_value double precision NOT NULL,
    sample_size integer NOT NULL CHECK (sample_size > 0),
    baseline text,
    calibration_method text,
    confidence_interval text,
    backtest_metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    supersedes text REFERENCES soa_intelligence.calibration_registry(calibration_id),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE soa_intelligence.external_source_registry (
    external_source_id text PRIMARY KEY,
    provider text NOT NULL,
    source_role text NOT NULL,
    license text,
    freshness text NOT NULL,
    quality_metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    purpose_restrictions jsonb NOT NULL DEFAULT '[]'::jsonb,
    trust_profile text,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE soa_intelligence.runs (
    run_id text PRIMARY KEY,
    project_id text REFERENCES soa_core.projects(project_id),
    analysis_profile_id text,
    analysis_profile_version text,
    purpose text,
    status text NOT NULL,
    mode text NOT NULL DEFAULT 'MOCK' CHECK (mode IN ('MOCK','REPLAY','LIVE')),
    started_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE soa_intelligence.model_runs (
    model_run_id text PRIMARY KEY,
    run_id text NOT NULL REFERENCES soa_intelligence.runs(run_id),
    mode text NOT NULL CHECK (mode IN ('MOCK','REPLAY','LIVE')),
    provider text,
    model_id text,
    model_version text,
    input_hash text,
    toolset_hash text,
    response_hash text,
    captured_at timestamptz,
    usage_metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE soa_intelligence.tool_runs (
    tool_run_id text PRIMARY KEY,
    run_id text NOT NULL REFERENCES soa_intelligence.runs(run_id),
    tool_provider text,
    tool_name text NOT NULL,
    request_hash text,
    response_hash text,
    status text NOT NULL,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE soa_intelligence.embeddings (
    embedding_id text PRIMARY KEY,
    owner_type text NOT NULL,
    owner_id text NOT NULL,
    model_id text NOT NULL,
    model_version text,
    embedding vector,
    evidence_ref_id text REFERENCES soa_evidence.evidence_references(evidence_ref_id),
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

COMMIT;
