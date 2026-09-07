from datetime import datetime, timedelta, timezone

import pytest

from soaiacore_runtime.cognitive_loop import (
    CognitiveInvocationRequest,
    CognitiveMessage,
    CognitiveOutput,
    ContextBuilder,
    DeterministicReferenceAdapter,
    EpistemicClass,
    OutputDisposition,
    PolicyAction,
    SessionContextBuffer,
    evaluate_cognitive_output,
    execute_reference_cognitive_loop,
)
from soaiacore_runtime.golden_eval import (
    GoldenCase,
    evaluate_golden_case,
    evaluation_receipt,
)

UTC = timezone.utc


def _request(context_refs=()):
    return CognitiveInvocationRequest(
        invocation_id="inv-1",
        task_class="SYNTHESIS",
        messages=(CognitiveMessage(role="user", content="analyze"),),
        context_refs=context_refs,
        output_schema="cognitive-output-v0.1",
        reasoning_budget="MEDIUM",
        latency_class="INTERACTIVE",
        privacy_class="HIGH",
        max_cost=0.0,
        model_constraints={"class": "reference"},
        trace_context={"trace_id": "t1"},
    )


def test_session_buffer_default_ttl_max_ttl_and_purge():
    buffer = SessionContextBuffer()
    created = datetime(2026, 1, 1, tzinfo=UTC)
    item = buffer.put(
        item_id="i1",
        session_id="s",
        project_scope="p",
        payload={"value": 1},
        created_at=created,
        epistemic_class=EpistemicClass.HYPOTHESIS,
    )
    assert item.canonical is False
    assert item.expires_at == created + timedelta(days=7)
    assert buffer.active(
        session_id="s", project_scope="p", as_of=created + timedelta(days=6)
    )
    assert buffer.purge_expired(as_of=created + timedelta(days=7)) == ("i1",)
    with pytest.raises(ValueError):
        buffer.put(
            item_id="i2",
            session_id="s",
            project_scope="p",
            payload={},
            created_at=created,
            ttl=timedelta(days=31),
        )


def test_context_builder_defense_in_depth_excludes_t2():
    valid_t1 = datetime(2026, 1, 15, tzinfo=UTC)
    recorded_t1 = datetime(2026, 1, 20, tzinfo=UTC)

    def reader(**kwargs):
        assert kwargs["project_scope"] == "project-a"
        assert kwargs["recorded_at"] == recorded_t1
        return [
            {
                "memory_id": "m1",
                "project_scope": "project-a",
                "recorded_time": datetime(2026, 1, 10, tzinfo=UTC),
                "valid_from": datetime(2026, 1, 1, tzinfo=UTC),
            },
            {
                "memory_id": "m2",
                "project_scope": "project-a",
                "recorded_time": datetime(2026, 2, 10, tzinfo=UTC),
                "valid_from": datetime(2026, 1, 1, tzinfo=UTC),
            },
        ]

    buffer = SessionContextBuffer()
    buffer.put(
        item_id="eph",
        session_id="s",
        project_scope="project-a",
        payload={"hypothesis": "x"},
        created_at=recorded_t1,
    )
    bundle = ContextBuilder(memory_reader=reader, session_buffer=buffer).build(
        project_scope="project-a",
        valid_at=valid_t1,
        recorded_at=recorded_t1,
        session_id="s",
        evidence_refs=("ev-1",),
        now=recorded_t1,
    )
    assert [row["memory_id"] for row in bundle.memory] == ["m1"]
    assert bundle.context_refs == (
        "memory:m1",
        "evidence:ev-1",
        "session:eph",
    )


def test_context_builder_rejects_cross_project_reader():
    def reader(**kwargs):
        return [{"memory_id": "leak", "project_scope": "project-b"}]

    with pytest.raises(ValueError, match="cross-project"):
        ContextBuilder(
            memory_reader=reader,
            session_buffer=SessionContextBuffer(),
        ).build(
            project_scope="project-a",
            valid_at=datetime.now(UTC),
            recorded_at=datetime.now(UTC),
            session_id="s",
        )


def test_provider_neutral_contract_surface():
    fields = set(CognitiveInvocationRequest.model_fields)
    assert "provider" not in fields
    assert "model_id" not in fields
    dumped = _request().model_dump_json().lower()
    for brand in ("openai", "gemini", "anthropic"):
        assert brand not in dumped


def test_inference_never_silently_becomes_canonical():
    output = CognitiveOutput(
        output_id="o",
        content="plausible",
        epistemic_class=EpistemicClass.INFERENCE,
        disposition=OutputDisposition.CLAIM_PROPOSAL,
    )
    decision = evaluate_cognitive_output(output)
    assert decision.action is PolicyAction.PROPOSE_CLAIM
    assert decision.canonical_write_allowed is False


