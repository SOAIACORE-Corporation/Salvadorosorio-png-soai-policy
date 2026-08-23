# ReviewPolicy Contract v0.1

Returns exactly one mode: `NONE`, `OPTIONAL`, or `REQUIRED`.

Inputs may include:
- AnalysisProfile;
- purpose;
- sensitivity;
- identity uncertainty;
- methodology-specific gates;
- downstream consequence;
- authorization tier.

Rules:
1. Automated validation is universal for governed outputs.
2. Human review is conditional, never a universal validity requirement.
3. `REQUIRED` blocks governed downstream use until protocol completion.
4. The decision and reason codes are written to the ContextReceipt.
