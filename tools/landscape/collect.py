#!/usr/bin/env python3
"""Manifest-driven, read-only Landscape Intelligence collector.

It consumes already-collected source files, normalizes them, and emits one
deterministic canonical bundle. It performs no external calls.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from bundle import bundle_records
from normalize import normalize


def collect_manifest(manifest: dict[str, Any], *, base_dir: Path) -> dict[str, Any]:
    version = manifest.get("manifest_version")
    if version != "0.1":
        raise ValueError(f"unsupported manifest_version: {version}")

    entries = manifest.get("sources")
    if not isinstance(entries, list) or not entries:
        raise ValueError("manifest sources must be a non-empty list")

    records = []
    for entry in entries:
        kind = entry.get("kind")
        rel = entry.get("path")
        if not kind or not rel:
            raise ValueError("each source entry requires kind and path")
        path = (base_dir / rel).resolve()
        try:
            path.relative_to(base_dir.resolve())
        except ValueError as exc:
            raise ValueError(f"source path escapes base directory: {rel}") from exc
        raw = json.loads(path.read_text(encoding="utf-8"))
        records.append(normalize(kind, raw))

    bundle = bundle_records(records)
    bundle["manifest_version"] = version
    bundle["source_count"] = len(entries)
    return bundle


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Collect normalized Landscape records from a local manifest")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    manifest_path = args.manifest.resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    result = collect_manifest(manifest, base_dir=manifest_path.parent)
    rendered = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
