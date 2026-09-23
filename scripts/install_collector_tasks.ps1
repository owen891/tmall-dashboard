[CmdletBinding(SupportsShouldProcess)]
param(
    [string]$ProjectRoot = (Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)),
    [string]$TaskPrefix = 'TmallDashboard',
    [string]$RunAsUser = '',
    [switch]$Remove
)

$ErrorActionPreference = 'Stop'
$collectScript = Join-Path $ProjectRoot 'scripts\run_daily_collect.ps1'
$backupScript = Join-Path $ProjectRoot 'scripts\run_daily_backup.ps1'
$observeScript = Join-Path $ProjectRoot 'scripts\run_collector_observability.ps1'
$tasks = @(
    @{ Name = "$TaskPrefix-Collectors"; Script = $collectScript; Schedule = 'DAILY'; Time = '11:30' },
    @{ Name = "$TaskPrefix-Observability"; Script = $observeScript; Schedule = 'DAILY'; Time = '12:15' },
    @{ Name = "$TaskPrefix-Backup"; Script = $backupScript; Schedule = 'DAILY'; Time = '03:00' }
)

foreach ($task in $tasks) {
    if ($Remove) {
        if ($PSCmdlet.ShouldProcess($task.Name, 'remove scheduled task')) {
            & schtasks.exe /Delete /TN $task.Name /F 2>$null | Out-Null
        }
        continue
    }
    if (-not (Test-Path -LiteralPath $task.Script)) { throw "脚本不存在: $($task.Script)" }
    $action = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$($task.Script)`""
    $createArgs = @('/Create', '/TN', $task.Name, '/TR', $action,
                    '/SC', $task.Schedule, '/ST', $task.Time, '/F')
    if ($RunAsUser) { $createArgs += @('/RU', $RunAsUser) }
    if ($PSCmdlet.ShouldProcess($task.Name, 'create or update scheduled task')) {
        & schtasks.exe @createArgs
        if ($LASTEXITCODE -ne 0) { throw "创建计划任务失败: $($task.Name)" }
    }
}
