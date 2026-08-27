# P1 OIDC, session and RBAC gate

Issue: #18
Classification: `SECURITY_GATE / IMPLEMENTATION_DECISION`

## Decision

The controlled pilot authenticates operators at the Web boundary with OIDC Authorization Code + PKCE. Web retains an opaque session identifier in a `Secure`, `HttpOnly`, `SameSite=Lax` cookie and stores the session record server-side. OIDC access tokens, ID tokens, provider subjects, email addresses and client secrets are not retained in the session or returned to the browser.

Web derives a stable pseudonymous `operator_id` from the OIDC issuer and subject. Each Web-to-Core `/v1/*` request carries that identifier, the mapped role, a correlation ID and a short-lived HMAC signature covering the HTTP method, path/query and request-body digest. Core rejects missing, expired, malformed, tampered or unauthorized contexts before entering a product handler. Health endpoints remain available without operator credentials.

This preserves the existing browser → Web/BFF → Core boundary. The browser never receives Core, PostgreSQL or Blob credentials and cannot construct the internal signature.

## Minimal roles

- `OPERATOR`: may enter the portal and execute the approved MOCK pilot flow.
- `ADMIN`: includes operator access and is accepted by the reusable ADMIN-only guard.
- `REVIEWER`: not introduced because the current pilot ReviewPolicy does not require an interactive reviewer role.

There are currently no administrative mutation screens. Any future ADMIN-only route must call the existing role guard and include a negative OPERATOR test.

## Required runtime configuration

All values are server-side. Secret values must come from the approved deployment secret source and must never be committed.

| Variable | Purpose |
|---|---|
| `SOAIACORE_OIDC_ISSUER` | Exact HTTPS OIDC issuer URL |
| `SOAIACORE_OIDC_CLIENT_ID` | Confidential Web client identifier |
| `SOAIACORE_OIDC_CLIENT_SECRET` | Confidential Web client secret |
| `SOAIACORE_WEB_BASE_URL` | Canonical HTTPS Web origin used for the redirect URI |
| `SOAIACORE_OIDC_OPERATOR_GROUP` | Role/group value mapped to `OPERATOR`; default `SOAIACORE_OPERATOR` |
| `SOAIACORE_OIDC_ADMIN_GROUP` | Role/group value mapped to `ADMIN`; default `SOAIACORE_ADMIN` |
| `SOAIACORE_SESSION_TTL_SECONDS` | Maximum session lifetime; default 28,800 seconds |
| `SOAIACORE_INTERNAL_AUTH_SECRET` | At least 32-byte shared secret mounted independently in Web and Core |
| `SOAIACORE_INTERNAL_AUTH_REQUIRED` | Core fail-closed switch; defaults to `true` from environment |

The registered redirect URI is `${SOAIACORE_WEB_BASE_URL}/api/auth/callback`. Insecure HTTP is always rejected by runtime configuration validation.

## Session and deployment constraint

The minimal pilot session store is process-local and intentionally bounded to the existing Web scale of zero-to-one replica. A restart expires all sessions safely. Horizontal Web scaling requires a shared encrypted session store and belongs to production hardening (#19); do not increase Web above one replica before that control exists.

## Public and protected routes

- Public: `/login`, `/forbidden`, `/api/auth/*`, `/api/health/live`, `/api/health/ready`.
- Protected: the portal, workflow, runs, receipts, context/evidence views and every `/api/operator/*` or `/api/runs/*` BFF route.
- Core: every `/v1/*` route requires signed operator context when the default environment configuration is used.

## Acceptance evidence

Automated tests cover OIDC discovery, Authorization Code + PKCE, RS256 verification, role mapping, opaque session creation/expiry, unsafe redirect rejection, ADMIN enforcement, Web-to-Core signing, missing/tampered/expired context rejection and secret non-disclosure. The existing MOCK lifecycle and BFF regression suites remain required.

No Architecture v0.7 change is required.
