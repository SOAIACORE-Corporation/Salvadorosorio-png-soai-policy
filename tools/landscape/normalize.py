#!/usr/bin/env python3
"""Read-only normalizers for SOAiaCore Landscape Intelligence v0.1.

This module converts already-collected source payloads into canonical records.
It performs no cloud calls and has no mutation path.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from identity import azure_asset_id

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "schemas" / "landscape-intelligence-v0.1.schema.json"


def _validator() -> Draft202012Validator:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def _utc(value: str | None = None) -> str:
    if value:
        return value
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sha256(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest().upper()


def source_record(
    *,
    source_id: str,
    system: str,
    source_type: str,
    collected_at: str,
    location: str | None = None,
    payload_hash: str | None = None,
    freshness: str = "current",
    trust_level: str = "authoritative",
) -> dict[str, Any]:
    return {
        "source_id": source_id,
        "system": system,
        "source_type": source_type,
        "location": location,
        "collected_at": collected_at,
        "hash": payload_hash,
        "freshness": freshness,
        "trust_level": trust_level,
    }


def normalize_azure_resource(raw: dict[str, Any], *, source: dict[str, Any]) -> dict[str, Any]:
    required = ("subscription_id", "resource_id", "name", "resource_type")
    missing = [key for key in required if not raw.get(key)]
    if missing:
        raise ValueError(f"azure resource missing required fields: {', '.join(missing)}")

    environment = raw.get("environment") or raw.get("tags", {}).get("Environment") or "unknown"
    environment = str(environment).lower()
    if environment not in {"p0", "dev", "test", "prod", "unknown"}:
        environment = "unknown"

    asset_id = azure_asset_id(raw['subscription_id'], raw['resource_id'])
    record = {
        "schema_version": "0.1",
        "record_id": f"asset:{asset_id}",
        "record_type": "asset",
        "source": source,
        "observed_at": raw.get("observed_at") or source["collected_at"],
        "payload": {
            "asset_id": asset_id,
            "provider": "azure",
            "scope": raw["subscription_id"],
            "environment": environment,
            "resource_type": raw["resource_type"],
            "native_id": raw["resource_id"],
            "name": raw["name"],
            "owner": raw.get("owner"),
            "status": raw.get("status", "ACTIVE"),
        },
    }
    _validator().validate(record)
    return record


def normalize_cost(raw: dict[str, Any], *, source: dict[str, Any]) -> dict[str, Any]:
    cost_type = raw.get("cost_type", "observed")
    amount = raw.get("amount")
    currency = raw.get("currency")

    if amount is None:
        cost_type = "unknown"
        currency = None

    record = {
        "schema_version": "0.1",
        "record_id": raw["cost_id"],
        "record_type": "cost_snapshot",
        "source": source,
        "observed_at": raw.get("observed_at") or source["collected_at"],
        "payload": {
            "cost_id": raw["cost_id"],
            "scope_id": raw["scope_id"],
            "period": raw["period"],
            "amount": amount,
            "currency": currency,
            "cost_type": cost_type,
            "formula": raw.get("formula"),
            "confidence": float(raw.get("confidence", 1.0 if amount is not None else 0.0)),
        },
    }
    _validator().validate(record)
    return record


def normalize_terraform_plan_summary(raw: dict[str, Any], *, source: dict[str, Any]) -> dict[str, Any]:
    add = int(raw.get("add", 0))
    change = int(raw.get("change", 0))
    destroy = int(raw.get("destroy", 0))
    total = add + change + destroy
    adjudication = raw.get("adjudication", "PENDING")
    status = raw.get("status", "OPEN")

    record = {
        "schema_version": "0.1",
        "record_id": raw["finding_id"],
        "record_type": "finding",
        "source": source,
        "observed_at": raw.get("observed_at") or source["collected_at"],
        "payload": {
            "finding_id": raw["finding_id"],
            "asset_id": None,
            "type": "drift",
            "adjudication": adjudication,
            "severity": raw.get("severity", "UNKNOWN" if total else "INFO"),
            "status": status,
            "evidence_refs": [f"terraform-plan:{add}-add-{change}-change-{destroy}-destroy"],
            "confidence": float(raw.get("confidence", 1.0)),
        },
    }
    _validator().validate(record)
    return record



def normalize_terraform_state(raw: dict[str, Any], *, source: dict[str, Any]) -> dict[str, Any]:
    required = ("observation_id", "asset_id", "address", "resource_type")
    missing = [key for key in required if not raw.get(key)]
    if missing:
        raise ValueError(f"terraform state missing required fields: {', '.join(missing)}")

    record = {
        "schema_version": "0.1",
        "record_id": raw["observation_id"],
        "record_type": "observation",
        "source": source,
        "observed_at": raw.get("observed_at") or source["collected_at"],
        "payload": {
            "observation_id": raw["observation_id"],
            "asset_id": raw["asset_id"],
            "fact_type": "config",
            "value": {
                "address": raw["address"],
                "resource_type": raw["resource_type"],
                "native_id": raw.get("native_id"),
                "attributes": raw.get("attributes", {}),
            },
            "unit": None,
            "evidence_refs": raw.get("evidence_refs", []),
            "confidence": float(raw.get("confidence", 1.0)),
        },
    }
    _validator().validate(record)
    return record


def normalize_github_iac(raw: dict[str, Any], *, source: dict[str, Any]) -> dict[str, Any]:
    required = ("observation_id", "asset_id", "repo", "commit", "path")
    missing = [key for key in required if not raw.get(key)]
    if missing:
        raise ValueError(f"github iac observation missing required fields: {', '.join(missing)}")

    record = {
        "schema_version": "0.1",
        "record_id": raw["observation_id"],
        "record_type": "observation",
        "source": source,
        "observed_at": raw.get("observed_at") or source["collected_at"],
        "payload": {
            "observation_id": raw["observation_id"],
            "asset_id": raw["asset_id"],
            "fact_type": "config",
            "value": {
                "repo": raw["repo"],
                "commit": raw["commit"],
                "path": raw["path"],
                "intent": raw.get("intent", {}),
            },
            "unit": None,
            "evidence_refs": raw.get("evidence_refs", []),
            "confidence": float(raw.get("confidence", 1.0)),
        },
    }
    _validator().validate(record)
    return record


def normalize_monitoring(raw: dict[str, Any], *, source: dict[str, Any]) -> dict[str, Any]:
    required = ("observation_id", "asset_id", "metric", "state")
    missing = [key for key in required if not raw.get(key)]
    if missing:
        raise ValueError(f"monitoring observation missing required fields: {', '.join(missing)}")

    record = {
        "schema_version": "0.1",
        "record_id": raw["observation_id"],
        "record_type": "observation",
        "source": source,
        "observed_at": raw.get("observed_at") or source["collected_at"],
        "payload": {
            "observation_id": raw["observation_id"],
            "asset_id": raw["asset_id"],
            "fact_type": "health",
            "value": {
                "metric": raw["metric"],
                "state": raw["state"],
                "value": raw.get("value"),
                "threshold": raw.get("threshold"),
                "window": raw.get("window"),
            },
            "unit": raw.get("unit"),
            "evidence_refs": raw.get("evidence_refs", []),
            "confidence": float(raw.get("confidence", 1.0)),
        },
    }
    _validator().validate(record)
    return record



def normalize_security_rbac(raw: dict[str, Any], *, source: dict[str, Any]) -> dict[str, Any]:
    required = ("observation_id", "asset_id", "scope", "principal_id", "role")
    missing = [key for key in required if not raw.get(key)]
    if missing:
        raise ValueError(f"security/rbac observation missing required fields: {', '.join(missing)}")
    record = {
        "schema_version": "0.1",
        "record_id": raw["observation_id"],
        "record_type": "observation",
        "source": source,
        "observed_at": raw.get("observed_at") or source["collected_at"],
        "payload": {
            "observation_id": raw["observation_id"],
            "asset_id": raw["asset_id"],
            "fact_type": "identity",
            "value": {
                "scope": raw["scope"],
                "principal_id": raw["principal_id"],
                "role": raw["role"],
                "inherited": bool(raw.get("inherited", False)),
                "assignment_id": raw.get("assignment_id"),
                "scope_level": raw.get("scope_level", "unknown"),
            },
            "unit": None,
            "evidence_refs": raw.get("evidence_refs", []),
            "confidence": float(raw.get("confidence", 1.0)),
        },
    }
    _validator().validate(record)
    return record


def normalize_runtime(raw: dict[str, Any], *, source: dict[str, Any]) -> dict[str, Any]:
    required = ("observation_id", "asset_id", "service", "environment", "health")
    missing = [key for key in required if not raw.get(key)]
    if missing:
        raise ValueError(f"runtime observation missing required fields: {', '.join(missing)}")
    record = {
        "schema_version": "0.1",
        "record_id": raw["observation_id"],
        "record_type": "observation",
        "source": source,
        "observed_at": raw.get("observed_at") or source["collected_at"],
        "payload": {
            "observation_id": raw["observation_id"],
            "asset_id": raw["asset_id"],
            "fact_type": "health",
            "value": {
                "service": raw["service"],
                "environment": raw["environment"],
                "health": raw["health"],
                "version": raw.get("version"),
                "endpoint": raw.get("endpoint"),
                "dependencies": raw.get("dependencies", []),
            },
            "unit": None,
            "evidence_refs": raw.get("evidence_refs", []),
            "confidence": float(raw.get("confidence", 1.0)),
        },
    }
    _validator().validate(record)
    return record


def normalize_github_pr(raw: dict[str, Any], *, source: dict[str, Any]) -> dict[str, Any]:
    required = ("observation_id", "repo", "pr_number", "status")
    missing = [key for key in required if not raw.get(key)]
    if missing:
        raise ValueError(f"github PR observation missing required fields: {', '.join(missing)}")
    record = {
        "schema_version": "0.1",
        "record_id": raw["observation_id"],
        "record_type": "observation",
        "source": source,
        "observed_at": raw.get("observed_at") or source["collected_at"],
        "payload": {
            "observation_id": raw["observation_id"],
            "asset_id": raw.get("asset_id"),
            "fact_type": "state",
            "value": {
                "repo": raw["repo"],
                "pr_number": int(raw["pr_number"]),
                "status": raw["status"],
                "draft": bool(raw.get("draft", False)),
                "merge_commit": raw.get("merge_commit"),
                "approvals": raw.get("approvals", []),
            },
            "unit": None,
            "evidence_refs": raw.get("evidence_refs", []),
            "confidence": float(raw.get("confidence", 1.0)),
        },
    }
    _validator().validate(record)
    return record


def normalize_committee_decision(raw: dict[str, Any], *, source: dict[str, Any]) -> dict[str, Any]:
    required = ("decision_id", "decision_type", "authority", "rationale", "status")
    missing = [key for key in required if not raw.get(key)]
    if missing:
        raise ValueError(f"committee decision missing required fields: {', '.join(missing)}")
    record = {
        "schema_version": "0.1",
        "record_id": raw["decision_id"],
        "record_type": "decision",
        "source": source,
        "observed_at": raw.get("observed_at") or source["collected_at"],
        "payload": {
            "decision_id": raw["decision_id"],
            "finding_id": raw.get("finding_id"),
            "decision_type": raw["decision_type"],
            "authority": raw["authority"],
            "rationale": raw["rationale"],
            "conditions": raw.get("conditions", []),
            "status": raw["status"],
        },
    }
    _validator().validate(record)
    return record


def normalize(kind: str, raw: dict[str, Any]) -> dict[str, Any]:
    collected_at = raw.get("collected_at") or raw.get("observed_at") or _utc()
    system_map = {
        "azure-resource": ("azure", "api"),
        "cost": ("cost", "api"),
        "terraform-plan-summary": ("terraform", "plan"),
        "terraform-state": ("terraform", "state"),
        "github-iac": ("github", "repo"),
        "monitoring": ("monitoring", "telemetry"),
        "security-rbac": ("azure", "api"),
        "runtime": ("runtime", "telemetry"),
        "github-pr": ("github", "api"),
        "committee-decision": ("drive", "human_decision"),
    }
    if kind not in system_map:
        raise ValueError(f"unsupported kind: {kind}")

    system, source_type = system_map[kind]
    source = source_record(
        source_id=raw.get("source_id", f"{system}:{_sha256(raw)[:16]}"),
        system=system,
        source_type=source_type,
        collected_at=collected_at,
        location=raw.get("source_location"),
        payload_hash=raw.get("source_hash") or _sha256(raw),
        freshness=raw.get("freshness", "current"),
        trust_level=raw.get("trust_level", "authoritative"),
    )
    if kind == "azure-resource":
        return normalize_azure_resource(raw, source=source)
    if kind == "cost":
        return normalize_cost(raw, source=source)
    if kind == "terraform-plan-summary":
        return normalize_terraform_plan_summary(raw, source=source)
    if kind == "terraform-state":
        return normalize_terraform_state(raw, source=source)
    if kind == "github-iac":
        return normalize_github_iac(raw, source=source)
    if kind == "monitoring":
        return normalize_monitoring(raw, source=source)
    if kind == "security-rbac":
        return normalize_security_rbac(raw, source=source)
    if kind == "runtime":
        return normalize_runtime(raw, source=source)
    if kind == "github-pr":
        return normalize_github_pr(raw, source=source)
    return normalize_committee_decision(raw, source=source)


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Normalize collected Landscape evidence")
    parser.add_argument("--kind", required=True, choices=["azure-resource", "cost", "terraform-plan-summary", "terraform-state", "github-iac", "monitoring", "security-rbac", "runtime", "github-pr", "committee-decision"])
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    raw = json.loads(args.input.read_text(encoding="utf-8"))
    record = normalize(args.kind, raw)
    rendered = json.dumps(record, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
