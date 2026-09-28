#!/usr/bin/env python3
"""Aggregate the base operating-error register with append-only error events."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_error_register(root: Path) -> dict[str, Any]:
    base_path = root / "schemas" / "examples" / "landscape" / "operating-error-register-v0.1.json"
    events_dir = root / "schemas" / "examples" / "landscape" / "error-events"

    base = json.loads(base_path.read_text(encoding="utf-8"))
    entries = list(base.get("entries", []))

    if events_dir.exists():
        for path in sorted(events_dir.glob("ERR-*.json")):
            entries.append(json.loads(path.read_text(encoding="utf-8")))

    ids = [entry.get("error_id") for entry in entries]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate error_id across base register and append-only events")

    result = dict(base)
    result["entries"] = entries
    result["base_entry_count"] = len(base.get("entries", []))
    result["append_only_event_count"] = len(entries) - result["base_entry_count"]
    result["total_entry_count"] = len(entries)
    return result
