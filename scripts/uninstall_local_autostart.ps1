$ErrorActionPreference = 'Stop'

$taskName = 'TMallDashboardLocal'
& schtasks.exe /Delete /TN $taskName /F | Out-Host
if ($LASTEXITCODE -ne 0) {
    throw "Failed to delete scheduled task $taskName"
}
