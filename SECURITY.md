# Security Policy

## Scope
This repository contains deployment policy, hardening scripts and governance for SOAiaCore. It must not contain production secrets, private message payloads, session cookies, OAuth tokens, API keys, raw restricted media or browser profiles.

## Security invariants
- Production application services do not run as root.
- Application ports remain loopback-only unless explicitly reverse-proxied.
- Secrets are server-side only and never placed in query strings.
- Messaging integrations default to `OBSERVE_ONLY=true`.
- Sensitive analysis requires approval where configured.
- Drafts never transition automatically to send/publish.
- External backups containing restricted material are encrypted before leaving the host.
- Every deployment must produce a receipt tied to host and Git commit.

## Credential exposure
If a credential appears in Git, chat, screenshot, URL, proxy log or browser history, treat it as exposed: revoke/rotate first, investigate second.

## Reporting
Open a private security channel/issue with no secret values or message payloads. Reference only hashes, timestamps, component names and sanitized evidence.

## Merge gate
Security-relevant changes remain in draft until syntax/static validation passes and target-host PRECHECK/receipt evidence is attached.
