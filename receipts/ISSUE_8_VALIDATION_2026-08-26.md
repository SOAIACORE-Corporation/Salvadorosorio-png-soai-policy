# SOAIACORE Issue #8 Validation Receipt

- ISSUE_8_STATUS: `PASS`
- ISSUE: `#8 · P1-01 Core read/query surface for internal product flows`
- BRANCH: `rebuild/p0-06a-runtime`
- COMMIT_BASELINE: `a9fa2c6782ce935943fe16df2fceff9dfb680c9c`
- RECORDED_UTC: `2026-08-26T20:53:48.8453102Z`

## Implemented surface

- Added bounded, deterministically ordered read/query endpoints for Projects, Corpora,
  Contexts, ContextCapsules, AnalysisProfiles, Evidence metadata, and Run history.
- Added positive, not-found, invalid-filter, sanitization, OpenAPI, and filter tests.
- Recursively removed credentials, sensitive metadata keys, URI userinfo, query strings,
  and fragments from read responses.
- Corrected Run history to use the canonical `started_at` column.
- Applied `corpus_id` filtering when `project_id` is omitted.

## Local PostgreSQL/pgvector gate

- POSTGRESQL_RUNTIME: `PASS` — PostgreSQL 17.11; healthy container reused on host port 5432.
- PGVECTOR: `PASS` — extension `vector=0.8.6`.
- MIGRATIONS: `PASS` — 8/8 registered and verified (`0001` through `0008`).
- Migration mechanism: `soaiacore_runtime.migrations.apply_migrations` and
  `verify_migrations`, invoked by the worker migrate/precheck commands and acceptance fixture.
- POSTGRESQL_ACCEPTANCE_STATUS: `PASS` — `tests/acceptance/test_runtime_acceptance.py`: 26 passed.
- Minimal regression: `PASS` — `tests/test_container_runtime_contracts.py`: 2 passed.
- Web sub-suite: `PASS` — `npm test`: 3 passed.

## Required receipt fields

- POST_FIX_RUNTIME_SUITE: `PASS`
- TESTS_TOTAL: `28` (26 acceptance + 2 minimal regression)
- PASS: `28`
- FAIL: `0`
- SKIPPED: `0`
- BLOCKED: `0`
- FILES_CHANGED_THIS_EXECUTION: `0` (worktree status was unchanged by validation)
- FINAL_DIFF_STAT: `3` tracked files with textual diff; `429 insertions, 5 deletions`; `git diff --check=PASS`.
- ARCHITECTURE_CHANGE_REQUIRED: `NO`
- SECURITY_REGRESSION: `NONE` (sanitization and secret-leak checks passed)
- READY_FOR_COMMIT: `YES`
- BLOCKER: `NONE` — the Compose start error was a duplicate bind on port 5432; the existing healthy PostgreSQL instance was reused.
- NEXT_ACTION: `Review the diff and commit when authorized; do not push until explicitly requested.`

No Azure, Terraform, GHCR, Issue #9, or historical 2026-08-23 receipts were changed.
No commit or push was performed.
