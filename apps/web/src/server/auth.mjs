import {
  createHash,
  createPublicKey,
  randomBytes,
  timingSafeEqual,
  verify as verifySignature,
} from "node:crypto";

export const SESSION_COOKIE = "__Host-soaiacore_session";
export const OIDC_STATE_COOKIE = "__Host-soaiacore_oidc_state";

const VALID_ROLES = new Set(["OPERATOR", "ADMIN"]);
const MAX_PENDING_STATES = 1_000;
const MAX_SESSIONS = 10_000;
const stateKey = Symbol.for("soaiacore.oidc.states");
const sessionKey = Symbol.for("soaiacore.operator.sessions");
const discoveryKey = Symbol.for("soaiacore.oidc.discovery");
const states = globalThis[stateKey] ?? new Map();
const sessions = globalThis[sessionKey] ?? new Map();
const discoveryCache = globalThis[discoveryKey] ?? new Map();
globalThis[stateKey] = states;
globalThis[sessionKey] = sessions;
globalThis[discoveryKey] = discoveryCache;

export class AuthError extends Error {
  constructor(code, message, status = 401) {
    super(message);
    this.name = "AuthError";
    this.code = code;
    this.status = status;
  }
}

function base64url(value) {
  return Buffer.from(value).toString("base64url");
}

function normalizeIssuer(value) {
  return value.replace(/\/$/, "");
}

function positiveInteger(value, fallback) {
  const parsed = Number.parseInt(value ?? "", 10);
  return Number.isSafeInteger(parsed) && parsed > 0 ? parsed : fallback;
}

export function authConfig(environment = process.env) {
  const issuer = environment.SOAIACORE_OIDC_ISSUER?.trim();
  const clientId = environment.SOAIACORE_OIDC_CLIENT_ID?.trim();
  const clientSecret = environment.SOAIACORE_OIDC_CLIENT_SECRET?.trim();
  const webBaseUrl = environment.SOAIACORE_WEB_BASE_URL?.trim();
  if (!issuer || !clientId || !clientSecret || !webBaseUrl) {
    throw new AuthError(
      "AUTH_NOT_CONFIGURED",
      "Operator authentication is not configured.",
      503,
    );
  }
  const issuerUrl = new URL(issuer);
  const baseUrl = new URL(webBaseUrl);
  if (issuerUrl.protocol !== "https:" || baseUrl.protocol !== "https:") {
    throw new AuthError("AUTH_CONFIGURATION_INVALID", "OIDC URLs must use HTTPS.", 503);
  }
  return {
    issuer: normalizeIssuer(issuerUrl.toString()),
    clientId,
    clientSecret,
    webBaseUrl: normalizeIssuer(baseUrl.toString()),
    redirectUri: `${normalizeIssuer(baseUrl.toString())}/api/auth/callback`,
    operatorGroup: environment.SOAIACORE_OIDC_OPERATOR_GROUP?.trim() || "SOAIACORE_OPERATOR",
    adminGroup: environment.SOAIACORE_OIDC_ADMIN_GROUP?.trim() || "SOAIACORE_ADMIN",
    sessionTtlSeconds: positiveInteger(environment.SOAIACORE_SESSION_TTL_SECONDS, 28_800),
    secureCookies: true,
  };
}

export function safeReturnTo(value, fallback = "/") {
  if (typeof value !== "string" || !value.startsWith("/") || value.startsWith("//")) {
    return fallback;
  }
  try {
    const parsed = new URL(value, "https://return.invalid");
    if (parsed.origin !== "https://return.invalid") return fallback;
    return `${parsed.pathname}${parsed.search}${parsed.hash}`;
  } catch {
    return fallback;
  }
}

function cookie(name, value, { maxAge, secure = true } = {}) {
  const parts = [
    `${name}=${encodeURIComponent(value)}`,
    "Path=/",
    "HttpOnly",
    "SameSite=Lax",
    `Max-Age=${Math.max(0, Math.floor(maxAge ?? 0))}`,
  ];
  if (secure) parts.push("Secure");
  return parts.join("; ");
}

