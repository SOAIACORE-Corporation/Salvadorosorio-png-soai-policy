[CmdletBinding()]
param(
    [switch]$Apply,
    [switch]$AuthorizeIam,
    [string]$SubscriptionId = '108eb4dd-25b3-4a7f-8d5e-4ec4389c3f0d',
    [string]$Location = 'eastus2',
    [string]$BootstrapResourceGroup = 'rg-soa-intelligence-bootstrap',
    [string]$IdentityName = 'id-soa-intelligence-gha-dev',
    [string]$Repository = 'SOAIACORE-Corporation/Salvadorosorio-png-soai-policy',
    [string]$FeatureBranch = 'feature/soa-intelligence-a2-postgres-20260906-r2',
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
    throw 'Authenticated subscription does not match expected subscription. Refusing to continue.'
}

$tenantId = [string]$account.tenantId
Write-Boundary 'AZURE_ACCOUNT_CONTEXT' 'PASS'
Write-Boundary 'SUBSCRIPTION_MATCH' 'PASS'
Write-Boundary 'MODE' ($(if ($Apply) { 'APPLY' } else { 'PLAN_ONLY' }))
Write-Boundary 'IAM_AUTHORIZED' ($(if ($AuthorizeIam) { 'YES' } else { 'NO' }))

$issuer = 'https://token.actions.githubusercontent.com'
$audience = 'api://AzureADTokenExchange'
$featureSubject = "repo:${Repository}:ref:refs/heads/${FeatureBranch}"
$mainSubject = "repo:${Repository}:ref:refs/heads/main"

Write-Host ''
Write-Host 'Planned identity:'
Write-Host "  resource-group:  $BootstrapResourceGroup"
Write-Host "  identity:        $IdentityName"
Write-Host "  feature subject: $featureSubject"
Write-Host "  main subject:    $mainSubject"
Write-Host '  generic PR subject: FORBIDDEN / removed if present'
Write-Host ''

if (-not $Apply) {
    Write-Host 'PLAN_ONLY: no Azure resources, federated credentials, or RBAC assignments were changed.'
    Write-Host 'To execute identity/federation reconciliation, rerun with -Apply.'
    Write-Host 'To also ensure the narrowly-scoped backend read roles, use -Apply -AuthorizeIam.'
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
        $existingObject = $existing | ConvertFrom-Json
        $existingIssuer = [string]$existingObject.issuer
        $existingSubject = [string]$existingObject.subject
        $existingAudiences = @($existingObject.audiences | ForEach-Object { [string]$_ })

        if ($existingIssuer -ne $issuer) {
            throw "Federated credential '$Name' exists with an unexpected issuer. Refusing implicit replacement."
        }
        if ($existingSubject -ne $Subject) {
            throw "Federated credential '$Name' exists with an unexpected subject. Refusing implicit replacement."
        }
        if ($existingAudiences.Count -ne 1 -or $existingAudiences[0] -ne $audience) {
            throw "Federated credential '$Name' exists with an unexpected audience set. Refusing implicit replacement."
        }

        Write-Boundary ("FEDERATED_CREDENTIAL_{0}_CREATED" -f $Name.ToUpperInvariant()) 'false'
        Write-Boundary ("FEDERATED_CREDENTIAL_{0}_ISSUER_MATCH" -f $Name.ToUpperInvariant()) 'true'
        Write-Boundary ("FEDERATED_CREDENTIAL_{0}_SUBJECT_MATCH" -f $Name.ToUpperInvariant()) 'true'
        Write-Boundary ("FEDERATED_CREDENTIAL_{0}_AUDIENCE_MATCH" -f $Name.ToUpperInvariant()) 'true'
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
    Write-Boundary ("FEDERATED_CREDENTIAL_{0}_ISSUER_MATCH" -f $Name.ToUpperInvariant()) 'true'
    Write-Boundary ("FEDERATED_CREDENTIAL_{0}_SUBJECT_MATCH" -f $Name.ToUpperInvariant()) 'true'
    Write-Boundary ("FEDERATED_CREDENTIAL_{0}_AUDIENCE_MATCH" -f $Name.ToUpperInvariant()) 'true'
}

