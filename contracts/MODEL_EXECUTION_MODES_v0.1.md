# Model Execution Modes v0.1

## MOCK
No provider call. Deterministic fixtures.

## REPLAY
Reuse captured output keyed by:
- model_id
- model_version
- AnalysisProfile version
- prompt/input hash
- toolset hash
- response hash
- capture time

## LIVE
Real provider call. Requires explicit purpose, provider eligibility and cost gate.

Default development mode: MOCK or REPLAY.
