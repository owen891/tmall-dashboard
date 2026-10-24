# ============================================================
# 补采兜底：T-1 有缺口才补，已齐全则什么都不做
#
# 背景（2026-10-22）：
#   这台机器每天关机重启。09:00 的全量采集由 Windows 计划任务
#   TmallDashboard-Daily 用纯脚本执行（scripts\daily_collect_all.ps1），
#   不再依赖 DSH 宿主，也不受模型额度影响。
#
#   本脚本是第二道网：按库里实际行数判断缺哪个源，只补缺的，齐全就直接退出。
#   触发方式：
#     - 每天 10:30 / 13:00 / 17:00（09:00 那轮通常已结束）
#     - 登录后 5 分钟（配合下面的时间闸门，避免和 09:00 那轮抢）
#   任务设置了 StartWhenAvailable，开机晚于触发点也会在开机后补跑。
#
# 幂等：采集器都是 upsert；run_daily_collect.ps1 自带 collect.lock 互斥，
#       与 09:00 主链路重叠时会直接 SKIP 退出，不会双链并发。
#
# 用法：
#   .\scripts\catchup_collect.ps1              # 正常兜底（带 09:25 时间闸门）
#   .\scripts\catchup_collect.ps1 -DryRun      # 只报告缺口，不采集
#   .\scripts\catchup_collect.ps1 -Force       # 忽略时间闸门
#   .\scripts\catchup_collect.ps1 -Date 2026-10-21
# ============================================================

param(
    [string]$Date = '',
    [string]$NotBefore = '09:25',
    [switch]$Force,
    [switch]$DryRun
)

$ErrorActionPreference = 'Continue'

# ---------- 宿主自愈 ----------
# run_daily_collect.ps1 是 UTF-8 无 BOM 且含中文：Windows PowerShell 5.1 会按 ANSI
# 解码，直接报 "Missing closing '}'" 解析失败，而且**退出码仍是 0**，会静默漏采。
# （2026-10-22 实测踩过。）这里若检测到 5.1，自动改用 PowerShell 7 重跑本脚本。
if ($PSVersionTable.PSVersion.Major -lt 7) {
    $pwshPath = Join-Path $env:ProgramFiles 'PowerShell\7\pwsh.exe'
    if (Test-Path -LiteralPath $pwshPath) {
        $relaunchArgs = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $PSCommandPath)
        if ($Date) { $relaunchArgs += @('-Date', $Date) }
        if ($NotBefore) { $relaunchArgs += @('-NotBefore', $NotBefore) }
        if ($Force) { $relaunchArgs += '-Force' }
        if ($DryRun) { $relaunchArgs += '-DryRun' }
        & $pwshPath @relaunchArgs
        exit $LASTEXITCODE
    }
    Write-Warning '未找到 PowerShell 7，run_daily_collect.ps1 在 5.1 下会解析失败，补采可能无效。'
}

$ProjectRoot = if ($env:TMALL_PROJECT_ROOT) { $env:TMALL_PROJECT_ROOT } else { Split-Path -Parent $PSScriptRoot }
$LogDir = if ($env:TMALL_LOG_DIR) { $env:TMALL_LOG_DIR } else { Join-Path $ProjectRoot 'logs' }
if (-not (Test-Path -LiteralPath $LogDir)) { New-Item -ItemType Directory -Path $LogDir -Force | Out-Null }
$LogFile = Join-Path $LogDir ("catchup-collect-{0}.log" -f (Get-Date -Format 'yyyyMMdd-HHmmss'))

$env:PYTHONIOENCODING = 'utf-8'
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = $OutputEncoding

function Write-Log {
    param([string]$Message, [string]$Level = 'INFO')
    $line = "[{0}] [{1}] {2}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Level, $Message
    Write-Output $line
    Add-Content -LiteralPath $LogFile -Value $line -Encoding UTF8
}

Write-Log '=== 补采兜底开始 ==='
Write-Log "日志文件: $LogFile"

