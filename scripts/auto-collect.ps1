# ============================================================
# 完整RPA自动化采集脚本
# 功能：启动Chrome -> 自动登录BI -> 打开所有页面 -> 触发采集 -> 等待完成 -> 输出结果
# 用法:
#   .\auto-collect.ps1                    # 采集全部
#   .\auto-collect.ps1 -Sources bi_daily,bi_monthly  # 只采集BI
#   .\auto-collect.ps1 -Sources sycm_flow,sycm_item_flow,sycm_market,wanxiangtai  # 只采集其他
# 可通过 Windows 任务计划程序每天定时调用
# ============================================================

param(
    [string[]]$Sources = @('bi_daily', 'bi_monthly', 'sycm_flow', 'sycm_item_flow', 'sycm_market', 'wanxiangtai')
)

$ErrorActionPreference = "Continue"

# powershell.exe -File passes comma-separated sources as a single argument.
$Sources = @($Sources | ForEach-Object { $_ -split ',' } | ForEach-Object { $_.Trim() } | Where-Object { $_ })

# Scheduled Python processes write to a pipe, which otherwise defaults to GBK.
# Use the same encoding on both sides so status symbols and Chinese survive.
$env:PYTHONIOENCODING = 'utf-8'
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = $OutputEncoding

# ==================== 配置 ====================
$ChromePath = "C:\Program Files\Google\Chrome\Application\chrome.exe"
$ChromeDebugPort = if ($env:TMALL_CDP_PORT) { [int]$env:TMALL_CDP_PORT } else { 9223 }
$ChromeUserDataDir = "$env:LOCALAPPDATA\TmallDashboard\CollectorChrome"
$ChromeHeadless = if ($env:TMALL_CHROME_HEADLESS) { $env:TMALL_CHROME_HEADLESS -eq '1' } else { $false }  # 默认有界面模式，方便手动处理验证码
$DashboardUrl = "http://127.0.0.1:5000"
$ProjectRoot = if ($env:TMALL_PROJECT_ROOT) { $env:TMALL_PROJECT_ROOT } else { Split-Path -Parent $PSScriptRoot }
$PythonPath = if ($env:TMALL_COLLECT_PYTHON) { $env:TMALL_COLLECT_PYTHON } else { Join-Path $ProjectRoot '.venv\Scripts\python.exe' }
$LogDir = if ($env:TMALL_LOG_DIR) { $env:TMALL_LOG_DIR } else { Join-Path $ProjectRoot 'logs' }

if (-not (Test-Path -LiteralPath $PythonPath)) { throw "采集 Python 不存在: $PythonPath" }

$ChromeStartTimeout = 30
# Must exceed COLLECT_TIMEOUT in api/collect_api.py (900s for full-column BI collection).
$CollectWaitTimeout = if ($env:TMALL_COLLECT_WAIT_TIMEOUT) { [int]$env:TMALL_COLLECT_WAIT_TIMEOUT } else { 1200 }
$CloseChromeAfterCollect = $false

$BIUsername = $env:BI_USERNAME
$BIPassword = $env:BI_PASSWORD
$CredentialFile = if ($env:TMALL_CREDENTIAL_FILE) { $env:TMALL_CREDENTIAL_FILE } else { 'E:\桌面\AI\BI.txt' }
if (([string]::IsNullOrWhiteSpace($BIUsername) -or [string]::IsNullOrWhiteSpace($BIPassword)) -and (Test-Path -LiteralPath $CredentialFile)) {
    $credentialLines = Get-Content -LiteralPath $CredentialFile -Encoding UTF8
    for ($i = 0; $i -lt $credentialLines.Count; $i++) {
        if ($credentialLines[$i] -match '^账号[：:]\s*(.+)$' -and $i + 1 -lt $credentialLines.Count) {
            $fileUsername = $Matches[1].Trim()
            if ($credentialLines[$i + 1] -match '^密码[：:]\s*(.+)$') {
                $filePassword = $Matches[1].Trim()
                if ([string]::IsNullOrWhiteSpace($BIUsername)) { $BIUsername = $fileUsername }
                if ([string]::IsNullOrWhiteSpace($BIPassword)) { $BIPassword = $filePassword }
            }
            if (-not [string]::IsNullOrWhiteSpace($BIUsername) -and -not [string]::IsNullOrWhiteSpace($BIPassword)) { break }
        }
    }
}
if ($Sources | Where-Object { $_ -like 'bi_*' }) {
    # auto_login_bi.py also reads credentials saved in the dashboard settings.
}

