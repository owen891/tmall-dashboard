[CmdletBinding()]
param(
    [string]$RunId = $(if ($env:TMALL_COLLECT_RUN_ID) { $env:TMALL_COLLECT_RUN_ID } else { [guid]::NewGuid().ToString('N') }),
    [string]$ShopId = $(if ($env:TMALL_SHOP_ID) { $env:TMALL_SHOP_ID } elseif ($env:TMALL_LEGACY_SHOP_ID) { $env:TMALL_LEGACY_SHOP_ID } else { 'default' }),
    [string]$Start = '',
    [string]$End = '',
    [string]$DbPath = $(if ($env:TMALL_DB_PATH) { $env:TMALL_DB_PATH } else { '' }),
    [int]$CdpPort = $(if ($env:TMALL_CDP_PORT) { [int]$env:TMALL_CDP_PORT } else { 9223 }),
    [string]$ResultFile = '',
    [string[]]$Sources = @()
)

# 定时采集脚本 - 按顺序运行所有数据源采集
# 用法: .\run_daily_collect.ps1
# 可通过 Windows 任务计划程序每天定时调用

$ErrorActionPreference = "Continue"

$ProjectRoot = if ($env:TMALL_PROJECT_ROOT) { $env:TMALL_PROJECT_ROOT } else { Split-Path -Parent $PSScriptRoot }
# 统一解释器解析（2026-10-23 修复「统一运行」缺陷）：不再硬编码 .venv，
# 与 auto-collect / catchup / aggregate 一致走 resolve_runtime.ps1
# （TMALL_COLLECT_PYTHON → data/runtime.json → .venv）。
# 修复前这里与 auto-collect.ps1 用的是两个不同解释器：auto-collect 调 API 触发采集
# （服务端 runtime python），而本脚本自己跑 check_collect_lease.py 与子进程采集器时
# 用 venv python。venv 侧被安全软件拦截时，本脚本与采集链其余部分表现不一致。
. (Join-Path $PSScriptRoot 'resolve_runtime.ps1')
try {
    $VENV_PYTHON = Resolve-CollectorPython -ProjectRoot $ProjectRoot
} catch {
    Write-Host "[ERROR] 运行时解析失败：$($_.Exception.Message)" -ForegroundColor Red
    exit 20
}
$COLLECTORS_DIR = if ($env:TMALL_COLLECTORS_DIR) { $env:TMALL_COLLECTORS_DIR } else {
    # 2026-10-23 起私有插件目录（仓库内独立 git 仓库）为权威版本，与 api/collect_api.py
    # 的 _default_collectors_dir() 优先级对齐；外部 BI采集\collectors 仅作回退（独立采集工具）。
    $internalCollectors = Join-Path $ProjectRoot 'collectors'
    if (Test-Path -LiteralPath $internalCollectors) { $internalCollectors } else { Join-Path (Split-Path -Parent $ProjectRoot) 'BI采集\collectors' }
}
$LOG_DIR = if ($env:TMALL_LOG_DIR) { $env:TMALL_LOG_DIR } else { Join-Path $ProjectRoot 'logs' }
$TIMEOUT_SECONDS = if ($env:TMALL_COLLECT_TIMEOUT_SECONDS) { [int]$env:TMALL_COLLECT_TIMEOUT_SECONDS } else { 600 }
$env:TMALL_COLLECT_RUN_ID = $RunId
$env:TMALL_SHOP_ID = $ShopId
$env:TMALL_CDP_PORT = [string]$CdpPort
if ($DbPath) { $env:TMALL_DB_PATH = (Resolve-Path -LiteralPath $DbPath -ErrorAction Stop).Path }

