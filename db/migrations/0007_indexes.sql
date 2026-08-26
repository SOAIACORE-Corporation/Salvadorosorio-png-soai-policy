BEGIN;

CREATE INDEX idx_evidence_source ON soa_evidence.evidence_objects(source_id);
CREATE INDEX idx_evidence_state ON soa_evidence.evidence_objects(evidence_state);
CREATE INDEX idx_evref_evidence ON soa_evidence.evidence_references(evidence_id);

CREATE INDEX idx_identity_claim_actor ON soa_identity.identity_claims(observed_actor_id);
CREATE INDEX idx_identity_claim_subject ON soa_identity.identity_claims(candidate_subject_id);
CREATE INDEX idx_alias_subject ON soa_identity.aliases(canonical_subject_id);

CREATE INDEX idx_claim_subject ON soa_core.claims(subject_id);
CREATE INDEX idx_claim_kind ON soa_core.claims(claim_kind);
CREATE INDEX idx_claim_epistemic ON soa_core.claims(epistemic_class);
CREATE INDEX idx_claim_profile ON soa_core.claims(analysis_profile_id, analysis_profile_version);

CREATE INDEX idx_run_profile ON soa_intelligence.runs(analysis_profile_id, analysis_profile_version);
CREATE INDEX idx_job_status ON soa_ops.jobs(status);
CREATE INDEX idx_receipt_run ON soa_ops.context_receipts(run_id);

COMMIT;
