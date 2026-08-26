BEGIN;

ALTER TABLE soa_intelligence.runs
    ADD COLUMN IF NOT EXISTS context_capsule_id text
    REFERENCES soa_core.context_capsules(context_capsule_id);

CREATE INDEX IF NOT EXISTS idx_run_context_capsule
    ON soa_intelligence.runs(context_capsule_id);

ALTER TABLE soa_core.claims
    ADD COLUMN IF NOT EXISTS run_id text
    REFERENCES soa_intelligence.runs(run_id);

CREATE INDEX IF NOT EXISTS idx_claim_run
    ON soa_core.claims(run_id);

CREATE UNIQUE INDEX IF NOT EXISTS uq_context_receipts_terminal_run
    ON soa_ops.context_receipts(run_id)
    WHERE run_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS soa_ops.idempotency_keys (
    operation text NOT NULL,
    key_hash text NOT NULL,
    request_hash text NOT NULL,
    resource_type text NOT NULL,
    resource_id text NOT NULL,
    response_payload jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (operation, key_hash)
);

CREATE OR REPLACE FUNCTION soa_ops.prevent_context_receipt_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'soa_ops.context_receipts is append-only';
END;
$$;

CREATE OR REPLACE TRIGGER trg_context_receipts_append_only
BEFORE UPDATE OR DELETE ON soa_ops.context_receipts
FOR EACH ROW
EXECUTE FUNCTION soa_ops.prevent_context_receipt_mutation();

INSERT INTO soa_ops.schema_registry(
    schema_name,
    version,
    maturity,
    checksum_sha256,
    metadata
)
VALUES (
    'runtime-integrity',
    '0008',
    'M1',
    NULL,
    '{"purpose":"P0-06A runtime relational invariants"}'::jsonb
)
ON CONFLICT (schema_name) DO NOTHING;

COMMIT;
