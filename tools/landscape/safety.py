#!/usr/bin/env python3
"""Pure action-safety checks. No execution capability."""

from __future__ import annotations

from typing import Any


def assess_action_safety(action_record: dict[str, Any]) -> dict[str, Any]:
    if action_record.get("record_type") != "action":
        raise ValueError("action record required")
    p=action_record["payload"]
    irreversible = p.get("action_type") == "remove" and p.get("rollback") is None
    if irreversible:
        return {
            "gate":"EXPLICIT_APPROVAL_REQUIRED",
            "reversible":False,
            "reason":"Removal has no rollback plan; trivial severity does not remove irreversibility risk.",
        }
    return {
        "gate":"STANDARD_CONTROL",
        "reversible":p.get("rollback") is not None,
        "reason":"Action follows standard controlled-change evaluation.",
    }
