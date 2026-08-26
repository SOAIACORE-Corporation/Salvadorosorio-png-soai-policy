import { randomUUID } from "node:crypto";

import { CoreApiError, coreRequest } from "./core-client.mjs";

const ACTIONS = new Set([
  "create_project",
  "create_corpus",
  "create_context",
  "create_capsule",
  "create_run",
]);
const REQUEST_ID_PATTERN = /^[A-Za-z0-9_-]{8,100}$/;
const PROFILE_ID_PATTERN = /^AP-[0-9]{3}$/;

export class OperatorValidationError extends Error {
  constructor(code, message) {
    super(message);
    this.name = "OperatorValidationError";
    this.code = code;
    this.status = 400;
  }
}

function requiredText(value, label, maxLength = 200) {
  const text = String(value ?? "").trim();
  if (!text) {
    throw new OperatorValidationError("OPERATOR_INPUT_REQUIRED", `${label} is required.`);
  }
  if (text.length > maxLength) {
    throw new OperatorValidationError(
      "OPERATOR_INPUT_TOO_LONG",
      `${label} must be ${maxLength} characters or fewer.`,
    );
  }
  return text;
}

function optionalIdentifier(value, label) {
  const text = String(value ?? "").trim();
  if (!text || text.length > 200 || !/^[A-Za-z0-9_.:-]+$/.test(text)) {
    throw new OperatorValidationError("OPERATOR_SELECTION_INVALID", `${label} is invalid.`);
  }
  return text;
}

function resourceId(prefix, uuidImpl) {
  return `${prefix}_${uuidImpl().replaceAll("-", "")}`;
}

export function workflowIdempotencyKey(action, requestId) {
  if (!ACTIONS.has(action)) {
    throw new OperatorValidationError("OPERATOR_ACTION_INVALID", "The requested action is invalid.");
  }
  const normalized = String(requestId ?? "").trim();
  if (!REQUEST_ID_PATTERN.test(normalized)) {
    throw new OperatorValidationError(
      "OPERATOR_REQUEST_ID_INVALID",
      "The operation request identifier is invalid.",
    );
  }
  return `web-${action}-${normalized}`;
}

function queryPath(path, values) {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(values)) {
    if (value) query.set(key, value);
  }
  query.set("limit", "100");
  return `${path}?${query}`;
}

export async function loadOperatorWorkflow(
  selection = {},
  { coreRequestImpl = coreRequest } = {},
) {
  const projectId = String(selection.projectId ?? "").trim();
  const corpusId = String(selection.corpusId ?? "").trim();
  const contextId = String(selection.contextId ?? "").trim();
  const capsuleId = String(selection.capsuleId ?? "").trim();

  const [projects, profiles] = await Promise.all([
    coreRequestImpl("/v1/projects?limit=100"),
    coreRequestImpl("/v1/analysis-profiles?limit=100"),
  ]);
  const corpora = projectId
    ? await coreRequestImpl(
        `/v1/projects/${encodeURIComponent(projectId)}/corpora?limit=100`,
      )
    : [];
  const contexts = projectId
    ? await coreRequestImpl(
        queryPath("/v1/contexts", { project_id: projectId, corpus_id: corpusId }),
      )
    : [];
  const capsules = contextId
    ? await coreRequestImpl(
        queryPath("/v1/context-capsules", { context_id: contextId }),
      )
    : [];
  const selectedCapsule = capsuleId
    ? await coreRequestImpl(`/v1/context-capsules/${encodeURIComponent(capsuleId)}`)
    : null;

  return { projects, corpora, contexts, capsules, profiles, selectedCapsule };
}

async function writeCore(coreRequestImpl, path, method, body, idempotencyKey) {
  const result = await coreRequestImpl(path, {
    method,
    body,
    idempotencyKey,
    includeResponseMetadata: true,
  });
  return {
    resource: result.data,
    idempotencyReplayed: result.idempotencyReplayed,
  };
}

