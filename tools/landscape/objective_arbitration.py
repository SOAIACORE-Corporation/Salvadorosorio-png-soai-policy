#!/usr/bin/env python3
"""Cross-objective resource interference analysis for MOCATRIZ."""

from __future__ import annotations

from itertools import combinations
from typing import Any


def assess_objective_interference(
    objectives: list[dict[str, Any]],
) -> dict[str, Any]:
    """Detect incompatible material actions across independently valid objectives.

    This control detects interference. It does not invent an arbitration winner.
    """
    objective_ids = [obj.get("objective_id") for obj in objectives]
    if any(not isinstance(x, str) or not x for x in objective_ids):
        raise ValueError("objective_id is required")
    if len(objective_ids) != len(set(objective_ids)):
        raise ValueError("objective_id must be unique")

    claims: dict[str, list[dict[str, Any]]] = {}
    for objective in objectives:
        objective_id = objective["objective_id"]
        for action in objective.get("actions", []):
            if action.get("material", True) is not True:
                continue
            resource_ref = action.get("resource_ref")
            mode = action.get("mode")
            if not isinstance(resource_ref, str) or not resource_ref:
                raise ValueError("material action requires resource_ref")
            if mode not in {"READ", "WRITE"}:
                raise ValueError("material action mode must be READ or WRITE")
            claims.setdefault(resource_ref, []).append(
                {
                    "objective_id": objective_id,
                    "action_id": action.get("action_id"),
                    "mode": mode,
                    "desired_state_hash": action.get("desired_state_hash"),
                    "declared_priority": objective.get("priority"),
                }
            )

    conflicts: list[dict[str, Any]] = []
    serializations: list[dict[str, Any]] = []
    coalescible: list[dict[str, Any]] = []

    for resource_ref, resource_claims in claims.items():
        for left, right in combinations(resource_claims, 2):
            if left["objective_id"] == right["objective_id"]:
                continue
            modes = {left["mode"], right["mode"]}
            base = {
                "resource_ref": resource_ref,
                "objectives": sorted([left["objective_id"], right["objective_id"]]),
                "actions": [left.get("action_id"), right.get("action_id")],
            }
            if modes == {"READ"}:
                continue
            if modes == {"READ", "WRITE"}:
                serializations.append({
                    **base,
                    "classification": "READ_WRITE_INTERFERENCE",
                })
                continue

            left_hash = left.get("desired_state_hash")
            right_hash = right.get("desired_state_hash")
            if (
                isinstance(left_hash, str)
                and left_hash
                and isinstance(right_hash, str)
                and right_hash
                and left_hash == right_hash
            ):
                coalescible.append({
                    **base,
                    "classification": "COALESCIBLE_WRITE",
                    "desired_state_hash": left_hash,
                })
            else:
                conflicts.append({
                    **base,
                    "classification": "INCOMPATIBLE_WRITE",
                    "left_desired_state_hash": left_hash,
                    "right_desired_state_hash": right_hash,
                    "automatic_winner": None,
                })

    if conflicts:
        status = "ARBITRATION_REQUIRED"
    elif serializations:
        status = "SERIALIZE_REQUIRED"
    elif coalescible:
        status = "COALESCE_REQUIRED"
    else:
        status = "CLEAR"

    return {
        "status": status,
        "parallel_execution_allowed": status == "CLEAR",
        "conflicts": conflicts,
        "serializations": serializations,
        "coalescible": coalescible,
    }
