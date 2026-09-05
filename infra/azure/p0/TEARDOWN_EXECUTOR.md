# Governed P0 teardown executor

`Invoke-P0GovernedTeardown.ps1` implements the cleanup control tracked by #47 without authorizing teardown by itself.

## Safety model

- Default mode is `PlanOnly`.
- Scope is pinned to subscription `108eb4dd-25b3-4a7f-8d5e-4ec4389c3f0d` and pilot resource group `rg-soaiacore-p0-34utxi`.
- The state backend resource group `rg-soaiacore-tfstate-34utxi` is verified separately and is never the teardown target.
- Execution requires a sanitized #38 authority receipt proving `remote_backend_initialized=true/PASS`, `plan_no_destroy_verified=true/PASS`, and `config_state_reconciled=true/PASS`.
- There is no direct `terraform destroy` path.
- Every AzureRM delete in a saved plan must resolve inside the exact pinned P0 resource-group scope; state-backend or out-of-scope deletes fail closed.
- `ApplyReviewedPlan` requires the exact reviewed SHA-256, literal adjudication token `APPLY_REVIEWED_P0_DESTROY_PLAN`, named authority `Salvador Osorio Ayala`, and an external authorization evidence reference.

## Artifact namespace hardening

Raw plans and plan JSON are sensitive. The executor therefore uses a single canonical artifact namespace:

`<operator-home>/.soaiacore-governed-artifacts/p0-teardown-evidence`

Custom `-ArtifactRoot` locations are disabled; if supplied, the value must resolve exactly to that canonical root.

Before any artifact is trusted or staged, the executor:

1. verifies the operator home is owned by the current operator and is not writable/delete-controllable by another untrusted principal;
2. rejects symlink, junction and filesystem reparse-point components fail-closed;
3. creates and restricts the governed parent and canonical artifact root to the current operator;
4. verifies every ancestor from the artifact root back to the operator home is operator-owned and not writable by other principals;
5. rejects the complete Git worktree as an artifact destination;
6. creates every child directory with timestamp + GUID collision resistance and refuses reuse.

Windows uses inheritance-protected current-user-only ACLs for governed artifact directories. Non-Windows hosts use `chmod 700` on directories and `chmod 600` on files, plus owner/mode checks on the full ancestor chain.

## Reviewed-plan TOCTOU control

For `ApplyReviewedPlan`, the caller-supplied plan is a staging source only. It is copied exactly once into a newly allocated canonical owner-only child. After staging:

- the original source variables are nulled and never reopened;
- SHA-256 verification runs only on the staged copy;
- `terraform show -json` and scope validation run only on the staged copy;
- an immediate pre-apply SHA-256 check re-verifies the same staged artifact;
- any eventual `terraform apply` can target only that staged path.

This executor does not itself authorize destructive execution.

## Current authorization

#46 is CLOSED with `CONTROLLED_EXTENSION` authorized through `2026-09-20T05:59:59Z` and cumulative P0 cost ceiling `USD 10.00`.

The current lifecycle envelope does **not** authorize teardown, production, LIVE-provider promotion or destructive execution. #47 authorizes implementation and static validation of the cleanup control only.

Do not run `PlanOnly` unless the required backend/config-state authority receipt is truthful and complete. Do not run `ApplyReviewedPlan` unless a future explicit teardown disposition exists and the exact saved-plan SHA has been separately reviewed and formally adjudicated by Salvador Osorio Ayala.
