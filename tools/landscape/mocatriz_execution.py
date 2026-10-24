#!/usr/bin/env python3
"""MOCATRIZ adaptive execution state and telemetry primitives."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


FINAL_STATUSES = {
    "COMPLETED",
    "COMPLETED_WITH_EXCEPTIONS",
    "MITIGATED",
    "PENDING",
    "WAITING_HUMAN",
    "BLOCKED",
    "SHOWSTOPPER",
}


@dataclass(frozen=True)
class HumanTask:
    objective_id: str
    execution_id: str
    human_task_id: str
    correlation_id: str
    reason: str
    question: str
    evidence: tuple[str, ...]
    resume_from: str
    status: str = "WAITING_HUMAN"

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["evidence"] = list(self.evidence)
        return result


def create_human_task(
    *,
    objective_id: str,
    execution_id: str,
    human_task_id: str,
    correlation_id: str,
    reason: str,
    question: str,
    evidence: list[str],
    resume_from: str,
) -> dict[str, Any]:
    values = {
        "objective_id": objective_id,
        "execution_id": execution_id,
        "human_task_id": human_task_id,
        "correlation_id": correlation_id,
        "reason": reason,
        "question": question,
        "resume_from": resume_from,
    }
    for name, value in values.items():
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{name} is required")
    return HumanTask(
        objective_id=objective_id,
        execution_id=execution_id,
        human_task_id=human_task_id,
        correlation_id=correlation_id,
        reason=reason,
        question=question,
        evidence=tuple(evidence),
        resume_from=resume_from,
    ).to_dict()


def correlate_human_response(task: dict[str, Any], response: dict[str, Any]) -> dict[str, Any]:
    keys = ("objective_id", "execution_id", "human_task_id", "correlation_id")
    mismatches = [key for key in keys if task.get(key) != response.get(key)]
    if mismatches:
        raise ValueError("correlation mismatch: " + ", ".join(mismatches))
    return {
        "correlation_status": "MATCHED",
        "resume_from": task["resume_from"],
        "response_evidence": response.get("answer"),
        "recommended_phase": "UNDERSTAND",
    }


def objective_completion(criteria: list[dict[str, Any]]) -> dict[str, Any]:
    applicable = [c for c in criteria if c.get("applicable", True) is True]
    for criterion in applicable:
        if not isinstance(criterion.get("satisfied"), bool):
            raise ValueError("applicable criteria require boolean satisfied")
    total = len(applicable)
    satisfied = sum(1 for c in applicable if c["satisfied"])
    completion_applicable = total > 0
    pct = None if total == 0 else round(satisfied / total * 100, 2)
    material_unresolved = [
        str(c.get("criterion_id"))
        for c in applicable
        if not c["satisfied"] and c.get("material", True) is True
    ]
    return {
        "applicable_criteria": total,
        "satisfied_criteria": satisfied,
        "objective_completion_pct": pct,
        "completion_applicable": completion_applicable,
        "material_unresolved_criteria": material_unresolved,
    }


def determine_final_status(
    criteria: list[dict[str, Any]],
    *,
    waiting_human: bool = False,
    showstopper: bool = False,
    blocked: bool = False,
    accepted_exceptions: bool = False,
    stop_assessment: dict[str, Any] | None = None,
) -> dict[str, Any]:
    completion = objective_completion(criteria)
    if showstopper:
        if not stop_assessment or stop_assessment.get("showstopper_justified") is not True:
            raise ValueError("SHOWSTOPPER requires evidence-backed stop assessment")
        status = "SHOWSTOPPER"
    elif waiting_human:
        status = "WAITING_HUMAN"
    elif blocked:
        status = "BLOCKED"
    elif not completion["completion_applicable"]:
        status = "PENDING"
    elif completion["material_unresolved_criteria"]:
        status = "PENDING"
    elif accepted_exceptions:
        status = "COMPLETED_WITH_EXCEPTIONS"
    else:
        status = "COMPLETED"
    return {"final_status": status, **completion}


def detect_false_completion(
    claimed_status: str,
    criteria: list[dict[str, Any]],
) -> dict[str, Any]:
    if claimed_status not in FINAL_STATUSES:
        raise ValueError(f"unsupported claimed status: {claimed_status}")
    completion = objective_completion(criteria)
    false_completion = (
        claimed_status in {"COMPLETED", "COMPLETED_WITH_EXCEPTIONS"}
        and (
            not completion["completion_applicable"]
            or bool(completion["material_unresolved_criteria"])
        )
    )
    return {
        "claimed_status": claimed_status,
        "false_completion": false_completion,
        **completion,
    }


def assess_strategy_adaptation(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Derive adaptive mutation vs drift from execution evidence.

    Expected event types:
    - strategy_attempt: objective_id, strategy_id, result, evidence[]
    - strategy_change: objective_id, from_strategy, to_strategy, basis_evidence[]
    """
    active_objective: str | None = None
    failed_or_partial: dict[str, set[str]] = {}
    seen_strategies: set[str] = set()
    evidence_at_entry: dict[str, set[str]] = {}
    cumulative_evidence: set[str] = set()
    classifications: list[dict[str, Any]] = []

    for event in events:
        event_type = event.get("type")
        if event_type == "strategy_attempt":
            objective_id = event.get("objective_id")
            strategy_id = event.get("strategy_id")
            result = event.get("result")
            evidence = event.get("evidence", [])
            if not isinstance(objective_id, str) or not objective_id:
                raise ValueError("strategy_attempt requires objective_id")
            if not isinstance(strategy_id, str) or not strategy_id:
                raise ValueError("strategy_attempt requires strategy_id")
            if result not in {"SUCCESS", "FAILED", "PARTIAL"}:
                raise ValueError("strategy_attempt result must be SUCCESS, FAILED or PARTIAL")
            if not isinstance(evidence, list) or not all(isinstance(x, str) and x for x in evidence):
                raise ValueError("strategy_attempt evidence must be a list of non-empty strings")

            if active_objective is None:
                active_objective = objective_id
            elif objective_id != active_objective:
                classifications.append({
                    "classification": "DRIFT",
                    "reason": "OBJECTIVE_DEPARTURE",
                    "strategy_id": strategy_id,
                    "objective_id": objective_id,
                })

            seen_strategies.add(strategy_id)
            evidence_at_entry.setdefault(strategy_id, set(cumulative_evidence))
            cumulative_evidence.update(evidence)
            if result in {"FAILED", "PARTIAL"}:
                failed_or_partial.setdefault(strategy_id, set()).update(evidence)

        elif event_type == "strategy_change":
            objective_id = event.get("objective_id")
            from_strategy = event.get("from_strategy")
            to_strategy = event.get("to_strategy")
            basis = event.get("basis_evidence", [])
            if not isinstance(objective_id, str) or not objective_id:
                raise ValueError("strategy_change requires objective_id")
            if not isinstance(from_strategy, str) or not from_strategy:
                raise ValueError("strategy_change requires from_strategy")
            if not isinstance(to_strategy, str) or not to_strategy:
                raise ValueError("strategy_change requires to_strategy")
            if not isinstance(basis, list) or not all(isinstance(x, str) and x for x in basis):
                raise ValueError("strategy_change basis_evidence must be a list of non-empty strings")

            reasons: list[str] = []
            if active_objective is None or objective_id != active_objective:
                reasons.append("OBJECTIVE_DEPARTURE")
            if from_strategy not in failed_or_partial:
                reasons.append("NO_FAILED_OR_PARTIAL_TRIGGER")
            if from_strategy == to_strategy:
                reasons.append("NO_STRATEGY_CHANGE")
            if not basis:
                reasons.append("NO_BASIS_EVIDENCE")
            elif from_strategy in failed_or_partial and not (
                set(basis) & failed_or_partial[from_strategy]
            ):
                reasons.append("UNSUPPORTED_BY_PRIOR_RESULT")

            if to_strategy in seen_strategies:
                prior_basis = evidence_at_entry.get(to_strategy, set())
                if set(basis).issubset(prior_basis):
                    reasons.append("UNPRODUCTIVE_REVISIT")

            if reasons:
                classifications.append({
                    "classification": "DRIFT",
                    "reason": "+".join(sorted(set(reasons))),
                    "from_strategy": from_strategy,
                    "to_strategy": to_strategy,
                    "objective_id": objective_id,
                    "basis_evidence": list(basis),
                })
            else:
                classifications.append({
                    "classification": "ADAPTIVE_MUTATION",
                    "reason": "EVIDENCE_DRIVEN_STRATEGY_CHANGE",
                    "from_strategy": from_strategy,
                    "to_strategy": to_strategy,
                    "objective_id": objective_id,
                    "basis_evidence": list(basis),
                })
                seen_strategies.add(to_strategy)
                evidence_at_entry[to_strategy] = set(cumulative_evidence)

    adaptive = sum(1 for item in classifications if item["classification"] == "ADAPTIVE_MUTATION")
    drift = sum(1 for item in classifications if item["classification"] == "DRIFT")
    return {
        "adaptive_mutation_count": adaptive,
        "drift_count": drift,
        "classifications": classifications,
        "objective_id": active_objective,
    }



