import { CoreApiError, coreRequest } from "./core-client.mjs";

const CAPSULE_ID_PATTERN = /^cap_[A-Za-z0-9_-]+$/;

export class ContextInspectorValidationError extends Error {
  constructor(message = "The context capsule identifier is invalid.") {
    super(message);
    this.name = "ContextInspectorValidationError";
    this.code = "CONTEXT_CAPSULE_INVALID";
    this.status = 400;
  }
}

function text(value) {
  return typeof value === "string" ? value : null;
}

function evidenceSummary(refId, metadata, error) {
  if (error || !metadata) {
    return { evidence_ref_id: refId, availability: "UNAVAILABLE" };
  }
  return {
    evidence_ref_id: refId,
    availability: text(metadata.content_availability) ?? "METADATA_ONLY",
    evidence_state: text(metadata.evidence_state),
    evidence_state_snapshot: text(metadata.evidence_state_snapshot),
    modality: text(metadata.modality),
    locator: text(metadata.locator),
    excerpt_hash: text(metadata.excerpt_hash),
    content_sha256: text(metadata.content_sha256),
  };
}

export async function loadContextInspector(
  capsuleId,
  { coreRequestImpl = coreRequest } = {},
) {
  const normalizedId = String(capsuleId ?? "").trim();
  if (!CAPSULE_ID_PATTERN.test(normalizedId)) throw new ContextInspectorValidationError();

  const capsule = await coreRequestImpl(`/v1/context-capsules/${encodeURIComponent(normalizedId)}`);
  const payload = capsule?.payload ?? {};
  const context = await coreRequestImpl(
    `/v1/contexts/${encodeURIComponent(capsule.context_id)}`,
  );
  const evidenceRefs = Array.isArray(payload.evidence_refs) ? payload.evidence_refs : [];
  const evidenceResults = await Promise.all(
    evidenceRefs.map(async (refId) => {
      try {
        return evidenceSummary(refId, await coreRequestImpl(`/v1/evidence/${encodeURIComponent(refId)}`));
      } catch (error) {
        if (!(error instanceof CoreApiError)) throw error;
        return evidenceSummary(refId, null, error);
      }
    }),
  );

  return {
    capsule: {
      context_capsule_id: text(capsule.context_capsule_id),
      context_id: text(capsule.context_id),
      schema_version: text(capsule.schema_version),
      input_hash: text(capsule.input_hash),
      created_at: text(capsule.created_at),
    },
    context: {
      context_id: text(context.context_id),
      project_id: text(context.project_id),
      context_type: text(context.context_type),
      valid_from: text(context.valid_from),
      valid_until: text(context.valid_until),
      label: text(context.dimensions?.label),
      corpus_id: text(context.dimensions?.corpus_id),
    },
    binding: {
      analysis_profile_id: text(payload.analysis_profile_id),
      analysis_profile_version: text(payload.analysis_profile_version),
      purpose: text(payload.purpose),
      synthetic_only: payload.synthetic_only === true,
      identity_refs: Array.isArray(payload.identity_refs) ? payload.identity_refs.length : 0,
      evidence_refs: evidenceRefs.length,
    },
    integrity: {
      immutable: true,
      input_hash_present: Boolean(capsule.input_hash),
      profile_bound: Boolean(payload.analysis_profile_id && payload.analysis_profile_version),
    },
    evidence: evidenceResults,
  };
}

export function publicContextInspectorError(error) {
  if (error instanceof ContextInspectorValidationError) {
    return { status: error.status, error: { code: error.code, message: error.message } };
  }
  if (error instanceof CoreApiError) {
    const status = error.status >= 400 && error.status < 500 ? error.status : 502;
    return {
      status,
      error: {
        code: status === 502 ? "CONTEXT_INSPECTOR_UNAVAILABLE" : error.code,
        message: status === 502 ? "The Core service is temporarily unavailable." : error.message,
      },
    };
  }
  return {
    status: 500,
    error: { code: "CONTEXT_INSPECTOR_FAILED", message: "The context inspector could not be loaded." },
  };
}
