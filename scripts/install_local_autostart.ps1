$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
$startScript = Join-Path $PSScriptRoot 'start_local_production.ps1'
$taskName = 'TMallDashboardLocal'
$powershell = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
$taskAction = "`"$powershell`" -NoProfile -ExecutionPolicy Bypass -File `"$startScript`""

& schtasks.exe /Create /TN $taskName /SC ONLOGON /RL LIMITED /TR $taskAction /F | Out-Host
if ($LASTEXITCODE -ne 0) {
    throw "Failed to create scheduled task $taskName"
}