# ==================== 采集互斥锁（改进路线 2026-10-01 P3.2） ====================
# 两条采集链（计划任务链 run_daily_collect.ps1 / RPA 链 auto-collect.ps1）共用同一
# 数据库与同一 CDP Chrome，同时运行会互相污染（09-30 曾出现采集失败）。锁文件带
# PID + 2 小时 TTL：崩溃残留不会永久死锁（PID 已死或超时即自动接管）。
$CollectLockPath = Join-Path $LOG_DIR 'collect.lock'
$CollectLockTtlSeconds = 7200
function Test-CollectLockBusy {
    if (-not (Test-Path -LiteralPath $CollectLockPath)) { return $false }
    $raw = (Get-Content -LiteralPath $CollectLockPath -ErrorAction SilentlyContinue | Select-Object -First 1) -as [string]
    $ownerPid = $null
    if ($raw -match '"pid"\s*:\s*(\d+)') { $ownerPid = [int]$Matches[1] }
    $ageSeconds = ((Get-Date) - (Get-Item -LiteralPath $CollectLockPath).LastWriteTime).TotalSeconds
    $ownerAlive = $false
    if ($ownerPid) { $ownerAlive = [bool](Get-Process -Id $ownerPid -ErrorAction SilentlyContinue) }
    if ($ageSeconds -lt $CollectLockTtlSeconds -and $ownerAlive) { return $true }
    Remove-Item -LiteralPath $CollectLockPath -Force -ErrorAction SilentlyContinue
    return $false
}
function Release-CollectLock {
    if (Test-Path -LiteralPath $CollectLockPath) {
        Remove-Item -LiteralPath $CollectLockPath -Force -ErrorAction SilentlyContinue
    }
}
if (Test-CollectLockBusy) {
    Write-Output "SKIP: 另一条采集链正在运行（锁：$CollectLockPath）。本次退出，避免双链并发。"
    # 修复前这里直接 exit 0，结果文件都不写：计划任务看到 LastTaskResult=0，
    # 与「全部来源采全」完全无法区分。现在留一份 outcome='skipped' 的凭据。
    $skipResultPath = if ($ResultFile) { [IO.Path]::GetFullPath($ResultFile) } else { Join-Path $LOG_DIR "collect-$RunId.result.json" }
    try {
        . (Join-Path $PSScriptRoot 'collect_result.ps1')
        $skipResult = New-CollectRunResult -RunId $RunId -ShopId $ShopId -Sources $Sources `
            -Start $Start -End $End -Chain 'run_daily_collect'
        Add-CollectSourceResult -Result $skipResult -Source 'chain' -Outcome 'skipped' `
            -Reason 'collect_lock_busy' -Detail $CollectLockPath
        Set-CollectRunOutcome -Result $skipResult
        Write-CollectRunResult -Result $skipResult -Path $skipResultPath | Out-Null
    } catch {
        Write-Output "WARN: 无法写入 SKIP 结果文件: $($_.Exception.Message)"
    }
    exit 0
}
('{"pid": ' + $PID + ', "started_at": "' + (Get-Date -Format o) + '"}') | Set-Content -LiteralPath $CollectLockPath -Encoding UTF8
# ==================== 互斥锁已获取 ====================


if (-not (Test-Path -LiteralPath $VENV_PYTHON)) { throw "采集 Python 不存在: $VENV_PYTHON" }
if (-not (Test-Path -LiteralPath $COLLECTORS_DIR)) { throw "采集器目录不存在: $COLLECTORS_DIR" }

# 采集顺序（有依赖关系的放后面）
# Project = $true 表示脚本在 $ProjectRoot\scripts 下（而非 $COLLECTORS_DIR）。
# 注意：BI商品日度走 overViewPageList 接口，该接口受 BI「视窗列配置」限制，
# 永远不返回 product_cost / sales_cost / logistics_cost / other_cost /
# custom_cost / platform_fee 等成本列（142 个成本列全部 inDisplay=False）。
# 成本只能来自「导出表格数据」的 xlsx 宽表，所以必须紧跟一步 BI商品宽表。
# DateStyle 声明每个采集器**实际接受**的日期参数形式。修复前所有非宽表采集器
# 一律走位置参数，实测三处对不上（2026-10-23 逐个验证）：
#   positional  sys.argv[1] = YYYY-MM-DD  —— collect_overview_full / collect_sycm_flow
#                                          / collect_sycm_item_flow_v6 / collect_sycm_market
#   month       sys.argv[1] = YYYY-MM     —— aggregate_monthly 传 YYYY-MM-DD 会当成月份，
#                                          聚合出 0 行但**退出码仍是 0**，静默漏采
#   wide        --dates / --from --to     —— export_bi_wide
#   flags       --start / --end           —— collect_wanxiangtai_dims_v4 是 argparse，
#                                          传位置参数直接 "unrecognized arguments" exit 2
$COLLECTORS = @(
    @{ Name = "BI商品日度"; Script = "collect_overview_full.py"; DateStyle = 'positional' },
    @{ Name = "BI商品宽表(成本)"; Script = "export_bi_wide.py"; Project = $true; WideExport = $true; DateStyle = 'wide' },
    @{ Name = "BI商品月度"; Script = "aggregate_monthly.py"; DateStyle = 'month' },
    @{ Name = "生意参谋-店铺流量"; Script = "collect_sycm_flow.py"; DateStyle = 'positional' },
    @{ Name = "生意参谋-单品流量"; Script = "collect_sycm_item_flow_v6.py"; DateStyle = 'positional' },
    @{ Name = "生意参谋-市场数据"; Script = "collect_sycm_market.py"; DateStyle = 'positional' },
    @{ Name = "万相台推广"; Script = "collect_wanxiangtai_dims_v4.py"; DateStyle = 'flags' }
)
$sourceAliases = @{
    bi_daily = 'collect_overview_full'; bi_wide = 'export_bi_wide'
    bi_monthly = 'aggregate_monthly'
    sycm_flow = 'collect_sycm_flow'; sycm_item_flow = 'collect_sycm_item_flow_v6'
    sycm_market = 'collect_sycm_market'; wanxiangtai = 'collect_wanxiangtai_dims_v4'
}
# 宽表导出的目标日期：显式 -Start 优先，否则取昨天（与 BI商品日度默认口径一致）
$wideExportDate = if ($Start) { $Start } else { (Get-Date).AddDays(-1).ToString('yyyy-MM-dd') }