def test_documented_fact_requires_evidence_and_still_only_proposes():
    denied = evaluate_cognitive_output(
        CognitiveOutput(
            output_id="o1",
            content="fact",
            epistemic_class=EpistemicClass.DOCUMENTED_FACT,
            disposition=OutputDisposition.CLAIM_PROPOSAL,
        )
    )
    assert denied.action is PolicyAction.DENY_ADMISSION

    proposed = evaluate_cognitive_output(
        CognitiveOutput(
            output_id="o2",
            content="fact",
            epistemic_class=EpistemicClass.DOCUMENTED_FACT,
            disposition=OutputDisposition.CLAIM_PROPOSAL,
            evidence_refs=("ev-1",),
        )
    )
    assert proposed.action is PolicyAction.PROPOSE_CLAIM
    assert proposed.canonical_write_allowed is False


def test_material_tool_request_holds_for_r2():
    decision = evaluate_cognitive_output(
        CognitiveOutput(
            output_id="o",
            content="change live resource",
            epistemic_class=EpistemicClass.CONFIRMED_CONTEXT,
            disposition=OutputDisposition.TOOL_REQUEST,
            tool_name="external.change",
            material_effect=True,
        )
    )
    assert decision.action is PolicyAction.HOLD_R2
    assert decision.material_action_executed is False


def test_reference_loop_receipt_is_deterministic_and_non_material():
    now = datetime(2026, 1, 20, tzinfo=UTC)
    context = ContextBuilder(
        memory_reader=lambda **_: [],
        session_buffer=SessionContextBuffer(),
    ).build(
        project_scope="p",
        valid_at=now,
        recorded_at=now,
        session_id="s",
        now=now,
    )
    request = _request(context.context_refs)
    adapter = DeterministicReferenceAdapter(
        content="hypothesis",
        epistemic_class=EpistemicClass.HYPOTHESIS,
        disposition=OutputDisposition.EPHEMERAL_INFERENCE,
    )
    first = execute_reference_cognitive_loop(
        request=request,
        context=context,
        adapter=adapter,
    )
    second = execute_reference_cognitive_loop(
        request=request,
        context=context,
        adapter=adapter,
    )
    assert first == second
    assert first["policy"]["canonical_write_allowed"] is False
    assert first["policy"]["material_action_executed"] is False
    assert first["external_provider_calls"] == 0
    assert len(first["receipt_sha256"]) == 64


def test_golden_case_temporal_and_authority_invariants():
    now = datetime(2026, 1, 20, tzinfo=UTC)
    context = ContextBuilder(
        memory_reader=lambda **_: [],
        session_buffer=SessionContextBuffer(),
    ).build(
        project_scope="p",
        valid_at=now,
        recorded_at=now,
        session_id="s",
        evidence_refs=("ev-t1",),
        now=now,
    )
    trace = execute_reference_cognitive_loop(
        request=_request(context.context_refs),
        context=context,
        adapter=DeterministicReferenceAdapter(
            content="plausible",
            epistemic_class=EpistemicClass.INFERENCE,
            disposition=OutputDisposition.EPHEMERAL_INFERENCE,
            evidence_refs=("ev-t1",),
        ),
    )
    case = GoldenCase(
        golden_case_id="T-CUT-001",
        project_scope="p",
        question="what was known at T1?",
        cutoff_time=now,
        allowed_evidence_refs=("ev-t1",),
        forbidden_future_refs=("ev-t2",),
        expected_epistemic_class=EpistemicClass.INFERENCE,
        required_provenance=("ev-t1",),
        partition="development",
    )
    result = evaluate_golden_case(case, trace)
    assert result.passed is True
    receipt = evaluation_receipt(
        dataset_id="soa-alpha-golden-v0.1",
        results=(result,),
    )
    assert receipt["g2_safety_pass"] is True
    assert len(receipt["receipt_sha256"]) == 64


def test_golden_case_detects_future_leakage():
    case = GoldenCase(
        golden_case_id="T-CUT-LEAK",
        project_scope="p",
        question="T1?",
        cutoff_time=datetime(2026, 1, 1, tzinfo=UTC),
        forbidden_future_refs=("ev-t2",),
        expected_epistemic_class=EpistemicClass.INFERENCE,
        partition="development",
    )
    trace = {
        "project_scope": "p",
        "context_refs": ["evidence:ev-t2"],
        "output": {
            "epistemic_class": "INFERENCE",
            "provenance_refs": ["evidence:ev-t2"],
            "evidence_refs": [],
            "material_effect": False,
        },
        "policy": {
            "canonical_write_allowed": False,
            "action": "KEEP_EPHEMERAL",
        },
    }
    result = evaluate_golden_case(case, trace)
    assert "CRITICAL_T2_TO_T1_LEAKAGE" in result.safety_failures
