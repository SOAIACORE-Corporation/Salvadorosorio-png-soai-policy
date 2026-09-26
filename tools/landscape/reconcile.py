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


def _latest_config_by_system(records: list[dict[str, Any]], asset_id: str) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for record in records:
        payload = record.get("payload", {})
        if payload.get("asset_id") != asset_id:
            continue
        if record.get("record_type") != "observation" or payload.get("fact_type") != "config":
            continue
        system = record.get("source", {}).get("system")
        if system not in {"azure", "terraform", "github"}:
            continue
        current = latest.get(system)
        if current is None or record.get("observed_at", "") >= current.get("observed_at", ""):
            latest[system] = record
    return latest


def _comparable_for_system(record: dict[str, Any]) -> dict[str, Any]:
    value = record["payload"]["value"]
    system = record["source"]["system"]
    if system == "terraform":
        return _comparable_terraform(value)
    if system == "github":
        return _comparable_github(value)
    allowed = ("resource_type", "native_id", "location", "sku", "public_network_access", "identity", "image")
    return {key: value[key] for key in allowed if key in value}


def _triple_classification(values: dict[str, Any]) -> str:
    azure = values["azure"]
    terraform = values["terraform"]
    github = values["github"]
    if azure == terraform != github:
        return "DECLARATIVE_DRIFT"
    if azure == github != terraform:
        return "MANAGED_DRIFT"
    if terraform == github != azure:
        return "PHYSICAL_DRIFT"
    return "MULTI_SOURCE_DIVERGENCE"


def reconcile_triple(
    records: list[dict[str, Any]],
    *,
    required_systems: tuple[str, ...] = ("azure", "terraform", "github"),
) -> list[dict[str, Any]]:
    """Reconcile physical, managed and declarative configuration without mutation.

    Missing required source coverage becomes a VISIBILITY_GAP. Contradictions are
    classified but always remain PENDING; this function never proposes or executes
    a repair.
    """
    asset_ids = sorted({
        r.get("payload", {}).get("asset_id")
        for r in records
        if r.get("payload", {}).get("asset_id")
    })
    findings: list[dict[str, Any]] = []

    for asset_id in asset_ids:
        latest = _latest_config_by_system(records, asset_id)
        present = tuple(system for system in required_systems if system in latest)
        missing = tuple(system for system in required_systems if system not in latest)

        if len(present) >= 2 and missing:
            evidence_refs = [latest[s]["record_id"] for s in present]
            observed_at = max(latest[s]["observed_at"] for s in present)
            suffix = _digest({"asset_id": asset_id, "missing": missing, "present": present})
            finding = {
                "schema_version": "0.1",
                "record_id": f"finding:visibility:{suffix}",
                "record_type": "finding",
                "source": {
                    "source_id": "landscape-reconciler-v0.2",
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
                    "finding_id": f"finding:visibility:{suffix}",
                    "asset_id": asset_id,
                    "type": "visibility_gap",
                    "classification": "SOURCE_VISIBILITY_GAP",
                    "adjudication": "VISIBILITY_GAP",
                    "severity": "UNKNOWN",
                    "status": "VISIBILITY_GAP",
                    "evidence_refs": evidence_refs,
                    "confidence": 1.0,
                },
            }
            _validator().validate(finding)
            findings.append(finding)

        if len(present) < 2:
            continue

        comparable = {system: _comparable_for_system(latest[system]) for system in present}
        common_keys = set.intersection(*(set(v) for v in comparable.values())) if comparable else set()
        conflicts = {
            key: {system: comparable[system][key] for system in present}
            for key in sorted(common_keys)
            if len({json.dumps(comparable[system][key], sort_keys=True) for system in present}) > 1
        }
        if not conflicts:
            continue

        if set(present) == {"azure", "terraform", "github"}:
            classes = {
                _triple_classification({
                    "azure": conflicts[key]["azure"],
                    "terraform": conflicts[key]["terraform"],
                    "github": conflicts[key]["github"],
                })
                for key in conflicts
            }
            classification = classes.pop() if len(classes) == 1 else "MULTI_SOURCE_DIVERGENCE"
        else:
            classification = "PAIRWISE_DRIFT"

        evidence_refs = [latest[s]["record_id"] for s in present]
        observed_at = max(latest[s]["observed_at"] for s in present)
        suffix = _digest({"asset_id": asset_id, "classification": classification, "conflicts": conflicts})
        finding = {
            "schema_version": "0.1",
            "record_id": f"finding:reconcile-v2:{suffix}",
            "record_type": "finding",
            "source": {
                "source_id": "landscape-reconciler-v0.2",
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
                "finding_id": f"finding:reconcile-v2:{suffix}",
                "asset_id": asset_id,
                "type": "drift",
                "classification": classification,
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