$sourceNames = @{
    'bi_daily' = 'BI商品日度'
    'bi_monthly' = 'BI商品月度'
    'sycm_flow' = '生意参谋-店铺流量'
    'sycm_item_flow' = '生意参谋-单品流量'
    'sycm_market' = '生意参谋-市场数据'
    'wanxiangtai' = '万相台推广'
}

$needBIPage = $Sources | Where-Object { $_ -like 'bi_*' }
$needOtherPages = $Sources | Where-Object { $_ -like 'sycm_*' -or $_ -eq 'wanxiangtai' }

if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
}

$logFile = Join-Path $LogDir "auto-collect-$(Get-Date -Format 'yyyyMMdd-HHmmss').log"

function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$timestamp] [$Level] $Message"
    Write-Host $line
    Add-Content -Path $logFile -Value $line -Encoding UTF8
}

Write-Log "========================================"
Write-Log "  RPA 自动化采集开始"
Write-Log "  采集数据源: $($Sources -join ', ')"
Write-Log "========================================"

# 1. 检查看板服务；不在则自动拉起。
# 计划任务只负责触发采集，原先看板没启动就直接 exit 1，整批采集静默跳过。
Write-Log "`n[1/6] 检查看板服务状态..."
function Test-Dashboard {
    try {
        $null = Invoke-WebRequest -Uri "$DashboardUrl/api/health" -UseBasicParsing -TimeoutSec 5
        return $true
    } catch { return $false }
}
if (Test-Dashboard) {
    Write-Log "  ✓ 看板服务运行正常"
} else {
    Write-Log "  看板服务未启动，尝试自动拉起..."
    $dashboardScript = Join-Path $ProjectRoot 'app.py'
    Start-Process -FilePath $PythonPath -ArgumentList "`"$dashboardScript`"" `
        -WorkingDirectory $ProjectRoot -WindowStyle Hidden
    $dashboardReady = $false
    for ($i = 0; $i -lt 60; $i++) {
        Start-Sleep -Seconds 1
        if (Test-Dashboard) { Write-Log "  ✓ 看板服务已启动（$($i+1)秒）"; $dashboardReady = $true; break }
    }
    if (-not $dashboardReady) {
        Write-Log "  ✗ 看板服务自动启动失败，无法触发采集" "ERROR"
        exit 1
    }
}

# 2. 启动Chrome调试模式
Write-Log "`n[2/6] 检查并启动Chrome调试模式..."
function Test-ChromeDebug {
    try {
        $resp = Invoke-WebRequest -Uri "http://127.0.0.1:$ChromeDebugPort/json/version" -UseBasicParsing -TimeoutSec 2
        return ($resp.StatusCode -eq 200)
    } catch { return $false }
}

