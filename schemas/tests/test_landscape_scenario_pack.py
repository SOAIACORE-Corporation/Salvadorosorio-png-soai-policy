from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "landscape"))

from normalize import normalize  # noqa: E402
from pipeline import analyze  # noqa: E402


def test_simple_missing_owner_remains_visible():
    asset = normalize("azure-resource", {
        "subscription_id":"sub","resource_id":"res1","name":"res1",
        "resource_type":"generic","environment":"prod","owner":None,
        "observed_at":"2026-09-26T03:00:00Z"
    })
    assert asset["payload"]["owner"] is None
    result = analyze([asset])
    assert result["finding_count"] == 1
    assert result["findings"][0]["payload"]["type"] == "governance"
    assert result["findings"][0]["payload"]["adjudication"] == "VISIBILITY_GAP"


def test_zero_cost_is_distinct_from_unknown_cost():
    zero = normalize("cost", {
        "cost_id":"cost:zero","scope_id":"asset:x","period":"2026-09",
        "amount":0.0,"currency":"USD","cost_type":"observed",
        "observed_at":"2026-09-26T03:00:00Z"
    })
    unknown = normalize("cost", {
        "cost_id":"cost:unknown","scope_id":"asset:y","period":"2026-09",
        "amount":None,"currency":"USD",
        "observed_at":"2026-09-26T03:00:00Z"
    })
    assert zero["payload"]["amount"] == 0.0
    assert zero["payload"]["cost_type"] == "observed"
    assert unknown["payload"]["amount"] is None
    assert unknown["payload"]["cost_type"] == "unknown"


def test_draft_pr_never_becomes_decision():
    pr = normalize("github-pr", {
        "observation_id":"obs:pr:84","repo":"org/repo","pr_number":84,
        "status":"open","draft":True,"observed_at":"2026-09-26T03:00:00Z"
    })
    assert pr["record_type"] == "observation"
    assert pr["payload"]["value"]["draft"] is True


def test_broad_rbac_security_case_is_inferred_from_visibility():
    rbac = normalize("security-rbac", {
        "observation_id":"obs:rbac:vault","asset_id":"asset:keyvault",
        "scope":"/kv","scope_level":"vault","principal_id":"p1",
        "role":"Key Vault Secrets User","observed_at":"2026-09-26T03:00:00Z"
    })
    result = analyze([rbac])
    assert result["finding_count"] == 1
    assert result["findings"][0]["payload"]["type"] == "security"


def test_simple_runtime_dependency_is_derived_without_incident():
    runtime = normalize("runtime", {
        "observation_id":"obs:runtime:core","asset_id":"asset:core",
        "service":"core","environment":"prod","health":"Healthy",
        "dependencies":["asset:db"],"observed_at":"2026-09-26T03:00:00Z"
    })
    result = analyze([runtime])
    assert result["derived_dependency_count"] == 1
    assert result["finding_count"] == 0
