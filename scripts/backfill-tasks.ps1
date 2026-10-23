# ============================================================
# 滚动重采计划任务入口（Windows 任务计划程序调用）
#   weekly  : 每周二 10:00 重采近 14 天（利润事后修订 + 13 天退款字段窗口刚过）
#   monthly : 每月 3 日 10:15 全量重采上个自然月（月复盘定稿前拿到定稿利润）
# 实际窗口计算/互斥锁/登录/补采在 backfill_rolling.py，本文件只做编码与 venv。
# ============================================================
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('weekly', 'monthly')]
    [string]$Mode
)

$ErrorActionPreference = "Continue"
$env:PYTHONIOENCODING = 'utf-8'
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = $OutputEncoding

$ProjectRoot = if ($env:TMALL_PROJECT_ROOT) { $env:TMALL_PROJECT_ROOT } else { Split-Path -Parent $PSScriptRoot }
# 统一解释器解析（2026-10-23 修复「统一运行」缺陷）：不再硬编码 .venv，
# 与采集/聚合/备份链一致走 resolve_runtime.ps1。
. (Join-Path $PSScriptRoot 'resolve_runtime.ps1')
try {
    $PythonPath = Resolve-CollectorPython -ProjectRoot $ProjectRoot
} catch {
    Write-Host "[ERROR] 运行时解析失败：$($_.Exception.Message)" -ForegroundColor Red
    exit 20
}

& $PythonPath (Join-Path $PSScriptRoot 'backfill_rolling.py') -Mode $Mode
exit $LASTEXITCODE
