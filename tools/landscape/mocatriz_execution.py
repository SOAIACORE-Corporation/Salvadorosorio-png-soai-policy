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
    pct = 100.0 if total == 0 else round(satisfied / total * 100, 2)
    material_unresolved = [
        str(c.get("criterion_id"))
        for c in applicable
        if not c["satisfied"] and c.get("material", True) is True
    ]
    return {
        "applicable_criteria": total,
        "satisfied_criteria": satisfied,
        "objective_completion_pct": pct,
        "material_unresolved_criteria": material_unresolved,
    }


def determine_final_status(
    criteria: list[dict[str, Any]],
    *,
    waiting_human: bool = False,
    showstopper: bool = False,
    blocked: bool = False,
    accepted_exceptions: bool = False,
) -> dict[str, Any]:
    completion = objective_completion(criteria)
    if showstopper:
        status = "SHOWSTOPPER"
    elif waiting_human:
        status = "WAITING_HUMAN"
    elif blocked:
        status = "BLOCKED"
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
        and bool(completion["material_unresolved_criteria"])
    )
    return {
        "claimed_status": claimed_status,
        "false_completion": false_completion,
        **completion,
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
