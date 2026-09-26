#!/usr/bin/env python3
"""Adaptive memory-integrity cycle for SOAiaCore / Landscape Intelligence.

The cycle composes existing evidentiary continuity with three execution-quality
metrics. It remains read-only: it assesses evidence and execution traces but
does not mutate source systems or grant authority.
"""

from __future__ import annotations

from typing import Any

from recovery_manifest import assess_recovery_manifest


CRITICAL_GATES = {
    "MISSING_REQUIRED_AUTHORITY",
    "MISSING_MATERIAL_PRIMARY_EVIDENCE",
}


def assess_human_interaction_efficiency(events: list[dict[str, Any]] | None) -> dict[str, Any]:
    events = list(events or [])
    for event in events:
        if not isinstance(event.get("required"), bool):
            raise ValueError("human interaction events require boolean 'required'")

    total = len(events)
    necessary = sum(1 for event in events if event["required"])
    avoidable = total - necessary

    if total == 0:
        efficiency = 100.0
        avoidable_rate = 0.0
    else:
        efficiency = round(necessary / total * 100, 2)
        avoidable_rate = round(avoidable / total * 100, 2)

    return {
        "total_human_actions": total,
        "necessary_human_actions": necessary,
        "avoidable_human_actions": avoidable,
        "human_interaction_efficiency_pct": efficiency,
        "avoidable_human_interaction_rate_pct": avoidable_rate,
    }


def assess_recovery_efficiency(events: list[dict[str, Any]] | None) -> dict[str, Any]:
    events = list(events or [])
    recoverable = []
    for event in events:
        if not isinstance(event.get("recoverable"), bool):
            raise ValueError("recovery events require boolean 'recoverable'")
        if not isinstance(event.get("resolved"), bool):
            raise ValueError("recovery events require boolean 'resolved'")
        if not isinstance(event.get("human_intervention_required"), bool):
            raise ValueError("recovery events require boolean 'human_intervention_required'")
        if event["recoverable"]:
            recoverable.append(event)

    total = len(recoverable)
    resolved = sum(1 for event in recoverable if event["resolved"])
    autonomous = sum(
        1
        for event in recoverable
        if event["resolved"] and not event["human_intervention_required"]
    )
    unresolved = total - resolved

    recovery_efficiency = 100.0 if total == 0 else round(autonomous / total * 100, 2)

    return {
        "recoverable_events": total,
        "resolved_recoverable_events": resolved,
        "autonomously_resolved_events": autonomous,
        "unresolved_recoverable_events": unresolved,
        "recovery_efficiency_pct": recovery_efficiency,
    }


def assess_methodology_controls(controls: list[dict[str, Any]] | None) -> dict[str, Any]:
    controls = list(controls or [])
    executed = [control for control in controls if control.get("executed", True) is True]

    for control in executed:
        if not isinstance(control.get("changed_outcome"), bool):
            raise ValueError("executed controls require boolean 'changed_outcome'")

    count = len(executed)
    useful = sum(1 for control in executed if control["changed_outcome"])
    non_value_adding = count - useful

    if count == 0:
        yield_pct = 100.0
        overhead_pct = 0.0
    else:
        yield_pct = round(useful / count * 100, 2)
        overhead_pct = round(non_value_adding / count * 100, 2)

    return {
        "executed_controls": count,
        "useful_controls": useful,
        "non_value_adding_controls": non_value_adding,
        "control_yield_pct": yield_pct,
        "methodological_overhead_pct": overhead_pct,
    }


def run_memory_cycle(
    manifest: dict[str, Any],
    *,
    human_interactions: list[dict[str, Any]] | None = None,
    recovery_events: list[dict[str, Any]] | None = None,
    controls: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Run OBSERVE → UNDERSTAND → RESOLVE → DEMONSTRATE."""

    recovery = assess_recovery_manifest(manifest)
    counts = recovery["requirement_counts"]
    expected = sum(d["expected"] for d in counts.values())
    confirmed = sum(d["confirmed"] for d in counts.values())
    completion = 100.0 if expected == 0 else round(confirmed / expected * 100, 2)

    critical = sorted(set(recovery["gates"]) & CRITICAL_GATES)
    unresolved = recovery["unconfirmed_requirement_ids"]

    if critical:
        canonicalization = "BLOCKED"
    elif unresolved:
        canonicalization = "PARTIAL"
    else:
        canonicalization = "ELIGIBLE"

    resolution_actions = [
        f"RECOVER_OR_ADJUDICATE:{requirement_id}"
        for requirement_id in unresolved
    ] or ["NO_CORRECTIVE_ACTION_REQUIRED"]

    human = assess_human_interaction_efficiency(human_interactions)
    recovery_efficiency = assess_recovery_efficiency(recovery_events)
    method = assess_methodology_controls(controls)

    return {
        "memory_cycle_version": "0.1",
        "methodology": "OBSERVE_UNDERSTAND_RESOLVE_DEMONSTRATE",
        "observe": {
            "required_requirements": expected,
            "confirmed_requirements": confirmed,
            "requirement_completion_pct": completion,
            "unconfirmed_requirement_ids": unresolved,
        },
        "understand": {
            "context_integrity_score_pct": recovery["claimable_score_pct"],
            "context_integrity_band": recovery["confidence_band"],
            "gates": recovery["gates"],
            "critical_gates": critical,
        },
        "resolve": {
            "canonicalization_status": canonicalization,
            "actions": resolution_actions,
            "automatic_source_mutation": False,
        },
        "demonstrate": {
            "context_integrity": recovery,
            "human_interaction": human,
            "recovery_efficiency": recovery_efficiency,
            "methodology_efficiency": method,
        },
        "semantics": {
            "confidence_rule": "Context Integrity measures evidentiary continuity, not AI correctness probability.",
            "canonicalization_rule": "Confidence alone never grants canonical status when a critical gate is open.",
            "authority_rule": "The cycle is read-only and never grants execution or exception authority.",
            "adaptivity_rule": "Recoverable friction may be corrected or bypassed; critical evidence or authority gates stop canonicalization.",
        },
    }
