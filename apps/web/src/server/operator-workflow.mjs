import { createHash } from "node:crypto";

const IDENTIFIER = /^[A-Za-z0-9_.:-]{1,200}$/;
const PROFILE_ID = /^AP-[0-9]{3}$/;
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export function requiredText(value, label, maxLength = 200) {
  const text = String(value ?? "").trim();
  if (!text || text.length > maxLength) {
    throw new Error(`INVALID_${label.toUpperCase().replaceAll(" ", "_")}`);
  }
  return text;
}

export function requiredIdentifier(value, label = "identifier") {
  const identifier = requiredText(value, label);
  if (!IDENTIFIER.test(identifier)) {
    throw new Error(`INVALID_${label.toUpperCase().replaceAll(" ", "_")}`);
  }
  return identifier;
}

export function requiredProfileId(value) {
  const profileId = requiredText(value, "analysis profile ID");
  if (!PROFILE_ID.test(profileId)) throw new Error("INVALID_ANALYSIS_PROFILE_ID");
  return profileId;
}

export function requiredProfileSelection(value) {
  const selection = requiredText(value, "analysis profile", 300);
  const separator = selection.indexOf("@");
  if (separator < 1) throw new Error("INVALID_ANALYSIS_PROFILE");
  return {
    analysis_profile_id: requiredProfileId(selection.slice(0, separator)),
    analysis_profile_version: requiredText(
      selection.slice(separator + 1),
      "analysis profile version",
    ),
  };
}

export function requiredRequestToken(value) {
  const token = String(value ?? "").trim();
  if (!UUID.test(token)) throw new Error("INVALID_REQUEST_TOKEN");
  return token.toLowerCase();
}

export function deterministicResourceId(prefix, requestToken) {
  const token = requiredRequestToken(requestToken).replaceAll("-", "");
  return `${prefix}_${token}`;
}

export function idempotencyKey(operation, requestToken) {
  return `web-${operation}-${requiredRequestToken(requestToken)}`;
}

export function syntheticContentHash(requestToken) {
  return createHash("sha256")
    .update(`SOAIACORE synthetic operator fixture ${requiredRequestToken(requestToken)}`)
    .digest("hex");
}

export function workflowPath(values = {}) {
  const query = new URLSearchParams();
  for (const key of ["project_id", "corpus_id", "context_id", "capsule_id", "notice", "error"]) {
    if (values[key]) query.set(key, String(values[key]));
  }
  const suffix = query.toString();
  return suffix ? `/runs/new?${suffix}` : "/runs/new";
}

export function publicErrorCode(error) {
  const code = String(error?.code ?? error?.message ?? "REQUEST_FAILED");
  return /^[A-Z0-9_]{1,80}$/.test(code) ? code : "REQUEST_FAILED";
}

export function profileFromCapsule(capsule) {
  const payload = capsule?.payload;
  if (!payload || typeof payload !== "object") return null;
  try {
    return {
      analysis_profile_id: requiredProfileId(payload.analysis_profile_id),
      analysis_profile_version: requiredText(
        payload.analysis_profile_version,
        "analysis profile version",
      ),
    };
  } catch {
    return null;
  }
}
