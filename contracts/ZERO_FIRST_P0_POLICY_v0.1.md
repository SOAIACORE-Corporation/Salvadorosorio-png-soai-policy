# SOAIACORE ZERO_FIRST P0 Policy v0.1

1. Routine development requires no persistent billable cloud compute.
2. Azure integration spend must be bounded, attributable and pre-authorized.
3. Budgets are alerts, not hard caps.
4. Terraform allowlist + provider policy is the primary resource/SKU guard.
5. Every ephemeral deployment requires a real cleanup executor; tags alone do not count.
6. Model mode defaults to MOCK/REPLAY for routine development.
7. LIVE requires purpose + provider eligibility + explicit cost gate.
8. Observability defaults to MINIMAL; BENCHMARK is temporary.
9. Export receipts, benchmark outputs and cost summary before teardown.
10. Production environment is not created in P0.