# aggregate_monthly 要的是 YYYY-MM。修复前把 YYYY-MM-DD 直接位置传进去，
# 它拿整串当月份去 LIKE '2026-10-22-%'，聚合 0 行却仍 exit 0。
$monthArg = if ($Start) { $Start.Substring(0, 7) } else { (Get-Date).AddDays(-1).ToString('yyyy-MM') }

# 按 DateStyle 生成某个采集器的日期参数。核心原则：**采集器不认识日期参数时，
# 绝不静默用它的内部默认值**——那正是「补采 10-21 却采了 10-22」这类错位的来源。
function Get-CollectorDateArguments {
    param($Collector, [string]$StartDate, [string]$EndDate)
    $style = if ($Collector.DateStyle) { $Collector.DateStyle } else { 'positional' }
    switch ($style) {
        'wide' {
            if ($StartDate -and $EndDate -and $EndDate -ne $StartDate) {
                return @('--from', $StartDate, '--to', $EndDate)
            }
            return @('--dates', $(if ($StartDate) { $StartDate } else { $wideExportDate }))
        }
        'month' {
            # 月度聚合是「重算整月」，不区分 from/to。
            return @($monthArg)
        }
        'flags' {
            if ($StartDate) {
                return @('--start', $StartDate, '--end', $(if ($EndDate) { $EndDate } else { $StartDate }))
            }
            return @()
        }
        default {
            $args = @()
            if ($StartDate) { $args += $StartDate }
            if ($EndDate) { $args += $EndDate }
            return $args
        }
    }
}

# 创建日志目录
if (-not (Test-Path $LOG_DIR)) {
    New-Item -ItemType Directory -Path $LOG_DIR -Force | Out-Null
}

$logFile = Join-Path $LOG_DIR "collect-$(Get-Date -Format 'yyyyMMdd-HHmmss').log"
$resultPath = if ($ResultFile) { [IO.Path]::GetFullPath($ResultFile) } else { Join-Path $LOG_DIR "collect-$RunId.result.json" }
$resultRows = @()

