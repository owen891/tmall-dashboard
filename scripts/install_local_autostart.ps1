param(
    [string]$SourceDatabasePath = (Join-Path (Split-Path -Parent $PSScriptRoot) 'data\dashboard.db')
)

$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
$startScript = Join-Path $PSScriptRoot 'start_local_production.ps1'
$backupScript = Join-Path $PSScriptRoot 'backup_local_production.ps1'
$taskName = 'TMallDashboardLocal'
$backupTaskName = 'TMallDashboardBackupDaily'
$python = Join-Path $env:LOCALAPPDATA 'Programs\Python\Python314\python.exe'
$powershell = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
$dataRoot = Join-Path $env:ProgramData 'TMallDashboard'
$dataDirectory = Join-Path $dataRoot 'data'
$logDirectory = Join-Path $dataRoot 'logs'
$database = Join-Path $dataDirectory 'dashboard.db'
$sourceDatabase = [System.IO.Path]::GetFullPath($SourceDatabasePath)

function Get-TaskSnapshot([string]$RegisteredTaskName) {
    if (Get-ScheduledTask -TaskName $RegisteredTaskName -ErrorAction SilentlyContinue) {
        return Export-ScheduledTask -TaskName $RegisteredTaskName
    }
    return $null
}

function Restore-TaskSnapshot([string]$RegisteredTaskName, [string]$Snapshot) {
    if ($null -ne $Snapshot) {
        Register-ScheduledTask -TaskName $RegisteredTaskName -Xml $Snapshot -Force | Out-Null
        return
    }

    if (Get-ScheduledTask -TaskName $RegisteredTaskName -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $RegisteredTaskName -Confirm:$false
    }
}

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

if ($taskAction.Length -gt 261) {
    throw "Service task command is too long for schtasks.exe: $($taskAction.Length) characters"
}

$backupTaskActionDefinition = New-ScheduledTaskAction `
    -Execute $powershell `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$backupScript`" -PythonPath `"$python`"" `
    -WorkingDirectory $projectRoot
$backupTaskTrigger = New-ScheduledTaskTrigger -Daily -At '02:30'
$backupTaskPrincipal = New-ScheduledTaskPrincipal -User 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
$backupTaskSettings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$serviceTaskSnapshot = Get-TaskSnapshot $taskName
$backupTaskSnapshot = Get-TaskSnapshot $backupTaskName

try {
    Register-ScheduledTask `
        -TaskName $backupTaskName `
        -Action $backupTaskActionDefinition `
        -Trigger $backupTaskTrigger `
        -Principal $backupTaskPrincipal `
        -Settings $backupTaskSettings `
        -Force | Out-Null

    & schtasks.exe /Create /TN $taskName /SC ONLOGON /RL LIMITED /TR $taskAction /F | Out-Host
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create scheduled task $taskName"
    }
} catch {
    Restore-TaskSnapshot $taskName $serviceTaskSnapshot
    Restore-TaskSnapshot $backupTaskName $backupTaskSnapshot
    throw
}