function cookieValue(header, name) {
  for (const item of (header ?? "").split(";")) {
    const [key, ...rest] = item.trim().split("=");
    if (key === name) return decodeURIComponent(rest.join("="));
  }
  return null;
}

function prune(nowSeconds) {
  for (const [id, state] of states) if (state.expiresAt <= nowSeconds) states.delete(id);
  for (const [id, session] of sessions) if (session.expiresAt <= nowSeconds) sessions.delete(id);
}

async function discovery(config, fetchImpl) {
  const cached = discoveryCache.get(config.issuer);
  if (cached) return cached;
  const response = await fetchImpl(`${config.issuer}/.well-known/openid-configuration`, {
    headers: { Accept: "application/json" },
    cache: "no-store",
  });
  if (!response.ok) throw new AuthError("OIDC_DISCOVERY_FAILED", "Identity provider is unavailable.", 503);
  const metadata = await response.json();
  if (
    normalizeIssuer(metadata.issuer ?? "") !== config.issuer ||
    !metadata.authorization_endpoint?.startsWith("https://") ||
    !metadata.token_endpoint?.startsWith("https://") ||
    !metadata.jwks_uri?.startsWith("https://")
  ) {
    throw new AuthError("OIDC_DISCOVERY_INVALID", "Identity provider metadata is invalid.", 503);
  }
  discoveryCache.set(config.issuer, metadata);
  return metadata;
}

function claimValues(claims) {
  const values = [];
  for (const key of ["roles", "groups"]) {
    const value = claims[key];
    if (Array.isArray(value)) values.push(...value);
    else if (typeof value === "string") values.push(value);
  }
  return new Set(values.map((value) => String(value).toUpperCase()));
}

export function roleFromClaims(claims, config) {
  const values = claimValues(claims);
  if (values.has("ADMIN") || values.has(config.adminGroup.toUpperCase())) return "ADMIN";
  if (values.has("OPERATOR") || values.has(config.operatorGroup.toUpperCase())) return "OPERATOR";
  throw new AuthError("OPERATOR_ROLE_FORBIDDEN", "This identity is not authorized for the pilot.", 403);
}

export function createSessionFromClaims(claims, config, nowSeconds = Math.floor(Date.now() / 1000)) {
  if (!claims.sub || !claims.iss) throw new AuthError("OIDC_IDENTITY_INVALID", "Identity claims are invalid.");
  const role = roleFromClaims(claims, config);
  const operatorId = `op_${createHash("sha256")
    .update(`${claims.iss}\u0000${claims.sub}`)
    .digest("hex")
    .slice(0, 24)}`;
  const id = base64url(randomBytes(32));
  const expiresAt = Math.min(
    nowSeconds + config.sessionTtlSeconds,
    Number.isFinite(claims.exp) ? claims.exp : Number.MAX_SAFE_INTEGER,
  );
  const session = Object.freeze({ id, operatorId, role, issuedAt: nowSeconds, expiresAt });
  prune(nowSeconds);
  if (sessions.size >= MAX_SESSIONS) {
    throw new AuthError("SESSION_CAPACITY_REACHED", "Operator session capacity is temporarily unavailable.", 503);
  }
  sessions.set(id, session);
  return session;
}

export function sessionById(id, nowSeconds = Math.floor(Date.now() / 1000)) {
  prune(nowSeconds);
  if (!id) return null;
  return sessions.get(id) ?? null;
}

export function sessionFromRequest(request, nowSeconds = Math.floor(Date.now() / 1000)) {
  return sessionById(cookieValue(request.headers.get("cookie"), SESSION_COOKIE), nowSeconds);
}

export function requireSession(request, requiredRole = "OPERATOR") {
  const session = sessionFromRequest(request);
  if (!session) throw new AuthError("AUTHENTICATION_REQUIRED", "Sign in is required.", 401);
  requireRole(session, requiredRole);
  return session;
}