if (Test-ChromeDebug) {
    Write-Log "  ✓ Chrome调试模式已在运行"
} else {
    Write-Log "  启动Chrome调试模式..."
    $chromeArgs = @(
        "--remote-debugging-port=$ChromeDebugPort",
        "--remote-allow-origins=*",
        "--user-data-dir=`"$ChromeUserDataDir`"",
        "--no-first-run",
        "--no-default-browser-check"
    )
    if ($ChromeHeadless) { $chromeArgs += '--headless=new'; $chromeArgs += '--disable-gpu' }
    Start-Process -FilePath $ChromePath -ArgumentList $chromeArgs -WindowStyle Hidden

    for ($i = 0; $i -lt $ChromeStartTimeout; $i++) {
        Start-Sleep -Seconds 1
        if (Test-ChromeDebug) { Write-Log "  ✓ Chrome启动成功（$($i+1)秒）"; break }
    }
}

# 3. 自动登录 & 打开页面
Write-Log "`n[3/6] 自动登录BI页面并打开采集页面..."
if ($needBIPage -or $needOtherPages) {
    $autoLoginScript = Join-Path $ProjectRoot "scripts\auto_login_bi.py"
    $loginArgs = @($autoLoginScript)
    if (-not $needBIPage) { $loginArgs += '--skip-bi-login' }
    if ($BIUsername) { $env:BI_USERNAME = $BIUsername }
    if ($BIPassword) { $env:BI_PASSWORD = $BIPassword }
    
    # 第一次尝试：headless模式自动登录
    $loginOutput = & $PythonPath @loginArgs 2>&1
    foreach ($line in $loginOutput) { Write-Log "  $line" }
    $biLoginFailed = ($LASTEXITCODE -ne 0)
    
    # 如果BI登录失败，尝试弹出有界面浏览器让用户手动登录
    if ($biLoginFailed -and $needBIPage) {
        Write-Log "  ⚠ 自动登录失败（可能需要验证码/滑块），切换到有界面模式，请手动完成登录..." "WARN"
        
        # 关闭当前headless Chrome
        Get-Process chrome -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like "*$ChromeUserDataDir*" } | Stop-Process -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 2
        
        # 用有界面模式重新启动Chrome
        Write-Log "  启动有界面Chrome，请在弹出的窗口中手动完成登录..."
        $chromeArgs = @(
            "--remote-debugging-port=$ChromeDebugPort",
            "--remote-allow-origins=*",
            "--user-data-dir=`"$ChromeUserDataDir`"",
            "--no-first-run",
            "--no-default-browser-check",
            "https://primeet.ecbis.cn/login"
        )
        Start-Process -FilePath $ChromePath -ArgumentList $chromeArgs -WindowStyle Normal
        
        # 等待用户手动登录（最多等待5分钟）
        Write-Log "  等待手动登录（最多5分钟）..."
        $manualLoginOK = $false
        for ($i = 0; $i -lt 300; $i++) {
            Start-Sleep -Seconds 1
            try {
                $resp = Invoke-WebRequest -Uri "http://127.0.0.1:$ChromeDebugPort/json" -UseBasicParsing -TimeoutSec 2
                $tabs = $resp.Content | ConvertFrom-Json
                $biTab = $tabs | Where-Object { $_.url -like "*primeet.ecbis.cn*" -and $_.url -notlike "*login*" } | Select-Object -First 1
                if ($biTab) {
                    $manualLoginOK = $true
                    Write-Log "  ✓ 检测到BI登录成功！"
                    break
                }
            } catch { }
        }
        
        if (-not $manualLoginOK) {
            Write-Log "  ⚠ 等待5分钟仍未检测到登录成功，跳过BI相关任务" "WARN"
            $Sources = @($Sources | Where-Object { $_ -notlike 'bi_*' })
            $needBIPage = $false
        }
    } elseif ($biLoginFailed) {
        Write-Log "  ⚠ BI页面登录失败，将跳过BI相关采集任务，继续执行其他采集" "WARN"
        $Sources = @($Sources | Where-Object { $_ -notlike 'bi_*' })
        $needBIPage = $false
    }
    
    Write-Log "  等待页面加载..."
    Start-Sleep -Seconds 5
} else {
    Write-Log "  - 无需打开页面"
}

# 3b. 万相台自动登录（cookie 持久化，只在过期时才账密登录）
if ($Sources -contains 'wanxiangtai') {
    Write-Log "`n[3b] 检查万相台登录态..."
    $wxtLoginScript = Join-Path $ProjectRoot "scripts\auto_login_wanxiangtai.py"
    $wxtOutput = & $PythonPath $wxtLoginScript 2>&1
    foreach ($line in $wxtOutput) { Write-Log "  $line" }
}

# 4. 触发采集任务
Write-Log "`n[4/6] 触发采集任务..."
$triggered = @()
foreach ($source in $Sources) {
    $name = $sourceNames[$source]
    try {
        $body = @{source = $source} | ConvertTo-Json
        $resp = Invoke-WebRequest -Uri "$DashboardUrl/api/collect/trigger" -Method POST -Body $body -ContentType "application/json" -UseBasicParsing -TimeoutSec 60
        $data = $resp.Content | ConvertFrom-Json
        if ($data.ok) { Write-Log "  ✓ 已触发: $name"; $triggered += $source }
        else { Write-Log "  ✗ 触发失败: $name - $($data.message)" "WARN" }
    } catch {
        Write-Log "  ✗ 触发异常: $name - $($_.Exception.Message)" "WARN"
    }
    Start-Sleep -Seconds 2
}

if ($triggered.Count -eq 0) { Write-Log "  ✗ 没有触发任何任务" "ERROR"; exit 1 }
Write-Log "  成功触发 $($triggered.Count) 个任务"

# 5. 等待采集完成
Write-Log "`n[5/6] 等待采集完成..."
for ($i = 0; $i -lt $CollectWaitTimeout; $i += 10) {
    Start-Sleep -Seconds 10
    $running = 0; $completed = 0; $partial = 0; $failed = 0; $unknown = 0
    foreach ($source in $triggered) {
        try {
            $resp = Invoke-WebRequest -Uri "$DashboardUrl/api/collect/log/$source" -UseBasicParsing -TimeoutSec 5
            $status = ($resp.Content | ConvertFrom-Json).data.status
            if ($status -in @('queued', 'running')) { $running++ }
            elseif ($status -eq 'completed') { $completed++ }
            elseif ($status -eq 'partial') { $partial++ }
            elseif ($status -in @('failed', 'auth_required', 'blocked', 'cancelled', 'timed_out')) { $failed++ }
            else { $unknown++ }
        } catch {}
    }
    Write-Log "  已等待 $($i+10)秒: 运行中=$running, 完成=$completed, 部分成功=$partial, 失败=$failed, 未知=$unknown"
    if ($running -eq 0 -and $unknown -eq 0) { Write-Log "  ✓ 全部任务已结束"; break }
}

# 5b. 聚合店铺日汇总（从 daily_data 补 store_daily_facts）
Write-Log "`n[5b] 聚合店铺日汇总..."
$aggScript = Join-Path $ProjectRoot "scripts\aggregate_store_daily.py"
$aggregateFailed = $false
if (Test-Path $aggScript) {
    $backupDir = if ($env:TMALL_BACKUP_DIR) { $env:TMALL_BACKUP_DIR } else { Join-Path $ProjectRoot 'data\backups' }
    if (-not (Test-Path -LiteralPath $backupDir)) {
        New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
    }
    $aggBackup = Join-Path $backupDir "aggregate-store-daily-$(Get-Date -Format 'yyyyMMdd-HHmmss').db"
    $aggOutput = & $PythonPath $aggScript --apply --backup-destination $aggBackup 2>&1
    foreach ($line in $aggOutput) { Write-Log "  $line" }
    if ($LASTEXITCODE -ne 0) { Write-Log "  ✗ 聚合脚本退出码: $LASTEXITCODE" "ERROR"; $aggregateFailed = $true }
} else {
    Write-Log "  ✗ 聚合脚本不存在: $aggScript" "ERROR"
    $aggregateFailed = $true
}


# 6. 输出最终状态
Write-Log "`n[6/6] 最终状态:"
$successCount = 0; $failCount = 0
foreach ($source in $triggered) {
    $name = $sourceNames[$source]
    try {
        $resp = Invoke-WebRequest -Uri "$DashboardUrl/api/collect/log/$source" -UseBasicParsing -TimeoutSec 5
        $data = $resp.Content | ConvertFrom-Json
        if ($data.data.status -eq 'completed') { Write-Log "  ✓ $name : 成功"; $successCount++ }
        elseif ($data.data.status -eq 'partial') { Write-Log "  ⚠ $name : 部分成功 - $($data.data.error)"; $failCount++ }
        elseif ($data.data.status -in @('failed', 'auth_required', 'blocked', 'cancelled', 'timed_out')) { Write-Log "  ✗ $name : $($data.data.status) - $($data.data.error)"; $failCount++ }
        else { Write-Log "  ✗ $name : 未完成（$($data.data.status)）"; $failCount++ }
    } catch { Write-Log "  ✗ $name : 无法查询"; $failCount++ }
}

Write-Log "========================================"
Write-Log "  成功: $successCount, 失败: $failCount"
Write-Log "========================================"

if ($failCount -gt 0 -or $aggregateFailed) { exit 1 } else { exit 0 }
