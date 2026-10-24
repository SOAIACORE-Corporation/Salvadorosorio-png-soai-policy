#!/usr/bin/env python3
"""Audit current control state without rewriting historical error records."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from error_register import load_error_register

AUDIT_STATUSES = {"CONTROLLED", "ACCEPTED_GAP", "OPEN", "WAITING_HUMAN"}


def load_control_validations(root: Path) -> list[dict[str, Any]]:
    directory = root / "schemas" / "examples" / "landscape" / "error-control-validations"
    if not directory.exists():
        return []
    result = []
    for path in sorted(directory.glob("VAL-*.json")):
        item = json.loads(path.read_text(encoding="utf-8"))
        if item.get("status") not in AUDIT_STATUSES:
            raise ValueError(f"unsupported validation status: {item.get('status')}")
        if not item.get("error_id"):
            raise ValueError("validation requires error_id")
        if not item.get("evidence_refs"):
            raise ValueError("validation requires evidence_refs")
        result.append(item)
    return result


def audit_error_controls(root: Path) -> dict[str, Any]:
    register = load_error_register(root)
    validations = load_control_validations(root)
    validation_by_error: dict[str, dict[str, Any]] = {}
    for validation in validations:
        validation_by_error[validation["error_id"]] = validation

    rows = []
    for entry in register["entries"]:
        validation = validation_by_error.get(entry["error_id"])
        effective = (
            validation["status"]
            if validation is not None
            else entry["control_status"]
        )
        rows.append({
            "error_id": entry["error_id"],
            "class": entry["class"],
            "historical_status": entry["control_status"],
            "effective_status": effective,
            "validation_id": validation.get("validation_id") if validation else None,
            "validation_evidence_refs": validation.get("evidence_refs", []) if validation else [],
            "human_required": validation.get("human_required", False) if validation else False,
        })

    counts = {}
    for row in rows:
        counts[row["effective_status"]] = counts.get(row["effective_status"], 0) + 1

    unresolved = [
        row["error_id"]
        for row in rows
        if row["effective_status"] in {"OPEN", "MITIGATED", "WAITING_HUMAN"}
    ]
    human_required = [
        row["error_id"]
        for row in rows
        if row["effective_status"] == "WAITING_HUMAN" or row["human_required"] is True
    ]

    return {
        "error_control_audit_version": "0.1",
        "total_errors": len(rows),
        "status_counts": counts,
        "unresolved_error_ids": unresolved,
        "human_required_error_ids": human_required,
        "all_errors_accounted_for": len(rows) > 0,
        "all_errors_closed_or_explicit_gap": len(unresolved) == 0,
        "rows": rows,
    }
