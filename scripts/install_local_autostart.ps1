param(
    [string]$SourceDatabasePath = (Join-Path (Split-Path -Parent $PSScriptRoot) 'data\dashboard.db')
)

$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
$startScript = Join-Path $PSScriptRoot 'start_local_production.ps1'
$taskName = 'TMallDashboardLocal'
$python = Join-Path $env:LOCALAPPDATA 'Programs\Python\Python314\python.exe'
$powershell = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
$dataRoot = Join-Path $env:ProgramData 'TMallDashboard'
$dataDirectory = Join-Path $dataRoot 'data'
$logDirectory = Join-Path $dataRoot 'logs'
$database = Join-Path $dataDirectory 'dashboard.db'
$sourceDatabase = [System.IO.Path]::GetFullPath($SourceDatabasePath)

if (-not (Test-Path -LiteralPath $sourceDatabase)) {
    throw "Source database was not found at $sourceDatabase"
}

if (-not (Test-Path -LiteralPath $python)) {
    throw "Python 3.14 was not found at $python"
}

New-Item -ItemType Directory -Path $dataDirectory, $logDirectory -Force | Out-Null
if (-not (Test-Path -LiteralPath $database)) {
    Copy-Item -LiteralPath $sourceDatabase -Destination $database -ErrorAction Stop
}

$integrity = & $python -c "import sqlite3; c=sqlite3.connect(r'$database'); print(c.execute('PRAGMA integrity_check').fetchone()[0]); c.close()"
if ($LASTEXITCODE -ne 0 -or $integrity -ne 'ok') {
    throw "Runtime database integrity check failed for $database"
}

$taskAction = "`"$powershell`" -NoProfile -ExecutionPolicy Bypass -File `"$startScript`""

& schtasks.exe /Create /TN $taskName /SC ONLOGON /RL LIMITED /TR $taskAction /F | Out-Host
if ($LASTEXITCODE -ne 0) {
    throw "Failed to create scheduled task $taskName"
}
