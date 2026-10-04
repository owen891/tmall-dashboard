<#
.SYNOPSIS
    注册 / 更新 / 移除 tmall-dashboard 的 Windows 计划任务。

.DESCRIPTION
    2026-10-02 重写。原版本有三个问题，会误导后来者：
      1. 注册的任务名（-Collectors / -Observability / -Backup）与线上实际完全不符；
      2. 用 schtasks.exe，而线上是用 PowerShell 的 Register-ScheduledTask 注册的
         （schtasks.exe 在部分受限环境还会被安全策略直接拦截）；
      3. 引用 run_daily_collect.ps1，但线上采集走的是 auto-collect.ps1
         （RPA 链：自动登录 + 触发 API + 等采集完成）。
    新版本按 Get-ScheduledTask 实测的现状重建，支持 -WhatIf 预演。

    当前任务体系（2026-10-02 实测）：
      Collect-Others     09:30  auto-collect.ps1 -Sources sycm_flow,sycm_item_flow,sycm_market,wanxiangtai
      Collect-BI         11:30  auto-collect.ps1 -Sources bi_daily,bi_monthly
      Aggregate-Daily    12:30  aggregate_store_daily_task.ps1   （独立聚合，不依赖采集脚本是否跑完）
      Observability      13:00  run_collector_observability.ps1  （巡检 + 告警落库）
      DailyBackup        03:00  run_daily_backup.ps1             （默认 Disabled）

    另有两个非定时任务，本脚本不自动注册（避免意外副作用，需要时手工建）：
      CollectorChrome   无触发器，跑 start-chrome-debug.ps1 起 CDP 9223，是采集的前置依赖
      DevServer         登录时触发，跑 start_dev_server.py

.PARAMETER ProjectRoot
    项目根目录。缺省按脚本位置推断（不要在 param 默认值里求 $MyInvocation —— 
    通过 powershell.exe -File 调用时那里是空的，会让脚本第一行就抛错）。

.PARAMETER RunAsUser
    运行身份，缺省沿用现有任务的做法：当前用户 / Interactive / Limited。

.PARAMETER Remove
    移除本脚本管理的任务。

.EXAMPLE
    .\install_collector_tasks.ps1 -WhatIf      # 预演，不实际改动
    .\install_collector_tasks.ps1              # 注册 / 更新
    .\install_collector_tasks.ps1 -Remove -WhatIf
#>
[CmdletBinding(SupportsShouldProcess)]
param(
    [string]$ProjectRoot,
    [string]$TaskPrefix = 'TmallDashboard',
    [string]$RunAsUser = '',
    [switch]$Remove
)

$ErrorActionPreference = 'Stop'

if (-not $ProjectRoot) {
    $ProjectRoot = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
}
if (-not (Test-Path -LiteralPath $ProjectRoot)) { throw "项目根目录不存在: $ProjectRoot" }

$tasks = @(
    @{ Suffix = 'Collect-Others';  Script = 'auto-collect.ps1';                 Args = '-Sources sycm_flow,sycm_item_flow,sycm_market,wanxiangtai'; Time = '09:30' }
    @{ Suffix = 'Collect-BI';      Script = 'auto-collect.ps1';                 Args = '-Sources bi_daily,bi_monthly';                               Time = '11:30' }
    @{ Suffix = 'Aggregate-Daily'; Script = 'aggregate_store_daily_task.ps1';   Args = '';                                                           Time = '12:30' }
    @{ Suffix = 'Observability';   Script = 'run_collector_observability.ps1';  Args = '';                                                           Time = '13:00' }
    @{ Suffix = 'DailyBackup';     Script = 'run_daily_backup.ps1';             Args = '';                                                           Time = '03:00'; Disabled = $true }
)

# 与线上现有任务对齐：72 小时执行上限（实际不会跑到）、错过就补跑、
# 同一任务不并发（IgnoreNew）、允许电池供电时启动。
$settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Hours 72) `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries

if ($RunAsUser) {
    $principal = New-ScheduledTaskPrincipal -UserId $RunAsUser -LogonType Interactive -RunLevel Limited
} else {
    $principal = $null   # 交给 Register-ScheduledTask 用当前用户
}

foreach ($task in $tasks) {
    $name = "$TaskPrefix-$($task.Suffix)"

    if ($Remove) {
        if ($PSCmdlet.ShouldProcess($name, '移除计划任务')) {
            $existing = Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
            if ($existing) { Unregister-ScheduledTask -TaskName $name -Confirm:$false }
            Write-Host "已移除: $name"
        }
        continue
    }

    $scriptPath = Join-Path $ProjectRoot "scripts\$($task.Script)"
    if (-not (Test-Path -LiteralPath $scriptPath)) { throw "脚本不存在: $scriptPath" }

    $argument = "-ExecutionPolicy Bypass -File `"$scriptPath`""
    if ($task.Args) { $argument += " $($task.Args)" }

    $action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $argument -WorkingDirectory $ProjectRoot
    $trigger = New-ScheduledTaskTrigger -Daily -At $task.Time

    if ($PSCmdlet.ShouldProcess($name, "注册计划任务 @ $($task.Time)")) {
        $registerArgs = @{
            TaskName    = $name
            Action      = $action
            Trigger     = $trigger
            Settings    = $settings
            Description = "tmall-dashboard: $($task.Script) $($task.Args)".Trim()
            Force       = $true
        }
        if ($principal) { $registerArgs.Principal = $principal }
        $null = Register-ScheduledTask @registerArgs

        if ($task.Disabled) {
            Disable-ScheduledTask -TaskName $name | Out-Null
            Write-Host "已注册: $name @ $($task.Time) [Disabled]"
        } else {
            Write-Host "已注册: $name @ $($task.Time)"
        }
    }
}

if (-not $Remove) {
    Write-Host ''
    Write-Host '当前 Tmall* 任务：'
    Get-ScheduledTask | Where-Object { $_.TaskName -like "$TaskPrefix*" } | Sort-Object TaskName | ForEach-Object {
        $info = Get-ScheduledTaskInfo -TaskName $_.TaskName -ErrorAction SilentlyContinue
        Write-Host ("  {0,-42} [{1}] NextRun={2}" -f $_.TaskName, $_.State, $info.NextRunTime)
    }
}
