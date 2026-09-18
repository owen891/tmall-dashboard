[CmdletBinding()]
param(
    [string]$ProjectRoot = (Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)),
    [string]$BaseUrl = $(if ($env:TMALL_DASHBOARD_URL) { $env:TMALL_DASHBOARD_URL } else { 'http://127.0.0.1:5000' }),
    [string]$Database = $(if ($env:TMALL_DB_PATH) { $env:TMALL_DB_PATH } else { 'data/dashboard.db' })
)

$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $ProjectRoot
$python = if ($env:TMALL_COLLECT_PYTHON) { $env:TMALL_COLLECT_PYTHON } else { Join-Path $ProjectRoot '.venv\Scripts\python.exe' }
$logDir = Join-Path $ProjectRoot 'logs'
New-Item -ItemType Directory -Path $logDir -Force | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$healthOutput = Join-Path $logDir "collector-health-$stamp.json"
$schemaOutput = Join-Path $logDir "collector-schema-$stamp.json"

& $python (Join-Path $ProjectRoot 'scripts\collector_healthcheck.py') --base-url $BaseUrl --output $healthOutput
$healthExit = $LASTEXITCODE
& $python (Join-Path $ProjectRoot 'scripts\collector_schema_check.py') --base-url $BaseUrl --db-path $Database --output $schemaOutput
$schemaExit = $LASTEXITCODE

if ($healthExit -eq 0 -and $schemaExit -eq 0) { exit 0 }
if ($healthExit -eq 2 -or $schemaExit -eq 2) { exit 2 }
exit 1
