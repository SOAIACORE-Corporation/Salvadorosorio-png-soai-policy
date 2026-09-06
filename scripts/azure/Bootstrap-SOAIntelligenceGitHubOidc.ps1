[CmdletBinding()]
param(
    [switch]$Apply,
    [switch]$AuthorizeIam,
    [string]$SubscriptionId = '108eb4dd-25b3-4a7f-8d5e-4ec4389c3f0d',
    [string]$Location = 'eastus2',
    [string]$BootstrapResourceGroup = 'rg-soa-intelligence-bootstrap',
    [string]$IdentityName = 'id-soa-intelligence-gha-dev',
    [string]$Repository = 'SOAIACORE-Corporation/Salvadorosorio-png-soai-policy',
    [string]$StateResourceGroup = 'rg-soaiacore-tfstate-34utxi',
    [string]$StateStorageAccount = 'stsoaiacoretf34utxi'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Invoke-AzJson {
    param([Parameter(Mandatory)][string[]]$Arguments)
    $raw = & az @Arguments --only-show-errors --output json
    if ($LASTEXITCODE -ne 0) {
        throw "Azure CLI command failed: az $($Arguments -join ' ')"
    }
    if ([string]::IsNullOrWhiteSpace($raw)) { return $null }
    return $raw | ConvertFrom-Json
}

function Write-Boundary {
    param([string]$Name, [string]$Value)
    Write-Host ("{0}={1}" -f $Name, $Value)
}

$account = Invoke-AzJson -Arguments @('account','show')
if (-not $account) { throw 'Azure CLI is not authenticated. Run az login / Cloud Shell first.' }
if ($account.id -ne $SubscriptionId) {
    throw "Authenticated subscription does not match expected subscription. Refusing to continue."
}

$tenantId = [string]$account.tenantId
Write-Boundary 'AZURE_ACCOUNT_CONTEXT' 'PASS'
Write-Boundary 'SUBSCRIPTION_MATCH' 'PASS'
Write-Boundary 'MODE' ($(if ($Apply) { 'APPLY' } else { 'PLAN_ONLY' }))
Write-Boundary 'IAM_AUTHORIZED' ($(if ($AuthorizeIam) { 'YES' } else { 'NO' }))

$issuer = 'https://token.actions.githubusercontent.com'
$audience = 'api://AzureADTokenExchange'
$prSubject = "repo:${Repository}:pull_request"
$mainSubject = "repo:${Repository}:ref:refs/heads/main"

Write-Host ''
Write-Host 'Planned identity:'
Write-Host "  resource-group: $BootstrapResourceGroup"
Write-Host "  identity:       $IdentityName"
Write-Host "  PR subject:     $prSubject"
Write-Host "  main subject:   $mainSubject"
Write-Host ''

if (-not $Apply) {
    Write-Host 'PLAN_ONLY: no Azure resources or RBAC assignments were changed.'
    Write-Host 'To execute identity creation, rerun with -Apply.'
    Write-Host 'To also grant the narrowly-scoped preflight RBAC roles, use -Apply -AuthorizeIam.'
    Write-Boundary 'AZURE_MUTATION' 'false'
    exit 0
}

$rg = & az group show --name $BootstrapResourceGroup --only-show-errors --output json 2>$null
if ($LASTEXITCODE -ne 0) {
    Invoke-AzJson -Arguments @('group','create','--name',$BootstrapResourceGroup,'--location',$Location) | Out-Null
    Write-Boundary 'BOOTSTRAP_RESOURCE_GROUP_CREATED' 'true'
} else {
    Write-Boundary 'BOOTSTRAP_RESOURCE_GROUP_CREATED' 'false'
}

$identityRaw = & az identity show --resource-group $BootstrapResourceGroup --name $IdentityName --only-show-errors --output json 2>$null
if ($LASTEXITCODE -ne 0) {
    $identity = Invoke-AzJson -Arguments @('identity','create','--resource-group',$BootstrapResourceGroup,'--name',$IdentityName,'--location',$Location)
    Write-Boundary 'USER_ASSIGNED_IDENTITY_CREATED' 'true'
} else {
    $identity = $identityRaw | ConvertFrom-Json
    Write-Boundary 'USER_ASSIGNED_IDENTITY_CREATED' 'false'
}

$clientId = [string]$identity.clientId
$principalId = [string]$identity.principalId
if ([string]::IsNullOrWhiteSpace($clientId) -or [string]::IsNullOrWhiteSpace($principalId)) {
    throw 'Managed identity did not return clientId/principalId.'
}

function Ensure-FederatedCredential {
    param(
        [Parameter(Mandatory)][string]$Name,
        [Parameter(Mandatory)][string]$Subject
    )

    $existing = & az identity federated-credential show `
        --resource-group $BootstrapResourceGroup `
        --identity-name $IdentityName `
        --name $Name `
        --only-show-errors --output json 2>$null

    if ($LASTEXITCODE -eq 0) {
        Write-Boundary ("FEDERATED_CREDENTIAL_{0}_CREATED" -f $Name.ToUpperInvariant()) 'false'
        return
    }

    Invoke-AzJson -Arguments @(
        'identity','federated-credential','create',
        '--resource-group',$BootstrapResourceGroup,
        '--identity-name',$IdentityName,
        '--name',$Name,
        '--issuer',$issuer,
        '--subject',$Subject,
        '--audiences',$audience
    ) | Out-Null
    Write-Boundary ("FEDERATED_CREDENTIAL_{0}_CREATED" -f $Name.ToUpperInvariant()) 'true'
}

Ensure-FederatedCredential -Name 'github-pr' -Subject $prSubject
Ensure-FederatedCredential -Name 'github-main' -Subject $mainSubject

if ($AuthorizeIam) {
    $stateRgId = & az group show --name $StateResourceGroup --query id --output tsv --only-show-errors
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($stateRgId)) { throw 'State resource group not found.' }

    $storageId = & az storage account show `
        --resource-group $StateResourceGroup `
        --name $StateStorageAccount `
        --query id --output tsv --only-show-errors
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($storageId)) { throw 'State storage account not found.' }

    & az role assignment create `
        --assignee-object-id $principalId `
        --assignee-principal-type ServicePrincipal `
        --role Reader `
        --scope $stateRgId `
        --only-show-errors --output none
    if ($LASTEXITCODE -ne 0) { throw 'Failed assigning Reader on state resource group.' }

    & az role assignment create `
        --assignee-object-id $principalId `
        --assignee-principal-type ServicePrincipal `
        --role 'Storage Blob Data Reader' `
        --scope $storageId `
        --only-show-errors --output none
    if ($LASTEXITCODE -ne 0) { throw 'Failed assigning Storage Blob Data Reader on state account.' }

    Write-Boundary 'STATE_RG_READER_GRANTED' 'true'
    Write-Boundary 'STATE_BLOB_DATA_READER_GRANTED' 'true'
} else {
    Write-Host 'IAM NOT CHANGED. OIDC identity exists, but the backend preflight will still require scoped read roles.'
}

Write-Host ''
Write-Host 'Non-secret GitHub configuration values:'
Write-Host "AZURE_CLIENT_ID=$clientId"
Write-Host "AZURE_TENANT_ID=$tenantId"
Write-Host "AZURE_SUBSCRIPTION_ID=$SubscriptionId"
Write-Host ''
Write-Host 'These identifiers are not credentials. Do not store passwords or client secrets.'
Write-Boundary 'CLIENT_SECRET_CREATED' 'false'
Write-Boundary 'SUBSCRIPTION_CONTRIBUTOR_GRANTED' 'false'
Write-Boundary 'BOOTSTRAP_STATUS' 'PASS'
