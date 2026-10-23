<#
.SYNOPSIS
Register selected dashboard tasks without silently enabling paused jobs.
.DESCRIPTION
Existing triggers, settings, principal and enabled state are preserved unless
-Enable/-Disable or -RunAsUser is explicitly supplied. New tasks are disabled.
Only selected tasks are changed. -WhatIf performs no scheduler mutation.
DevServer is opt-in; legacy browser/backfill tasks are not managed here.
#>
[CmdletBinding(SupportsShouldProcess)]
param(
    [string]$ProjectRoot,
    [ValidatePattern('^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$')]
    [string]$TaskPrefix = 'TmallDashboard',
    [ValidateSet('Collect-Others','Collect-BI','Aggregate-Daily','Observability','DailyBackup','DevServer')]
    [string[]]$TaskSuffixes = @('Collect-Others','Collect-BI','Aggregate-Daily','Observability','DailyBackup'),
    [string]$RunAsUser = '',
    [switch]$Enable,
    [switch]$Disable,
    [switch]$Remove
)
$ErrorActionPreference = 'Stop'
if ($Enable -and $Disable) { throw 'Enable and Disable are mutually exclusive' }
if ($Remove -and ($Enable -or $Disable)) { throw 'Remove cannot change enabled state' }
if (-not $ProjectRoot) { $ProjectRoot = Split-Path -Parent $PSScriptRoot }
$ProjectRoot = (Resolve-Path -LiteralPath $ProjectRoot).ProviderPath
$wrapper = Join-Path $ProjectRoot 'scripts\run_scheduled_task.ps1'
if (-not $Remove -and -not (Test-Path -LiteralPath $wrapper -PathType Leaf)) {
    throw "Scheduled entry point not found: $wrapper"
}
$times = @{'Collect-Others'='09:30'; 'Collect-BI'='11:30'; 'Aggregate-Daily'='12:30'; 'Observability'='13:00'; 'DailyBackup'='03:00'}
foreach ($suffix in ($TaskSuffixes | Select-Object -Unique)) {
    $name = "$TaskPrefix-$suffix"
    $existing = Get-ScheduledTask -TaskName $name -TaskPath '\' -ErrorAction SilentlyContinue
    if ($Remove) {
        if ($existing -and $PSCmdlet.ShouldProcess($name, 'Remove selected scheduled task')) {
            Unregister-ScheduledTask -TaskName $name -TaskPath '\' -Confirm:$false
        }
        continue
    }
    $enabled = if ($Enable) { $true } elseif ($Disable) { $false } elseif ($existing) { [bool]$existing.Settings.Enabled } else { $false }
    # Native objects are preserved for registered tasks, including scheduler conditions.
    $settings = if ($existing) { $existing.Settings } else {
        $timeLimit = if ($suffix -eq 'DevServer') { [TimeSpan]::Zero } else { New-TimeSpan -Hours 72 }
        New-ScheduledTaskSettingsSet -ExecutionTimeLimit $timeLimit -StartWhenAvailable -MultipleInstances IgnoreNew -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
    }
    $settings.Enabled = $enabled
    $trigger = if ($existing) { $existing.Triggers } elseif ($suffix -eq 'DevServer') {
        New-ScheduledTaskTrigger -AtLogOn
    } else { New-ScheduledTaskTrigger -Daily -At $times[$suffix] }
    $principal = if ($RunAsUser) {
        New-ScheduledTaskPrincipal -UserId $RunAsUser -LogonType Interactive -RunLevel Limited
    } elseif ($existing) { $existing.Principal } else {
        New-ScheduledTaskPrincipal -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
    }
    $argument = "-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$wrapper`" -ProjectRoot `"$ProjectRoot`" -TaskSuffix $suffix"
    $action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $argument -WorkingDirectory $ProjectRoot
    if ($PSCmdlet.ShouldProcess($name, "Register selected task; Enabled=$enabled")) {
        $registerArgs = @{
            TaskName=$name; TaskPath='\'; Action=$action;
            Settings=$settings; Principal=$principal; Force=$true;
        }
        # Omit empty triggers: Register-ScheduledTask rejects explicit $null,
        # while omitting Trigger correctly preserves an on-demand task.
        if ($null -ne $trigger -and @($trigger).Count -gt 0) { $registerArgs.Trigger = $trigger }
        if ($existing) {
            if ($null -ne $existing.Description) { $registerArgs.Description = $existing.Description }
        } else { $registerArgs.Description = "tmall-dashboard: controlled runtime / $suffix" }
        $null = Register-ScheduledTask @registerArgs
        Write-Output "REGISTERED $name Enabled=$enabled"
    }
}
