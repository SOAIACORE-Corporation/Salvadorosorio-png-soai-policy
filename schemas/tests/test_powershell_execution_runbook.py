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
