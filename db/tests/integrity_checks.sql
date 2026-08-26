-- Basic architecture integrity checks. Expected result for each query: 0 rows.

-- Probability cannot exist without methodology + calibration.
SELECT claim_id
FROM soa_core.claims
WHERE probability_estimate IS NOT NULL
  AND (methodology_ref IS NULL OR calibration_ref IS NULL);

-- Evidence references must point to evidence.
SELECT er.evidence_ref_id
FROM soa_evidence.evidence_references er
LEFT JOIN soa_evidence.evidence_objects eo ON eo.evidence_id = er.evidence_id
WHERE eo.evidence_id IS NULL;

-- Canonical subjects with duplicate IDs are impossible by PK; check alias duplicate active values per subject.
SELECT canonical_subject_id, alias_value, count(*)
FROM soa_identity.aliases
WHERE valid_until IS NULL
GROUP BY canonical_subject_id, alias_value
HAVING count(*) > 1;

-- Ground truth provenance protocol must always be present.
SELECT ground_truth_item_id
FROM soa_adjudication.ground_truth_items
WHERE provenance_protocol IS NULL OR btrim(provenance_protocol) = '';
