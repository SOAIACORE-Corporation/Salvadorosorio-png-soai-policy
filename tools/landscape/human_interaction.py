#!/usr/bin/env python3
"""Human interaction efficiency and preflight-completeness evaluator."""

from __future__ import annotations

from typing import Any


def _ratio(numerator: int, denominator: int) -> dict[str, Any]:
    if denominator == 0:
        return {
            "numerator": numerator,
            "denominator": denominator,
            "result_pct": None,
            "status": "NOT_EXERCISED",
        }
    return {
        "numerator": numerator,
        "denominator": denominator,
        "result_pct": round((numerator / denominator) * 100, 2),
        "status": "MEASURED",
    }


def evaluate_preflight_completeness(
    *,
    preconditions: list[dict[str, Any]],
    validated_before_first_human_action: list[str],
    human_actions: list[dict[str, Any]],
) -> dict[str, Any]:
    """Evaluate whether machine-verifiable prerequisites were exhausted first."""
    ids = [item.get("id") for item in preconditions]
    if any(not item for item in ids) or len(ids) != len(set(ids)):
        raise ValueError("precondition ids must be non-empty and unique")

    machine_required = {
        item["id"]
        for item in preconditions
        if item.get("machine_verifiable") is True
        and item.get("required_before_human_action") is True
    }
    validated = set(validated_before_first_human_action)
    unknown = validated - set(ids)
    if unknown:
        raise ValueError(f"unknown validated preconditions: {sorted(unknown)}")

    missed = sorted(machine_required - validated)

    total_human = len(human_actions)
    necessary = sum(
        1
        for action in human_actions
        if action.get("authority_required") is True
        and action.get("rework_due_to_precheck_miss") is not True
    )
    avoidable = sum(
        1
        for action in human_actions
        if action.get("rework_due_to_precheck_miss") is True
        or action.get("authority_required") is not True
    )

    if necessary + avoidable != total_human:
        raise ValueError("every human action must classify as necessary or avoidable")

    status = "FAIL_PRECHECK_MISS" if missed or avoidable else "PASS"

    return {
        "status": status,
        "precheck_complete": not missed,
        "required_machine_preconditions": sorted(machine_required),
        "validated_before_first_human_action": sorted(validated & machine_required),
        "missed_precondition_ids": missed,
        "human_actions": {
            "total": total_human,
            "necessary": necessary,
            "avoidable": avoidable,
        },
        "human_interaction_efficiency": _ratio(necessary, total_human),
        "avoidable_human_interaction_rate": _ratio(avoidable, total_human),
    }
