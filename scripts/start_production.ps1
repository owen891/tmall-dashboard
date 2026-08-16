[CmdletBinding()]
param(
    [string]$ListenHost = '0.0.0.0',
    [int]$Port = 5000,
    [string]$Database = 'data/dashboard.db',
    [switch]$BackupBeforeStart,
    [switch]$SkipPreflight
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $projectRoot

if ([string]::IsNullOrWhiteSpace($env:DASHBOARD_USERNAME) -or
    [string]::IsNullOrWhiteSpace($env:DASHBOARD_PASSWORD)) {
    throw 'DASHBOARD_USERNAME and DASHBOARD_PASSWORD must be set before starting production.'
}

$databasePath = (Resolve-Path -LiteralPath $Database -ErrorAction Stop).Path
$env:TMALL_DB_PATH = $databasePath

$listeners = @(Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue)
if ($listeners.Count -gt 0) {
    $owners = ($listeners | Select-Object -ExpandProperty OwningProcess -Unique) -join ', '
    throw "Port $Port is already in use by process(es): $owners. Stop the existing service or choose another port."
}

if ($BackupBeforeStart) {
    & py -3 scripts/backup_database.py --source $databasePath
    if ($LASTEXITCODE -ne 0) {
        throw "Database backup failed with exit code $LASTEXITCODE. Waitress was not started."
    }
}

if (-not $SkipPreflight) {
    & py -3 scripts/production_preflight.py --database $databasePath --require-auth
    if ($LASTEXITCODE -ne 0) {
        throw "Production preflight failed with exit code $LASTEXITCODE. Waitress was not started."
    }
}

& py -3 -m waitress `
    "--host=$ListenHost" `
    "--port=$Port" `
    '--trusted-proxy=127.0.0.1' `
    '--trusted-proxy-headers=x-forwarded-for' `
    'wsgi:application'