export function requireRole(session, requiredRole) {
  if (!VALID_ROLES.has(requiredRole)) throw new TypeError("Unknown operator role");
  if (requiredRole === "ADMIN" && session.role !== "ADMIN") {
    throw new AuthError("ADMIN_ROLE_REQUIRED", "Administrator access is required.", 403);
  }
  return session;
}

export function safeSession(session) {
  return { operator_id: session.operatorId, role: session.role, expires_at: session.expiresAt };
}

export async function beginOidcLogin(request, { environment = process.env, fetchImpl = fetch } = {}) {
  const config = authConfig(environment);
  const metadata = await discovery(config, fetchImpl);
  const now = Math.floor(Date.now() / 1000);
  prune(now);
  if (states.size >= MAX_PENDING_STATES) {
    throw new AuthError("OIDC_CAPACITY_REACHED", "Sign-in capacity is temporarily unavailable.", 503);
  }
  const state = base64url(randomBytes(24));
  const nonce = base64url(randomBytes(24));
  const verifier = base64url(randomBytes(32));
  const challenge = base64url(createHash("sha256").update(verifier).digest());
  const returnTo = safeReturnTo(new URL(request.url).searchParams.get("return_to"));
  states.set(state, { nonce, verifier, returnTo, expiresAt: now + 600 });
  const authorization = new URL(metadata.authorization_endpoint);
  authorization.search = new URLSearchParams({
    response_type: "code",
    client_id: config.clientId,
    redirect_uri: config.redirectUri,
    scope: "openid profile",
    state,
    nonce,
    code_challenge: challenge,
    code_challenge_method: "S256",
  }).toString();
  return new Response(null, {
    status: 302,
    headers: {
      Location: authorization.toString(),
      "Set-Cookie": cookie(OIDC_STATE_COOKIE, state, { maxAge: 600, secure: config.secureCookies }),
      "Cache-Control": "no-store",
    },
  });
}

function parseJwt(token) {
  const parts = token.split(".");
  if (parts.length !== 3) throw new AuthError("OIDC_ID_TOKEN_INVALID", "Identity token is invalid.");
  try {
    return {
      header: JSON.parse(Buffer.from(parts[0], "base64url").toString("utf8")),
      claims: JSON.parse(Buffer.from(parts[1], "base64url").toString("utf8")),
      signed: Buffer.from(`${parts[0]}.${parts[1]}`),
      signature: Buffer.from(parts[2], "base64url"),
    };
  } catch {
    throw new AuthError("OIDC_ID_TOKEN_INVALID", "Identity token is invalid.");
  }
}

async function validateIdToken(token, metadata, config, expectedNonce, fetchImpl) {
  const parsed = parseJwt(token);
  if (parsed.header.alg !== "RS256" || typeof parsed.header.kid !== "string") {
    throw new AuthError("OIDC_ID_TOKEN_INVALID", "Identity token algorithm is not allowed.");
  }
  const response = await fetchImpl(metadata.jwks_uri, { headers: { Accept: "application/json" }, cache: "no-store" });
  if (!response.ok) throw new AuthError("OIDC_KEYS_UNAVAILABLE", "Identity verification keys are unavailable.", 503);
  const jwks = await response.json();
  const jwk = jwks.keys?.find((candidate) => candidate.kid === parsed.header.kid && candidate.kty === "RSA");
  if (!jwk) throw new AuthError("OIDC_ID_TOKEN_INVALID", "Identity token key is invalid.");
  const valid = verifySignature("RSA-SHA256", parsed.signed, createPublicKey({ key: jwk, format: "jwk" }), parsed.signature);
  if (!valid) throw new AuthError("OIDC_ID_TOKEN_INVALID", "Identity token signature is invalid.");
  const now = Math.floor(Date.now() / 1000);
  const audience = Array.isArray(parsed.claims.aud) ? parsed.claims.aud : [parsed.claims.aud];
  const multipleAudiencesWithoutAuthorizedParty =
    audience.length > 1 && parsed.claims.azp !== config.clientId;
  if (
    normalizeIssuer(parsed.claims.iss ?? "") !== config.issuer ||
    !audience.includes(config.clientId) ||
    !Number.isFinite(parsed.claims.exp) ||
    parsed.claims.exp <= now ||
    (Number.isFinite(parsed.claims.nbf) && parsed.claims.nbf > now + 60) ||
    (Number.isFinite(parsed.claims.iat) && parsed.claims.iat > now + 60) ||
    multipleAudiencesWithoutAuthorizedParty ||
    parsed.claims.nonce !== expectedNonce
  ) {
    throw new AuthError("OIDC_ID_TOKEN_INVALID", "Identity token claims are invalid.");
  }
  return parsed.claims;
}

