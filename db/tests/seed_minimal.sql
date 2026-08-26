BEGIN;

INSERT INTO soa_core.projects(project_id,name) VALUES ('prj_test','SOAIACORE Local Gate');
INSERT INTO soa_core.corpora(corpus_id,project_id,name) VALUES ('cor_test','prj_test','Synthetic Corpus');

INSERT INTO soa_identity.observed_actors(observed_actor_id,corpus_id,source_local_ref,display_label)
VALUES ('act_test','cor_test','src-local-1','Synthetic Actor');

INSERT INTO soa_identity.canonical_subjects(canonical_subject_id,identity_resolution_status)
VALUES ('sub_test','ADJUDICATED');

INSERT INTO soa_identity.identity_claims(identity_claim_id,observed_actor_id,candidate_subject_id,claim_type,confidence_class,status)
VALUES ('idc_test','act_test','sub_test','LINK_CANDIDATE','HIGH','OPEN');

INSERT INTO soa_identity.identity_decisions(identity_decision_id,decision_type,observed_actor_id,canonical_subject_id,decided_by,rationale_summary)
VALUES ('idd_test','LINK','act_test','sub_test','local_gate','Synthetic verified link for test');

INSERT INTO soa_evidence.source_artifacts(source_id,corpus_id,source_type,source_locator,content_sha256,byte_size)
VALUES ('src_test','cor_test','TEXT','fixture://local-gate',repeat('a',64),100);

INSERT INTO soa_evidence.evidence_objects(evidence_id,source_id,evidence_state,object_locator,content_sha256,modality)
VALUES ('ev_test','src_test','ADMISSIBLE','fixture://ev-test',repeat('b',64),'TEXT');

INSERT INTO soa_evidence.evidence_references(evidence_ref_id,evidence_id,source_id,locator,support_type,relationship,evidence_state_snapshot,admissibility_scope)
VALUES ('evref_test','ev_test','src_test','lines:1-1','DIRECT','supports local gate claim','ADMISSIBLE','AP-001');

INSERT INTO soa_intelligence.analysis_profiles(analysis_profile_id,version,name,human_review_mode,restricted_workflow,config,maturity)
VALUES ('AP-001','1.0.0','Local Gate Factual','NONE',false,'{}'::jsonb,'M2');

INSERT INTO soa_intelligence.calibration_registry(calibration_id,analysis_profile_id,methodology_ref,metric_name,metric_value,sample_size)
VALUES ('cal_test','AP-001','forecast-test-v1','brier',0.12,100);

INSERT INTO soa_intelligence.runs(run_id,project_id,analysis_profile_id,analysis_profile_version,purpose,status,mode)
VALUES ('run_test','prj_test','AP-001','1.0.0','LOCAL_GATE','RUNNING','MOCK');

INSERT INTO soa_core.contexts(context_id,project_id,context_type,dimensions)
VALUES ('ctx_test','prj_test','TEST','{"temporal":{},"relational":{}}'::jsonb);

INSERT INTO soa_core.claims(
 claim_id,subject_id,statement,claim_kind,epistemic_class,analysis_profile_id,analysis_profile_version,
 methodology_ref,confidence_score,confidence_semantics,status
) VALUES (
 'clm_test','sub_test','Synthetic documented observation.','OBSERVATION','DOCUMENTED_FACT','AP-001','1.0.0',
 'factual-test-v1',0.95,'uncalibrated confidence','ACTIVE'
);

INSERT INTO soa_core.claim_evidence(claim_id,evidence_ref_id,evidence_role)
VALUES ('clm_test','evref_test','SUPPORTING');

INSERT INTO soa_core.context_graph_edges(edge_id,from_ref,to_ref,relation_type,directed,valid_from,evidence_ref_id)
VALUES ('edge_test','sub_test','ctx_test','OBSERVED_IN',true,now(),'evref_test');

INSERT INTO soa_ops.context_receipts(
 context_receipt_id,run_id,context_id,analysis_profile_id,purpose_class,precheck_status,review_mode,
 identity_summary,evidence_refs,claims_created,output_status
) VALUES (
 'cr_test','run_test','ctx_test','AP-001','LOCAL_GATE','PASS','NONE',
 '{"resolution_status":"SUFFICIENT"}'::jsonb,'["evref_test"]'::jsonb,'["clm_test"]'::jsonb,'COMPLETED'
);

COMMIT;
