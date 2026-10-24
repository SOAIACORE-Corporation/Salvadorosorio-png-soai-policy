#!/usr/bin/env python3
"""Human interaction efficiency and preflight-completeness evaluator."""

from __future__ import annotations

from datetime import datetime
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



def _parse_timestamp(value: str, *, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} is required")
    normalized = value.strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        raise ValueError(f"{field} must be timezone-aware")
    return parsed


def evaluate_preflight_freshness(
    *,
    preconditions: list[dict[str, Any]],
    action_time: str,
) -> dict[str, Any]:
    """Fail closed when material preflight evidence is stale or has unknown freshness.

    Supported freshness modes:
    - IMMUTABLE: the checked fact is content-addressed or otherwise immutable.
    - VALID_UNTIL: evidence is valid only through an explicit timestamp.
    - VERSIONED: the version observed during preflight must equal the current version.
    """
    ids = [item.get("id") for item in preconditions]
    if any(not item for item in ids) or len(ids) != len(set(ids)):
        raise ValueError("precondition ids must be non-empty and unique")

    action_at = _parse_timestamp(action_time, field="action_time")
    stale: list[str] = []
    unknown: list[str] = []
    fresh: list[str] = []

    for item in preconditions:
        if item.get("material", True) is not True:
            continue
        precondition_id = item["id"]
        if item.get("validated") is not True:
            stale.append(precondition_id)
            continue

        mode = item.get("freshness_mode")
        if mode == "IMMUTABLE":
            fresh.append(precondition_id)
        elif mode == "VALID_UNTIL":
            try:
                valid_until = _parse_timestamp(item.get("valid_until"), field="valid_until")
            except (TypeError, ValueError):
                unknown.append(precondition_id)
                continue
            if action_at > valid_until:
                stale.append(precondition_id)
            else:
                fresh.append(precondition_id)
        elif mode == "VERSIONED":
            observed_version = item.get("observed_version")
            current_version = item.get("current_version")
            if not isinstance(observed_version, str) or not observed_version:
                unknown.append(precondition_id)
            elif not isinstance(current_version, str) or not current_version:
                unknown.append(precondition_id)
            elif observed_version != current_version:
                stale.append(precondition_id)
            else:
                fresh.append(precondition_id)
        else:
            unknown.append(precondition_id)

    revalidate = sorted(set(stale + unknown))
    return {
        "status": "REVALIDATE_REQUIRED" if revalidate else "PASS",
        "action_authorized": not revalidate,
        "fresh_precondition_ids": sorted(fresh),
        "stale_precondition_ids": sorted(stale),
        "unknown_freshness_ids": sorted(unknown),
        "revalidation_required_ids": revalidate,
    }
