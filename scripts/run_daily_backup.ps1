# 定时数据库备份脚本
# 用法: .\run_daily_backup.ps1
# 保留策略: 7天日备 + 4周周备（每周日的备份保留4周）

$ErrorActionPreference = "Continue"

# 配置。计划任务可通过环境变量覆盖，默认跟随脚本所在项目目录。
$PROJECT_DIR = if ($env:TMALL_PROJECT_ROOT) { $env:TMALL_PROJECT_ROOT } else { Split-Path -Parent $PSScriptRoot }
$VENV_PYTHON = if ($env:TMALL_COLLECT_PYTHON) { $env:TMALL_COLLECT_PYTHON } else { Join-Path $PROJECT_DIR '.venv\Scripts\python.exe' }
$BACKUP_SCRIPT = Join-Path $PROJECT_DIR 'scripts\backup_database.py'
$DB_PATH = if ($env:TMALL_DB_PATH) { $env:TMALL_DB_PATH } else { Join-Path $PROJECT_DIR 'data\dashboard.db' }
$BACKUP_DIR = if ($env:TMALL_BACKUP_DIR) { $env:TMALL_BACKUP_DIR } else { Join-Path $PROJECT_DIR 'data\backups' }
$LOG_DIR = if ($env:TMALL_LOG_DIR) { $env:TMALL_LOG_DIR } else { Join-Path $PROJECT_DIR 'logs' }
$RETENTION_DAYS = if ($env:TMALL_BACKUP_RETENTION_DAYS) { [int]$env:TMALL_BACKUP_RETENTION_DAYS } else { 7 }
$RETENTION_WEEKS = if ($env:TMALL_BACKUP_RETENTION_WEEKS) { [int]$env:TMALL_BACKUP_RETENTION_WEEKS } else { 4 }

# 创建日志目录
if (-not (Test-Path $LOG_DIR)) {
    New-Item -ItemType Directory -Path $LOG_DIR -Force | Out-Null
}

$logFile = Join-Path $LOG_DIR "backup-$(Get-Date -Format 'yyyyMMdd-HHmmss').log"

function Write-Log {
    param([string]$Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$timestamp] $Message"
    Write-Host $line
    Add-Content -Path $logFile -Value $line -Encoding UTF8
}

Write-Log "=== 开始每日备份 ==="
Write-Log "数据库: $DB_PATH"
Write-Log "备份目录: $BACKUP_DIR"

# 1. 检查数据库是否存在
if (-not (Test-Path $DB_PATH)) {
    Write-Log "✗ 数据库不存在: $DB_PATH"
    exit 1
}

$dbSize = (Get-Item $DB_PATH).Length / 1MB
Write-Log "数据库大小: $([math]::Round($dbSize, 2)) MB"

# 2. 执行备份（用现有的 backup_database.py，带完整性校验）
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backupFile = Join-Path $BACKUP_DIR "dashboard-daily-$stamp.db"

try {
    $result = & $VENV_PYTHON $BACKUP_SCRIPT --source $DB_PATH --destination $backupFile 2>&1
    $exitCode = $LASTEXITCODE

    if ($exitCode -eq 0 -and (Test-Path $backupFile)) {
        $backupSize = (Get-Item $backupFile).Length / 1MB
        Write-Log "✓ 备份成功: $backupFile ($([math]::Round($backupSize, 2)) MB)"
    } else {
        Write-Log "✗ 备份失败，退出码: $exitCode"
        Write-Log "  输出: $result"
        exit 1
    }
} catch {
    Write-Log "✗ 备份异常: $($_.Exception.Message)"
    exit 1
}

# 3. 清理旧备份（保留策略）
Write-Log "--- 清理旧备份 ---"
$today = Get-Date
$cutoffDaily = $today.AddDays(-$RETENTION_DAYS)
$cutoffWeekly = $today.AddDays(-$RETENTION_WEEKS * 7)

$dailyBackups = Get-ChildItem -Path $BACKUP_DIR -Filter "dashboard-daily-*.db" -ErrorAction SilentlyContinue
$removedCount = 0
$removedSize = 0

foreach ($backup in $dailyBackups) {
    $isSunday = ($backup.LastWriteTime.DayOfWeek -eq 'Sunday')

    if ($isSunday) {
        # 周日备份：保留4周
        if ($backup.LastWriteTime -lt $cutoffWeekly) {
            $removedSize += $backup.Length
            Remove-Item $backup.FullName -Force
            $removedCount++
            Write-Log "  删除周备(超4周): $($backup.Name)"
        }
    } else {
        # 日常备份：保留7天
        if ($backup.LastWriteTime -lt $cutoffDaily) {
            $removedSize += $backup.Length
            Remove-Item $backup.FullName -Force
            $removedCount++
            Write-Log "  删除日备(超7天): $($backup.Name)"
        }
    }
}

if ($removedCount -gt 0) {
    Write-Log "  共删除 $removedCount 个旧备份，释放 $([math]::Round($removedSize/1MB, 2)) MB"
} else {
    Write-Log "  无需清理"
}

# 4. 清理7天前的备份日志
Get-ChildItem -Path $LOG_DIR -Filter "backup-*.log" | Where-Object {
    $_.LastWriteTime -lt (Get-Date).AddDays(-7)
} | Remove-Item -Force -ErrorAction SilentlyContinue

# 5. 统计当前备份
$allBackups = Get-ChildItem -Path $BACKUP_DIR -Filter "*.db"
$totalSize = ($allBackups | Measure-Object -Property Length -Sum).Sum / 1MB
Write-Log "--- 备份统计 ---"
Write-Log "  备份文件总数: $($allBackups.Count)"
Write-Log "  备份总大小: $([math]::Round($totalSize, 2)) MB"

Write-Log "=== 备份完成 ==="
exit 0
