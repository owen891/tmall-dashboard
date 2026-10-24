<# One allowlisted task, one project-scoped runtime; no implicit elevation. #>
[CmdletBinding()]
param(
    [string]$ProjectRoot,
    [Parameter(Mandatory)]
    [ValidateSet('Collect-Others','Collect-BI','Aggregate-Daily','Observability','DailyBackup','DevServer')]
    [string]$TaskSuffix
)
$ErrorActionPreference = 'Stop'
if (-not $ProjectRoot) { $ProjectRoot = Split-Path -Parent $PSScriptRoot }
$ProjectRoot = (Resolve-Path -LiteralPath $ProjectRoot).ProviderPath
. (Join-Path $ProjectRoot 'scripts\resolve_runtime.ps1')
$python = Resolve-CollectorPython -ProjectRoot $ProjectRoot
$env:TMALL_PROJECT_ROOT = $ProjectRoot
$env:TMALL_COLLECT_PYTHON = $python
$env:PYTHONIOENCODING = 'utf-8'
$env:NO_PROXY = (@($env:NO_PROXY -split ',') + @('localhost','127.0.0.1','::1') | Where-Object { $_ } | Select-Object -Unique) -join ','
Set-Location -LiteralPath $ProjectRoot
$global:LASTEXITCODE = 0
switch ($TaskSuffix) {
    'Collect-BI' { & (Join-Path $ProjectRoot 'scripts\auto-collect.ps1') -Sources @('bi_daily','bi_monthly') }
    'Collect-Others' { & (Join-Path $ProjectRoot 'scripts\auto-collect.ps1') -Sources @('sycm_flow','sycm_item_flow','sycm_market','wanxiangtai') }
    'Aggregate-Daily' { & (Join-Path $ProjectRoot 'scripts\aggregate_store_daily_task.ps1') }
    'Observability' { & (Join-Path $ProjectRoot 'scripts\run_collector_observability.ps1') -ProjectRoot $ProjectRoot }
    'DailyBackup' { & (Join-Path $ProjectRoot 'scripts\run_daily_backup.ps1') }
    'DevServer' { & $python (Join-Path $ProjectRoot 'scripts\start_dev_server.py') }
}
exit $LASTEXITCODE
