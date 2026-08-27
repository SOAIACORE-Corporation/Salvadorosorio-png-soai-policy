import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";

import { CoreApiError } from "../src/server/core-client.mjs";
import {
  loadOperatorWorkflow,
  performOperatorAction,
  publicOperatorError,
  workflowIdempotencyKey,
} from "../src/server/operator-workflow.mjs";
import {
  loadContextInspector,
  publicContextInspectorError,
} from "../src/server/context-inspector.mjs";
import {
  loadEvidenceExplorer,
  publicEvidenceExplorerError,
} from "../src/server/evidence-explorer.mjs";

test("operator snapshot uses filtered Core read APIs through the server", async () => {
  const calls = [];
  const responses = new Map([
    ["/v1/projects?limit=100", [{ project_id: "prj_one", name: "One" }]],
    ["/v1/analysis-profiles?limit=100", [{ analysis_profile_id: "AP-101", version: "1.0.0" }]],
    ["/v1/projects/prj_one/corpora?limit=100", [{ corpus_id: "cor_one", name: "Corpus" }]],
    ["/v1/contexts?project_id=prj_one&corpus_id=cor_one&limit=100", [{ context_id: "ctx_one" }]],
    ["/v1/context-capsules?context_id=ctx_one&limit=100", [{ context_capsule_id: "cap_one" }]],
    ["/v1/context-capsules/cap_one", { context_capsule_id: "cap_one", payload: {} }],
  ]);
  const snapshot = await loadOperatorWorkflow(
    { projectId: "prj_one", corpusId: "cor_one", contextId: "ctx_one", capsuleId: "cap_one" },
    { coreRequestImpl: async (requestPath) => { calls.push(requestPath); return responses.get(requestPath); } },
  );
  assert.equal(snapshot.projects[0].project_id, "prj_one");
  assert.equal(snapshot.selectedCapsule.context_capsule_id, "cap_one");
  assert.deepEqual(calls.sort(), [...responses.keys()].sort());
});

test("context inspector reads capsule lineage and evidence metadata through the BFF", async () => {
  const calls = [];
  const responses = new Map([
    ["/v1/context-capsules/cap_one", {
      context_capsule_id: "cap_one",
      context_id: "ctx_one",
      schema_version: "P0-RUNTIME-1",
      input_hash: "hash_one",
      created_at: "2026-08-26T00:00:00Z",
      payload: {
        project_id: "prj_one",
        analysis_profile_id: "AP-101",
        analysis_profile_version: "1.0.0",
        purpose: "Synthetic",
        synthetic_only: true,
        identity_refs: [],
        evidence_refs: ["evref_one"],
      },
    }],
    ["/v1/contexts/ctx_one", {
      context_id: "ctx_one",
      project_id: "prj_one",
      context_type: "P1_SYNTHETIC_OPERATOR",
      dimensions: { corpus_id: "cor_one", label: "Bounded context" },
    }],
    ["/v1/evidence/evref_one", {
      evidence_ref_id: "evref_one",
      evidence_state: "VERIFIED",
      content_availability: "METADATA_ONLY",
      modality: "TEXT",
      locator: "synthetic://fixture/one",
    }],
  ]);
  const snapshot = await loadContextInspector("cap_one", {
    coreRequestImpl: async (requestPath) => { calls.push(requestPath); return responses.get(requestPath); },
  });
  assert.equal(snapshot.integrity.immutable, true);
  assert.equal(snapshot.binding.analysis_profile_id, "AP-101");
  assert.equal(snapshot.context.label, "Bounded context");
  assert.equal(snapshot.evidence[0].evidence_state, "VERIFIED");
  assert.deepEqual(calls.sort(), [...responses.keys()].sort());
});

test("context inspector rejects malformed capsule IDs without exposing internals", async () => {
  await assert.rejects(() => loadContextInspector("cap one", { coreRequestImpl: async () => ({}) }));
  const failure = publicContextInspectorError(new Error("secret connection string"));
  assert.equal(failure.error.code, "CONTEXT_INSPECTOR_FAILED");
  assert.equal(JSON.stringify(failure).includes("secret"), false);
});

