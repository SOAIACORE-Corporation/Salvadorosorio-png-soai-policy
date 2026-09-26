# SCN-027 · Source outcome is not evidence quality

A completed CI run reports failure, while its metadata, timestamp and result are fully retrievable.

Expected:
- Treat the CI record as valid durable evidence of a failed validation.
- Preserve `source_outcome=failure`.
- Do not degrade evidence quality merely because the observed outcome is undesirable.
- An in-progress or incomplete CI record may be PARTIAL.
- Requirement binding must be explicit; source type alone must not invent authority or causal meaning.

Status: ACTIVE / TESTED by `schemas/tests/test_landscape_durable_evidence_adapters.py`.