export async function completeOidcLogin(request, { environment = process.env, fetchImpl = fetch } = {}) {
  const config = authConfig(environment);
  const metadata = await discovery(config, fetchImpl);
  const url = new URL(request.url);
  const state = url.searchParams.get("state");
  const code = url.searchParams.get("code");
  const stateCookie = cookieValue(request.headers.get("cookie"), OIDC_STATE_COOKIE);
  const comparable = state && stateCookie && state.length === stateCookie.length;
  if (!comparable || !timingSafeEqual(Buffer.from(state), Buffer.from(stateCookie))) {
    throw new AuthError("OIDC_STATE_INVALID", "OIDC transaction is invalid.");
  }
  const transaction = states.get(state);
  states.delete(state);
  const now = Math.floor(Date.now() / 1000);
  if (!code || !transaction || transaction.expiresAt <= now) {
    throw new AuthError("OIDC_TRANSACTION_EXPIRED", "OIDC transaction has expired.");
  }
  const tokenResponse = await fetchImpl(metadata.token_endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded", Accept: "application/json" },
    body: new URLSearchParams({
      grant_type: "authorization_code",
      code,
      redirect_uri: config.redirectUri,
      client_id: config.clientId,
      client_secret: config.clientSecret,
      code_verifier: transaction.verifier,
    }),
    cache: "no-store",
  });
  if (!tokenResponse.ok) throw new AuthError("OIDC_TOKEN_EXCHANGE_FAILED", "Identity provider rejected the login.");
  const tokens = await tokenResponse.json();
  if (typeof tokens.id_token !== "string") throw new AuthError("OIDC_ID_TOKEN_MISSING", "Identity provider response is incomplete.");
  const claims = await validateIdToken(tokens.id_token, metadata, config, transaction.nonce, fetchImpl);
  const session = createSessionFromClaims(claims, config, now);
  return new Response(null, {
    status: 302,
    headers: [
      ["Location", `${config.webBaseUrl}${transaction.returnTo}`],
      ["Set-Cookie", cookie(SESSION_COOKIE, session.id, { maxAge: session.expiresAt - now, secure: config.secureCookies })],
      ["Set-Cookie", cookie(OIDC_STATE_COOKIE, "", { maxAge: 0, secure: config.secureCookies })],
      ["Cache-Control", "no-store"],
    ],
  });
}

export function logout(request, { environment = process.env } = {}) {
  let secure = true;
  let baseUrl = new URL(request.url).origin;
  try {
    const config = authConfig(environment);
    secure = config.secureCookies;
    baseUrl = config.webBaseUrl;
  } catch {
    // Logout remains available during a configuration incident.
  }
  const id = cookieValue(request.headers.get("cookie"), SESSION_COOKIE);
  if (id) sessions.delete(id);
  return new Response(null, {
    status: 303,
    headers: {
      Location: `${baseUrl}/login`,
      "Set-Cookie": cookie(SESSION_COOKIE, "", { maxAge: 0, secure }),
      "Cache-Control": "no-store",
    },
  });
}

export function authErrorResponse(error) {
  const failure = error instanceof AuthError
    ? error
    : new AuthError("AUTHENTICATION_FAILED", "Authentication could not be completed.", 500);
  return Response.json(
    { error: { code: failure.code, message: failure.message } },
    { status: failure.status, headers: { "Cache-Control": "no-store" } },
  );
}

export function resetAuthStateForTests() {
  states.clear();
  sessions.clear();
  discoveryCache.clear();
}
