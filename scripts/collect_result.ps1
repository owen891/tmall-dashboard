# ============================================================
# 采集运行结果契约（所有采集链入口共用）
#
# 背景（2026-10-23）：
#   修复前三条采集链各自用「退出码 0 = 成功」表达完成，但 0 同时意味着：
#     - 全部来源真的采全了；
#     - 另一条链正在跑，本次整体 SKIP 什么都没做；
#     - PowerShell 5.1 解析失败（run_daily_collect.ps1 是 UTF-8 无 BOM + 中文，
#       5.1 报 "Missing closing '}'" 但退出码仍是 0）。
#   于是「跳过」「静默漏采」「真成功」在计划任务里完全一样（LastTaskResult=0），
#   10-22 的 store_daily_facts 缺天就是这么被藏住的。
#
#   本契约把「运行结果」与「进程退出码」分开：
#     outcome  语义化的运行结论，写进结果 JSON，供监控/健康检查读取；
#     exitCode 只用于进程间传播，0 只代表 succeeded。
#   SKIP 依旧是 exit 0（避免计划任务把正常让路记成失败），但 outcome='skipped'
#   与 reason 使它在结果文件里不可与成功混淆。
#
# 用法：
#   . (Join-Path $PSScriptRoot 'collect_result.ps1')
#   $result = New-CollectRunResult -RunId $RunId -Sources $Sources
#   Add-CollectSourceResult -Result $result -Source 'bi_daily' -Outcome 'succeeded' -ExitCode 0
#   Set-CollectRunOutcome -Result $result
#   Write-CollectRunResult -Result $result -Path $resultPath
#   exit (Get-CollectRunExitCode -Result $result)
# ============================================================

# 退出码 ↔ outcome 的映射。20-23 已被 runtime/browser/login/cookie 分类占用
# （见 auto-collect.ps1），这里只定义运行结论对应的码。
$script:CollectOutcomeExitCodes = @{
    'succeeded' = 0
    'skipped'   = 0   # 让路给另一条链：不是失败，但 outcome 会写明
    'partial'   = 1
    'failed'    = 1
    'blocked'   = 22  # 需要人工介入（登录/浏览器），沿用既有分类
}

function New-CollectRunResult {
    param(
        [string]$RunId = [guid]::NewGuid().ToString('N'),
        [string]$ShopId = '',
        [string[]]$Sources = @(),
        [string]$Start = '',
        [string]$End = '',
        [string]$Chain = ''
    )
    return [ordered]@{
        schema_version     = 2
        event              = 'collect_run'
        run_id             = $RunId
        chain              = $Chain
        shop_id            = $ShopId
        start              = $Start
        end                = $End
        outcome            = 'pending'
        reason             = ''
        requested_sources  = @($Sources)
        succeeded          = 0
        failed             = 0
        skipped            = 0
        results            = @()
        generated_at       = (Get-Date).ToString('o')
    }
}

function Add-CollectSourceResult {
    param(
        [Parameter(Mandatory = $true)] $Result,
        [Parameter(Mandatory = $true)] [string]$Source,
        [Parameter(Mandatory = $true)] [string]$Outcome,   # succeeded/failed/skipped/partial/blocked
        [int]$ExitCode = 0,
        [string]$Reason = '',
        [string]$Detail = '',
        [Nullable[datetime]]$StartedAt = $null,
        [Nullable[double]]$DurationSeconds = $null
    )
    $row = [ordered]@{
        source    = $Source
        outcome   = $Outcome
        exit_code = $ExitCode
        reason    = $Reason
        detail    = $Detail
    }
    # 注意（2026-10-23 修复）：[Nullable[datetime]] 参数在 PowerShell 参数绑定阶段
    # 会被**解包**成普通 [datetime]，因此 $StartedAt.Value 恒为 $null，
    # 对它调 .ToString('o') 会抛 "You cannot call a method on a null-valued expression"。
    # 结果：run_daily_collect.ps1 里所有带 -StartedAt 的调用（成功路径与超时路径）
    # 全部抛异常并被外层 catch 记成 'exception' 失败 —— 补采即使完全成功也永远报失败。
    # 正确写法是直接在解包后的值上调用。
    if ($null -ne $StartedAt) { $row['started_at'] = ([datetime]$StartedAt).ToString('o') }
    if ($null -ne $DurationSeconds) { $row['duration_seconds'] = [math]::Round([double]$DurationSeconds, 2) }
    $Result['results'] = @($Result['results']) + $row
}

# 从各来源结果推导整体结论。优先级：failed > partial > blocked > skipped > succeeded。
function Set-CollectRunOutcome {
    param([Parameter(Mandatory = $true)] $Result, [string]$Reason = '')
    $rows = @($Result['results'])
    $counts = @{ succeeded = 0; failed = 0; skipped = 0; partial = 0; blocked = 0 }
    foreach ($row in $rows) {
        $key = [string]$row['outcome']
        if ($counts.ContainsKey($key)) { $counts[$key]++ } else { $counts['failed']++ }
    }
    $Result['succeeded'] = $counts['succeeded']
    $Result['failed'] = $counts['failed'] + $counts['partial'] + $counts['blocked']
    $Result['skipped'] = $counts['skipped']

    if ($rows.Count -eq 0) {
        $outcome = 'skipped'
        $defaultReason = 'no_sources_processed'
    } elseif ($counts['failed'] -gt 0) {
        $outcome = 'failed'
        $defaultReason = 'source_failed'
    } elseif ($counts['blocked'] -gt 0) {
        $outcome = 'blocked'
        $defaultReason = 'needs_human_action'
    } elseif ($counts['partial'] -gt 0) {
        $outcome = 'partial'
        $defaultReason = 'partial_coverage'
    } elseif ($counts['succeeded'] -eq 0 -and $counts['skipped'] -gt 0) {
        $outcome = 'skipped'
        $defaultReason = 'all_sources_skipped'
    } else {
        $outcome = 'succeeded'
        $defaultReason = ''
    }
    $Result['outcome'] = $outcome
    $Result['reason'] = if ($Reason) { $Reason } else { $defaultReason }
    $Result['generated_at'] = (Get-Date).ToString('o')
}

function Write-CollectRunResult {
    param([Parameter(Mandatory = $true)] $Result, [Parameter(Mandatory = $true)] [string]$Path)
    $parent = Split-Path -Parent $Path
    if ($parent -and -not (Test-Path -LiteralPath $parent)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
    $Result | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $Path -Encoding UTF8
    return $Path
}

function Get-CollectRunExitCode {
    param([Parameter(Mandatory = $true)] $Result)
    $outcome = [string]$Result['outcome']
    if ($script:CollectOutcomeExitCodes.ContainsKey($outcome)) {
        return [int]$script:CollectOutcomeExitCodes[$outcome]
    }
    return 1
}

# 供其它脚本读取上游结果文件（例如 daily_collect_all 读 run_daily_collect 的结果）。
function Read-CollectRunResult {
    param([Parameter(Mandatory = $true)] [string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) { return $null }
    try {
        return (Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json)
    } catch {
        return $null
    }
}
