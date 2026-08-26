"use server";

import { redirect } from "next/navigation";
import { coreRequest } from "../../../server/core-client.mjs";
import {
  deterministicResourceId,
  idempotencyKey,
  profileFromCapsule,
  publicErrorCode,
  requiredIdentifier,
  requiredProfileSelection,
  requiredRequestToken,
  requiredText,
  syntheticContentHash,
  workflowPath,
} from "../../../server/operator-workflow.mjs";

function selection(formData) {
  const values = {};
  for (const key of ["project_id", "corpus_id", "context_id", "capsule_id"]) {
    const value = String(formData.get(key) ?? "").trim();
    if (value) values[key] = value;
  }
  return values;
}

function fail(error, values) {
  redirect(workflowPath({ ...values, error: publicErrorCode(error) }));
}

export async function createProject(formData) {
  const requestToken = String(formData.get("request_token") ?? "");
  let projectId;
  try {
    requiredRequestToken(requestToken);
    const name = requiredText(formData.get("name"), "project name");
    projectId = deterministicResourceId("prj", requestToken);
    await coreRequest(`/v1/projects/${encodeURIComponent(projectId)}`, {
      method: "PUT",
      body: { name, status: "ACTIVE", metadata: { synthetic: true, source: "WEB_OPERATOR" } },
      idempotencyKey: idempotencyKey("project", requestToken),
    });
  } catch (error) {
    fail(error, {});
  }
  redirect(workflowPath({ project_id: projectId, notice: "PROJECT_READY" }));
}

export async function createCorpus(formData) {
  const values = selection(formData);
  const requestToken = String(formData.get("request_token") ?? "");
  let corpusId;
  try {
    const projectId = requiredIdentifier(values.project_id, "project ID");
    requiredRequestToken(requestToken);
    const name = requiredText(formData.get("name"), "corpus name");
    corpusId = deterministicResourceId("cor", requestToken);
    await coreRequest(
      `/v1/projects/${encodeURIComponent(projectId)}/corpora/${encodeURIComponent(corpusId)}`,
      {
        method: "PUT",
        body: { name, metadata: { synthetic: true, source: "WEB_OPERATOR" } },
        idempotencyKey: idempotencyKey("corpus", requestToken),
      },
    );
  } catch (error) {
    fail(error, values);
  }
  redirect(workflowPath({ ...values, corpus_id: corpusId, notice: "CORPUS_READY" }));
}

export async function createContext(formData) {
  const values = selection(formData);
  const requestToken = String(formData.get("request_token") ?? "");
  let contextId;
  try {
    const projectId = requiredIdentifier(values.project_id, "project ID");
    const corpusId = requiredIdentifier(values.corpus_id, "corpus ID");
    requiredRequestToken(requestToken);
    const label = requiredText(formData.get("label"), "context label");
    contextId = deterministicResourceId("ctx", requestToken);
    await coreRequest("/v1/contexts", {
      method: "POST",
      body: {
        context_id: contextId,
        project_id: projectId,
        context_type: "P1_SYNTHETIC",
        dimensions: { corpus_id: corpusId, label, synthetic: true },
      },
      idempotencyKey: idempotencyKey("context", requestToken),
    });
  } catch (error) {
    fail(error, values);
  }
  redirect(workflowPath({ ...values, context_id: contextId, notice: "CONTEXT_READY" }));
}

