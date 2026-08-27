import assert from "node:assert/strict";
import { createSign, generateKeyPairSync } from "node:crypto";
import test from "node:test";

import {
  AuthError,
  SESSION_COOKIE,
  beginOidcLogin,
  completeOidcLogin,
  createSessionFromClaims,
  logout,
  requireRole,
  requireSession,
  resetAuthStateForTests,
  roleFromClaims,
  safeReturnTo,
  safeSession,
  sessionById,
} from "../src/server/auth.mjs";
import { coreRequest } from "../src/server/core-client.mjs";
import { withOperatorContext } from "../src/server/operator-context.mjs";

const config = {
  issuer: "https://login.example.test/tenant/v2.0",
  clientId: "pilot-client",
  operatorGroup: "SOAIACORE_OPERATOR",
  adminGroup: "SOAIACORE_ADMIN",
  sessionTtlSeconds: 3_600,
};

test.beforeEach(() => resetAuthStateForTests());

test("OIDC role mapping admits OPERATOR and ADMIN only", () => {
  assert.equal(roleFromClaims({ roles: ["SOAIACORE_OPERATOR"] }, config), "OPERATOR");
  assert.equal(roleFromClaims({ groups: ["SOAIACORE_ADMIN"] }, config), "ADMIN");
  assert.throws(
    () => roleFromClaims({ roles: ["READER"] }, config),
    (error) => error instanceof AuthError && error.code === "OPERATOR_ROLE_FORBIDDEN",
  );
});

test("opaque server-side session authenticates, expires, and exposes no identity token", () => {
  const now = Math.floor(Date.now() / 1000);
  const session = createSessionFromClaims(
    {
      iss: config.issuer,
      sub: "sensitive-provider-subject",
      exp: now + 10_000,
      roles: ["SOAIACORE_OPERATOR"],
      email: "operator@example.test",
      access_token: "must-never-be-stored",
    },
    config,
    now,
  );
  const request = new Request("https://pilot.example.test/api/operator/workflow", {
    headers: { Cookie: `${SESSION_COOKIE}=${encodeURIComponent(session.id)}` },
  });
  assert.equal(requireSession(request).operatorId, session.operatorId);
  assert.deepEqual(Object.keys(safeSession(session)).sort(), ["expires_at", "operator_id", "role"]);
  assert.equal(JSON.stringify(session).includes("sensitive-provider-subject"), false);
  assert.equal(JSON.stringify(session).includes("must-never-be-stored"), false);
  assert.equal(sessionById(session.id, session.expiresAt), null);
});

test("ADMIN-only guard rejects OPERATOR and permits ADMIN", () => {
  assert.throws(
    () => requireRole({ role: "OPERATOR" }, "ADMIN"),
    (error) => error instanceof AuthError && error.code === "ADMIN_ROLE_REQUIRED",
  );
  assert.equal(requireRole({ role: "ADMIN" }, "ADMIN").role, "ADMIN");
});

test("authenticated OPERATOR context reaches Core through the signed BFF boundary", async () => {
  const now = Math.floor(Date.now() / 1000);
  const session = createSessionFromClaims(
    { iss: config.issuer, sub: "operator-flow", exp: now + 600, roles: [config.operatorGroup] },
    config,
    now,
  );
  let captured;
  const result = await withOperatorContext(session, () =>
    coreRequest("/v1/runs/run_test", {
      environment: {
        CORE_API_BASE_URL: "https://core.internal",
        SOAIACORE_INTERNAL_AUTH_SECRET: "test-only-internal-auth-secret-32-bytes-minimum",
      },
      fetchImpl: async (url, options) => {
        captured = { url, options };
        return Response.json({ run_id: "run_test", status: "COMPLETED", mode: "MOCK" });
      },
    }),
  );
  assert.equal(result.mode, "MOCK");
  assert.equal(captured.options.headers["X-SOAIA-Operator-ID"], session.operatorId);
  assert.equal(captured.options.headers["X-SOAIA-Operator-Role"], "OPERATOR");
});

test("logout revokes the server-side session and expires the browser cookie", () => {
  const now = Math.floor(Date.now() / 1000);
  const session = createSessionFromClaims(
    { iss: config.issuer, sub: "logout-flow", exp: now + 600, roles: [config.operatorGroup] },
    config,
    now,
  );
  const environment = {
    SOAIACORE_OIDC_ISSUER: config.issuer,
    SOAIACORE_OIDC_CLIENT_ID: config.clientId,
    SOAIACORE_OIDC_CLIENT_SECRET: "client-secret",
    SOAIACORE_WEB_BASE_URL: "https://pilot.example.test",
  };
  const response = logout(
    new Request("https://pilot.example.test/api/auth/logout", {
      method: "POST",
      headers: { Cookie: `${SESSION_COOKIE}=${session.id}` },
    }),
    { environment },
  );
  assert.equal(response.status, 303);
  assert.match(response.headers.get("set-cookie"), /Max-Age=0/);
  assert.equal(sessionById(session.id), null);
});

