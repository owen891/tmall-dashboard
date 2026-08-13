$ErrorActionPreference = 'Stop'

$taskName = 'TMallDashboardLocal'
$backupTaskName = 'TMallDashboardBackupDaily'
foreach ($registeredTask in @($taskName, $backupTaskName)) {
    & schtasks.exe /Query /TN $registeredTask /FO LIST *> $null
    if ($LASTEXITCODE -eq 0) {
        & schtasks.exe /Delete /TN $registeredTask /F | Out-Host
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to delete scheduled task $registeredTask"
        }
    }
}
