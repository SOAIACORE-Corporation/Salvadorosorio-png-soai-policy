import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { CoreApiError, coreBaseUrl, coreRequest } from "../src/server/core-client.mjs";

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
