from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "azure" / "Invoke-SOAIntelligenceBootstrapPreflight.ps1"
LAUNCHER = ROOT / "scripts" / "azure" / "Invoke-SOAIntelligenceBootstrapPreflight.cmd"


def test_preflight_detects_execution_policy_refspec_and_workspace_risk():
    text = SCRIPT.read_text(encoding="utf-8")
    assert "Get-ExecutionPolicy -Scope Process" in text
    assert "Get-ExecutionPolicy -Scope CurrentUser" in text
    assert "git -C $RepoRoot config --get-all remote.origin.fetch" in text
    assert "GIT_REFSPEC_RESTRICTED" in text
    assert "git -C $RepoRoot status --porcelain" in text
    assert "WORKSPACE_BRANCH_MUTATION_RISK" in text


def test_cmd_launcher_handles_process_scoped_execution_policy():
    text = LAUNCHER.read_text(encoding="utf-8")
    assert "powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass" in text
    assert "Invoke-SOAIntelligenceBootstrapPreflight.ps1" in text
