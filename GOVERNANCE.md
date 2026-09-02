# Repository Governance

**Status:** CANONICAL REFERENCE · ACTIVE

This repository follows the SOAiaCore GitHub governance and technical-hygiene policy maintained in:

`SOAIACORE-Corporation/policy-continuidad/policies/GITHUB_GOVERNANCE_HYGIENE.md`

The policy governs evidence-state clarity, document canonicality, branch and pull-request hygiene, secret handling, Terraform state/plan discipline, public metadata, review closure, deviations, and minimum receipts.

Repository-specific controls may be stricter. Where this repository's architecture, security contracts, validation gates, or runbooks impose a stricter requirement, the stricter requirement governs.

## Required operating pattern

Material changes should follow:

`CONTEXT → SYNC → PRECHECK → EXECUTE / CHANGE → VALIDATE → RECEIPT`

Automation and gates provide evidence and control. Human adjudication remains authoritative; an exception must be recorded rather than misrepresented as a passed gate.

## Infrastructure rule

For Terraform-managed Azure changes, configuration or static validation is not equivalent to runtime evidence. A cloud state may be called VERIFIED only after the authorized backend, saved plan/apply where applicable, runtime validation, and receipt exist.