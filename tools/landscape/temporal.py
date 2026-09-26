#!/usr/bin/env python3
"""Simple temporal inference over Landscape Intelligence history.

These rules favor visibility and recurrence over opaque prediction.
"""

from __future__ import annotations

from collections import Counter
from typing import Any


def infer_temporal_patterns(snapshots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if len(snapshots) < 2:
        return []

    patterns: list[dict[str, Any]] = []

    # Repeated finding: same finding present in every recent snapshot.
    finding_sets = [
        {f["record_id"] for f in snap["analysis"].get("findings", [])}
        for snap in snapshots
    ]
    repeated = set.intersection(*finding_sets) if finding_sets else set()
    for fid in sorted(repeated):
        patterns.append({
            "pattern_type": "PERSISTENT_FINDING",
            "subject_id": fid,
            "occurrences": len(snapshots),
            "confidence": 1.0,
            "interpretation": "Finding persisted across all supplied snapshots; persistence is evidence, not automatic escalation.",
        })

    # Cost trend: compare observed cost records with same scope and period-independent identity.
    series: dict[str, list[float]] = {}
    for snap in snapshots:
        for record in snap["bundle"]["records"]:
            if record["record_type"] != "cost_snapshot":
                continue
            p = record["payload"]
            if p.get("cost_type") != "observed" or p.get("amount") is None:
                continue
            series.setdefault(p["scope_id"], []).append(float(p["amount"]))

    for scope, values in sorted(series.items()):
        if len(values) < 2:
            continue
        if all(b > a for a, b in zip(values, values[1:])):
            patterns.append({
                "pattern_type": "MONOTONIC_COST_INCREASE",
                "subject_id": scope,
                "occurrences": len(values),
                "confidence": 1.0,
                "interpretation": "Observed cost increased in every supplied snapshot; no technical incident is implied.",
            })

    # Repeated visibility gap.
    gap_counts = Counter()
    for snap in snapshots:
        for finding in snap["analysis"].get("findings", []):
            p = finding["payload"]
            if p.get("adjudication") == "VISIBILITY_GAP":
                gap_counts[p["finding_id"]] += 1
    for fid, count in sorted(gap_counts.items()):
        if count >= 2:
            patterns.append({
                "pattern_type": "REPEATED_VISIBILITY_GAP",
                "subject_id": fid,
                "occurrences": count,
                "confidence": 1.0,
                "interpretation": "Visibility gap recurred; the missing information itself is now a historical signal.",
            })

    return patterns