# ---------- 0. 时间闸门 ----------
# 09:00 的 Windows 计划任务 TmallDashboard-Daily 是主链路；09:25 之前不介入，
# 避免和它抢浏览器与平台请求。
# 闸门定在 09:25 而不是 10:25：开机晚于 09:00 时主链路已 misfire，
# 没理由再干等一小时（2026-10-22 之前就是这样把补采拖到 10:30 的）。
if (-not $Force) {
    try {
        $gate = [datetime]::ParseExact($NotBefore, 'HH:mm', $null)
        $now = Get-Date
        if ($now -lt $gate) {
            Write-Log ("当前 {0} 早于闸门 {1}，09:00 脚本主链路负责，本次不补采。" -f $now.ToString('HH:mm'), $NotBefore)
            Write-Log '=== 补采兜底结束（未到时间闸门） ==='
            exit 0
        }
    } catch {
        Write-Log "时间闸门解析失败，继续执行: $($_.Exception.Message)" 'WARN'
    }
}

# ---------- 0.5 主链路互斥检查 ----------
# run_daily_collect.ps1 自己也有锁，但等到那时已经晚了：会白跑一次缺口检查，
# 还会让任务结果变成「失败」。这里先看锁，主链路在跑就直接让路。
$lockPath = Join-Path $LogDir 'collect.lock'
if ((-not $Force) -and (Test-Path -LiteralPath $lockPath)) {
    $lockBusy = $false
    try {
        $lockRaw = Get-Content -LiteralPath $lockPath -Raw -ErrorAction Stop
        $lock = $lockRaw | ConvertFrom-Json
        $lockPid = [int]$lock.pid
        if ($lockPid -gt 0 -and (Get-Process -Id $lockPid -ErrorAction SilentlyContinue)) { $lockBusy = $true }
    } catch { $lockBusy = $false }
    if ($lockBusy) {
        Write-Log "主链路正在采集（锁 $lockPath），本次让路，不补采。" 'WARN'
        Write-Log '=== 补采兜底结束（主链路在跑） ==='
        exit 0
    }
    Write-Log "发现陈旧锁（属主进程已退出），忽略。" 'WARN'
}

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
Write-Log "目标日期: $Date"

# ---------- 3. 只读查缺口 ----------
$gapScript = Join-Path $PSScriptRoot 'check_collect_gaps.py'
$gapJson = & $python $gapScript --date $Date --json 2>&1
$gapText = ($gapJson -join "`n").Trim()
Write-Log ("缺口检查原始输出: " + $gapText)

$gap = $null
try {
    $gap = $gapText | ConvertFrom-Json
} catch {
    Write-Log "缺口检查结果不是合法 JSON，终止: $($_.Exception.Message)" 'ERROR'
    exit 1
}

if (-not $gap.ok) {
    Write-Log "缺口检查失败: $($gap.error)" 'ERROR'
    exit 1
}

$missing = @($gap.missing_sources)
$dailyRows = 0
if ($gap.tables.daily_data) { $dailyRows = [int]$gap.tables.daily_data.rows }

Write-Log ("缺失来源: " + $(if ($missing.Count -gt 0) { $missing -join ', ' } else { '无' }))
Write-Log ("需重跑汇总: " + $(if ($gap.aggregate_needed) { '是' } else { '否' }))

if ($missing.Count -eq 0 -and -not $gap.aggregate_needed) {
    Write-Log "$Date 数据已齐全，无需补采。"
    Write-Log '=== 补采兜底结束（无需动作） ==='
    exit 0
}

if ($DryRun) {
    Write-Log ("DryRun：将补采 [" + ($missing -join ', ') + "]，汇总=" + $gap.aggregate_needed)
    Write-Log '=== 补采兜底结束（DryRun） ==='
    exit 0
}

# ---------- 4. 补采缺失来源 ----------
$collectExit = 0
if ($missing.Count -gt 0) {
    # 前置：CDP 必须通，否则 bi / 万相台 必然失败。
    # 注意：Windows PowerShell 5.1 的 Invoke-WebRequest 没有 -NoProxy（PS7 才有），
    # 这里改用 TCP 探测，既不依赖参数版本，也不受系统代理影响。
    $cdpOk = $false
    try {
        $client = New-Object System.Net.Sockets.TcpClient
        $iar = $client.BeginConnect('127.0.0.1', [int]$env:TMALL_CDP_PORT, $null, $null)
        if ($iar.AsyncWaitHandle.WaitOne(3000) -and $client.Connected) { $cdpOk = $true }
        $client.Close()
    } catch { $cdpOk = $false }
    if (-not $cdpOk) {
        Write-Log "CDP $($env:TMALL_CDP_PORT) 不通，跳过补采（浏览器未就绪）" 'ERROR'
        Write-Log '=== 补采兜底结束（浏览器未就绪） ==='
        exit 21
    }

    $sourcesLiteral = "@('" + ($missing -join "','") + "')"
    Write-Log "执行补采: .\scripts\run_daily_collect.ps1 -Sources $sourcesLiteral -Start $Date"
    $collectLog = Join-Path $LogDir ("catchup-sources-{0}.log" -f (Get-Date -Format 'yyyyMMdd-HHmmss'))
    # 必须把 -Start 透传下去：修复前只传 -Sources，子进程于是采「它自己算的昨天」，
    # 补 10-21 时实际采的是 10-22，缺口永远补不上而退出码还是 0。
    & (Join-Path $PSScriptRoot 'run_daily_collect.ps1') -Sources $missing -Start $Date -End $Date 2>&1 |
        Tee-Object -FilePath $collectLog -Append |
        ForEach-Object { Add-Content -LiteralPath $LogFile -Value $_ -Encoding UTF8 }
    $collectExit = $LASTEXITCODE
    Write-Log "补采退出码: $collectExit（明细见 $collectLog）" $(if ($collectExit -eq 0) { 'INFO' } else { 'ERROR' })
}

