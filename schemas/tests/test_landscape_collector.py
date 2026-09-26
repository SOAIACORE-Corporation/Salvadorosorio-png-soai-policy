from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "landscape"))

from collect import collect_manifest  # noqa: E402


def test_manifest_collector_emits_deterministic_bundle(tmp_path):
    azure = {
        "subscription_id": "sub",
        "resource_id": "psql",
        "name": "psql",
        "resource_type": "postgresql_flexible_server",
        "environment": "p0",
        "observed_at": "2026-09-25T22:29:14Z",
    }
    cost = {
        "cost_id": "cost:test",
        "scope_id": "SOAiaCore",
        "period": "2026-09",
        "amount": 10.0,
        "currency": "USD",
        "cost_type": "observed",
        "observed_at": "2026-09-25T22:29:14Z",
    }
    (tmp_path / "azure.json").write_text(json.dumps(azure), encoding="utf-8")
    (tmp_path / "cost.json").write_text(json.dumps(cost), encoding="utf-8")
    manifest = {
        "manifest_version": "0.1",
        "sources": [
            {"kind": "azure-resource", "path": "azure.json"},
            {"kind": "cost", "path": "cost.json"},
        ],
    }
    first = collect_manifest(manifest, base_dir=tmp_path)
    second = collect_manifest(manifest, base_dir=tmp_path)
    assert first["sha256"] == second["sha256"]
    assert first["record_count"] == 2
    assert first["source_count"] == 2


def test_manifest_collector_rejects_empty_sources(tmp_path):
    try:
        collect_manifest({"manifest_version": "0.1", "sources": []}, base_dir=tmp_path)
    except ValueError as exc:
        assert "non-empty" in str(exc)
    else:
        raise AssertionError("empty collector manifest must fail")


def test_manifest_collector_rejects_path_escape(tmp_path):
    outside = tmp_path.parent / "outside.json"
    outside.write_text("{}", encoding="utf-8")
    manifest = {
        "manifest_version": "0.1",
        "sources": [{"kind": "cost", "path": "../outside.json"}],
    }
    try:
        collect_manifest(manifest, base_dir=tmp_path)
    except ValueError as exc:
        assert "escapes base directory" in str(exc)
    else:
        raise AssertionError("collector must not read outside manifest base directory")
