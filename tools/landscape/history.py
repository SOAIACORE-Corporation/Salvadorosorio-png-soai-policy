#!/usr/bin/env python3
"""Append-only local historical store for Landscape Intelligence bundles.

This is a read-only infrastructure capability: it persists analysis artifacts
to local files only. It performs no cloud or database writes.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest().upper()


def snapshot_id(bundle: dict[str, Any], observed_at: str) -> str:
    return f"{observed_at.replace(':','').replace('-','')}-{bundle['sha256'][:12]}"


def persist_snapshot(
    root: Path,
    *,
    bundle: dict[str, Any],
    analysis: dict[str, Any],
    observed_at: str | None = None,
) -> Path:
    observed_at = observed_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    sid = snapshot_id(bundle, observed_at)
    target = root / sid
    target.mkdir(parents=True, exist_ok=False)

    manifest = {
        "history_version": "0.1",
        "snapshot_id": sid,
        "observed_at": observed_at,
        "bundle_sha256": bundle["sha256"],
        "bundle_record_count": bundle["record_count"],
        "analysis_sha256": _sha(analysis),
        "finding_count": analysis.get("finding_count", 0),
        "impact_count": analysis.get("impact_count", 0),
        "decision_case_count": analysis.get("decision_case_count", 0),
    }
    (target / "bundle.json").write_text(json.dumps(bundle, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (target / "analysis.json").write_text(json.dumps(analysis, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (target / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return target


def list_snapshots(root: Path) -> list[dict[str, Any]]:
    if not root.exists():
        return []
    result = []
    for path in sorted(p for p in root.iterdir() if p.is_dir()):
        manifest = path / "manifest.json"
        if manifest.exists():
            result.append(json.loads(manifest.read_text(encoding="utf-8")))
    return result


def load_snapshot(root: Path, sid: str) -> dict[str, Any]:
    target = root / sid
    return {
        "manifest": json.loads((target / "manifest.json").read_text(encoding="utf-8")),
        "bundle": json.loads((target / "bundle.json").read_text(encoding="utf-8")),
        "analysis": json.loads((target / "analysis.json").read_text(encoding="utf-8")),
    }


def diff_snapshots(previous: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    def keyed(records):
        return {r["record_id"]: r for r in records}

    prev = keyed(previous["bundle"]["records"])
    curr = keyed(current["bundle"]["records"])

    added = sorted(set(curr) - set(prev))
    removed = sorted(set(prev) - set(curr))
    changed = sorted(
        rid for rid in set(prev) & set(curr)
        if _canonical(prev[rid]) != _canonical(curr[rid])
    )

    prev_findings = {f["record_id"] for f in previous["analysis"].get("findings", [])}
    curr_findings = {f["record_id"] for f in current["analysis"].get("findings", [])}

    return {
        "history_diff_version": "0.1",
        "added_record_ids": added,
        "removed_record_ids": removed,
        "changed_record_ids": changed,
        "new_finding_ids": sorted(curr_findings - prev_findings),
        "resolved_finding_ids": sorted(prev_findings - curr_findings),
        "unchanged": not (added or removed or changed or prev_findings != curr_findings),
    }
