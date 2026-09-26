from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "azure" / "Invoke-SOAIntelligenceBootstrapPreflight.ps1"


def test_powershell_preflight_exists_and_is_read_only_by_default():
    text = SCRIPT.read_text(encoding="utf-8")
    assert "PREFLIGHT_MODE' 'READ_ONLY" in text
    assert "MUTATION_PARAMETERS_PRESENT' 'false" in text
    assert "AZURE_MUTATION' 'false" in text
    assert "& $BootstrapScript" in text
    assert "& $BootstrapScript -Apply" not in text
    assert "& $BootstrapScript -AuthorizeIam" not in text


def test_powershell_preflight_checks_shell_path_az_and_auth():
    text = SCRIPT.read_text(encoding="utf-8")
    assert "$PSVersionTable.PSEdition" in text
    assert "$PSVersionTable.PSVersion" in text
    assert "Test-Path -LiteralPath $BootstrapScript" in text
    assert "Get-Command az" in text
    assert "az account show --only-show-errors --output none" in text


def test_powershell_preflight_avoids_pwsh7_only_shortcuts():
    text = SCRIPT.read_text(encoding="utf-8")
    assert "&&" not in text
    assert "??" not in text


def test_bootstrap_uses_isolated_landscape_oidc_credential_and_branch():
    bootstrap = (ROOT / "scripts" / "azure" / "Bootstrap-SOAIntelligenceGitHubOidc.ps1").read_text(encoding="utf-8")
    assert "[string]$FeatureBranch = 'feat/landscape-intelligence-data-model-v1'" in bootstrap
    assert "[string]$FeatureCredentialName = 'github-landscape-intelligence-v1'" in bootstrap
    assert "Ensure-FederatedCredential -Name $FeatureCredentialName -Subject $featureSubject" in bootstrap
    assert "Ensure-FederatedCredential -Name 'github-feature-a2' -Subject $featureSubject" not in bootstrap
    assert "Get-FederatedCredentialByName -Name 'github-pr'" in bootstrap


def test_azure_auth_workflow_listens_to_landscape_branch():
    workflow = (ROOT / ".github" / "workflows" / "azure-soa-intelligence-auth-preflight.yml").read_text(encoding="utf-8")
    assert "- feat/landscape-intelligence-data-model-v1" in workflow
