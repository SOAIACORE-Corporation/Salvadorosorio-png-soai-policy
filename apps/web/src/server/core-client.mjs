import { createHash, createHmac, randomUUID } from "node:crypto";

import { currentOperatorContext } from "./operator-context.mjs";

export class CoreApiError extends Error {
  constructor(code, message, status, details = {}) {
    super(message);
    this.name = "CoreApiError";
    this.code = code;
    this.status = status;
    this.details = details;
  }
}

export function coreBaseUrl(environment = process.env) {
  const value = environment.CORE_API_BASE_URL?.trim();
  if (!value) {
    throw new CoreApiError(
      "CORE_API_NOT_CONFIGURED",
      "Core API is unavailable.",
      503,
    );
  }
  const parsed = new URL(value);
  if (!['http:', 'https:'].includes(parsed.protocol) || parsed.username || parsed.password) {
    throw new CoreApiError(
      "CORE_API_CONFIGURATION_INVALID",
      "Core API configuration is invalid.",
      500,
    );
  }
  return value.replace(/\/$/, "");
}

export async function coreRequest(
  path,
  {
    method = "GET",
    body,
    idempotencyKey,
    includeResponseMetadata = false,
    fetchImpl = globalThis.fetch,
    environment = process.env,
    operatorContext,
  } = {},
) {
  if (!path.startsWith("/v1/") && !path.startsWith("/health/")) {
    throw new CoreApiError("CORE_PATH_REJECTED", "Core path is not allowed.", 400);
  }
  const headers = { Accept: "application/json" };
  const bodyText = body === undefined ? undefined : JSON.stringify(body);
  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
  }
  if (idempotencyKey) {
    headers["Idempotency-Key"] = idempotencyKey;
  }
  if (path.startsWith("/v1/")) {
    const operator = operatorContext ?? currentOperatorContext();
    const secret = environment.SOAIACORE_INTERNAL_AUTH_SECRET;
    if (!operator || !secret || Buffer.byteLength(secret, "utf8") < 32) {
      throw new CoreApiError(
        "CORE_AUTH_NOT_CONFIGURED",
        "The Core authorization boundary is unavailable.",
        503,
      );
    }
    const timestamp = Math.floor(Date.now() / 1000).toString();
    const correlationId = `corr_${randomUUID().replaceAll("-", "")}`;
    const parsedPath = new URL(path, "https://core.internal");
    const canonicalPath = `${parsedPath.pathname}${parsedPath.search}`;
    const contentSha256 = createHash("sha256").update(bodyText ?? "").digest("hex");
    const signaturePayload = [
      method.toUpperCase(),
      canonicalPath,
      timestamp,
      correlationId,
      operator.operatorId,
      operator.role,
      contentSha256,
    ].join("\n");
    headers["X-Correlation-ID"] = correlationId;
    headers["X-SOAIA-Operator-ID"] = operator.operatorId;
    headers["X-SOAIA-Operator-Role"] = operator.role;
    headers["X-SOAIA-Auth-Timestamp"] = timestamp;
    headers["X-SOAIA-Content-SHA256"] = contentSha256;
    headers["X-SOAIA-Auth-Signature"] = createHmac("sha256", secret)
      .update(signaturePayload)
      .digest("hex");
  }
  const response = await fetchImpl(`${coreBaseUrl(environment)}${path}`, {
    method,
    headers,
    body: bodyText,
    cache: "no-store",
  });
  const text = await response.text();
  let payload = {};
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      throw new CoreApiError("CORE_RESPONSE_INVALID", "Core returned invalid JSON.", 502);
    }
  }
  if (!response.ok) {
    const error = payload?.error ?? {};
    throw new CoreApiError(
      error.code ?? "CORE_REQUEST_FAILED",
      error.message ?? "Core rejected the request.",
      response.status,
      error.details ?? {},
    );
  }
  if (includeResponseMetadata) {
    return {
      data: payload,
      idempotencyReplayed: response.headers.get("Idempotency-Replayed") === "true",
    };
  }
  return payload;
}
