import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { CoreApiError, coreBaseUrl, coreRequest } from "../src/server/core-client.mjs";
import {
  deterministicResourceId,
  idempotencyKey,
  profileFromCapsule,
  publicErrorCode,
  requiredProfileSelection,
  requiredRequestToken,
  workflowPath,
} from "../src/server/operator-workflow.mjs";

test("WEB_BFF uses CORE_API_BASE_URL only on the server request", async () => {
  let captured;
  const payload = await coreRequest("/v1/runs/run_test", {
    environment: { CORE_API_BASE_URL: "https://core.internal" },
    fetchImpl: async (url, options) => {
      captured = { url, options };
      return new Response(JSON.stringify({ run_id: "run_test", status: "QUEUED" }), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    },
  });
  assert.equal(captured.url, "https://core.internal/v1/runs/run_test");
  assert.equal(captured.options.cache, "no-store");
  assert.equal(payload.run_id, "run_test");
});

test("WEB_BFF rejects credentials embedded in Core URL", () => {
  assert.throws(
    () => coreBaseUrl({ CORE_API_BASE_URL: "https://user:password@core.internal" }),
    (error) => error instanceof CoreApiError && error.code === "CORE_API_CONFIGURATION_INVALID",
  );
});

test("WEB_BFF source contains no direct persistence or public Core variable", () => {
  const sourceRoot = path.resolve(import.meta.dirname, "../src");
  const files = [];
  const visit = (directory) => {
    for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
      const target = path.join(directory, entry.name);
      if (entry.isDirectory()) visit(target);
      else files.push(target);
    }
  };
  visit(sourceRoot);
  const source = files.map((file) => fs.readFileSync(file, "utf8")).join("\n");
  assert.equal(source.includes("NEXT_PUBLIC_CORE"), false);
  assert.equal(source.includes("DATABASE_URL"), false);
  assert.equal(source.includes("POSTGRES_PASSWORD"), false);
  assert.equal(source.includes("AZURE_STORAGE_CONNECTION_STRING"), false);
});

test("operator workflow derives replay-safe resource and idempotency identifiers", () => {
  const token = "123e4567-e89b-42d3-a456-426614174000";
  assert.equal(
    deterministicResourceId("prj", token),
    "prj_123e4567e89b42d3a456426614174000",
  );
  assert.equal(idempotencyKey("project", token), `web-project-${token}`);
  assert.equal(requiredRequestToken(token.toUpperCase()), token);
  assert.throws(() => requiredRequestToken("not-a-token"), /INVALID_REQUEST_TOKEN/);
});

test("operator workflow keeps selections in Web URLs and sanitizes error codes", () => {
  assert.equal(
    workflowPath({ project_id: "prj one", corpus_id: "cor/one", notice: "READY" }),
    "/runs/new?project_id=prj+one&corpus_id=cor%2Fone&notice=READY",
  );
  assert.equal(publicErrorCode({ code: "RESOURCE_NOT_FOUND" }), "RESOURCE_NOT_FOUND");
  assert.equal(publicErrorCode({ message: "unsafe error detail" }), "REQUEST_FAILED");
});

test("operator workflow resolves the profile from an immutable capsule", () => {
  assert.deepEqual(requiredProfileSelection("AP-101@1.0.0"), {
    analysis_profile_id: "AP-101",
    analysis_profile_version: "1.0.0",
  });
  assert.deepEqual(
    profileFromCapsule({
      payload: { analysis_profile_id: "AP-101", analysis_profile_version: "1.0.0" },
    }),
    { analysis_profile_id: "AP-101", analysis_profile_version: "1.0.0" },
  );
  assert.equal(profileFromCapsule({ payload: { analysis_profile_id: "bad" } }), null);
});
