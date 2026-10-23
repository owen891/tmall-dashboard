[CmdletBinding()]
param(
    [string]$ProjectRoot,
    [string]$BaseUrl = $(if ($env:TMALL_DASHBOARD_URL) { $env:TMALL_DASHBOARD_URL } else { 'http://127.0.0.1:5000' }),
    [string]$Database = $(if ($env:TMALL_DB_PATH) { $env:TMALL_DB_PATH } else { 'data/dashboard.db' })
)

# 不要在 param 默认值里求 $MyInvocation.MyCommand.Path —— 通过
# powershell.exe -File 调用时它在参数绑定阶段为空，会让脚本在第一行就抛
# ParameterArgumentValidationError（2026-10-02 实测，这也是本脚本此前从未
# 成功运行过的原因）。$PSCommandPath 在 param 块之后才可靠。
if (-not $ProjectRoot) {
    $ProjectRoot = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
}

$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $ProjectRoot
# 统一解释器解析（2026-10-23 修复「统一运行」缺陷）：不再硬编码 .venv，
# 与采集/聚合/备份链一致走 resolve_runtime.ps1。
. (Join-Path $PSScriptRoot 'resolve_runtime.ps1')
try {
    $python = Resolve-CollectorPython -ProjectRoot $ProjectRoot
} catch {
    Write-Host "[ERROR] 运行时解析失败：$($_.Exception.Message)" -ForegroundColor Red
    exit 20
}
$logDir = Join-Path $ProjectRoot 'logs'
New-Item -ItemType Directory -Path $logDir -Force | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$healthOutput = Join-Path $logDir "collector-health-$stamp.json"
$schemaOutput = Join-Path $logDir "collector-schema-$stamp.json"

& $python (Join-Path $ProjectRoot 'scripts\collector_healthcheck.py') --base-url $BaseUrl --output $healthOutput
$healthExit = $LASTEXITCODE
& $python (Join-Path $ProjectRoot 'scripts\collector_schema_check.py') --base-url $BaseUrl --db-path $Database --output $schemaOutput
$schemaExit = $LASTEXITCODE

if ($healthExit -eq 0 -and $schemaExit -eq 0) { exit 0 }
if ($healthExit -eq 2 -or $schemaExit -eq 2) { exit 2 }
exit 1
