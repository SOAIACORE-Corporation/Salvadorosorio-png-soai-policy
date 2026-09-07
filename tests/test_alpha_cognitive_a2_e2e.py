from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from soaiacore_runtime.a2_context import A2CanonicalMemoryReader
from soaiacore_runtime.a2_persistence import apply_a2_persistence
from soaiacore_runtime.cognitive_loop import (
    CognitiveInvocationRequest,
    CognitiveMessage,
    ContextBuilder,
    DeterministicReferenceAdapter,
    EpistemicClass,
    OutputDisposition,
    SessionContextBuffer,
    execute_reference_cognitive_loop,
)
from soaiacore_runtime.golden_eval import GoldenCase, evaluate_golden_case, evaluation_receipt


ROOT = Path(__file__).resolve().parents[1]
UTC = timezone.utc


def _truncate_a2(database) -> None:
    with database.connect(autocommit=True) as connection:
        connection.execute(
            "TRUNCATE soa_memory.memory_claim_lineage, soa_memory.canonical_memory, "
            "soa_memory.episodic_temporal_memory, soa_memory.operational_state, "
            "soa_decision.decision_ledger RESTART IDENTITY CASCADE",
            prepare=False,
        )


def _request(context_refs: tuple[str, ...]) -> CognitiveInvocationRequest:
    return CognitiveInvocationRequest(
        invocation_id="g1-a2-e2e",
        task_class="SYNTHESIS",
        messages=(CognitiveMessage(role="user", content="what was known at T1?"),),
        context_refs=context_refs,
        output_schema="cognitive-output-v0.1",
        reasoning_budget="MEDIUM",
        latency_class="INTERACTIVE",
        privacy_class="HIGH",
        max_cost=0.0,
        model_constraints={"class": "reference"},
        trace_context={"trace_id": "g1-a2-e2e"},
    )


def test_context_builder_reads_real_a2_bitemporal_state_without_t2_or_cross_project_leak(database):
    apply_a2_persistence(
        database,
        base_migration_dir=ROOT / "db" / "migrations",
        a2_migration_dir=ROOT / "db" / "a2_migrations",
    )
    _truncate_a2(database)

    try:
        with database.connect(autocommit=True) as connection:
            connection.execute(
                """
                INSERT INTO soa_memory.canonical_memory(
                  memory_id,logical_memory_id,version_no,project_scope,content,
                  epistemic_class,admission_state,observed_time,recorded_time,valid_from
                ) VALUES
                  ('mem-a-t1','logical-a',1,'project-a','{"value":"T1"}'::jsonb,
                   'DOCUMENTED_FACT','ADMITTED','2026-01-01Z','2026-01-10Z','2026-01-01Z'),
                  ('mem-a-t2','logical-a',2,'project-a','{"value":"T2"}'::jsonb,
                   'DOCUMENTED_FACT','ADMITTED','2026-02-01Z','2026-02-10Z','2026-01-01Z'),
                  ('mem-b-t1','logical-b',1,'project-b','{"value":"OTHER_PROJECT"}'::jsonb,
                   'DOCUMENTED_FACT','ADMITTED','2026-01-01Z','2026-01-10Z','2026-01-01Z')
                """,
                prepare=False,
            )

        valid_t1 = datetime(2026, 1, 15, tzinfo=UTC)
        recorded_t1 = datetime(2026, 1, 20, tzinfo=UTC)
        builder = ContextBuilder(
            memory_reader=A2CanonicalMemoryReader(database),
            session_buffer=SessionContextBuffer(),
        )
        context = builder.build(
            project_scope="project-a",
            valid_at=valid_t1,
            recorded_at=recorded_t1,
            session_id="g1",
            now=recorded_t1,
        )

        assert [row["memory_id"] for row in context.memory] == ["mem-a-t1"]
        assert "memory:mem-a-t2" not in context.context_refs
        assert "memory:mem-b-t1" not in context.context_refs

        trace = execute_reference_cognitive_loop(
            request=_request(context.context_refs),
            context=context,
            adapter=DeterministicReferenceAdapter(
                content="T1 is the only admissible situated memory.",
                epistemic_class=EpistemicClass.INFERENCE,
                disposition=OutputDisposition.EPHEMERAL_INFERENCE,
            ),
        )
        case = GoldenCase(
            golden_case_id="G1-T-CUT-A2-001",
            project_scope="project-a",
            question="what was known at T1?",
            cutoff_time=recorded_t1,
            forbidden_future_refs=("mem-a-t2", "mem-b-t1"),
            expected_epistemic_class=EpistemicClass.INFERENCE,
            required_provenance=("memory:mem-a-t1",),
            partition="validation",
        )
        result = evaluate_golden_case(case, trace)
        assert result.passed is True
        assert result.safety_failures == ()
        assert result.checks["temporal_cut"] is True
        assert result.checks["project_scope"] is True

        receipt = evaluation_receipt(dataset_id="soa-alpha-g1-a2-e2e-v0.1", results=(result,))
        assert receipt["g2_safety_pass"] is True
        assert receipt["passed_cases"] == 1
        assert len(receipt["receipt_sha256"]) == 64

        deliberate_leak = {**trace, "context_refs": [*trace["context_refs"], "memory:mem-a-t2"]}
        leak_result = evaluate_golden_case(case, deliberate_leak)
        assert "CRITICAL_T2_TO_T1_LEAKAGE" in leak_result.safety_failures
    finally:
        _truncate_a2(database)