test("unauthenticated requests and unsafe post-login redirects are rejected", () => {
  const request = new Request("https://pilot.example.test/api/operator/workflow");
  assert.throws(
    () => requireSession(request),
    (error) => error instanceof AuthError && error.code === "AUTHENTICATION_REQUIRED",
  );
  assert.equal(safeReturnTo("https://attacker.example/"), "/");
  assert.equal(safeReturnTo("//attacker.example/"), "/");
  assert.equal(safeReturnTo("/workflow"), "/workflow");
});

test("OIDC authorization-code flow validates RS256, PKCE transaction, and creates opaque cookie", async () => {
  const { privateKey, publicKey } = generateKeyPairSync("rsa", { modulusLength: 2048 });
  const jwk = publicKey.export({ format: "jwk" });
  jwk.kid = "pilot-key";
  jwk.alg = "RS256";
  jwk.use = "sig";
  const environment = {
    SOAIACORE_OIDC_ISSUER: config.issuer,
    SOAIACORE_OIDC_CLIENT_ID: config.clientId,
    SOAIACORE_OIDC_CLIENT_SECRET: "oidc-client-secret-never-in-browser",
    SOAIACORE_WEB_BASE_URL: "https://pilot.example.test",
    SOAIACORE_OIDC_OPERATOR_GROUP: config.operatorGroup,
  };
  const metadata = {
    issuer: config.issuer,
    authorization_endpoint: `${config.issuer}/authorize`,
    token_endpoint: `${config.issuer}/token`,
    jwks_uri: `${config.issuer}/keys`,
  };
  let idToken;
  const fetchImpl = async (url, options = {}) => {
    if (url.endsWith("/.well-known/openid-configuration")) return Response.json(metadata);
    if (url === metadata.token_endpoint) {
      assert.equal(options.body.get("client_secret"), environment.SOAIACORE_OIDC_CLIENT_SECRET);
      assert.ok(options.body.get("code_verifier"));
      return Response.json({ id_token: idToken });
    }
    if (url === metadata.jwks_uri) return Response.json({ keys: [jwk] });
    throw new Error(`Unexpected request: ${url}`);
  };
  const start = await beginOidcLogin(
    new Request("https://pilot.example.test/api/auth/login?return_to=/workflow"),
    { environment, fetchImpl },
  );
  const authorization = new URL(start.headers.get("location"));
  const state = authorization.searchParams.get("state");
  const nonce = authorization.searchParams.get("nonce");
  const header = base64urlJson({ alg: "RS256", kid: jwk.kid, typ: "JWT" });
  const claims = base64urlJson({
    iss: config.issuer,
    sub: "provider-subject",
    aud: config.clientId,
    exp: Math.floor(Date.now() / 1000) + 600,
    nonce,
    roles: [config.operatorGroup],
  });
  const signer = createSign("RSA-SHA256");
  signer.update(`${header}.${claims}`);
  signer.end();
  idToken = `${header}.${claims}.${signer.sign(privateKey).toString("base64url")}`;
  const stateCookie = start.headers.get("set-cookie").split(";")[0];
  const callback = await completeOidcLogin(
    new Request(`https://pilot.example.test/api/auth/callback?code=code-1&state=${state}`, {
      headers: { Cookie: stateCookie },
    }),
    { environment, fetchImpl },
  );
  const setCookie = callback.headers.get("set-cookie");
  assert.equal(callback.status, 302);
  assert.equal(callback.headers.get("location"), "https://pilot.example.test/workflow");
  assert.match(setCookie, /HttpOnly/);
  assert.match(setCookie, /Secure/);
  assert.equal(setCookie.includes(environment.SOAIACORE_OIDC_CLIENT_SECRET), false);
  const sessionCookie = setCookie.match(/__Host-soaiacore_session=([^;,]+)/)?.[0];
  assert.ok(sessionCookie);
  const session = requireSession(
    new Request("https://pilot.example.test/api/operator/workflow", {
      headers: { Cookie: sessionCookie },
    }),
  );
  assert.equal(session.role, "OPERATOR");
});

function base64urlJson(value) {
  return Buffer.from(JSON.stringify(value)).toString("base64url");
}
