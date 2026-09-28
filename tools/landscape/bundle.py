#!/usr/bin/env python3
"""Build a deterministic read-only Landscape Intelligence bundle."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def bundle_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = sorted(records, key=lambda r: (r["record_type"], r["record_id"]))
    digest = hashlib.sha256(canonical_json(ordered).encode("utf-8")).hexdigest().upper()
    return {
        "bundle_version": "0.1",
        "record_count": len(ordered),
        "record_types": sorted({r["record_type"] for r in ordered}),
        "records": ordered,
        "sha256": digest,
    }


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Build a canonical Landscape Intelligence bundle")
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    records = [json.loads(path.read_text(encoding="utf-8")) for path in args.inputs]
    bundle = bundle_records(records)
    rendered = json.dumps(bundle, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
