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
  } = {},
) {
  if (!path.startsWith("/v1/") && !path.startsWith("/health/")) {
    throw new CoreApiError("CORE_PATH_REJECTED", "Core path is not allowed.", 400);
  }
  const headers = { Accept: "application/json" };
  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
  }
  if (idempotencyKey) {
    headers["Idempotency-Key"] = idempotencyKey;
  }
  const response = await fetchImpl(`${coreBaseUrl(environment)}${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
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

