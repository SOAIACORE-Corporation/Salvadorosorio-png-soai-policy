"use server";

import { randomUUID } from "node:crypto";
import { redirect } from "next/navigation";
import { coreRequest } from "../../../server/core-client.mjs";

export async function createSyntheticRun(formData) {
  const request = {
    context_capsule_id: String(formData.get("context_capsule_id") ?? "").trim(),
    analysis_profile_id: String(formData.get("analysis_profile_id") ?? "").trim(),
    analysis_profile_version: String(
      formData.get("analysis_profile_version") ?? "",
    ).trim(),
    purpose: String(formData.get("purpose") ?? "P0_SYNTHETIC_WEB").trim(),
    mode: "MOCK",
    mock_fixture_id: "documented-observation",
  };
  const result = await coreRequest("/v1/runs", {
    method: "POST",
    body: request,
    idempotencyKey: `web-${randomUUID()}`,
  });
  redirect(`/runs/${encodeURIComponent(result.run_id)}`);
}

