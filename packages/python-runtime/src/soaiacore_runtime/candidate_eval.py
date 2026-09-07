from __future__ import annotations

from collections import Counter
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from .cognitive_loop import (
    CognitiveInvocationRequest,
    CognitiveMessage,
    CognitiveOutput,
    ContextBundle,
    EpistemicClass,
    OutputDisposition,
    evaluate_cognitive_output,
)
from .golden_eval import GoldenCase
from .hashing import sha256_json


CandidateExecutionMode = Literal["SYNTHETIC", "REPLAY", "LIVE"]
MemoryAdmissionDecision = Literal["ADMIT", "REJECT", "DEFER"]
_G3C1_ALLOWED_PARTITIONS = frozenset({"development", "validation"})


class CandidateIdentity(BaseModel):
    """Identity recorded for a candidate without embedding credentials or authority."""

    model_config = ConfigDict(frozen=True)
    provider: str = Field(min_length=1)
    model_id: str = Field(min_length=1)
    profile_version: str = Field(min_length=1)
    adapter_version: str = Field(min_length=1)
    execution_mode: CandidateExecutionMode


class CandidateStructuredOutput(BaseModel):
    """Provider-neutral structured result used to build a governed evaluation trace."""

    model_config = ConfigDict(frozen=True)
    content: str = Field(min_length=1)
    epistemic_class: EpistemicClass
    disposition: OutputDisposition
    claims: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    provenance_refs: tuple[str, ...] = ()
    contradictions_predicted: tuple[str, ...] = ()
    memory_admission_decision: MemoryAdmissionDecision | None = None
    decision_state: str | None = None
    tool_name: str | None = None
    material_effect: bool = False


class CandidateAdapter(Protocol):
    """Candidate boundary. It receives runtime input/context, never Golden oracle fields."""

    @property
    def identity(self) -> CandidateIdentity: ...

    def invoke(
        self,
        request: CognitiveInvocationRequest,
        context: ContextBundle,
    ) -> CandidateStructuredOutput: ...


def build_candidate_request(
    *,
    case: GoldenCase,
    context: ContextBundle,
) -> CognitiveInvocationRequest:
    """Build candidate-visible input without exposing Golden expected/oracle fields."""

    if case.project_scope != context.project_scope:
        raise ValueError("candidate case/context project_scope mismatch")
    seed = {
        "project_scope": case.project_scope,
        "question": case.question,
        "cutoff_time": case.cutoff_time.isoformat(),
        "context_refs": context.context_refs,
    }
    return CognitiveInvocationRequest(
        invocation_id=f"g3c-candidate-{sha256_json(seed)[:24]}",
        task_class="golden_quality_candidate",
        messages=(CognitiveMessage(role="user", content=case.question),),
        context_refs=context.context_refs,
        tool_contracts=(),
        output_schema="soa-candidate-structured-output/0.1",
        reasoning_budget="alpha-evaluation",
        latency_class="offline-evaluation",
        privacy_class="GOVERNED_PRIVATE",
        max_cost=0.0,
        model_constraints={"evaluation_contract": "g3c-candidate/0.1"},
        trace_context={"evaluation_contract": "g3c-candidate/0.1"},
    )


def _candidate_output_to_cognitive_output(
    *,
    request: CognitiveInvocationRequest,
    result: CandidateStructuredOutput,
) -> CognitiveOutput:
    seed = {
        "invocation_id": request.invocation_id,
        "result": result.model_dump(mode="json"),
    }
    return CognitiveOutput(
        output_id=f"cout-{sha256_json(seed)[:24]}",
        content=result.content,
        epistemic_class=result.epistemic_class,
        disposition=result.disposition,
        evidence_refs=result.evidence_refs,
        provenance_refs=result.provenance_refs,
        tool_name=result.tool_name,
        material_effect=result.material_effect,
    )


def _critical_provenance_refs(result: CandidateStructuredOutput) -> tuple[str, ...]:
    ordered = list(result.provenance_refs)
    ordered.extend(f"evidence:{ref}" for ref in result.evidence_refs)
    return tuple(dict.fromkeys(ordered))


