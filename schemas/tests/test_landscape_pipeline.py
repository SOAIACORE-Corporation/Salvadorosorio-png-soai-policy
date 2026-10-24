from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "landscape"))

from normalize import normalize  # noqa: E402
from pipeline import analyze  # noqa: E402


def test_pipeline_derives_runtime_dependencies_without_deciding():
    runtime = normalize("runtime", {
        "observation_id":"obs:runtime:core","asset_id":"asset:core",
        "service":"core","environment":"p0","health":"Healthy",
        "dependencies":["asset:postgres","asset:keyvault"],
        "observed_at":"2026-09-26T02:00:00Z"
    })
    result = analyze([runtime])
    assert result["derived_dependency_count"] == 2
    assert result["finding_count"] == 0
    assert result["decision_case_count"] == 0


def test_pipeline_runtime_unhealthy_creates_decision_case():
    runtime = normalize("runtime", {
        "observation_id":"obs:runtime:web","asset_id":"asset:web",
        "service":"web","environment":"p0","health":"Unhealthy",
        "dependencies":["asset:core"],
        "observed_at":"2026-09-26T02:00:00Z"
    })
    result = analyze([runtime])
    assert result["finding_count"] == 1
    assert result["decision_case_count"] == 1
    case = result["decision_cases"][0]
    assert case["finding"]["adjudication"] == "PENDING"
    assert case["authority"]["execution_authority"] == "SEPARATE_APPROVAL_REQUIRED"


def test_pipeline_broad_rbac_creates_security_case_not_remove():
    rbac = normalize("security-rbac", {
        "observation_id":"obs:rbac:vault","asset_id":"asset:keyvault",
        "scope":"/subscriptions/sub/resourceGroups/rg/providers/Microsoft.KeyVault/vaults/kv",
        "scope_level":"vault","principal_id":"principal-1","role":"Key Vault Secrets User",
        "observed_at":"2026-09-26T02:00:00Z"
    })
    result = analyze([rbac])
    assert result["finding_count"] == 1
    finding = result["findings"][0]["payload"]
    assert finding["type"] == "security"
    assert finding["adjudication"] == "PENDING"
    assert finding["severity"] == "WARNING"
    assert result["decision_case_count"] == 1


def test_secret_scoped_rbac_does_not_raise_broad_access_case():
    rbac = normalize("security-rbac", {
        "observation_id":"obs:rbac:secret","asset_id":"asset:keyvault",
        "scope":"/subscriptions/sub/resourceGroups/rg/providers/Microsoft.KeyVault/vaults/kv/secrets/db",
        "scope_level":"secret","principal_id":"principal-1","role":"Key Vault Secrets User",
        "observed_at":"2026-09-26T02:00:00Z"
    })
    result = analyze([rbac])
    assert result["finding_count"] == 0
    assert result["decision_case_count"] == 0
