from __future__ import annotations

from typing import Any

from .golden_eval import GoldenCase, evaluate_golden_case
from .quality_eval import QualityObservation


_VALID_MEMORY_DECISIONS = {"ADMIT", "REJECT", "DEFER"}


def _as_string_tuple(value: Any) -> tuple[str, ...] | None:
    if value is None:
        return None
    if not isinstance(value, (list, tuple)):
        raise ValueError("quality signal must be a list or tuple of strings")
    if not all(isinstance(item, str) for item in value):
        raise ValueError("quality signal contains a non-string item")
    return tuple(value)


def _provenance_correct(candidate: str, required: tuple[str, ...]) -> bool:
    required_set = set(required)
    return (
        candidate in required_set
        or f"evidence:{candidate}" in required_set
        or candidate.startswith("evidence:")
        and candidate.removeprefix("evidence:") in required_set
    )


def quality_observation_from_trace(
    *,
    case: GoldenCase,
    trace: dict[str, Any],
) -> QualityObservation:
    """Convert one captured trace into deterministic G3 measurement inputs.

    Only signals that can be checked exactly are measured. Missing semantic signals
    remain None so the aggregate becomes NOT_MEASURED rather than silently passing.
    """

    result = evaluate_golden_case(case, trace)
    quality = trace.get("quality_signals", {})
    if quality is None:
        quality = {}
    if not isinstance(quality, dict):
        raise ValueError("quality_signals must be an object")

    critical_refs = _as_string_tuple(quality.get("critical_provenance_refs"))
    if critical_refs is None:
        critical_claimed = None
        critical_correct = None
    else:
        critical_claimed = len(critical_refs)
        critical_correct = sum(
            _provenance_correct(ref, case.required_provenance)
            for ref in critical_refs
        )

    predicted_contradictions = _as_string_tuple(
        quality.get("contradictions_predicted")
    )
    if predicted_contradictions is None:
        contradictions_expected = None
        contradictions_predicted = None
        contradictions_true_positive = None
    else:
        expected_set = set(case.contradictions_expected)
        predicted_set = set(predicted_contradictions)
        contradictions_expected = len(expected_set)
        contradictions_predicted = len(predicted_set)
        contradictions_true_positive = len(expected_set & predicted_set)

    memory_decision = quality.get("memory_admission_decision")
    if memory_decision is None:
        memory_admissions_predicted = None
        memory_admissions_true_positive = None
    else:
        if not isinstance(memory_decision, str) or memory_decision not in _VALID_MEMORY_DECISIONS:
            raise ValueError("invalid memory_admission_decision quality signal")
        memory_admissions_predicted = int(memory_decision == "ADMIT")
        memory_admissions_true_positive = int(
            memory_decision == "ADMIT"
            and case.expected_decision_state == "ADMIT"
        )

    decision_state = quality.get("decision_state")
    if decision_state is None:
        decision_reconstruction_expected = None
        decision_reconstruction_correct = None
    else:
        if not isinstance(decision_state, str):
            raise ValueError("decision_state quality signal must be a string")
        decision_reconstruction_expected = case.expected_decision_state is not None
        decision_reconstruction_correct = (
            case.expected_decision_state is not None
            and decision_state == case.expected_decision_state
        )

    schema_valid = quality.get("schema_valid")
    if schema_valid is not None and not isinstance(schema_valid, bool):
        raise ValueError("schema_valid quality signal must be a boolean")

    return QualityObservation(
        golden_case_id=case.golden_case_id,
        partition=case.partition,
        temporal_correct=result.checks["temporal_cut"],
        critical_provenance_claimed=critical_claimed,
        critical_provenance_correct=critical_correct,
        contradictions_expected=contradictions_expected,
        contradictions_predicted=contradictions_predicted,
        contradictions_true_positive=contradictions_true_positive,
        memory_admissions_predicted=memory_admissions_predicted,
        memory_admissions_true_positive=memory_admissions_true_positive,
        decision_reconstruction_expected=decision_reconstruction_expected,
        decision_reconstruction_correct=decision_reconstruction_correct,
        schema_valid=schema_valid,
        project_scope_correct=result.checks["project_scope"],
        epistemic_label_correct=result.checks["epistemic_label"],
    )


def quality_observations_from_traces(
    *,
    cases: tuple[GoldenCase, ...],
    traces_by_case_id: dict[str, dict[str, Any]],
) -> tuple[QualityObservation, ...]:
    """Create one observation per case; incomplete trace coverage fails closed."""

    case_ids = [case.golden_case_id for case in cases]
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("duplicate golden_case_id in runner input")
    expected = set(case_ids)
    observed = set(traces_by_case_id)
    missing = sorted(expected - observed)
    extra = sorted(observed - expected)
    if missing or extra:
        raise ValueError(f"trace coverage mismatch; missing={missing}, extra={extra}")
    return tuple(
        quality_observation_from_trace(
            case=case,
            trace=traces_by_case_id[case.golden_case_id],
        )
        for case in cases
    )
