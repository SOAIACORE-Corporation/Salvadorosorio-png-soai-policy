BEGIN;

CREATE EXTENSION IF NOT EXISTS vector;

CREATE SCHEMA IF NOT EXISTS soa_core;
CREATE SCHEMA IF NOT EXISTS soa_identity;
CREATE SCHEMA IF NOT EXISTS soa_evidence;
CREATE SCHEMA IF NOT EXISTS soa_intelligence;
CREATE SCHEMA IF NOT EXISTS soa_adjudication;
CREATE SCHEMA IF NOT EXISTS soa_ops;
CREATE SCHEMA IF NOT EXISTS experimental;

CREATE TABLE IF NOT EXISTS soa_ops.schema_registry (
    schema_name text PRIMARY KEY,
    version text NOT NULL,
    maturity text NOT NULL CHECK (maturity IN ('M0','M1','M2','M3')),
    checksum_sha256 text,
    applied_at timestamptz NOT NULL DEFAULT now(),
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb
);

COMMIT;
