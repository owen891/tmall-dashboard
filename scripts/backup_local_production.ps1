param(
    [string]$DatabasePath = (Join-Path $env:ProgramData 'TMallDashboard\data\dashboard.db'),
    [string]$LogDirectory = (Join-Path $env:ProgramData 'TMallDashboard\logs'),
    [string]$PythonPath = (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python314\python.exe')
)

$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
$python = [System.IO.Path]::GetFullPath($PythonPath)
$database = [System.IO.Path]::GetFullPath($DatabasePath)
$logDirectory = [System.IO.Path]::GetFullPath($LogDirectory)
$logFile = Join-Path $logDirectory 'backup.log'

if (-not (Test-Path -LiteralPath $python)) {
    throw "Python 3.14 was not found at $python"
}

if (-not (Test-Path -LiteralPath $database)) {
    throw "Database was not found at $database"
}

New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
$env:TMALL_DB_PATH = $database

Push-Location $projectRoot
try {
    & $python -c "from scripts.import_data import backup_database; raise SystemExit(0 if backup_database() else 1)" 2>&1 |
        Tee-Object -FilePath $logFile -Append
    if ($LASTEXITCODE -ne 0) {
        throw "Runtime database backup failed for $database"
    }
} finally {
    Pop-Location
}
