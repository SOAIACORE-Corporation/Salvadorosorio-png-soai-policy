#!/usr/bin/env python3
"""Transitive dependency integrity for evidence-derived SOAiaCore state."""

from __future__ import annotations

from typing import Any


CURRENT_STATES = {
    "CURRENT",
    "CONFIRMED",
    "VERIFIED",
    "ADMISSIBLE",
    "DOCUMENTED_FACT",
    "CONFIRMED_CONTEXT",
}
REVALIDATION_STATES = {
    "SUPERSEDED",
    "STALE",
    "STALE_INFORMATION",
    "UNKNOWN",
    "PARTIAL",
}
INVALID_STATES = {
    "REJECTED",
    "QUARANTINED",
    "INVALID",
}


def _intrinsic_effective_state(state: str) -> str:
    normalized = str(state).strip().upper()
    if normalized in INVALID_STATES:
        return "INVALID"
    if normalized in REVALIDATION_STATES:
        return "REVALIDATION_REQUIRED"
    if normalized in CURRENT_STATES:
        return "CURRENT"
    return "REVALIDATION_REQUIRED"


def evaluate_dependency_integrity(
    *,
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
) -> dict[str, Any]:
    """Propagate material evidence invalidation without mutating historical nodes.

    Each edge is dependency -> dependent. Non-material edges preserve lineage but do not
    invalidate the dependent.
    """
    node_map: dict[str, dict[str, Any]] = {}
    for node in nodes:
        node_id = node.get("id")
        if not isinstance(node_id, str) or not node_id:
            raise ValueError("node id is required")
        if node_id in node_map:
            raise ValueError(f"duplicate node id: {node_id}")
        node_map[node_id] = node

    incoming: dict[str, list[str]] = {node_id: [] for node_id in node_map}
    for edge in edges:
        dependency = edge.get("dependency_id")
        dependent = edge.get("dependent_id")
        if dependency not in node_map or dependent not in node_map:
            raise ValueError("dependency edges must reference known nodes")
        if edge.get("material", True) is True:
            incoming[dependent].append(dependency)

    memo: dict[str, str] = {}
    visiting: set[str] = set()

    def resolve(node_id: str) -> str:
        if node_id in memo:
            return memo[node_id]
        if node_id in visiting:
            raise ValueError("dependency cycle detected")
        visiting.add(node_id)

        state = _intrinsic_effective_state(node_map[node_id].get("state", "UNKNOWN"))
        dependency_states = [resolve(dep) for dep in incoming[node_id]]

        if state == "INVALID" or "INVALID" in dependency_states:
            effective = "INVALID"
        elif state == "REVALIDATION_REQUIRED" or "REVALIDATION_REQUIRED" in dependency_states:
            effective = "REVALIDATION_REQUIRED"
        else:
            effective = "CURRENT"

        visiting.remove(node_id)
        memo[node_id] = effective
        return effective

    for node_id in node_map:
        resolve(node_id)

    invalid = sorted(node_id for node_id, state in memo.items() if state == "INVALID")
    revalidate = sorted(
        node_id for node_id, state in memo.items() if state == "REVALIDATION_REQUIRED"
    )
    current = sorted(node_id for node_id, state in memo.items() if state == "CURRENT")

    return {
        "status": "CURRENT" if not invalid and not revalidate else "REVALIDATION_REQUIRED",
        "effective_states": dict(sorted(memo.items())),
        "current_ids": current,
        "revalidation_required_ids": revalidate,
        "invalid_ids": invalid,
    }