export async function performOperatorAction(
  input,
  { coreRequestImpl = coreRequest, uuidImpl = randomUUID } = {},
) {
  const action = String(input?.action ?? "");
  const idempotencyKey = workflowIdempotencyKey(action, input?.request_id);
  const values = input?.values ?? {};

  if (action === "create_project") {
    const projectId = resourceId("prj", uuidImpl);
    return writeCore(
      coreRequestImpl,
      `/v1/projects/${projectId}`,
      "PUT",
      {
        name: requiredText(values.name, "Project name"),
        status: "ACTIVE",
        metadata: { synthetic: true, source: "P1_WEB_OPERATOR" },
      },
      idempotencyKey,
    );
  }

  if (action === "create_corpus") {
    const projectId = optionalIdentifier(values.project_id, "Project selection");
    const corpusId = resourceId("cor", uuidImpl);
    return writeCore(
      coreRequestImpl,
      `/v1/projects/${encodeURIComponent(projectId)}/corpora/${corpusId}`,
      "PUT",
      {
        name: requiredText(values.name, "Corpus name"),
        metadata: { synthetic: true, source: "P1_WEB_OPERATOR" },
      },
      idempotencyKey,
    );
  }

  if (action === "create_context") {
    const projectId = optionalIdentifier(values.project_id, "Project selection");
    const corpusId = optionalIdentifier(values.corpus_id, "Corpus selection");
    const contextId = resourceId("ctx", uuidImpl);
    return writeCore(
      coreRequestImpl,
      "/v1/contexts",
      "POST",
      {
        context_id: contextId,
        project_id: projectId,
        context_type: "P1_SYNTHETIC_OPERATOR",
        dimensions: {
          corpus_id: corpusId,
          label: requiredText(values.label, "Context label"),
          synthetic: true,
        },
      },
      idempotencyKey,
    );
  }

  const profileId = optionalIdentifier(values.analysis_profile_id, "Analysis profile");
  const profileVersion = requiredText(values.analysis_profile_version, "Profile version", 100);
  if (!PROFILE_ID_PATTERN.test(profileId)) {
    throw new OperatorValidationError(
      "OPERATOR_PROFILE_INVALID",
      "The selected analysis profile is invalid.",
    );
  }

  if (action === "create_capsule") {
    const projectId = optionalIdentifier(values.project_id, "Project selection");
    const corpusId = optionalIdentifier(values.corpus_id, "Corpus selection");
    const contextId = optionalIdentifier(values.context_id, "Context selection");
    const capsuleId = resourceId("cap", uuidImpl);
    return writeCore(
      coreRequestImpl,
      "/v1/context-capsules",
      "POST",
      {
        context_capsule_id: capsuleId,
        context_id: contextId,
        schema_version: "P0-RUNTIME-1",
        payload: {
          project_id: projectId,
          corpus_id: corpusId,
          context_id: contextId,
          analysis_profile_id: profileId,
          analysis_profile_version: profileVersion,
          identity_refs: [],
          evidence_refs: [],
          synthetic_only: true,
          purpose: requiredText(values.purpose, "Purpose"),
        },
      },
      idempotencyKey,
    );
  }

  const capsuleId = optionalIdentifier(values.context_capsule_id, "Context capsule");
  const capsule = await coreRequestImpl(
    `/v1/context-capsules/${encodeURIComponent(capsuleId)}`,
  );
  if (
    capsule?.payload?.analysis_profile_id !== profileId ||
    capsule?.payload?.analysis_profile_version !== profileVersion
  ) {
    throw new OperatorValidationError(
      "OPERATOR_CAPSULE_PROFILE_MISMATCH",
      "The selected profile differs from the immutable capsule. Create a new capsule for this profile.",
    );
  }
  return writeCore(
    coreRequestImpl,
    "/v1/runs",
    "POST",
    {
      context_capsule_id: capsuleId,
      analysis_profile_id: profileId,
      analysis_profile_version: profileVersion,
      purpose: requiredText(values.purpose, "Purpose"),
      mode: "MOCK",
      mock_fixture_id: "documented-observation",
    },
    idempotencyKey,
  );
}

export function publicOperatorError(error) {
  if (error instanceof OperatorValidationError) {
    return { status: error.status, error: { code: error.code, message: error.message } };
  }
  if (error instanceof CoreApiError) {
    const status = error.status >= 400 && error.status < 500 ? error.status : 502;
    return {
      status,
      error: {
        code: error.code,
        message: status === 502 ? "The Core service is temporarily unavailable." : error.message,
      },
    };
  }
  return {
    status: 500,
    error: { code: "OPERATOR_REQUEST_FAILED", message: "The operator request could not be completed." },
  };
}
