# ============================================================
# 独立聚合任务：从 daily_data 重算 store_daily_facts
#
# 背景（2026-10-02）：
#   聚合原先只挂在 auto-collect.ps1 的 [5b]，位置在「等待采集完成」之后。
#   采集脚本一旦被中断（2026-10-02 实测 LastTaskResult=0xC000013A），聚合就
#   静默不跑，store_daily_facts 悄悄落后于 daily_data，且不产生任何报错——
#   9-30 那次事故里 store_daily_facts 停在 9-29 就是这个原因。
#   本脚本把聚合拆成独立计划任务，与「采集是否跑完」彻底解耦。
#
# 与 auto-collect.ps1 的关系：
#   [5b] 保留原调用（正常结束时及时聚合），两个入口都带 --skip-if-current，
#   先跑的一方真正聚合，后跑的一方零成本跳过，不会重复产生 2.9GB 全量备份。
#
# 用法：
#   .\aggregate_store_daily_task.ps1
#   .\aggregate_store_daily_task.ps1 -LookbackDays 30
# ============================================================

param(
    [int]$LookbackDays = 14,
    # 等采集锁释放的上限。采集批次最晚 11:30 启动、等待上限 20 分钟，
    # 45 分钟足以覆盖「登录重试 + 采集 + 等待」的最坏情况。
    [int]$LockWaitSeconds = 2700
)

$ErrorActionPreference = "Continue"

# 计划任务里 Python 的 stdout 是管道，默认按 GBK 解码，中文/符号会乱码。
$env:PYTHONIOENCODING = 'utf-8'
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = $OutputEncoding

# ==================== 配置 ====================
$ProjectRoot = if ($env:TMALL_PROJECT_ROOT) { $env:TMALL_PROJECT_ROOT } else { Split-Path -Parent $PSScriptRoot }
$PythonPath = if ($env:TMALL_COLLECT_PYTHON) { $env:TMALL_COLLECT_PYTHON } else { Join-Path $ProjectRoot '.venv\Scripts\python.exe' }
$LogDir = if ($env:TMALL_LOG_DIR) { $env:TMALL_LOG_DIR } else { Join-Path $ProjectRoot 'logs' }
$BackupDir = if ($env:TMALL_BACKUP_DIR) { $env:TMALL_BACKUP_DIR } else { Join-Path $ProjectRoot 'data\backups' }
$AggScript = Join-Path $ProjectRoot 'scripts\aggregate_store_daily.py'
$CollectLockPath = Join-Path $LogDir 'collect.lock'
# 与 auto-collect.ps1 保持一致的锁约定（只读判定，本脚本不获取也不释放锁）。
$CollectLockTtlSeconds = 7200

if (-not (Test-Path -LiteralPath $PythonPath)) { throw "采集 Python 不存在: $PythonPath" }
if (-not (Test-Path -LiteralPath $AggScript)) { throw "聚合脚本不存在: $AggScript" }
foreach ($dir in @($LogDir, $BackupDir)) {
    if (-not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
}

$logFile = Join-Path $LogDir "aggregate-daily-$(Get-Date -Format 'yyyyMMdd-HHmmss').log"

function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    $line = "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] [$Level] $Message"
    Write-Host $line
    Add-Content -Path $logFile -Value $line -Encoding UTF8
}

# 采集锁是否仍被活着的进程持有。与 auto-collect.ps1:Test-CollectLockBusy 同源
# （TTL 7200s + 属主 PID 存活）；此处不删除过期锁文件，那是采集链自己的职责。
function Test-CollectLockBusy {
    if (-not (Test-Path -LiteralPath $CollectLockPath)) { return $false }
    $raw = (Get-Content -LiteralPath $CollectLockPath -ErrorAction SilentlyContinue | Select-Object -First 1) -as [string]
    $ownerPid = $null
    if ($raw -match '"pid"\s*:\s*(\d+)') { $ownerPid = [int]$Matches[1] }
    $ageSeconds = ((Get-Date) - (Get-Item -LiteralPath $CollectLockPath).LastWriteTime).TotalSeconds
    $ownerAlive = $false
    if ($ownerPid) { $ownerAlive = [bool](Get-Process -Id $ownerPid -ErrorAction SilentlyContinue) }
    return ($ageSeconds -lt $CollectLockTtlSeconds -and $ownerAlive)
}

Write-Log "========================================"
Write-Log "  独立聚合任务开始（lookback=$LookbackDays 天）"
Write-Log "========================================"

# 1. 等待采集链让出锁。聚合读 daily_data、采集写 daily_data，虽然 SQLite 事务
#    下并发不会损坏数据，但在采集中途聚合会读到半截数据并被 --skip-if-current
#    判为「不一致」而写库。等一等更安全。
if (Test-CollectLockBusy) {
    Write-Log "采集锁被占用，等待其释放（最多 $LockWaitSeconds 秒）..."
    $waited = 0
    while ((Test-CollectLockBusy) -and ($waited -lt $LockWaitSeconds)) {
        Start-Sleep -Seconds 30
        $waited += 30
        Write-Log "  已等待 $waited 秒..."
    }
    if (Test-CollectLockBusy) {
        Write-Log "等待超时，采集仍在运行；仍执行聚合（幂等 + 回看窗口，次日会重算修正）" "WARN"
    } else {
        Write-Log "  ✓ 采集锁已释放（等待 $waited 秒）"
    }
} else {
    Write-Log "采集锁空闲，直接执行聚合"
}

# 2. 执行聚合。--skip-if-current 让「另一个入口已经聚合过」的情况零成本退出，
#    避免每天两份 2.9GB 全量备份。
$backup = Join-Path $BackupDir "aggregate-store-daily-$(Get-Date -Format 'yyyyMMdd-HHmmss').db"
Write-Log "执行聚合：aggregate_store_daily.py --apply --skip-if-current"
$aggOutput = & $PythonPath $AggScript --apply --lookback-days $LookbackDays `
    --skip-if-current --backup-destination $backup 2>&1
$exitCode = $LASTEXITCODE
foreach ($line in $aggOutput) { Write-Log "  $line" }

if ($exitCode -ne 0) {
    Write-Log "✗ 聚合失败，退出码 $exitCode" "ERROR"
    Write-Log "========================================"
    exit 1
}

if (Test-Path -LiteralPath $backup) {
    Write-Log "✓ 聚合完成，备份：$backup"
} else {
    Write-Log "✓ 聚合完成（数据已是最新，未产生备份）"
}
Write-Log "========================================"
exit 0