test("evidence explorer returns metadata-first lineage and claim role", async () => {
  const calls = [];
  const responses = new Map([
    ["/v1/evidence/evref_one", {
      evidence_ref_id: "evref_one", locator: "synthetic://fixture/one", support_type: "DIRECT",
      relationship: "SUPPORTS", evidence_state_snapshot: "VERIFIED", admissibility_scope: "P0_MOCK",
      excerpt_hash: "excerpt_hash", provenance_chain_ref: "prov_one", evidence_id: "ev_one",
      evidence_state: "VERIFIED", modality: "TEXT", content_sha256: "content_hash", object_locator: "blob://redacted",
      evidence_metadata: { synthetic: true, secret: "must-not-pass" }, source_id: "src_one", corpus_id: "cor_one",
      source_type: "FIXTURE", source_locator: "synthetic://source", byte_size: 42, source_metadata: { title: "Fixture" },
      content_availability: "METADATA_ONLY",
    }],
    ["/v1/claims/clm_one", { claim_id: "clm_one", statement: "Synthetic claim", claim_kind: "OBSERVATION", epistemic_class: "SUPPORTED", status: "ACTIVE", supporting_evidence_refs: ["evref_one"], contradicting_evidence_refs: [] }],
  ]);
  const result = await loadEvidenceExplorer("evref_one", { claimId: "clm_one", coreRequestImpl: async (requestPath) => { calls.push(requestPath); return responses.get(requestPath); } });
  assert.equal(result.evidence_object.evidence_state, "VERIFIED");
  assert.equal(result.evidence_object.metadata.secret, undefined);
  assert.equal(result.claim.role, "SUPPORTING");
  assert.equal(result.content.raw_blob_access, "NOT_IMPLEMENTED");
  assert.deepEqual(calls.sort(), [...responses.keys()].sort());
});

test("evidence explorer errors are deterministic and sanitized", () => {
  const failure = publicEvidenceExplorerError(new Error("storage secret"));
  assert.equal(failure.status, 500);
  assert.equal(failure.error.code, "EVIDENCE_EXPLORER_FAILED");
  assert.equal(JSON.stringify(failure).includes("secret"), false);
});

test("operator project creation generates the ID server-side and sends idempotency", async () => {
  let captured;
  const result = await performOperatorAction(
    { action: "create_project", request_id: "request_12345678", values: { name: "Synthetic project" } },
    {
      uuidImpl: () => "00000000-0000-0000-0000-000000000001",
      coreRequestImpl: async (requestPath, options) => {
        captured = { requestPath, options };
        return { data: { project_id: "prj_00000000000000000000000000000001" }, idempotencyReplayed: false };
      },
    },
  );
  assert.equal(captured.requestPath, "/v1/projects/prj_00000000000000000000000000000001");
  assert.equal(captured.options.method, "PUT");
  assert.equal(captured.options.idempotencyKey, "web-create_project-request_12345678");
  assert.equal(captured.options.body.metadata.synthetic, true);
  assert.equal(result.resource.project_id, "prj_00000000000000000000000000000001");
});

test("every intermediate Core write carries its stable idempotency key", async () => {
  const cases = [
    {
      action: "create_corpus",
      values: { project_id: "prj_one", name: "Synthetic corpus" },
    },
    {
      action: "create_context",
      values: { project_id: "prj_one", corpus_id: "cor_one", label: "Synthetic context" },
    },
    {
      action: "create_capsule",
      values: {
        project_id: "prj_one",
        corpus_id: "cor_one",
        context_id: "ctx_one",
        analysis_profile_id: "AP-101",
        analysis_profile_version: "1.0.0",
        purpose: "Synthetic capsule",
      },
    },
  ];
  for (const item of cases) {
    let captured;
    await performOperatorAction(
      { ...item, request_id: "request_stable_123" },
      {
        uuidImpl: () => "00000000-0000-0000-0000-000000000002",
        coreRequestImpl: async (requestPath, options) => {
          captured = { requestPath, options };
          return { data: {}, idempotencyReplayed: false };
        },
      },
    );
    assert.equal(captured.options.idempotencyKey, `web-${item.action}-request_stable_123`);
    assert.equal(captured.options.includeResponseMetadata, true);
  }
});

