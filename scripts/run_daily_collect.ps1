[CmdletBinding()]
param(
    [string]$RunId = $(if ($env:TMALL_COLLECT_RUN_ID) { $env:TMALL_COLLECT_RUN_ID } else { [guid]::NewGuid().ToString('N') }),
    [string]$ShopId = $(if ($env:TMALL_SHOP_ID) { $env:TMALL_SHOP_ID } else { '3828498662' }),
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
$VENV_PYTHON = if ($env:TMALL_COLLECT_PYTHON) { $env:TMALL_COLLECT_PYTHON } else { Join-Path $ProjectRoot '.venv\Scripts\python.exe' }
$COLLECTORS_DIR = if ($env:TMALL_COLLECTORS_DIR) { $env:TMALL_COLLECTORS_DIR } else {
    $externalCollectors = Join-Path (Split-Path -Parent $ProjectRoot) 'BI采集\collectors'
    if (Test-Path -LiteralPath $externalCollectors) { $externalCollectors } else { Join-Path $ProjectRoot 'collectors' }
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
$CollectLockPath = Join-Path $LogDir 'collect.lock'
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
    exit 0
}
('{"pid": ' + $PID + ', "started_at": "' + (Get-Date -Format o) + '"}') | Set-Content -LiteralPath $CollectLockPath -Encoding UTF8
# ==================== 互斥锁已获取 ====================


if (-not (Test-Path -LiteralPath $VENV_PYTHON)) { throw "采集 Python 不存在: $VENV_PYTHON" }
if (-not (Test-Path -LiteralPath $COLLECTORS_DIR)) { throw "采集器目录不存在: $COLLECTORS_DIR" }

# 采集顺序（有依赖关系的放后面）
$COLLECTORS = @(
    @{ Name = "BI商品日度"; Script = "collect_overview_full.py" },
    @{ Name = "BI商品月度"; Script = "aggregate_monthly.py" },
    @{ Name = "生意参谋-店铺流量"; Script = "collect_sycm_flow.py" },
    @{ Name = "生意参谋-单品流量"; Script = "collect_sycm_item_flow_v6.py" },
    @{ Name = "生意参谋-市场数据"; Script = "collect_sycm_market.py" },
    @{ Name = "万相台推广"; Script = "collect_wanxiangtai_dims_v4.py" }
)
$sourceAliases = @{
    bi_daily = 'collect_overview_full'; bi_monthly = 'aggregate_monthly'
    sycm_flow = 'collect_sycm_flow'; sycm_item_flow = 'collect_sycm_item_flow_v6'
    sycm_market = 'collect_sycm_market'; wanxiangtai = 'collect_wanxiangtai_dims_v4'
}

# 创建日志目录
if (-not (Test-Path $LOG_DIR)) {
    New-Item -ItemType Directory -Path $LOG_DIR -Force | Out-Null
}

$logFile = Join-Path $LOG_DIR "collect-$(Get-Date -Format 'yyyyMMdd-HHmmss').log"
$resultPath = if ($ResultFile) { [IO.Path]::GetFullPath($ResultFile) } else { Join-Path $LOG_DIR "collect-$RunId.result.json" }
$resultRows = @()

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
    $scriptPath = Join-Path $COLLECTORS_DIR $script

    # 双链互斥：RPA 链（/api/collect/trigger）持有该源的数据库租约时跳过，
    # 避免计划任务与手动触发对同一数据源并发采集。
    $leaseAlias = @{} ; foreach ($k in $sourceAliases.Keys()) { $leaseAlias[$sourceAliases[$k]] = $k }
    $leaseKey = if ($leaseAlias.ContainsKey($collector.Script.Replace('.py', ''))) { $leaseAlias[$collector.Script.Replace('.py', '')] } else { $collector.Script.Replace('.py', '') }
    $leaseCheck = & $VENV_PYTHON (Join-Path $ProjectRoot 'scripts\check_collect_lease.py') $leaseKey --shop-id $ShopId --db-path $DbPath 2>$null
    if ($LASTEXITCODE -eq 3) {
        Write-Log "--- 跳过 $name ：另一条采集链（RPA 手动触发）持有租约，避免并发 ---"
        continue
    }

    $collectorKey = $collector.Script.Replace('.py', '')
    $selectedKeys = @($Sources | ForEach-Object { if ($sourceAliases.ContainsKey($_)) { $sourceAliases[$_] } else { $_.Replace('.py', '') } })
    if ($Sources.Count -gt 0 -and $selectedKeys -notcontains $collectorKey) {
        Write-Log "--- 跳过未选择来源: $name ---"
        continue
    }

    Write-Log "--- 开始采集: $name ($script) ---"

    if (-not (Test-Path $scriptPath)) {
        Write-Log "  ✗ 脚本不存在: $scriptPath"
        $failCount++
        continue
    }

    try {
        $startedAt = Get-Date
        $stdoutPath = "$logFile.$($collector.Script).stdout.tmp"
        $stderrPath = "$logFile.$($collector.Script).stderr.tmp"
        $arguments = @('"' + $scriptPath + '"')
        if ($Start) { $arguments += $Start }
        if ($End) { $arguments += $End }
        $process = Start-Process -FilePath $VENV_PYTHON `
            -ArgumentList ($arguments -join ' ') `
            -WorkingDirectory $COLLECTORS_DIR `
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

        if ($process.ExitCode -eq 0) {
            Write-Log "  ✓ $name 采集成功"
            $successCount++
        } else {
            Write-Log "  ✗ $name 采集失败，退出码: $($process.ExitCode)"
            $failCount++
        }
        $resultRows += [ordered]@{
            source = $collector.Script.Replace('.py', '')
            name = $name
            status = if ($process.ExitCode -eq 0) { 'succeeded' } else { 'failed' }
            exit_code = $process.ExitCode
            started_at = $startedAt.ToString('o')
            finished_at = (Get-Date).ToString('o')
            duration_seconds = [math]::Round(((Get-Date) - $startedAt).TotalSeconds, 2)
        }
    } catch {
        Write-Log "  ✗ $name 采集异常: $($_.Exception.Message)"
        $failCount++
        $resultRows += [ordered]@{ source = $collector.Script.Replace('.py', ''); name = $name; status = 'error'; exit_code = 1; error = $_.Exception.Message }
    }

    # 采集间隔5秒，避免请求过快
    Start-Sleep -Seconds 5
}

Write-Log "=== 采集完成 ==="
Write-Log "成功: $successCount, 失败: $failCount, 总计: $($COLLECTORS.Count)"
$resultReport = [ordered]@{
    schema_version = 1
    event = 'batch_result'
    run_id = $RunId
    shop_id = $ShopId
    start = $Start
    end = $End
    succeeded = $successCount
    failed = $failCount
    results = $resultRows
    generated_at = (Get-Date).ToString('o')
}
$resultParent = Split-Path -Parent $resultPath
if ($resultParent -and -not (Test-Path $resultParent)) { New-Item -ItemType Directory -Path $resultParent -Force | Out-Null }
$resultReport | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $resultPath -Encoding UTF8
Write-Log "结果文件: $resultPath"

# 清理7天前的日志
Get-ChildItem -Path $LOG_DIR -Filter "collect-*.log" | Where-Object {
    $_.LastWriteTime -lt (Get-Date).AddDays(-7)
} | Remove-Item -Force -ErrorAction SilentlyContinue

Release-CollectLock
exit $failCount