# ---------- 5. 汇总 ----------
# 汇总失败必须向上传播：修复前这里只把退出码写进日志，脚本最终仍按 $collectExit
# 决定退出，于是「补采成功但汇总失败」在计划任务里表现为 0x0 成功。
$aggExit = 0
if ($gap.aggregate_needed) {
    if ($dailyRows -le 0) {
        Write-Log "daily_data 在 $Date 无数据（BI 未采），跳过汇总：聚合以 daily_data 为输入，无数据无意义。" 'WARN'
    } else {
        Write-Log "执行汇总: .\scripts\aggregate_store_daily_task.ps1 -Dates $Date"
        $aggLog = Join-Path $LogDir ("catchup-aggregate-{0}.log" -f (Get-Date -Format 'yyyyMMdd-HHmmss'))
        # 同样按目标日期聚合：修复前不带日期，聚合回看「今天往前 14 天」，
        # 与本次补的历史日期未必相交，补完也不会有 store_daily_facts。
        & (Join-Path $PSScriptRoot 'aggregate_store_daily_task.ps1') -Dates $Date 2>&1 |
            Tee-Object -FilePath $aggLog -Append |
            ForEach-Object { Add-Content -LiteralPath $LogFile -Value $_ -Encoding UTF8 }
        $aggExit = $LASTEXITCODE
        Write-Log "汇总退出码: $aggExit（明细见 $aggLog）" $(if ($aggExit -eq 0) { 'INFO' } else { 'ERROR' })
    }
}

# ---------- 6. 复核 ----------
# 复核必须用缺口检查器重新判定，而不是相信子进程的退出码：
# 采集器 exit 0 只代表「脚本跑完了」，是否真的把 $Date 这个分区补齐，只有
# 分区验收（presence/population/fields 三层）能回答。
$afterJson = & $python $gapScript --date $Date --json 2>&1
$afterText = ($afterJson -join "`n").Trim()
Write-Log ("复核: " + $afterText)

$remaining = @()
$afterAggregateNeeded = $false
try {
    $afterGap = $afterText | ConvertFrom-Json
    if ($afterGap.ok) {
        $remaining = @($afterGap.missing_sources)
        $afterAggregateNeeded = [bool]$afterGap.aggregate_needed
    } else {
        Write-Log "复核结果 ok=false: $($afterGap.error)" 'WARN'
    }
} catch {
    Write-Log "复核结果无法解析: $($_.Exception.Message)" 'WARN'
}

if ($remaining.Count -gt 0) {
    Write-Log ("复核仍有缺口: " + ($remaining -join ', ')) 'ERROR'
} else {
    Write-Log '复核通过：目标日期各分区均已通过验收。'
}
if ($afterAggregateNeeded) {
    Write-Log "复核仍显示需重跑汇总（$Date 的 store_daily_facts 仍未通过验收）" 'ERROR'
}

Write-Log '=== 补采兜底结束 ==='
# 退出码优先级：块级失败（浏览器未就绪 21 等）已提前 return；
# 这里先传播采集失败，再传播汇总失败，最后按复核结果兜底 —— 三者任一没做成都不能报成功。
if ($collectExit -ne 0) { exit $collectExit }
if ($aggExit -ne 0) { exit $aggExit }
if ($remaining.Count -gt 0 -or $afterAggregateNeeded) { exit 1 }
exit 0