test("operator run remains MOCK-only and matches the immutable capsule profile", async () => {
  const calls = [];
  const result = await performOperatorAction(
    {
      action: "create_run",
      request_id: "request_abcdefgh",
      values: {
        context_capsule_id: "cap_one",
        analysis_profile_id: "AP-101",
        analysis_profile_version: "1.0.0",
        purpose: "Synthetic operator run",
      },
    },
    {
      coreRequestImpl: async (requestPath, options = {}) => {
        calls.push({ requestPath, options });
        if (options.method !== "POST") {
          return {
            context_capsule_id: "cap_one",
            payload: { analysis_profile_id: "AP-101", analysis_profile_version: "1.0.0" },
          };
        }
        return { data: { run_id: "run_one", status: "QUEUED" }, idempotencyReplayed: true };
      },
    },
  );
  assert.equal(calls[1].requestPath, "/v1/runs");
  assert.equal(calls[1].options.body.mode, "MOCK");
  assert.equal(calls[1].options.body.mock_fixture_id, "documented-observation");
  assert.equal(calls[1].options.idempotencyKey, "web-create_run-request_abcdefgh");
  assert.equal(result.idempotencyReplayed, true);
});

test("operator blocks profile changes against an immutable capsule", async () => {
  await assert.rejects(
    performOperatorAction(
      {
        action: "create_run",
        request_id: "request_mismatch",
        values: {
          context_capsule_id: "cap_one",
          analysis_profile_id: "AP-102",
          analysis_profile_version: "2.0.0",
          purpose: "Synthetic operator run",
        },
      },
      {
        coreRequestImpl: async () => ({
          payload: { analysis_profile_id: "AP-101", analysis_profile_version: "1.0.0" },
        }),
      },
    ),
    (error) => error.code === "OPERATOR_CAPSULE_PROFILE_MISMATCH",
  );
});

test("operator errors are sanitized before reaching the browser", () => {
  const failure = publicOperatorError(
    new CoreApiError(
      "DATABASE_OPERATION_FAILED",
      "postgresql://user:secret@database.internal/runtime",
      503,
      { password: "secret" },
    ),
  );
  assert.equal(failure.status, 502);
  assert.equal(failure.error.message, "The Core service is temporarily unavailable.");
  assert.equal(JSON.stringify(failure).includes("secret"), false);
});

test("operator UI uses the Web BFF and does not expose manual resource ID inputs", () => {
  const appRoot = path.resolve(import.meta.dirname, "../src/app");
  const source = fs.readFileSync(path.join(appRoot, "workflow/workflow-client.js"), "utf8");
  const styles = fs.readFileSync(path.join(appRoot, "styles.css"), "utf8");
  assert.equal(source.includes('fetch("/api/operator/workflow"'), true);
  assert.equal(source.includes('name="context_capsule_id"'), false);
  assert.equal(source.includes("NEXT_PUBLIC_CORE"), false);
  assert.equal(source.includes('mode: "LIVE"'), false);
  assert.equal(source.includes('mode: "REPLAY"'), false);
  assert.equal(source.includes("disabled={disabled"), true);
  assert.equal(styles.includes("@media (max-width: 760px)"), true);
});

test("run status UI has bounded polling and lifecycle visibility", () => {
  const appRoot = path.resolve(import.meta.dirname, "../src/app");
  const source = fs.readFileSync(path.join(appRoot, "runs/[runId]/run-status-client.js"), "utf8");
  const route = fs.readFileSync(path.join(appRoot, "api/runs/[runId]/route.js"), "utf8");
  assert.equal(source.includes("MAX_AUTO_REFRESHES = 12"), true);
  assert.equal(source.includes("MAX_REFRESH_DELAY_MS = 15000"), true);
  assert.equal(source.includes("Retry status check"), true);
  assert.equal(source.includes("lifecycle-map"), true);
  assert.equal(source.includes("correlationId"), true);
  assert.equal(route.includes("RUN_STATUS_UNAVAILABLE"), true);
  assert.equal(route.includes("retryable: true"), true);
});

test("idempotency key derivation is stable and rejects malformed request IDs", () => {
  assert.equal(
    workflowIdempotencyKey("create_context", "request_same_123"),
    workflowIdempotencyKey("create_context", "request_same_123"),
  );
  assert.throws(
    () => workflowIdempotencyKey("create_context", "bad request"),
    (error) => error.code === "OPERATOR_REQUEST_ID_INVALID",
  );
});
