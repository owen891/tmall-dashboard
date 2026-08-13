param(
    [int]$Port = 5000,
    [string]$DatabasePath = (Join-Path $env:ProgramData 'TMallDashboard\data\dashboard.db'),
    [string]$LogDirectory = (Join-Path $env:ProgramData 'TMallDashboard\logs')
)

$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $env:LOCALAPPDATA 'Programs\Python\Python314\python.exe'
$database = [System.IO.Path]::GetFullPath($DatabasePath)
$logDirectory = [System.IO.Path]::GetFullPath($LogDirectory)
$stdoutLog = Join-Path $logDirectory 'waitress.stdout.log'
$stderrLog = Join-Path $logDirectory 'waitress.stderr.log'

if (-not (Test-Path -LiteralPath $python)) {
    throw "Python 3.14 was not found at $python"
}

if (-not (Test-Path -LiteralPath $database)) {
    throw "Database was not found at $database"
}

$listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($listener) {
    throw "Port $Port is already in use by process $($listener[0].OwningProcess)"
}

New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
$env:TMALL_DB_PATH = $database

Start-Process `
    -FilePath $python `
    -ArgumentList "-m waitress --host=127.0.0.1 --port=$Port wsgi:application" `
    -WorkingDirectory $projectRoot `
    -RedirectStandardOutput $stdoutLog `
    -RedirectStandardError $stderrLog `
    -WindowStyle Hidden | Out-Null