def assess_stop_decision(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Determine whether continuing, waiting for a human, blocking, or SHOWSTOPPER is justified.

    This intentionally avoids a fixed number of recovery attempts. It evaluates the
    evidence actually present: failed/partial recovery attempts, viable alternatives,
    human-resolvable dependencies, and material irreducible blockers.
    """
    recovery_attempts: list[dict[str, Any]] = []
    alternatives: list[dict[str, Any]] = []
    human_dependencies: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []

    for event in events:
        event_type = event.get("type")
        evidence = event.get("evidence", [])
        if not isinstance(evidence, list) or not all(isinstance(x, str) and x for x in evidence):
            raise ValueError("stop-decision evidence must be a list of non-empty strings")

        if event_type == "recovery_attempt":
            if event.get("result") not in {"SUCCESS", "FAILED", "PARTIAL", "IN_PROGRESS"}:
                raise ValueError("recovery_attempt result is invalid")
            recovery_attempts.append(event)
        elif event_type == "alternative":
            if event.get("status") not in {"VIABLE_UNTRIED", "FAILED", "BLOCKED"}:
                raise ValueError("alternative status is invalid")
            alternatives.append(event)
        elif event_type == "human_dependency":
            if not isinstance(event.get("required"), bool) or not isinstance(event.get("available"), bool):
                raise ValueError("human_dependency requires boolean required and available")
            human_dependencies.append(event)
        elif event_type == "blocker":
            if not isinstance(event.get("material"), bool) or not isinstance(event.get("resolvable"), bool):
                raise ValueError("blocker requires boolean material and resolvable")
            blockers.append(event)
        else:
            raise ValueError(f"unsupported stop-decision event type: {event_type}")

    if any(item["result"] == "SUCCESS" for item in recovery_attempts):
        return {
            "recommended_status": "CONTINUE",
            "showstopper_justified": False,
            "reason": "RECOVERY_SUCCEEDED",
        }

    if any(item["result"] == "IN_PROGRESS" for item in recovery_attempts):
        return {
            "recommended_status": "CONTINUE",
            "showstopper_justified": False,
            "reason": "RECOVERY_IN_PROGRESS",
        }

    if any(item["required"] and item["available"] for item in human_dependencies):
        return {
            "recommended_status": "WAITING_HUMAN",
            "showstopper_justified": False,
            "reason": "HUMAN_DEPENDENCY_AVAILABLE",
        }

    viable = [item for item in alternatives if item["status"] == "VIABLE_UNTRIED"]
    if viable:
        return {
            "recommended_status": "CONTINUE",
            "showstopper_justified": False,
            "reason": "VIABLE_ALTERNATIVE_REMAINS",
            "viable_alternative_ids": [str(item.get("alternative_id")) for item in viable],
        }

    failed_recovery = [
        item for item in recovery_attempts
        if item["result"] in {"FAILED", "PARTIAL"} and item["evidence"]
    ]
    alternatives_exhausted = bool(alternatives) and all(
        item["status"] in {"FAILED", "BLOCKED"} and bool(item["evidence"])
        for item in alternatives
    )
    irreducible_blockers = [
        item for item in blockers
        if item["material"] is True and item["resolvable"] is False and item["evidence"]
    ]

    if failed_recovery and alternatives_exhausted and irreducible_blockers:
        return {
            "recommended_status": "SHOWSTOPPER",
            "showstopper_justified": True,
            "reason": "RECOVERY_AND_KNOWN_ALTERNATIVES_EXHAUSTED_WITH_IRREDUCIBLE_BLOCKER",
            "failed_recovery_count": len(failed_recovery),
            "alternative_count": len(alternatives),
            "blocker_count": len(irreducible_blockers),
        }

    if irreducible_blockers:
        return {
            "recommended_status": "BLOCKED",
            "showstopper_justified": False,
            "reason": "BLOCKER_PRESENT_BUT_EXHAUSTION_NOT_DEMONSTRATED",
        }

    return {
        "recommended_status": "CONTINUE",
        "showstopper_justified": False,
        "reason": "INSUFFICIENT_EVIDENCE_TO_STOP",
    }

def methodology_telemetry(events: list[dict[str, Any]]) -> dict[str, Any]:
    counts = {
        "strategy_mutation_count": 0,
        "drift_count": 0,
        "recovery_attempt_count": 0,
        "recovery_success_count": 0,
        "human_task_count": 0,
        "resume_attempt_count": 0,
        "resume_success_count": 0,
        "correlation_attempt_count": 0,
        "correlation_success_count": 0,
    }
    for event in events:
        event_type = event.get("type")
        if event_type == "strategy_mutation":
            counts["strategy_mutation_count"] += 1
        elif event_type == "drift":
            counts["drift_count"] += 1
        elif event_type == "recovery":
            counts["recovery_attempt_count"] += 1
            if event.get("success") is True:
                counts["recovery_success_count"] += 1
        elif event_type == "human_task":
            counts["human_task_count"] += 1
        elif event_type == "resume":
            counts["resume_attempt_count"] += 1
            if event.get("success") is True:
                counts["resume_success_count"] += 1
        elif event_type == "correlation":
            counts["correlation_attempt_count"] += 1
            if event.get("success") is True:
                counts["correlation_success_count"] += 1

    def ratio(num: int, den: int) -> float | None:
        return None if den == 0 else round(num / den * 100, 2)

    return {
        **counts,
        "recovery_efficiency_pct": ratio(
            counts["recovery_success_count"], counts["recovery_attempt_count"]
        ),
        "resume_success_pct": ratio(
            counts["resume_success_count"], counts["resume_attempt_count"]
        ),
        "correlation_integrity_pct": ratio(
            counts["correlation_success_count"], counts["correlation_attempt_count"]
        ),
        "recovery_efficiency_applicable": counts["recovery_attempt_count"] > 0,
        "resume_success_applicable": counts["resume_attempt_count"] > 0,
        "correlation_integrity_applicable": counts["correlation_attempt_count"] > 0,
    }
