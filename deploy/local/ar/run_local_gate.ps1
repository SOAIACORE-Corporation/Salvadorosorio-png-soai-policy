$ErrorActionPreference = 'Stop'
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = (Resolve-Path (Join-Path $Here '..\..\..')).Path
$Compose = Join-Path $Here 'docker-compose.persistence.yml'

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error 'BLOCKED: Docker Desktop / docker CLI no está instalado o no está en PATH.'
    exit 20
}

docker compose version | Out-Null

function Cleanup-Gate {
    try { docker compose -f $Compose down -v --remove-orphans | Out-Null } catch {}
}

Cleanup-Gate
try {
    docker compose -f $Compose up -d postgres
    $ready = $false
    for ($i=0; $i -lt 60; $i++) {
        docker compose -f $Compose exec -T postgres pg_isready -U soaiacore -d soaiacore 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) { $ready = $true; break }
        Start-Sleep -Seconds 2
    }
    if (-not $ready) { throw 'FAIL: PostgreSQL no quedó listo.' }

    docker compose -f $Compose exec -T postgres psql -v ON_ERROR_STOP=1 -U soaiacore -d soaiacore -c "SELECT extname FROM pg_extension WHERE extname='vector';"
    docker compose -f $Compose exec -T postgres psql -v ON_ERROR_STOP=1 -U soaiacore -d soaiacore -c "SELECT count(*) AS canonical_tables FROM information_schema.tables WHERE table_schema IN ('soa_core','soa_identity','soa_evidence','soa_intelligence','soa_adjudication','soa_ops');"

    Get-Content -Raw (Join-Path $Root 'db/tests/seed_minimal.sql') | docker compose -f $Compose exec -T postgres psql -v ON_ERROR_STOP=1 -U soaiacore -d soaiacore
    if ($LASTEXITCODE -ne 0) { throw 'FAIL seed_minimal.sql' }

    Get-Content -Raw (Join-Path $Root 'db/tests/architecture_invariants.sql') | docker compose -f $Compose exec -T postgres psql -v ON_ERROR_STOP=1 -U soaiacore -d soaiacore
    if ($LASTEXITCODE -ne 0) { throw 'FAIL architecture_invariants.sql' }

    Get-Content -Raw (Join-Path $Root 'db/tests/integrity_checks.sql') | docker compose -f $Compose exec -T postgres psql -v ON_ERROR_STOP=1 -U soaiacore -d soaiacore
    if ($LASTEXITCODE -ne 0) { throw 'FAIL integrity_checks.sql' }

    Write-Host 'SOAIACORE_LOCAL_POSTGRES_GATE=PASS'
}
finally {
    Cleanup-Gate
}