function Ensure-RoleAssignment {
    param(
        [Parameter(Mandatory)][string]$RoleName,
        [Parameter(Mandatory)][string]$Scope,
        [Parameter(Mandatory)][string]$BoundaryName
    )

    $existingAssignmentId = & az role assignment list `
        --assignee $principalId `
        --role $RoleName `
        --scope $Scope `
        --query '[0].id' `
        --output tsv `
        --only-show-errors
    if ($LASTEXITCODE -ne 0) {
        throw "Failed checking existing role assignment '$RoleName' at scope '$Scope'."
    }

    if (-not [string]::IsNullOrWhiteSpace([string]$existingAssignmentId)) {
        Write-Boundary $BoundaryName 'present'
        return
    }

    & az role assignment create `
        --assignee-object-id $principalId `
        --assignee-principal-type ServicePrincipal `
        --role $RoleName `
        --scope $Scope `
        --only-show-errors --output none
    if ($LASTEXITCODE -ne 0) {
        throw "Failed creating role assignment '$RoleName' at scope '$Scope'."
    }
    Write-Boundary $BoundaryName 'created'
}

# Security hardening: a generic repo:...:pull_request subject is too broad for a public repository.
$legacyPrCredential = & az identity federated-credential show `
    --resource-group $BootstrapResourceGroup `
    --identity-name $IdentityName `
    --name 'github-pr' `
    --only-show-errors --output json 2>$null
if ($LASTEXITCODE -eq 0) {
    & az identity federated-credential delete `
        --resource-group $BootstrapResourceGroup `
        --identity-name $IdentityName `
        --name 'github-pr' `
        --yes `
        --only-show-errors
    if ($LASTEXITCODE -ne 0) { throw 'Failed removing legacy generic PR federated credential.' }
    Write-Boundary 'LEGACY_GENERIC_PR_CREDENTIAL_REMOVED' 'true'
} else {
    Write-Boundary 'LEGACY_GENERIC_PR_CREDENTIAL_REMOVED' 'false'
}

Ensure-FederatedCredential -Name 'github-feature-a2' -Subject $featureSubject
Ensure-FederatedCredential -Name 'github-main' -Subject $mainSubject

if ($AuthorizeIam) {
    $stateRgId = & az group show --name $StateResourceGroup --query id --output tsv --only-show-errors
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($stateRgId)) { throw 'State resource group not found.' }

    $storageId = & az storage account show `
        --resource-group $StateResourceGroup `
        --name $StateStorageAccount `
        --query id --output tsv --only-show-errors
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($storageId)) { throw 'State storage account not found.' }

    Ensure-RoleAssignment -RoleName 'Reader' -Scope $stateRgId -BoundaryName 'STATE_RG_READER'
    Ensure-RoleAssignment -RoleName 'Storage Blob Data Reader' -Scope $storageId -BoundaryName 'STATE_BLOB_DATA_READER'
} else {
    Write-Host 'IAM NOT CHANGED. OIDC federation was reconciled, but backend preflight requires the scoped read roles.'
}

Write-Host ''
Write-Host 'Non-secret GitHub configuration values:'
Write-Host "AZURE_CLIENT_ID=$clientId"
Write-Host "AZURE_TENANT_ID=$tenantId"
Write-Host "AZURE_SUBSCRIPTION_ID=$SubscriptionId"
Write-Host ''
Write-Host 'These identifiers are not credentials. Do not store passwords or client secrets.'
Write-Boundary 'GENERIC_PULL_REQUEST_FEDERATION_PRESENT' 'false'
Write-Boundary 'CLIENT_SECRET_CREATED' 'false'
Write-Boundary 'SUBSCRIPTION_CONTRIBUTOR_GRANTED' 'false'
Write-Boundary 'BOOTSTRAP_STATUS' 'PASS'
