from datetime import datetime, timezone
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from soaiacore_runtime.cognitive_loop import (
    CognitiveInvocationRequest,
    CognitiveMessage,
    CognitiveOutput,
    EpistemicClass,
    OutputDisposition,
)
from soaiacore_runtime.golden_eval import GoldenCase, evaluate_golden_case

ROOT = Path(__file__).resolve().parents[3]


def _schema(name: str):
    schema = json.loads((ROOT / "schemas" / name).read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def _request(**overrides):
    values = {
        "invocation_id": "inv-g0",
        "task_class": "SYNTHESIS",
        "messages": (CognitiveMessage(role="user", content="analyze"),),
        "context_refs": (),
        "tool_contracts": (),
        "output_schema": "cognitive-output-v0.1",
        "reasoning_budget": "MEDIUM",
        "latency_class": "INTERACTIVE",
        "privacy_class": "HIGH",
        "max_cost": 0.0,
        "model_constraints": {"capability": "reasoning"},
        "trace_context": {"trace_id": "trace-g0"},
    }
    values.update(overrides)
    return CognitiveInvocationRequest(**values)


def test_versioned_json_schemas_accept_reference_contracts():
    _schema("cognitive-invocation-request-v0.1.schema.json").validate(
        _request().model_dump(mode="json")
    )
    _schema("cognitive-output-v0.1.schema.json").validate(
        CognitiveOutput(
            output_id="out-g0",
            content="hypothesis",
            epistemic_class=EpistemicClass.HYPOTHESIS,
            disposition=OutputDisposition.EPHEMERAL_INFERENCE,
        ).model_dump(mode="json")
    )
    _schema("golden-case-v0.1.schema.json").validate(
        GoldenCase(
            golden_case_id="G0-001",
            project_scope="project-a",
            question="what was known?",
            cutoff_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
            expected_epistemic_class=EpistemicClass.HYPOTHESIS,
            partition="development",
        ).model_dump(mode="json")
    )


@pytest.mark.parametrize("forbidden", ["provider", "provider_id", "model_id", "vendor", "api_key"])
def test_provider_specific_constraints_are_rejected_by_domain_model(forbidden):
    with pytest.raises(ValidationError):
        _request(model_constraints={forbidden: "forbidden-value"})


def test_golden_safety_detects_critical_fact_without_provenance():
    case = GoldenCase(
        golden_case_id="PROV-001",
        project_scope="project-a",
        question="state the fact",
        cutoff_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
        expected_epistemic_class=EpistemicClass.DOCUMENTED_FACT,
        partition="development",
    )
    trace = {
        "project_scope": "project-a",
        "context_refs": [],
        "output": {
            "epistemic_class": "DOCUMENTED_FACT",
            "provenance_refs": [],
            "evidence_refs": [],
            "material_effect": False,
        },
        "policy": {"canonical_write_allowed": False, "action": "PROPOSE_CLAIM"},
    }
    result = evaluate_golden_case(case, trace)
    assert "CRITICAL_FACTUAL_CLAIM_WITHOUT_PROVENANCE" in result.safety_failures
