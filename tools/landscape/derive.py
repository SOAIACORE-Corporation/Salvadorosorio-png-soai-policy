#!/usr/bin/env python3
"""Pure derivations over canonical Landscape Intelligence records."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from normalize import _validator


def _digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


def derive_runtime_dependencies(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    derived: list[dict[str, Any]] = []
    for record in records:
        if record["record_type"] != "observation":
            continue
        payload = record["payload"]
        if payload.get("fact_type") != "health":
            continue
        value = payload.get("value") or {}
        deps = value.get("dependencies")
        if not isinstance(deps, list):
            continue
        asset_id = payload.get("asset_id")
        if not asset_id:
            continue
        for dep in sorted({str(d) for d in deps if str(d).strip()}):
            did = f"dependency:{_digest([asset_id, dep])}"
            item = {
                "schema_version": "0.1",
                "record_id": did,
                "record_type": "dependency",
                "source": {
                    "source_id": "landscape-runtime-dependency-deriver-v0.1",
                    "system": "other",
                    "source_type": "derived",
                    "location": "tools/landscape/derive.py",
                    "collected_at": record["observed_at"],
                    "hash": None,
                    "freshness": "current",
                    "trust_level": "derived",
                },
                "observed_at": record["observed_at"],
                "payload": {
                    "dependency_id": did,
                    "from_id": asset_id,
                    "to_id": dep,
                    "relation_type": "depends_on",
                    "criticality": "UNKNOWN",
                    "status": "ACTIVE",
                },
            }
            _validator().validate(item)
            derived.append(item)
    return sorted(derived, key=lambda r: r["record_id"])
