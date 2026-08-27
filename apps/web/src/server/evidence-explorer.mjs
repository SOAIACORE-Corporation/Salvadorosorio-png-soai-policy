import { CoreApiError, coreRequest } from "./core-client.mjs";

const IDENTIFIER_PATTERN = /^[A-Za-z0-9_.:-]{1,200}$/;
const APPROVED_METADATA_KEYS = new Set([
  "synthetic", "source", "label", "description", "mime_type", "title", "filename",
  "language", "page_count", "record_count", "provider", "version", "content_availability",
]);

export class EvidenceExplorerValidationError extends Error {
  constructor(message = "The evidence reference identifier is invalid.") {
    super(message);
    this.name = "EvidenceExplorerValidationError";
    this.code = "EVIDENCE_REFERENCE_INVALID";
    this.status = 400;
  }
}

function safeMetadata(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return {};
  return Object.fromEntries(
    Object.entries(value).filter(([key, item]) => APPROVED_METADATA_KEYS.has(key) && ["string", "number", "boolean"].includes(typeof item)),
  );
}

function safeText(value) {
  return typeof value === "string" ? value : null;
}

export async function loadEvidenceExplorer(
  evidenceRefId,
  { claimId = "", coreRequestImpl = coreRequest } = {},
) {
  const normalizedRef = String(evidenceRefId ?? "").trim();
  if (!IDENTIFIER_PATTERN.test(normalizedRef)) throw new EvidenceExplorerValidationError();
  const evidence = await coreRequestImpl(`/v1/evidence/${encodeURIComponent(normalizedRef)}`);

  let claim = null;
  const normalizedClaim = String(claimId ?? "").trim();
  if (normalizedClaim) {
    if (!IDENTIFIER_PATTERN.test(normalizedClaim)) throw new EvidenceExplorerValidationError("The claim identifier is invalid.");
    const sourceClaim = await coreRequestImpl(`/v1/claims/${encodeURIComponent(normalizedClaim)}`);
    const supporting = Array.isArray(sourceClaim.supporting_evidence_refs) && sourceClaim.supporting_evidence_refs.includes(normalizedRef);
    const contradicting = Array.isArray(sourceClaim.contradicting_evidence_refs) && sourceClaim.contradicting_evidence_refs.includes(normalizedRef);
    claim = {
      claim_id: safeText(sourceClaim.claim_id),
      statement: safeText(sourceClaim.statement),
      claim_kind: safeText(sourceClaim.claim_kind),
      epistemic_class: safeText(sourceClaim.epistemic_class),
      status: safeText(sourceClaim.status),
      role: supporting ? "SUPPORTING" : contradicting ? "CONTRADICTING" : "LINK_NOT_CONFIRMED",
    };
  }

  return {
    evidence_reference: {
      evidence_ref_id: safeText(evidence.evidence_ref_id),
      locator: safeText(evidence.locator),
      support_type: safeText(evidence.support_type),
      relationship: safeText(evidence.relationship),
      evidence_state_snapshot: safeText(evidence.evidence_state_snapshot),
      admissibility_scope: safeText(evidence.admissibility_scope),
      excerpt_hash: safeText(evidence.excerpt_hash),
      provenance_chain_ref: safeText(evidence.provenance_chain_ref),
    },
    evidence_object: {
      evidence_id: safeText(evidence.evidence_id),
      evidence_state: safeText(evidence.evidence_state),
      modality: safeText(evidence.modality),
      content_sha256: safeText(evidence.content_sha256),
      object_locator: safeText(evidence.object_locator),
      metadata: safeMetadata(evidence.evidence_metadata),
    },
    source_artifact: {
      source_id: safeText(evidence.source_id),
      corpus_id: safeText(evidence.corpus_id),
      source_type: safeText(evidence.source_type),
      source_locator: safeText(evidence.source_locator),
      byte_size: typeof evidence.byte_size === "number" ? evidence.byte_size : null,
      metadata: safeMetadata(evidence.source_metadata),
    },
    content: {
      availability: safeText(evidence.content_availability) ?? "NOT_IMPLEMENTED",
      raw_blob_access: "NOT_IMPLEMENTED",
    },
    claim,
  };
}

export function publicEvidenceExplorerError(error) {
  if (error instanceof EvidenceExplorerValidationError) {
    return { status: error.status, error: { code: error.code, message: error.message } };
  }
  if (error instanceof CoreApiError) {
    const status = error.status >= 400 && error.status < 500 ? error.status : 502;
    return {
      status,
      error: {
        code: status === 502 ? "EVIDENCE_EXPLORER_UNAVAILABLE" : error.code,
        message: status === 502 ? "The Core service is temporarily unavailable." : error.message,
      },
    };
  }
  return { status: 500, error: { code: "EVIDENCE_EXPLORER_FAILED", message: "The evidence explorer could not be loaded." } };
}
