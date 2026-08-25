[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

$credentialPath = Join-Path $PSScriptRoot "p0-ghcr-credential.clixml"
$repoRoot = (& git -C $PSScriptRoot rev-parse --show-toplevel).Trim()
if (-not $repoRoot) {
    throw "No se pudo localizar el repositorio Git."
}

$relativeCredentialPath = [System.IO.Path]::GetRelativePath(
    $repoRoot,
    $credentialPath
).Replace("\", "/")

& git -C $repoRoot check-ignore -q -- $relativeCredentialPath
if ($LASTEXITCODE -ne 0) {
    throw "El archivo cifrado no esta ignorado por Git. No se guardo ningun secreto."
}

if (Test-Path -LiteralPath $credentialPath) {
    throw "Ya existe una credencial P0 cifrada. No se sobrescribio."
}

Write-Host "Configuracion cifrada de GHCR para P0"
Write-Host "El PAT no se mostrara ni se guardara como texto."
Write-Host ""

$ghcrUsername = $null
while ($ghcrUsername -notmatch '^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$') {
    $ghcrUsername = Read-Host "Escribe solamente el usuario de GitHub (ejemplo: ozesnoso0903)"
    if ($ghcrUsername -notmatch '^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$') {
        Write-Warning "Usuario invalido. Escribe solamente el nombre."
    }
}

$secureToken = $null
while ($null -eq $secureToken -or $secureToken.Length -eq 0) {
    $secureToken = Read-Host "Pega el PAT classic con scope read:packages" -AsSecureString
    if ($secureToken.Length -eq 0) {
        Write-Warning "No se recibio ningun valor. Pega el PAT y pulsa Enter."
    }
}

$credential = [System.Management.Automation.PSCredential]::new(
    $ghcrUsername,
    $secureToken
)
$credential | Export-Clixml -LiteralPath $credentialPath -Force

$currentSid = [System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value
$currentUserGrant = "*$($currentSid):(F)"
& icacls.exe $credentialPath `
    "/inheritance:r" `
    "/grant:r" `
    $currentUserGrant `
    "*S-1-5-18:(F)" `
    "*S-1-5-32-544:(F)" | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "El PAT quedo cifrado con DPAPI, pero no se pudo restringir la ACL local."
}

$secureToken = $null
$credential = $null

Write-Host ""
Write-Host "CREDENTIAL_READY=true"
Write-Host "El PAT quedo cifrado con Windows DPAPI para este usuario."
Write-Host "Vuelve a Codex y escribe: listo"
