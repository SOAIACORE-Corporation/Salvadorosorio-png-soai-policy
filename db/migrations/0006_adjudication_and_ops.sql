BEGIN;

CREATE TABLE soa_adjudication.adjudications (
    adjudication_id text PRIMARY KEY,
    unit_ref text NOT NULL,
    analysis_profile_id text,
    blindness_status text,
    discrepancy_status text NOT NULL DEFAULT 'NOT_ASSESSED',
    final_decision text,
    final_confidence text,
    adjudicator_type text,
    adjudicator_ref text,
    status text NOT NULL DEFAULT 'OPEN',
    methodology_ref text,
    created_at timestamptz NOT NULL DEFAULT now(),
    closed_at timestamptz
);

CREATE TABLE soa_adjudication.adjudication_ratings (
    rating_id text PRIMARY KEY,
    adjudication_id text NOT NULL REFERENCES soa_adjudication.adjudications(adjudication_id),
    rater_id text NOT NULL,
    rater_type text NOT NULL,
    decision text,
    certainty text,
    evidence_refs jsonb NOT NULL DEFAULT '[]'::jsonb,
    requires_clarification boolean NOT NULL DEFAULT false,
    frozen_hash text,
    submitted_at timestamptz NOT NULL
);

CREATE TABLE soa_adjudication.ground_truth_ledgers (
    ground_truth_ledger_id text PRIMARY KEY,
    version text NOT NULL,
    scope text NOT NULL,
    analysis_profile_id text,
    status text NOT NULL,
    freeze_hash text,
    supersedes_ledger_id text REFERENCES soa_adjudication.ground_truth_ledgers(ground_truth_ledger_id),
    creation_protocol text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE soa_adjudication.ground_truth_items (
    ground_truth_item_id text PRIMARY KEY,
    ground_truth_ledger_id text NOT NULL REFERENCES soa_adjudication.ground_truth_ledgers(ground_truth_ledger_id),
    unit_ref text NOT NULL,
    final_label text NOT NULL,
    adjudication_ref text REFERENCES soa_adjudication.adjudications(adjudication_id),
    provenance_protocol text NOT NULL,
    confidence_class text,
    status text NOT NULL,
    supersedes_item_id text REFERENCES soa_adjudication.ground_truth_items(ground_truth_item_id),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE soa_ops.jobs (
    job_id text PRIMARY KEY,
    run_id text REFERENCES soa_intelligence.runs(run_id),
    job_type text NOT NULL,
    status text NOT NULL,
    attempts integer NOT NULL DEFAULT 0,
    payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    started_at timestamptz,
    completed_at timestamptz
);

CREATE TABLE soa_ops.context_receipts (
    context_receipt_id text PRIMARY KEY,
    run_id text REFERENCES soa_intelligence.runs(run_id),
    context_id text REFERENCES soa_core.contexts(context_id),
    analysis_profile_id text,
    purpose_class text,
    precheck_status text,
    review_mode text CHECK (review_mode IS NULL OR review_mode IN ('NONE','OPTIONAL','REQUIRED')),
    identity_summary jsonb NOT NULL DEFAULT '{}'::jsonb,
    evidence_refs jsonb NOT NULL DEFAULT '[]'::jsonb,
    claims_created jsonb NOT NULL DEFAULT '[]'::jsonb,
    adjudication_refs jsonb NOT NULL DEFAULT '[]'::jsonb,
    limitations jsonb NOT NULL DEFAULT '[]'::jsonb,
    input_hash text,
    context_hash text,
    output_hash text,
    output_status text NOT NULL,
    cost_observation jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE soa_ops.deployment_receipts (
    deployment_receipt_id text PRIMARY KEY,
    provider text,
    environment text,
    terraform_plan_hash text,
    approval_ref text,
    verification jsonb NOT NULL DEFAULT '{}'::jsonb,
    cost_summary jsonb NOT NULL DEFAULT '{}'::jsonb,
    teardown_status text,
    created_at timestamptz NOT NULL DEFAULT now()
);

COMMIT;
