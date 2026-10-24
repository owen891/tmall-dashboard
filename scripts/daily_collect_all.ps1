# ============================================================
# 每日全量采集（纯脚本主链路，不依赖 DSH 宿主 / 不依赖模型额度）
#
# 背景（2026-10-22）：
#   原先 09:00 的采集由 DSH 自动化驱动。模型账号一旦被限流（429 QUOTA），
#   自动化在第一步就死掉，一个采集批次都跑不了——2026-10-22 实测只活了 48 秒。
#   采集本身是纯脚本活，不该被模型额度绑架。
#
#   本脚本接管 09:00 的全量采集：按 4 批顺序跑，批间留间隔降低平台风控风险。
#   DSH 自动化改成 09:45 的「巡检与介入」——只有真的出缺口时才动用模型。
#
# 幂等/并发：采集器都是 upsert；run_daily_collect.ps1 自带 collect.lock 互斥，
#           与兜底链重叠时后来者直接 SKIP 退出，不会双链并发。
#
# 用法：
#   .\scripts\daily_collect_all.ps1
#   .\scripts\daily_collect_all.ps1 -Date 2026-10-21
#   .\scripts\daily_collect_all.ps1 -BatchGapSeconds 0     # 调试：批间不等待
#   .\scripts\daily_collect_all.ps1 -SkipAggregate         # 只采不汇总
# ============================================================

param(
    [string]$Date = '',
    [int]$BatchGapSeconds = 180,
    [switch]$SkipAggregate
)

$ErrorActionPreference = 'Continue'

# ---------- 宿主自愈 ----------
# run_daily_collect.ps1 是 UTF-8 无 BOM 且含中文：Windows PowerShell 5.1 会按 ANSI
# 解码，报 "Missing closing '}'" 解析失败，而且**退出码仍是 0**，会静默漏采。
# 这里若检测到 5.1，自动改用 PowerShell 7 重跑本脚本。
if ($PSVersionTable.PSVersion.Major -lt 7) {
    $pwshPath = Join-Path $env:ProgramFiles 'PowerShell\7\pwsh.exe'
    if (Test-Path -LiteralPath $pwshPath) {
        $relaunchArgs = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $PSCommandPath)
        if ($Date) { $relaunchArgs += @('-Date', $Date) }
        $relaunchArgs += @('-BatchGapSeconds', [string]$BatchGapSeconds)
        if ($SkipAggregate) { $relaunchArgs += '-SkipAggregate' }
        & $pwshPath @relaunchArgs
        exit $LASTEXITCODE
    }
    Write-Warning '未找到 PowerShell 7，run_daily_collect.ps1 在 5.1 下会解析失败，本次采集可能无效。'
}

$ProjectRoot = if ($env:TMALL_PROJECT_ROOT) { $env:TMALL_PROJECT_ROOT } else { Split-Path -Parent $PSScriptRoot }
$LogDir = if ($env:TMALL_LOG_DIR) { $env:TMALL_LOG_DIR } else { Join-Path $ProjectRoot 'logs' }
if (-not (Test-Path -LiteralPath $LogDir)) { New-Item -ItemType Directory -Path $LogDir -Force | Out-Null }
$LogFile = Join-Path $LogDir ("daily-collect-{0}.log" -f (Get-Date -Format 'yyyyMMdd-HHmmss'))

$env:PYTHONIOENCODING = 'utf-8'
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = $OutputEncoding

function Write-Log {
    param([string]$Message, [string]$Level = 'INFO')
    $line = "[{0}] [{1}] {2}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Level, $Message
    Write-Output $line
    Add-Content -LiteralPath $LogFile -Value $line -Encoding UTF8
}

Write-Log '=== 每日全量采集开始 ==='
Write-Log "日志文件: $LogFile"

# ---------- 1. 解析 runtime ----------
try {
    . (Join-Path $PSScriptRoot 'resolve_runtime.ps1')
    $python = Resolve-CollectorPython -ProjectRoot $ProjectRoot
    Write-Log "Python: $python"
} catch {
    Write-Log "Python runtime 解析失败: $($_.Exception.Message)" 'ERROR'
    # 20 = RUNTIME_CONFIG_INVALID，与 auto-collect.ps1 同码：同一个失败必须在
    # 整条链上给出同一个退出码，否则计划任务的 LastTaskResult 无法统一判读。
    exit 20
}

$env:TMALL_COLLECT_PYTHON = $python
$env:TMALL_CDP_PORT = if ($env:TMALL_CDP_PORT) { $env:TMALL_CDP_PORT } else { '9223' }

# ---------- 2. 目标日期 ----------
if (-not $Date) {
    $Date = (Get-Date).AddDays(-1).ToString('yyyy-MM-dd')
}
Write-Log "目标日期: $Date（T-1）"

