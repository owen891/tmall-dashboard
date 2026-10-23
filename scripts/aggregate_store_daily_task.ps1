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
    # 显式目标日期（YYYY-MM-DD，可多个）。给定时按这些日期聚合，忽略 -LookbackDays。
    # 补采链必须走这条路：回看窗口以「今天」为锚，补的是一个历史日期时两者未必相交，
    # 修复前 13:00 补采 10-22 却聚合了一个不含 10-22 的窗口，补完依旧没有 store_daily_facts。
    [string[]]$Dates = @(),
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

# 统一解释器解析（2026-10-23 修复「统一运行」缺陷）。
# 修复前这里硬编码 .venv\Scripts\python.exe，而采集链其它入口（auto-collect /
# catchup_collect / daily_collect_all / run_daily_collect）都走 resolve_runtime.ps1
# 读 data/runtime.json。于是同一条采集链里并存两个解释器：采集用 runtime python、
# 聚合用 venv python，两者的 site-packages 与进程身份都不同。
# 后果（实测）：2026-10-22 16:11 起 venv python 写 F: 盘被拦
# （PermissionError: [Errno 13]，而同一时刻 runtime python / 系统 python / cmd /
# PowerShell 写同一目录均正常），聚合每天失败；当时调用方忽略退出码，
# store_daily_facts 就此静默停更——这正是「采集数据对不齐」的直接根因之一。
# 改为统一走同一个解析器：TMALL_COLLECT_PYTHON 优先，其次 data/runtime.json，
# 最后才回退 .venv（回退逻辑只保留在 resolve_runtime.ps1 一处）。
. (Join-Path $PSScriptRoot 'resolve_runtime.ps1')
try {
    $PythonPath = Resolve-CollectorPython -ProjectRoot $ProjectRoot
} catch {
    # 运行时配置非法：沿用 auto-collect.ps1 的 20（RUNTIME_CONFIG_INVALID），
    # 让计划任务 LastTaskResult 与日志直接指向「配置坏了」而不是一个空路径。
    Write-Host "[ERROR] 运行时解析失败：$($_.Exception.Message)" -ForegroundColor Red
    exit 20
}
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

# 2. 备份目的地可写性预检 + 显式回退（2026-10-23 新增）。
#
# 背景（实测）：2026-10-22 16:11 起，F: 盘对部分 Python 进程间歇性拒绝写入
# （PermissionError: [Errno 13]），而同一时刻 cmd.exe / PowerShell / 系统 python /
# 采集用的 runtime python 写同一目录都正常；且会在写入中途翻转——本次实测
# 16:49:33 成功建出 0 字节目标文件，随后 12 分钟零字节零 CPU，进程卡死。
# 后果：聚合每天失败，store_daily_facts 静默停更。
#
# 「先备份再写库」这条安全属性不能因为一个外部卷不可靠就被破坏，也不能退化成
# 无声失败。所以这里在真正聚合前，用**即将执行备份的那个解释器**做一次真实写入
# 探测（不能用 .NET/PowerShell 探测：它们的写权限与 Python 不同，会给出假阳性），
# 不可写就回退到项目内 data\backups，并把回退事实写进日志。
function Test-BackupDestinationWritable {
    param([string]$Path, [string]$Python)
    try {
        if (-not (Test-Path -LiteralPath $Path)) {
            New-Item -ItemType Directory -Path $Path -Force -ErrorAction Stop | Out-Null
        }
    } catch { return $false }
    $probeFile = Join-Path $Path ('.write-probe-' + [guid]::NewGuid().ToString('N') + '.tmp')
    $probe = & $Python -c "import os,sys
p = sys.argv[1]
try:
    with open(p,'wb') as f:
        f.write(b'probe')
    os.remove(p)
    print('OK')
except Exception:
    print('FAIL')" $probeFile 2>&1
    if (Test-Path -LiteralPath $probeFile) { Remove-Item -LiteralPath $probeFile -Force -ErrorAction SilentlyContinue }
    return ((($probe -join '') -match 'OK') -eq $true)
}

$EffectiveBackupDir = $BackupDir
if (-not (Test-BackupDestinationWritable -Path $BackupDir -Python $PythonPath)) {
    Write-Log "备份目录不可写：$BackupDir（用 $PythonPath 实测写入失败）" "WARN"
    $fallbackDir = Join-Path $ProjectRoot 'data\backups'
    if (Test-BackupDestinationWritable -Path $fallbackDir -Python $PythonPath) {
        $EffectiveBackupDir = $fallbackDir
        Write-Log "已回退到可写备份目录：$EffectiveBackupDir（原配置：$BackupDir）" "WARN"
    } else {
        # 24 = BACKUP_DESTINATION_UNWRITABLE。宁可显式失败，也不做「无备份写库」。
        Write-Log "回退目录也不可写：$fallbackDir；放弃聚合（不做无备份的写库）" "ERROR"
        Write-Log "========================================"
        exit 24
    }
} else {
    Write-Log "备份目录可写：$BackupDir"
}

# 3. 执行聚合。--skip-if-current 让「另一个入口已经聚合过」的情况零成本退出，
#    避免每天两份 2.9GB 全量备份。
$backup = Join-Path $EffectiveBackupDir "aggregate-store-daily-$(Get-Date -Format 'yyyyMMdd-HHmmss').db"
$dateArgs = @()
$targets = @($Dates | ForEach-Object { $_ -split ',' } | ForEach-Object { $_.Trim() } | Where-Object { $_ })
if ($targets.Count -gt 0) {
    $dateArgs = @('--dates') + $targets
    Write-Log "执行聚合：aggregate_store_daily.py --apply --dates $($targets -join ',') --skip-if-current"
} else {
    Write-Log "执行聚合：aggregate_store_daily.py --apply --lookback-days $LookbackDays --skip-if-current"
}
$aggOutput = & $PythonPath $AggScript --apply --lookback-days $LookbackDays @dateArgs `
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
    # 2026-10-20 用户决定：正常运营不留整库快照（每天 15GB 快照曾写满 E 盘并导致
    # 聚合报 database or disk is full）。聚合成功后立即删除本次快照及 sidecar；
    # 失败路径保留快照（在上方 exit 1 分支之前不会走到这里），供人工排查。
    foreach ($suffix in @('', '-wal', '-shm', '-journal', '.manifest.json')) {
        $sidecar = "$backup$suffix"
        if (Test-Path -LiteralPath $sidecar) {
            Remove-Item -LiteralPath $sidecar -Force -ErrorAction SilentlyContinue
        }
    }
    if (-not (Test-Path -LiteralPath $backup)) {
        Write-Log "  已删除本次快照（用户要求：正常不留备份）"
    } else {
        Write-Log "  ⚠ 快照删除失败，请手动清理：$backup" "WARN"
    }
} else {
    Write-Log "✓ 聚合完成（数据已是最新，未产生备份）"
}
Write-Log "========================================"
exit 0