# 运行结果契约：outcome 与 exit code 分离（见 scripts\collect_result.ps1）。
. (Join-Path $PSScriptRoot 'collect_result.ps1')
$runResult = New-CollectRunResult -RunId $RunId -ShopId $ShopId -Sources $Sources `
    -Start $Start -End $End -Chain 'run_daily_collect'

function Write-Log {
    param([string]$Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$timestamp] $Message"
    Write-Host $line
    Add-Content -Path $logFile -Value $line -Encoding UTF8
}

Write-Log "=== 开始每日采集 ==="
Write-Log "日志文件: $logFile"

$successCount = 0
$failCount = 0

foreach ($collector in $COLLECTORS) {
    $name = $collector.Name
    $script = $collector.Script
    $isProjectScript = [bool]$collector.Project
    $scriptPath = if ($isProjectScript) { Join-Path $ProjectRoot "scripts\$script" } else { Join-Path $COLLECTORS_DIR $script }
    $scriptWorkDir = if ($isProjectScript) { $ProjectRoot } else { $COLLECTORS_DIR }

    # 双链互斥：RPA 链（/api/collect/trigger）持有该源的数据库租约时跳过，
    # 避免计划任务与手动触发对同一数据源并发采集。
    $leaseAlias = @{} ; foreach ($k in $sourceAliases.Keys) { $leaseAlias[$sourceAliases[$k]] = $k }
    $leaseKey = if ($leaseAlias.ContainsKey($collector.Script.Replace('.py', ''))) { $leaseAlias[$collector.Script.Replace('.py', '')] } else { $collector.Script.Replace('.py', '') }
    $leaseCheck = & $VENV_PYTHON (Join-Path $ProjectRoot 'scripts\check_collect_lease.py') $leaseKey --shop-id $ShopId --db-path $DbPath 2>$null
    if ($LASTEXITCODE -eq 3) {
        Write-Log "--- 跳过 $name ：另一条采集链（RPA 手动触发）持有租约，避免并发 ---"
        Add-CollectSourceResult -Result $runResult -Source $collector.Script.Replace('.py', '') `
            -Outcome 'skipped' -Reason 'lease_held_by_other_chain'
        continue
    }

    $collectorKey = $collector.Script.Replace('.py', '')
    $selectedKeys = @($Sources | ForEach-Object { if ($sourceAliases.ContainsKey($_)) { $sourceAliases[$_] } else { $_.Replace('.py', '') } })
    if ($Sources.Count -gt 0 -and $selectedKeys -notcontains $collectorKey) {
        Write-Log "--- 跳过未选择来源: $name ---"
        Add-CollectSourceResult -Result $runResult -Source $collectorKey `
            -Outcome 'skipped' -Reason 'not_requested'
        continue
    }

    Write-Log "--- 开始采集: $name ($script) ---"

    if (-not (Test-Path $scriptPath)) {
        Write-Log "  ✗ 脚本不存在: $scriptPath"
        $failCount++
        # 修复前这里不写 resultRows，结果文件里那次失败彻底消失。
        Add-CollectSourceResult -Result $runResult -Source $collectorKey `
            -Outcome 'failed' -ExitCode 1 -Reason 'script_not_found' -Detail $scriptPath
        continue
    }

    try {
        $startedAt = Get-Date
        $stdoutPath = "$logFile.$($collector.Script).stdout.tmp"
        $stderrPath = "$logFile.$($collector.Script).stderr.tmp"
        $arguments = @('"' + $scriptPath + '"')
        $arguments += Get-CollectorDateArguments -Collector $collector -StartDate $Start -EndDate $End
        $process = Start-Process -FilePath $VENV_PYTHON `
            -ArgumentList ($arguments -join ' ') `
            -WorkingDirectory $scriptWorkDir `
            -NoNewWindow -PassThru `
            -RedirectStandardOutput $stdoutPath `
            -RedirectStandardError $stderrPath `
            -ErrorAction Stop

        if (-not $process.WaitForExit($TIMEOUT_SECONDS * 1000)) {
            Write-Log "  ✗ $name 超时（$TIMEOUT_SECONDS 秒），终止进程" 
            Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
            $process.WaitForExit()
            foreach ($outputPath in @($stdoutPath, $stderrPath)) {
                if (Test-Path -LiteralPath $outputPath) {
                    $timedOutOutput = Get-Content -LiteralPath $outputPath -Raw -Encoding UTF8 -ErrorAction SilentlyContinue
                    if ($timedOutOutput) { Write-Log "  [timeout-output] $timedOutOutput" }
                    Remove-Item -LiteralPath $outputPath -Force -ErrorAction SilentlyContinue
                }
            }
            $failCount++
            $resultRows += [ordered]@{ source = $collectorKey; name = $name; status = 'timed_out'; exit_code = 124; error = "timeout_seconds=$TIMEOUT_SECONDS" }
            Add-CollectSourceResult -Result $runResult -Source $collectorKey `
                -Outcome 'failed' -ExitCode 124 -Reason 'timeout' `
                -Detail "timeout_seconds=$TIMEOUT_SECONDS" -StartedAt $startedAt `
                -DurationSeconds ((Get-Date) - $startedAt).TotalSeconds
            continue
        }

        # 读取输出
        if (Test-Path -LiteralPath $stdoutPath) {
            $stdout = Get-Content $stdoutPath -Raw -Encoding UTF8
            if ($stdout) {
                $stdout.Split("`n") | ForEach-Object {
                    if ($_.Trim()) { Write-Log "  [stdout] $_" }
                }
            }
            Remove-Item $stdoutPath -Force -ErrorAction SilentlyContinue
        }
        if (Test-Path -LiteralPath $stderrPath) {
            $stderr = Get-Content $stderrPath -Raw -Encoding UTF8
            if ($stderr) {
                $stderr.Split("`n") | ForEach-Object {
                    if ($_.Trim()) { Write-Log "  [stderr] $_" }
                }
            }
            Remove-Item $stderrPath -Force -ErrorAction SilentlyContinue
        }

        $sourceSucceeded = ($process.ExitCode -eq 0)
        if ($sourceSucceeded) {
            Write-Log "  ✓ $name 采集成功"
            $successCount++
        } else {
            Write-Log "  ✗ $name 采集失败，退出码: $($process.ExitCode)"
            $failCount++
        }

        # 结果记录与「采集是否成功」严格分离：记录动作自身出错只降级为 WARN，
        # 绝不能落进下面的采集 catch 分支，否则会被二次计为采集失败
        # （2026-10-23 曾因 collect_result.ps1 的 Nullable 缺陷导致失败数翻倍，
        #  且成功来源被误记成 exception 失败）。
        try {
            $finishedAt = Get-Date
            $resultRows += [ordered]@{
                source = $collectorKey
                name = $name
                status = if ($sourceSucceeded) { 'succeeded' } else { 'failed' }
                exit_code = $process.ExitCode
                started_at = $startedAt.ToString('o')
                finished_at = $finishedAt.ToString('o')
                duration_seconds = [math]::Round(($finishedAt - $startedAt).TotalSeconds, 2)
            }
            Add-CollectSourceResult -Result $runResult -Source $collectorKey `
                -Outcome $(if ($sourceSucceeded) { 'succeeded' } else { 'failed' }) `
                -ExitCode $process.ExitCode `
                -Reason $(if ($sourceSucceeded) { '' } else { 'nonzero_exit' }) `
                -StartedAt $startedAt -DurationSeconds ($finishedAt - $startedAt).TotalSeconds
        } catch {
            Write-Log "  ⚠ $name 结果记录失败（不影响采集结论）: $($_.Exception.Message)" 'WARN'
        }
    } catch {
        Write-Log "  ✗ $name 采集异常: $($_.Exception.Message)"
        $failCount++
        $resultRows += [ordered]@{ source = $collectorKey; name = $name; status = 'error'; exit_code = 1; error = $_.Exception.Message }
        Add-CollectSourceResult -Result $runResult -Source $collectorKey `
            -Outcome 'failed' -ExitCode 1 -Reason 'exception' -Detail $_.Exception.Message
    }

    # 采集间隔5秒，避免请求过快
    Start-Sleep -Seconds 5
}

Write-Log "=== 采集完成 ==="
Write-Log "成功: $successCount, 失败: $failCount, 总计: $($COLLECTORS.Count)"
Set-CollectRunOutcome -Result $runResult
# 结果文件统一用契约 schema：event='collect_run' + 契约 results[]，
# 计数取 Set-CollectRunOutcome 的推导值，与退出码同源。
# （修复前 event='batch_result' 但计数取自另一套 $successCount/$failCount，
#   两套口径会漂移，下游 daily_collect_all.ps1 读到的 failed 可能是重复计数。）
$resultReport = [ordered]@{
    schema_version = 2
    event = 'collect_run'
    run_id = $RunId
    shop_id = $ShopId
    start = $Start
    end = $End
    outcome = $runResult['outcome']
    reason = $runResult['reason']
    succeeded = $runResult['succeeded']
    failed = $runResult['failed']
    skipped = $runResult['skipped']
    results = @($runResult['results'])
    generated_at = (Get-Date).ToString('o')
}
$resultParent = Split-Path -Parent $resultPath
if ($resultParent -and -not (Test-Path $resultParent)) { New-Item -ItemType Directory -Path $resultParent -Force | Out-Null }
$resultReport | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $resultPath -Encoding UTF8
Write-Log "运行结论: $($runResult['outcome'])（$($runResult['reason'])），成功=$successCount 失败=$failCount 跳过=$($runResult['skipped'])"
Write-Log "结果文件: $resultPath"

# 清理7天前的日志
Get-ChildItem -Path $LOG_DIR -Filter "collect-*.log" | Where-Object {
    $_.LastWriteTime -lt (Get-Date).AddDays(-7)
} | Remove-Item -Force -ErrorAction SilentlyContinue

Release-CollectLock
# 退出码只承载「进程间传播」：0 仅代表 succeeded；1 代表有失败。
# 修复前是 exit $failCount，>255 会回绕成 0，把大批失败变成「成功」。
if ($runResult['outcome'] -eq 'succeeded' -or $runResult['outcome'] -eq 'skipped') { exit 0 }
exit 1