# ---------- 3. 前置：CDP 必须通 ----------
# 注意：Windows PowerShell 5.1 的 Invoke-WebRequest 没有 -NoProxy（PS7 才有），
# 这里用 TCP 探测，既不依赖参数版本，也不受系统代理影响。
$cdpOk = $false
try {
    $client = New-Object System.Net.Sockets.TcpClient
    $iar = $client.BeginConnect('127.0.0.1', [int]$env:TMALL_CDP_PORT, $null, $null)
    if ($iar.AsyncWaitHandle.WaitOne(3000) -and $client.Connected) { $cdpOk = $true }
    $client.Close()
} catch { $cdpOk = $false }

if (-not $cdpOk) {
    Write-Log "CDP $($env:TMALL_CDP_PORT) 不通，浏览器未就绪，本次不采集。" 'ERROR'
    Write-Log '（开机编排 boot-collector.ps1 负责拉起浏览器；请检查计划任务 TmallDashboard-Boot）' 'ERROR'
    Write-Log '=== 每日全量采集结束（浏览器未就绪） ==='
    exit 21
}
Write-Log "CDP $($env:TMALL_CDP_PORT) 可用"

# ---------- 4. 分批采集 ----------
$collectScript = Join-Path $PSScriptRoot 'run_daily_collect.ps1'
$batches = @(
    [pscustomobject]@{ Key = 'sycm';        Name = '生意参谋 店铺流量+单品流量'; Sources = @('sycm_flow', 'sycm_item_flow') },
    [pscustomobject]@{ Key = 'market';      Name = '生意参谋 市场数据';           Sources = @('sycm_market') },
    [pscustomobject]@{ Key = 'wanxiangtai'; Name = '万相台 推广';                 Sources = @('wanxiangtai') },
    [pscustomobject]@{ Key = 'bi';          Name = '边界BI 商品日度+月度';        Sources = @('bi_daily', 'bi_monthly') }
)

$results = @()
$index = 0
foreach ($batch in $batches) {
    $index++
    if ($index -gt 1 -and $BatchGapSeconds -gt 0) {
        Write-Log ("批间等待 {0} 秒（降低平台请求密度）..." -f $BatchGapSeconds)
        Start-Sleep -Seconds $BatchGapSeconds
    }

    $srcLiteral = "@('" + ($batch.Sources -join "','") + "')"
    Write-Log ("--- 批 {0}/{1}: {2} ---" -f $index, $batches.Count, $batch.Name)
    Write-Log ("执行: .\scripts\run_daily_collect.ps1 -Sources $srcLiteral -Start $Date")

    # 子脚本落一份结构化运行结果（outcome/succeeded/failed/skipped）。
    # 修复前这里靠正则抓子日志里的「成功: X, 失败: Y」——跳过与成功都写 0 失败，
    # 而且日志格式一改就静默失配（抓不到时只写「(未从子日志读到统计行)」当无事发生）。
    $childResult = Join-Path $LogDir ("daily-batch-{0}-{1}.result.json" -f $batch.Key, (Get-Date -Format 'yyyyMMdd-HHmmss'))

    # 必须把目标日期透传下去：修复前不带 -Start，子进程采「它自己算的昨天」，
    # 用 -Date 指定历史日期重采时永远采不到目标日。
    & $collectScript -Sources $batch.Sources -Start $Date -End $Date -ResultFile $childResult 2>&1 |
        ForEach-Object { Add-Content -LiteralPath $LogFile -Value $_ -Encoding UTF8 }
    $batchExit = $LASTEXITCODE

    # 优先用结果文件判定这一批实际采到什么，再退回退出码。
    $batchOutcome = 'unknown'
    $batchSucceeded = 0
    $batchFailed = 0
    $batchSkipped = 0
    if (Test-Path -LiteralPath $childResult) {
        try {
            $child = Get-Content -LiteralPath $childResult -Raw -Encoding UTF8 | ConvertFrom-Json
            if ($child.outcome) { $batchOutcome = [string]$child.outcome }
            if ($null -ne $child.succeeded) { $batchSucceeded = [int]$child.succeeded }
            if ($null -ne $child.failed) { $batchFailed = [int]$child.failed }
            if ($null -ne $child.skipped) { $batchSkipped = [int]$child.skipped }
        } catch {
            Write-Log ("批 {0} 结果文件无法解析: {1}" -f $batch.Key, $_.Exception.Message) 'WARN'
        }
    } else {
        Write-Log ("批 {0} 未产出结果文件: {1}" -f $batch.Key, $childResult) 'WARN'
    }

    $statLine = "outcome=$batchOutcome 成功=$batchSucceeded 失败=$batchFailed 跳过=$batchSkipped exit=$batchExit"
    $level = if ($batchExit -eq 0 -and $batchOutcome -in @('succeeded', 'skipped')) { 'INFO' } else { 'ERROR' }
    Write-Log ("批 {0} 退出码 {1} | {2}" -f $batch.Key, $batchExit, $statLine) $level

    $results += [pscustomobject]@{
        Key       = $batch.Key
        Name      = $batch.Name
        Exit      = $batchExit
        Outcome   = $batchOutcome
        Succeeded = $batchSucceeded
        Failed    = $batchFailed
        Skipped   = $batchSkipped
        Stat      = $statLine
        Log       = $childResult
    }
}

