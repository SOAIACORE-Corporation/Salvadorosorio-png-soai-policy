# ADR: P0 local Terraform state exception

- Status: Accepted
- Decision date: 2026-08-24
- Scope: P0 only
- Environment class: Internal engineering pilot
- Risk acceptance: Explicit
- Production pattern: False

## Decision

`P0_TERRAFORM_LOCAL_STATE=AUTHORIZED_EXCEPTION`.

A dedicated or protected remote Terraform backend is not required for this P0
pilot and must not block P0. This exception does not authorize creation of a
dedicated Azure backend or reuse of Cloud Shell as a backend.

`REMOTE_BACKEND_REQUIRED_BEFORE_PRODUCTION=true`. The exception expires with
the P0 lifecycle and must not be carried into production or any broader rollout.

## Compensating controls

1. Keep `terraform.tfstate*` and other `*.tfstate*` files outside Git.
2. Verify before apply that no Terraform state file has ever been tracked in
   the repository history.
3. Never print state, passwords, connection strings, or secrets in logs,
   receipts, or documentation.
4. Restrict local state access to the authorized operator and workstation.
5. Retain local state only for the P0 lifecycle.
6. At teardown, sanitize or securely remove sensitive state when it is no
   longer required.
7. Record this accepted exception in the P0 pre-apply receipt and deployment
   evidence.

## Guardrails

- No mass production deployment.
- No live providers.
- No Architecture v0.7 work.
- The remaining pre-apply blocker is anonymous public read of the three
  approved GHCR packages at their exact approved digests.
