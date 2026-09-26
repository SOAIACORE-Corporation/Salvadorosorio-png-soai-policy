#!/usr/bin/env python3
"""Read-only reconciliation for canonical Landscape Intelligence records.

Differences become PENDING findings. They do not become FIX without explicit
adjudication authority.
"""

from __future__ import annotations

from collections import defaultdict
import hashlib
import json
from typing import Any

from jsonschema import Draft202012Validator

from normalize import _validator


def _digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


def _comparable_terraform(value: dict[str, Any]) -> dict[str, Any]:
    attrs = value.get("attributes") or {}
    result = {}
    if value.get("resource_type") is not None:
        result["resource_type"] = value.get("resource_type")
    if value.get("native_id") is not None:
        result["native_id"] = value.get("native_id")
    for key in ("location", "sku", "public_network_access", "identity", "image"):
        if key in attrs:
            result[key] = attrs[key]
    return result


def _comparable_github(value: dict[str, Any]) -> dict[str, Any]:
    intent = value.get("intent") or {}
    allowed = ("resource_type", "native_id", "location", "sku", "public_network_access", "identity", "image")
    return {key: intent[key] for key in allowed if key in intent}


def reconcile(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_asset: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        payload = record.get("payload", {})
        asset_id = payload.get("asset_id")
        if asset_id:
            by_asset[asset_id].append(record)

    findings: list[dict[str, Any]] = []
    for asset_id, asset_records in sorted(by_asset.items()):
        tf = [
            r for r in asset_records
            if r["record_type"] == "observation"
            and r["payload"].get("fact_type") == "config"
            and r["source"]["system"] == "terraform"
        ]
        gh = [
            r for r in asset_records
            if r["record_type"] == "observation"
            and r["payload"].get("fact_type") == "config"
            and r["source"]["system"] == "github"
        ]
        if not tf or not gh:
            continue

        tf_value = _comparable_terraform(tf[-1]["payload"]["value"])
        gh_value = _comparable_github(gh[-1]["payload"]["value"])
        comparable_keys = sorted(set(tf_value) & set(gh_value))
        conflicts = {
            key: {"terraform": tf_value[key], "github": gh_value[key]}
            for key in comparable_keys
            if tf_value[key] != gh_value[key]
        }
        if not conflicts:
            continue

        evidence_refs = [tf[-1]["record_id"], gh[-1]["record_id"]]
        observed_at = max(tf[-1]["observed_at"], gh[-1]["observed_at"])
        suffix = _digest({"asset_id": asset_id, "conflicts": conflicts})
        finding = {
            "schema_version": "0.1",
            "record_id": f"finding:reconcile:{suffix}",
            "record_type": "finding",
            "source": {
                "source_id": "landscape-reconciler-v0.1",
                "system": "other",
                "source_type": "derived",
                "location": "tools/landscape/reconcile.py",
                "collected_at": observed_at,
                "hash": None,
                "freshness": "current",
                "trust_level": "derived",
            },
            "observed_at": observed_at,
            "payload": {
                "finding_id": f"finding:reconcile:{suffix}",
                "asset_id": asset_id,
                "type": "drift",
                "adjudication": "PENDING",
                "severity": "UNKNOWN",
                "status": "OPEN",
                "evidence_refs": evidence_refs,
                "confidence": 1.0,
            },
        }
        _validator().validate(finding)
        findings.append(finding)

    return findings