# ---------- 5. 汇总（仅当 daily_data 有数据） ----------
$gapScript = Join-Path $PSScriptRoot 'check_collect_gaps.py'
$dailyRows = 0
try {
    $gapText = ((& $python $gapScript --date $Date --json 2>&1) -join "`n").Trim()
    $gap = $gapText | ConvertFrom-Json
    if ($gap.tables.daily_data) { $dailyRows = [int]$gap.tables.daily_data.rows }
} catch {
    Write-Log "缺口检查失败（不影响已采数据）: $($_.Exception.Message)" 'WARN'
}

$aggExit = $null
if ($SkipAggregate) {
    Write-Log '按参数跳过汇总。'
} elseif ($dailyRows -le 0) {
    Write-Log "daily_data 在 $Date 无数据（BI 未出数），跳过汇总：聚合以 daily_data 为输入，无数据无意义。" 'WARN'
} else {
    Write-Log '--- 批 5/5: 门店事实汇总 ---'
    $aggLog = Join-Path $LogDir ("daily-aggregate-{0}.log" -f (Get-Date -Format 'yyyyMMdd-HHmmss'))
    # 按目标日期聚合：回看窗口以「今天」为锚，用 -Date 指定历史日期时两者未必相交。
    & (Join-Path $PSScriptRoot 'aggregate_store_daily_task.ps1') -Dates $Date 2>&1 |
        Tee-Object -FilePath $aggLog -Append |
        ForEach-Object { Add-Content -LiteralPath $LogFile -Value $_ -Encoding UTF8 }
    $aggExit = $LASTEXITCODE
    Write-Log ("汇总退出码: {0}（明细见 {1}）" -f $aggExit, $aggLog) $(if ($aggExit -eq 0) { 'INFO' } else { 'ERROR' })
}

# ---------- 6. 复核 ----------
# 复核按目标日期做三层分区验收，不再只看退出码：采集器 exit 0 只代表脚本跑完。
$afterText = ((& $python $gapScript --date $Date --json 2>&1) -join "`n").Trim()
Write-Log ("复核: " + $afterText)

$remaining = @()
$afterAggregateNeeded = $false
try {
    $afterGap = $afterText | ConvertFrom-Json
    if ($afterGap.ok) {
        $remaining = @($afterGap.missing_sources)
        $afterAggregateNeeded = [bool]$afterGap.aggregate_needed
    }
} catch {
    Write-Log ("复核结果无法解析: {0}" -f $_.Exception.Message) 'WARN'
}
if ($remaining.Count -gt 0) {
    Write-Log ("复核仍有缺口: " + ($remaining -join ', ')) 'ERROR'
} else {
    Write-Log '复核通过：目标日期各分区均已通过验收。'
}
if ($afterAggregateNeeded) {
    Write-Log ("复核仍显示需重跑汇总（$Date 的 store_daily_facts 未通过验收）") 'ERROR'
}

# ---------- 7. 小结 ----------
$failed = @($results | Where-Object { $_.Exit -ne 0 -or $_.Outcome -notin @('succeeded', 'skipped') })
Write-Log '=== 采集小结 ==='
foreach ($r in $results) {
    $mark = if ($r.Exit -eq 0 -and $r.Outcome -in @('succeeded', 'skipped')) { 'OK  ' } else { 'FAIL' }
    Write-Log ("  [{0}] {1} | {2}" -f $mark, $r.Name, $r.Stat) $(if ($mark -eq 'OK  ') { 'INFO' } else { 'ERROR' })
}
if ($null -ne $aggExit) {
    Write-Log ("  [{0}] 门店事实汇总 | 退出码 {1}" -f $(if ($aggExit -eq 0) { 'OK  ' } else { 'FAIL' }), $aggExit)
}

Write-Log '=== 每日全量采集结束 ==='
if ($failed.Count -gt 0) { exit 1 }
if ($null -ne $aggExit -and $aggExit -ne 0) { exit 1 }
# 复核兜底：即使每个子进程都报成功，只要目标日期仍有分区未过验收，就不能报 0。
if ($remaining.Count -gt 0 -or $afterAggregateNeeded) { exit 1 }
exit 0