def execute_g3c1_candidate_case(
    *,
    case: GoldenCase,
    context: ContextBundle,
    adapter: CandidateAdapter,
) -> dict[str, Any]:
    """Execute one pre-Holdout G3C1 candidate case and capture a deterministic trace.

    G3C1 deliberately has no Holdout override. Enabling Holdout requires a new,
    separately authorized G3C implementation change.
    """

    if case.partition not in _G3C1_ALLOWED_PARTITIONS:
        raise ValueError("G3C1 holdout execution is forbidden")
    if adapter.identity.execution_mode != "SYNTHETIC":
        raise ValueError("G3C1 permits SYNTHETIC candidate execution only")

    request = build_candidate_request(case=case, context=context)
    result = adapter.invoke(request, context)
    output = _candidate_output_to_cognitive_output(request=request, result=result)
    policy = evaluate_cognitive_output(output)

    output_body = output.model_dump(mode="json")
    output_body["claims"] = list(result.claims)
    body: dict[str, Any] = {
        "golden_case_id": case.golden_case_id,
        "partition": case.partition,
        "candidate": adapter.identity.model_dump(mode="json"),
        "invocation_id": request.invocation_id,
        "project_scope": context.project_scope,
        "valid_at": context.valid_at.isoformat(),
        "recorded_at": context.recorded_at.isoformat(),
        "context_refs": list(context.context_refs),
        "output": output_body,
        "policy": {
            "action": policy.action.value,
            "canonical_write_allowed": policy.canonical_write_allowed,
            "material_action_executed": policy.material_action_executed,
            "reason_codes": list(policy.reason_codes),
        },
        "quality_signals": {
            "critical_provenance_refs": list(_critical_provenance_refs(result)),
            "contradictions_predicted": list(result.contradictions_predicted),
            "memory_admission_decision": result.memory_admission_decision,
            "decision_state": result.decision_state,
            "schema_valid": True,
        },
        "candidate_call_count": 1,
        "external_provider_calls": 0,
        "oracle_fields_exposed": False,
        "holdout_executed": False,
    }
    return {**body, "trace_sha256": sha256_json(body)}


def execute_g3c1_candidate_dataset(
    *,
    cases: tuple[GoldenCase, ...],
    contexts_by_case_id: dict[str, ContextBundle],
    adapter: CandidateAdapter,
) -> tuple[dict[str, Any], ...]:
    """Execute exact development/validation coverage for a synthetic G3C1 candidate."""

    case_ids = [case.golden_case_id for case in cases]
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("duplicate golden_case_id in G3C1 candidate input")
    if not cases:
        raise ValueError("G3C1 candidate dataset cannot be empty")
    if any(case.partition not in _G3C1_ALLOWED_PARTITIONS for case in cases):
        raise ValueError("G3C1 dataset contains a forbidden Holdout case")

    expected = set(case_ids)
    observed = set(contexts_by_case_id)
    missing = sorted(expected - observed)
    extra = sorted(observed - expected)
    if missing or extra:
        raise ValueError(f"G3C1 context coverage mismatch; missing={missing}, extra={extra}")

    return tuple(
        execute_g3c1_candidate_case(
            case=case,
            context=contexts_by_case_id[case.golden_case_id],
            adapter=adapter,
        )
        for case in cases
    )


def _validated_trace_ref(trace: dict[str, Any]) -> dict[str, str]:
    trace_sha = trace.get("trace_sha256")
    if not isinstance(trace_sha, str) or len(trace_sha) != 64:
        raise ValueError("candidate trace digest is missing or malformed")
    trace_body = {key: value for key, value in trace.items() if key != "trace_sha256"}
    if sha256_json(trace_body) != trace_sha:
        raise ValueError("candidate trace digest mismatch")
    if trace.get("candidate_call_count") != 1:
        raise ValueError("candidate trace must represent exactly one invocation")
    if trace.get("holdout_executed") is not False:
        raise ValueError("candidate trace indicates Holdout execution")
    return {
        "golden_case_id": str(trace.get("golden_case_id", "")),
        "trace_sha256": trace_sha,
    }


def candidate_trace_receipt(
    *,
    traces: tuple[dict[str, Any], ...],
    expected_identity: CandidateIdentity,
) -> dict[str, Any]:
    """Create a deterministic pre-Holdout receipt bound to identity and trace digests."""

    if not traces:
        raise ValueError("candidate trace receipt requires at least one trace")
    identities = {sha256_json(trace.get("candidate", {})) for trace in traces}
    if identities != {sha256_json(expected_identity.model_dump(mode="json"))}:
        raise ValueError("candidate identity drift across traces")
    if any(trace.get("partition") not in _G3C1_ALLOWED_PARTITIONS for trace in traces):
        raise ValueError("candidate trace receipt contains Holdout execution")
    if any(int(trace.get("external_provider_calls", 0)) != 0 for trace in traces):
        raise ValueError("G3C1 external provider calls are forbidden")
    if any(trace.get("oracle_fields_exposed") is not False for trace in traces):
        raise ValueError("candidate/oracle separation not proven")

    trace_refs = tuple(
        sorted(
            (_validated_trace_ref(trace) for trace in traces),
            key=lambda item: item["golden_case_id"],
        )
    )
    case_ids = [item["golden_case_id"] for item in trace_refs]
    if not all(case_ids) or len(case_ids) != len(set(case_ids)):
        raise ValueError("candidate trace IDs must be unique and non-empty")

    counts = Counter(str(trace["partition"]) for trace in traces)
    body = {
        "candidate": expected_identity.model_dump(mode="json"),
        "case_count": len(traces),
        "partition_counts": {
            "development": counts["development"],
            "validation": counts["validation"],
            "holdout": 0,
        },
        "candidate_call_count": len(traces),
        "external_provider_calls": 0,
        "oracle_fields_exposed": False,
        "holdout_executed": False,
        "structured_quality_signals": True,
        "g3_quality_pass_claimed": False,
        "trace_refs": trace_refs,
    }
    return {**body, "receipt_sha256": sha256_json(body)}
