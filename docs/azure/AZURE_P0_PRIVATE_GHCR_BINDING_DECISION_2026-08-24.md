# Azure binding / P0 implementation decision: private GHCR pulls

- Status: Accepted, applied, and cloud-validated
- Decision date: 2026-08-24
- Architecture: v0.6 FINAL/FROZEN (unchanged)
- Scope: P0 internal engineering pilot only

## Decision

Keep `soaiacore-core`, `soaiacore-web`, and `soaiacore-worker` private in GHCR.
Anonymous pull is not a P0 requirement. Azure Container Apps Core/Web and the
Worker job authenticate directly to `ghcr.io` with registry username/password
binding, where the password reference targets an Azure Container Apps secret.

The credential is a short-lived GitHub personal access token (classic) limited
to `read:packages`; its owner must have read access to all three packages. This
is an Azure binding implementation decision and does not change Architecture
v0.6. No Azure Container Registry is created.

## Immutable image bindings

- Core: `ghcr.io/soaiacore-corporation/soaiacore-core@sha256:e6564cad60afa7f7e1828c193c3512c7f1b0ce53aed26459e0a61b8ac33fb467`
- Web: `ghcr.io/soaiacore-corporation/soaiacore-web@sha256:da26fd8bcf6cb2a4c242d380a28c682b19c6f094f0a898258a727ef558fa6c58`
- Worker: `ghcr.io/soaiacore-corporation/soaiacore-worker@sha256:971dc02fd1ba2306cd6e1d4864e8d7de0d447169256f7d89071bc5c94ccde9a1`

Tags, including `:latest`, are rejected by Terraform input validation for these
three variables.

## Secret handling

1. Supply `ghcr_token` only through `TF_VAR_ghcr_token` or an ignored,
   access-restricted `.tfvars` file. Never pass it as a command-line argument.
2. Mark the Terraform input `sensitive`; do not output it or include it in
   logs, receipts, documentation, images, or source control.
3. Store it in Azure as a Container Apps secret named `ghcr-pull-token`; registry
   blocks reference the secret name and never the token value.
4. AzureRM Container App/Job secret values are persisted in Terraform state.
   The approved P0 local-state exception therefore applies: restrict access to
   the operator, keep state/plan files outside Git, retain them only for the P0
   lifecycle, and sanitize them after teardown.
5. Revoke the PAT after P0 teardown or earlier if the pilot no longer requires
   image pulls.

## Plan and cost impact

The binding adds one secret and one `ghcr.io` registry block to each of the two
Container Apps and the Worker job. It creates no additional Terraform or Azure
resource, so an empty-state plan remains 24 add, 0 change, 0 destroy. Azure
Container Apps secrets and registry bindings have no separate resource charge;
the established USD 3.82-20.28 / 168h envelope is unchanged.

## Applied P0 implementation

Azure validated authenticated pulls for all three immutable digests. Core, Web,
and Worker each retain a private `ghcr.io` registry binding; no package was made
public and no ACR was created.

Two non-secret runtime bindings were required after the first cloud start:

- Core and Worker set `PYTHONPATH=/app/.venv/lib/python3.12/site-packages` so the
  approved Python images can resolve their installed packages without changing
  or rebuilding either digest.
- Web uses the stable internal Core ingress FQDN rather than a revision-specific
  FQDN, so an in-place Core revision does not break the Web-to-Core binding.

These are Azure binding corrections for P0. They do not change Architecture
v0.6, enable LIVE providers, create production capacity, or alter an OCI digest.
The applied and cloud-validation evidence is recorded in
`receipts/P0_AZURE_APPLY_E2E_OBSERVATION_2026-08-25.json`.
