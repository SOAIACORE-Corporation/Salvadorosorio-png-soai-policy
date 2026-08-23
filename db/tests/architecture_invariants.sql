\set ON_ERROR_STOP on

DO $$
DECLARE n integer;
BEGIN
  SELECT count(*) INTO n FROM soa_core.projects WHERE project_id='prj_test';
  IF n <> 1 THEN RAISE EXCEPTION 'project seed failed'; END IF;

  SELECT count(*) INTO n FROM soa_core.claims c
   JOIN soa_core.claim_evidence ce ON ce.claim_id=c.claim_id
   JOIN soa_evidence.evidence_references er ON er.evidence_ref_id=ce.evidence_ref_id
   WHERE c.claim_id='clm_test';
  IF n <> 1 THEN RAISE EXCEPTION 'claim/evidence provenance chain failed'; END IF;

  SELECT count(*) INTO n FROM soa_identity.identity_decisions
   WHERE identity_decision_id='idd_test' AND decision_type='LINK';
  IF n <> 1 THEN RAISE EXCEPTION 'identity decision persistence failed'; END IF;

  SELECT count(*) INTO n FROM soa_core.context_graph_edges
   WHERE edge_id='edge_test' AND from_ref='sub_test' AND to_ref='ctx_test';
  IF n <> 1 THEN RAISE EXCEPTION 'ContextGraph edge persistence failed'; END IF;

  SELECT count(*) INTO n FROM soa_ops.context_receipts
   WHERE context_receipt_id='cr_test' AND output_status='COMPLETED';
  IF n <> 1 THEN RAISE EXCEPTION 'receipt persistence failed'; END IF;
END $$;

-- Negative constraint test: probability without methodology/calibration MUST fail.
DO $$
BEGIN
  BEGIN
    INSERT INTO soa_core.claims(
      claim_id,statement,claim_kind,epistemic_class,analysis_profile_id,
      probability_estimate,status
    ) VALUES ('clm_invalid_probability','Invalid probability','ESTIMATE','INFERENCE','AP-001',0.7,'DRAFT');
    RAISE EXCEPTION 'constraint failure: invalid probability claim was accepted';
  EXCEPTION WHEN check_violation THEN
    NULL; -- expected
  END;
END $$;

-- Negative constraint test: unknown evidence FK MUST fail.
DO $$
BEGIN
  BEGIN
    INSERT INTO soa_core.claim_evidence(claim_id,evidence_ref_id,evidence_role)
      VALUES ('clm_test','evref_missing','SUPPORTING');
    RAISE EXCEPTION 'constraint failure: missing evidence reference was accepted';
  EXCEPTION WHEN foreign_key_violation THEN
    NULL; -- expected
  END;
END $$;

-- Human review must be conditional, not universal.
DO $$
DECLARE mode text;
BEGIN
  SELECT human_review_mode INTO mode
  FROM soa_intelligence.analysis_profiles
  WHERE analysis_profile_id='AP-001' AND version='1.0.0';
  IF mode <> 'NONE' THEN RAISE EXCEPTION 'ReviewPolicy non-rigidity failed'; END IF;
END $$;

SELECT 'LOCAL_GATE_SQL_INVARIANTS_PASS' AS result;
