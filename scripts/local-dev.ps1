# ---------------------------------------------------------------------------
# Start the whole platform locally, with no paid services and no Docker.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts/local-dev.ps1
#
# What it does:
#   1. loads the root .env into this process
#   2. checks the PostgreSQL connection
#   3. applies Alembic migrations
#   4. starts the API on the API_INTERNAL_URL port (default 8010)
#   5. starts the Next.js dashboard on port 3000
#
# Optional switches:
#   -SkipMigrate   do not run alembic upgrade head
#   -SkipApi       do not start the API (e.g. it is already running)
#   -SkipWeb       do not start the dashboard
#   -NoBrowser     do not open the login page
# ---------------------------------------------------------------------------
param(
    [switch]$SkipMigrate,
    [switch]$SkipApi,
    [switch]$SkipWeb,
    [switch]$NoBrowser
)

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$apiDir = Join-Path $root 'apps\api'
$webDir = Join-Path $root 'apps\web'
$python = Join-Path $root '.venv\Scripts\python.exe'
$alembic = Join-Path $root '.venv\Scripts\alembic.exe'
$uvicorn = Join-Path $root '.venv\Scripts\uvicorn.exe'
$envFile = Join-Path $root '.env'

function Write-Step($message) {
    Write-Host ""
    Write-Host "==> $message" -ForegroundColor Cyan
}

function Test-Port($port) {
    $listeners = Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue
    return [bool]$listeners
}

# --- 1. Load .env ----------------------------------------------------------
Write-Step "Loading $envFile"
if (-not (Test-Path $envFile)) {
    throw "Missing .env. Copy .env.example to .env and set DATABASE_URL first."
}

Get-Content $envFile | ForEach-Object {
    $line = $_.Trim()
    if ($line.Length -eq 0 -or $line.StartsWith('#')) { return }
    $splitAt = $line.IndexOf('=')
    if ($splitAt -lt 1) { return }
    $name = $line.Substring(0, $splitAt).Trim()
    $value = $line.Substring($splitAt + 1).Trim()
    if ($value.Length -ge 2) {
        $first = $value.Substring(0, 1)
        $last = $value.Substring($value.Length - 1, 1)
        if (($first -eq '"' -and $last -eq '"') -or ($first -eq "'" -and $last -eq "'")) {
            $value = $value.Substring(1, $value.Length - 2)
        }
    }
    Set-Item -Path ("Env:" + $name) -Value $value
}

if (-not $env:DATABASE_URL) { throw "DATABASE_URL is not set in .env" }
if (-not $env:JWT_SECRET) { throw "JWT_SECRET is not set in .env" }

$apiUrl = $env:API_INTERNAL_URL
if (-not $apiUrl) { $apiUrl = 'http://127.0.0.1:8010' }
$apiUrl = $apiUrl.TrimEnd('/')
$apiPort = ([Uri]$apiUrl).Port
$webPort = 3000

Write-Host "API:       $apiUrl"
Write-Host "Dashboard: http://localhost:$webPort"
Write-Host "Database:  $($env:DATABASE_URL)"
Write-Host "Email:     $($env:EMAIL_PROVIDER) (no real sends)"
Write-Host "Redis:     $(if ($env:REDIS_URL) { $env:REDIS_URL } else { 'disabled (in-process fallback)' })"

# --- 2. Check the database -------------------------------------------------
Write-Step "Checking the database connection"
$dbCheck = @'
import os
import sys
from sqlalchemy import create_engine, text

engine = create_engine(os.environ["DATABASE_URL"], connect_args={"connect_timeout": 5})
with engine.connect() as connection:
    connection.execute(text("select 1"))
engine.dispose()
print("Database connection OK")
'@
$dbCheck | & $python -
if ($LASTEXITCODE -ne 0) {
    throw "Cannot reach PostgreSQL. Check DATABASE_URL in .env and make sure the server is running."
}

# --- 3. Migrations ---------------------------------------------------------
if (-not $SkipMigrate) {
    Write-Step "Applying database migrations"
    Push-Location $apiDir
    try {
        & $alembic upgrade head
        if ($LASTEXITCODE -ne 0) { throw "alembic upgrade head failed." }
    }
    finally {
        Pop-Location
    }
}

# --- 4. Dashboard env ------------------------------------------------------
# Next.js reads env vars from apps/web, not the repository root.
$webEnv = Join-Path $webDir '.env.local'
$desired = "API_INTERNAL_URL=$apiUrl"
$lines = @()
if (Test-Path $webEnv) { $lines = @(Get-Content $webEnv) }
$found = $false
$updated = @()
foreach ($line in $lines) {
    if ($line -match '^\s*API_INTERNAL_URL\s*=') {
        $updated += $desired
        $found = $true
    }
    else {
        $updated += $line
    }
}
if (-not $found) { $updated += $desired }
$updated | Set-Content -Path $webEnv -Encoding ASCII
Write-Host "Wrote $webEnv -> $desired"

# --- 5. API ----------------------------------------------------------------
if (-not $SkipApi) {
    if (Test-Port $apiPort) {
        Write-Step "Port $apiPort is already in use; reusing the running API"
        Write-Host "Restart it if you changed .env." -ForegroundColor Yellow
    }
    else {
        Write-Step "Starting the API on port $apiPort"
        Start-Process -FilePath $uvicorn `
            -ArgumentList @('app.main:app', '--reload', '--port', "$apiPort") `
            -WorkingDirectory $apiDir
    }
}

# Wait for health so the dashboard does not race the API.
if (-not $SkipApi) {
    $healthy = $false
    for ($i = 0; $i -lt 60; $i++) {
        try {
            $response = Invoke-WebRequest -Uri "$apiUrl/health" -UseBasicParsing -TimeoutSec 2
            if ($response.StatusCode -eq 200) { $healthy = $true; break }
        }
        catch {
            Start-Sleep -Milliseconds 500
        }
    }
    if ($healthy) { Write-Host "API health OK" -ForegroundColor Green }
    else { Write-Host "API did not answer /health yet; check its window." -ForegroundColor Yellow }
}

# --- 6. Dashboard ----------------------------------------------------------
if (-not $SkipWeb) {
    if (Test-Port $webPort) {
        Write-Step "Port $webPort is already in use; reusing the running dashboard"
        Write-Host "Restart it if you changed .env or .env.local." -ForegroundColor Yellow
    }
    else {
        Write-Step "Starting the dashboard on port $webPort"
        Start-Process -FilePath 'cmd.exe' `
            -ArgumentList @('/k', "npm run dev -- --port $webPort") `
            -WorkingDirectory $webDir
    }
}

if (-not $NoBrowser) {
    Start-Process "http://localhost:$webPort/login"
}

Write-Host ""
Write-Host "Ready." -ForegroundColor Green
Write-Host "  Dashboard: http://localhost:$webPort"
Write-Host "  API docs:  $apiUrl/docs"
Write-Host "  Register:  http://localhost:$webPort/register"
Write-Host "  Sign in:   http://localhost:$webPort/login"
Write-Host ""
Write-Host "Stop the services with Ctrl+C in their windows (or close those windows)."
