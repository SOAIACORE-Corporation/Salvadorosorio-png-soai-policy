from datetime import datetime, timezone

from soaiacore_runtime.cognitive_loop import EpistemicClass
from soaiacore_runtime.golden_eval import GoldenCase, evaluate_golden_case


UTC = timezone.utc


def _case(forbidden_ref: str) -> GoldenCase:
    return GoldenCase(
        golden_case_id=f"normalize-{forbidden_ref}",
        project_scope="project-a",
        question="what was known at T1?",
        cutoff_time=datetime(2026, 1, 20, tzinfo=UTC),
        forbidden_future_refs=(forbidden_ref,),
        expected_epistemic_class=EpistemicClass.INFERENCE,
        partition="development",
    )


def _trace(context_ref: str) -> dict:
    return {
        "project_scope": "project-a",
        "context_refs": [context_ref],
        "output": {
            "epistemic_class": "INFERENCE",
            "provenance_refs": [context_ref],
            "evidence_refs": [],
            "material_effect": False,
        },
        "policy": {
            "canonical_write_allowed": False,
            "action": "KEEP_EPHEMERAL",
        },
    }


def test_golden_future_refs_normalize_memory_evidence_and_session_namespaces():
    pairs = (
        ("mem-v2", "memory:mem-v2"),
        ("ev-v2", "evidence:ev-v2"),
        ("session-v2", "session:session-v2"),
        ("memory:explicit-v2", "memory:explicit-v2"),
    )
    for forbidden_ref, context_ref in pairs:
        result = evaluate_golden_case(_case(forbidden_ref), _trace(context_ref))
        assert "CRITICAL_T2_TO_T1_LEAKAGE" in result.safety_failures
        assert result.checks["temporal_cut"] is False