export async function createCapsule(formData) {
  const values = selection(formData);
  const requestToken = String(formData.get("request_token") ?? "");
  let capsuleId;
  try {
    const projectId = requiredIdentifier(values.project_id, "project ID");
    const corpusId = requiredIdentifier(values.corpus_id, "corpus ID");
    const contextId = requiredIdentifier(values.context_id, "context ID");
    const {
      analysis_profile_id: profileId,
      analysis_profile_version: profileVersion,
    } = requiredProfileSelection(formData.get("analysis_profile"));
    const label = requiredText(formData.get("label"), "capsule label");
    requiredRequestToken(requestToken);

    capsuleId = deterministicResourceId("cap", requestToken);
    const subjectId = deterministicResourceId("sub", requestToken);
    const evidenceRefId = deterministicResourceId("evref", requestToken);
    const evidenceId = deterministicResourceId("ev", requestToken);
    const sourceId = deterministicResourceId("src", requestToken);

    await coreRequest("/v1/identity/resolve", {
      method: "POST",
      body: {
        observed_actor_id: deterministicResourceId("act", requestToken),
        corpus_id: corpusId,
        source_local_ref: `fixture://actor/${subjectId}`,
        display_label: "Synthetic operator subject",
        canonical_subject_id: subjectId,
        identity_resolution_status: "ADJUDICATED",
        identity_claim_id: deterministicResourceId("idc", requestToken),
        identity_decision_id: deterministicResourceId("idd", requestToken),
        decision_type: "LINK",
        evidence_refs: [evidenceRefId],
      },
      idempotencyKey: idempotencyKey("capsule-identity", requestToken),
    });

    await coreRequest("/v1/evidence/register", {
      method: "POST",
      body: {
        source_id: sourceId,
        corpus_id: corpusId,
        source_type: "TEXT",
        source_locator: `fixture://source/${sourceId}`,
        content_sha256: syntheticContentHash(requestToken),
        byte_size: 0,
        source_metadata: { synthetic: true, source: "WEB_OPERATOR" },
        evidence_id: evidenceId,
        evidence_state: "ADMISSIBLE",
        object_locator: `fixture://object/${evidenceId}`,
        modality: "TEXT",
        evidence_metadata: { synthetic: true },
        evidence_ref_id: evidenceRefId,
        locator: "bytes:0-0",
        support_type: "DIRECT",
        relationship: "SUPPORTS",
        admissibility_scope: profileId,
      },
      idempotencyKey: idempotencyKey("capsule-evidence", requestToken),
    });

    await coreRequest("/v1/context-capsules", {
      method: "POST",
      body: {
        context_capsule_id: capsuleId,
        context_id: contextId,
        schema_version: "P0-RUNTIME-1",
        payload: {
          project_id: projectId,
          corpus_id: corpusId,
          context_id: contextId,
          analysis_profile_id: profileId,
          analysis_profile_version: profileVersion,
          identity_refs: [subjectId],
          evidence_refs: [evidenceRefId],
          synthetic_only: true,
          purpose: "P1_INTERNAL_OPERATOR",
          label,
        },
      },
      idempotencyKey: idempotencyKey("capsule", requestToken),
    });
  } catch (error) {
    fail(error, values);
  }
  redirect(workflowPath({ ...values, capsule_id: capsuleId, notice: "CAPSULE_READY" }));
}

export async function createSyntheticRun(formData) {
  const values = selection(formData);
  const requestToken = String(formData.get("request_token") ?? "");
  let result;
  try {
    const capsuleId = requiredIdentifier(values.capsule_id, "capsule ID");
    requiredRequestToken(requestToken);
    const purpose = requiredText(formData.get("purpose"), "purpose");
    const capsule = await coreRequest(
      `/v1/context-capsules/${encodeURIComponent(capsuleId)}`,
    );
    const profile = profileFromCapsule(capsule);
    if (!profile) throw new Error("CAPSULE_PROFILE_UNAVAILABLE");
    result = await coreRequest("/v1/runs", {
      method: "POST",
      body: {
        context_capsule_id: capsuleId,
        ...profile,
        purpose,
        mode: "MOCK",
        mock_fixture_id: "documented-observation",
      },
      idempotencyKey: idempotencyKey("run", requestToken),
    });
  } catch (error) {
    fail(error, values);
  }
  redirect(`/runs/${encodeURIComponent(result.run_id)}`);
}
