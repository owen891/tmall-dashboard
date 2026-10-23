# ============================================================
# 完整RPA自动化采集脚本
# 功能：运行环境前置检查 -> 核验并复用选定浏览器 -> 会话检查 -> 触发采集 -> 等待完成
# 用法:
#   .\auto-collect.ps1                    # 采集全部
#   .\auto-collect.ps1 -Sources bi_daily,bi_monthly  # 只采集BI
#   .\auto-collect.ps1 -Sources sycm_flow,sycm_item_flow,sycm_market,wanxiangtai  # 只采集其他
# 可通过 Windows 任务计划程序每天定时调用
# ============================================================

param(
    [string[]]$Sources = @('bi_daily', 'bi_monthly', 'sycm_flow', 'sycm_item_flow', 'sycm_market', 'wanxiangtai'),
    # Explicit dependency injection for offline orchestration tests/embedded hosts.
    # No environment variable or deployment record can silently enable this seam.
    [scriptblock]$LocalRequest
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
$ChromeHeadless = if ($env:TMALL_CHROME_HEADLESS) { $env:TMALL_CHROME_HEADLESS -eq '1' } else { $false }  # 默认有界面模式，方便手动处理验证码
$DashboardUrl = if ($env:TMALL_DASHBOARD_URL) { $env:TMALL_DASHBOARD_URL.TrimEnd('/') } else { 'http://127.0.0.1:5000' }
$ProjectRoot = if ($env:TMALL_PROJECT_ROOT) { $env:TMALL_PROJECT_ROOT } else { Split-Path -Parent $PSScriptRoot }
. (Join-Path $PSScriptRoot 'resolve_runtime.ps1')
try { $PythonPath = Resolve-CollectorPython -ProjectRoot $ProjectRoot }
catch { Write-Error "RUNTIME_CONFIG_INVALID: $($_.Exception.Message)"; exit 20 }
if (@($Sources | Where-Object { $_ -ne 'bi_monthly' }).Count -gt 0) {
    try { $browser = Resolve-CollectorBrowser -ProjectRoot $ProjectRoot -PythonPath $PythonPath }
    catch { Write-Error "BROWSER_CONFIG_INVALID: $($_.Exception.Message)"; exit 21 }
} else {
    # Local monthly aggregation does not require a browser/configured profile.
    $browser = @{ reuse_only = $true; port = 9223 }
}
$ChromePath = $browser.executable
$ChromeDebugPort = $browser.port
$ChromeUserDataDir = $browser.user_data_dir
$env:TMALL_CDP_PORT = [string]$ChromeDebugPort

# Process-local only: remote proxies and system settings are left untouched.
$proxyBypass = @($env:NO_PROXY -split ','; $env:no_proxy -split ','; 'localhost'; '127.0.0.1'; '::1') | Where-Object { $_ } | Select-Object -Unique
$env:NO_PROXY = $proxyBypass -join ','
$env:no_proxy = $env:NO_PROXY
$LogDir = if ($env:TMALL_LOG_DIR) { $env:TMALL_LOG_DIR } else { Join-Path $ProjectRoot 'logs' }



if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir -Force -ErrorAction Stop | Out-Null
}

$logFile = Join-Path $LogDir "auto-collect-$(Get-Date -Format 'yyyyMMdd-HHmmss').log"

function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$timestamp] [$Level] $Message"
    Write-Host $line
    Add-Content -Path $logFile -Value $line -Encoding UTF8
}

# Windows PowerShell 5.1 has no -NoProxy switch. Bypass on this request only,
# never by disabling the machine/user/default proxy (remote services still use it).
function Invoke-LoopbackWebRequest {
    param([string]$Uri, [string]$Method = 'GET', [string]$Body,
          [string]$ContentType, [switch]$UseBasicParsing, [int]$TimeoutSec = 5)
    $parsed = [Uri]$Uri
    if (-not $parsed.IsLoopback -or $parsed.Scheme -notin @('http', 'https')) {
        throw 'LOCAL_ENDPOINT_REQUIRED'
    }
    if ($LocalRequest) {
        return & $LocalRequest $Uri $Method $Body
    }
    $request = [System.Net.HttpWebRequest]::Create($parsed)
    $request.Proxy = $null
    $request.AllowAutoRedirect = $false
    $request.Timeout = $TimeoutSec * 1000
    $request.ReadWriteTimeout = $TimeoutSec * 1000
    $request.Method = $Method
    if ($ContentType) { $request.ContentType = $ContentType }
    if ($Body) {
        $bytes = [System.Text.Encoding]::UTF8.GetBytes($Body)
        $request.ContentLength = $bytes.Length
        $stream = $request.GetRequestStream()
        try { $stream.Write($bytes, 0, $bytes.Length) } finally { $stream.Dispose() }
    }
    $response = $request.GetResponse()
    try {
        if ([int]$response.StatusCode -ne 200) { throw 'LOCAL_ENDPOINT_NOT_OK' }
        $reader = [System.IO.StreamReader]::new($response.GetResponseStream(), [System.Text.Encoding]::UTF8)
        try { return @{ StatusCode = [int]$response.StatusCode; Content = $reader.ReadToEnd() } }
        finally { $reader.Dispose() }
    } finally { $response.Dispose() }
}

function Invoke-CollectorPreflight {
    param([string]$Phase)
    $probe = Join-Path $ProjectRoot 'scripts/collector_preflight.py'
    $output = & $PythonPath $probe --root $ProjectRoot --sources ($Sources -join ',') --phase $Phase
    $code = $LASTEXITCODE
    foreach ($line in $output) { Write-Log "PREFLIGHT $line" }
    try { $report = ($output -join "`n") | ConvertFrom-Json -ErrorAction Stop }
    catch { Write-Log 'PREFLIGHT_PROTOCOL_INVALID' 'ERROR'; return $false }
    if ($code -ne 0 -or $report.ok -ne $true -or $report.phase -ne $Phase -or
        ($Phase -eq 'ready' -and $report.collection_ready -ne $true)) {
        Write-Log "PREFLIGHT_BLOCKED phase=$Phase exit=$code" 'ERROR'
        return $false
    }
    return $true
}
if (-not (Invoke-CollectorPreflight 'runtime')) { exit 20 }

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
    # 修复前这里直接 exit 0，与「全部来源采全」在计划任务里完全无法区分。
    # 留一份 outcome='skipped' 的结果凭据，健康检查/人工排障可据此判断。
    try {
        . (Join-Path $PSScriptRoot 'collect_result.ps1')
        $skipResult = New-CollectRunResult -Sources $Sources -Chain 'auto_collect'
        Add-CollectSourceResult -Result $skipResult -Source 'chain' -Outcome 'skipped' `
            -Reason 'collect_lock_busy' -Detail $CollectLockPath
        Set-CollectRunOutcome -Result $skipResult
        $skipPath = Join-Path $LogDir ("auto-collect-skip-{0}.json" -f (Get-Date -Format 'yyyyMMdd-HHmmss'))
        Write-CollectRunResult -Result $skipResult -Path $skipPath | Out-Null
        Write-Output "SKIP 结果已记录: $skipPath"
    } catch {
        Write-Output "WARN: 无法写入 SKIP 结果文件: $($_.Exception.Message)"
    }
    exit 0
}
('{"pid": ' + $PID + ', "started_at": "' + (Get-Date -Format o) + '"}') | Set-Content -LiteralPath $CollectLockPath -Encoding UTF8 -ErrorAction Stop
# ==================== 互斥锁已获取 ====================


$ChromeStartTimeout = 30
# Must exceed COLLECT_TIMEOUT in api/collect_api.py (900s for full-column BI collection).
$CollectWaitTimeout = if ($env:TMALL_COLLECT_WAIT_TIMEOUT) { [int]$env:TMALL_COLLECT_WAIT_TIMEOUT } else { 1200 }
$CloseChromeAfterCollect = $false

$needBIPage = $Sources -contains 'bi_daily'
$needOtherPages = $Sources | Where-Object { $_ -like 'sycm_*' -or $_ -eq 'wanxiangtai' }
$needsBrowser = $needBIPage -or $needOtherPages

$BIUsername = ''; $BIPassword = ''
if ($needBIPage -and -not $browser.reuse_only) {
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

}

$sourceNames = @{
    'bi_daily' = 'BI商品日度'
    'bi_monthly' = 'BI商品月度'
    'sycm_flow' = '生意参谋-店铺流量'
    'sycm_item_flow' = '生意参谋-单品流量'
    'sycm_market' = '生意参谋-市场数据'
    'wanxiangtai' = '万相台推广'
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
        $null = Invoke-LoopbackWebRequest -Uri "$DashboardUrl/healthz" -UseBasicParsing -TimeoutSec 5
        return $true
    } catch { return $false }
}
if (Test-Dashboard) {
    Write-Log "  ✓ 看板服务运行正常"
} else {
    Write-Log "  看板服务未启动，尝试自动拉起..."
    $dashboardScript = Join-Path $ProjectRoot 'scripts/start_dev_server.py'
    Start-Process -FilePath $PythonPath -ArgumentList "`"$dashboardScript`"" `
        -WorkingDirectory $ProjectRoot -WindowStyle Hidden
    $dashboardReady = $false
    for ($i = 0; $i -lt 60; $i++) {
        Start-Sleep -Seconds 1
        if (Test-Dashboard) { Write-Log "  ✓ 看板服务已启动（$($i+1)秒）"; $dashboardReady = $true; break }
    }
    if (-not $dashboardReady) {
        Write-Log "  ✗ 看板服务自动启动失败，无法触发采集" "ERROR"
        Release-CollectLock
        exit 1
    }
}

if ($needsBrowser) {
# 2. 只复用身份已核验的浏览器，不启动或切换用户浏览器。
Write-Log "`n[2/6] 检查已选择的采集浏览器..."
function Test-ChromeDebug {
    try {
        $resp = Invoke-LoopbackWebRequest -Uri "http://127.0.0.1:$ChromeDebugPort/json/version" -UseBasicParsing -TimeoutSec 2
        return ($resp.StatusCode -eq 200)
    } catch { return $false }
}

try { $null = Resolve-CollectorBrowser -ProjectRoot $ProjectRoot -PythonPath $PythonPath -Action identity }
catch { Write-Log "BROWSER_IDENTITY_BLOCKED: $($_.Exception.Message)" 'ERROR'; Release-CollectLock; exit 21 }
if (-not (Test-ChromeDebug)) {
    Write-Log 'BROWSER_NOT_READY: open the configured browser manually; no automatic start/restart/fallback.' 'ERROR'
    Release-CollectLock
    exit 21
}
}

if (-not (Invoke-CollectorPreflight 'transport')) { Release-CollectLock; exit 21 }

# 3. reuse_only 模式只读验证会话/页面；不会自动登录或新开标签。
Write-Log "`n[3/6] 检查采集会话与页面..."
if ($needBIPage -or $needOtherPages) {
    $autoLoginScript = Join-Path $ProjectRoot "scripts\auto_login_bi.py"
    $loginArgs = @($autoLoginScript, '--sources', ($Sources -join ','))
    if (-not $needBIPage) { $loginArgs += '--skip-bi-login' }
    if ($BIUsername) { $env:BI_USERNAME = $BIUsername }
    if ($BIPassword) { $env:BI_PASSWORD = $BIPassword }
    
    # Shared preparation script honors the selected browser's reuse_only policy.
    $loginOutput = & $PythonPath @loginArgs 2>&1
    foreach ($line in $loginOutput) { Write-Log "  $line" }
    $biLoginFailed = ($LASTEXITCODE -ne 0)
    
    if ($biLoginFailed) {
        Write-Log 'MANUAL_LOGIN_REQUIRED: complete login/captcha in the configured browser; no browser restart or new login tab.' 'ERROR'
        Release-CollectLock
        exit 22
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

if (-not (Invoke-CollectorPreflight 'ready')) { Release-CollectLock; exit 22 }

if ($needsBrowser) {
# 3c. 刷新cookie文件（从已登录Chrome导出最新cookie，供文件cookie采集模式使用）
Write-Log "`n[3c] 刷新cookie文件（文件cookie模式）..."
# 2026-10-23 起 cookie 导出脚本随采集插件移入项目内私有目录；外部 BI采集 目录作回退（独立采集工具）。
$cookieExportScript = Join-Path $ProjectRoot "collectors\export_cookies_v3.py"
if (-not (Test-Path -LiteralPath $cookieExportScript)) {
    $cookieExportScript = Join-Path $ProjectRoot "..\BI采集\export_cookies_v3.py"
}
if (Test-Path -LiteralPath $cookieExportScript) {
    try {
        $exportOutput = & $PythonPath $cookieExportScript 2>&1
        $exportCode = $LASTEXITCODE
        foreach ($line in $exportOutput) { Write-Log "  $line" }
        if ($exportCode -ne 0) {
            Write-Log "COOKIE_EXPORT_FAILED exit=$exportCode" 'ERROR'
            Release-CollectLock
            exit 23
        }
    } catch {
        Write-Log "COOKIE_EXPORT_FAILED: $_" 'ERROR'
        Release-CollectLock
        exit 23
    }
} else {
    Write-Log "  - cookie导出脚本不存在，跳过（采集将回退到CDP模式）" "WARN"
}

}

# 4. 触发采集任务
Write-Log "`n[4/6] 触发采集任务..."
$triggered = @()
# 串行模式：触发一个源并等待其完成后再触发下一个。
# 原因：2026-10-09/10-10/10-13 三个生意参谋源并行采集时同时写 dashboard.db，
# 触发 SQLite 文件锁冲突（unable to open database file），导致数据采到但全部落库失败。
foreach ($source in $Sources) {
    $name = $sourceNames[$source]
    try {
        $body = @{source = $source} | ConvertTo-Json
        $resp = Invoke-LoopbackWebRequest -Uri "$DashboardUrl/api/collect/trigger" -Method POST -Body $body -ContentType "application/json" -UseBasicParsing -TimeoutSec 60
        $data = $resp.Content | ConvertFrom-Json
        if ($data.ok) { Write-Log "  ✓ 已触发: $name"; $triggered += $source }
        else { Write-Log "  ✗ 触发失败: $name - $($data.message)" "WARN"; continue }
    } catch {
        Write-Log "  ✗ 触发异常: $name - $($_.Exception.Message)" "WARN"
        continue
    }
    # 等待当前源完成（避免与下一源并发写库）
    $sourceDone = $false
    for ($i = 0; $i -lt $CollectWaitTimeout; $i += 10) {
        Start-Sleep -Seconds 10
        $status = $null
        try {
            $resp = Invoke-LoopbackWebRequest -Uri "$DashboardUrl/api/collect/log/$source" -UseBasicParsing -TimeoutSec 5
            $status = ($resp.Content | ConvertFrom-Json).data.status
        } catch {}
        if ($null -eq $status) { continue }
        if ($status -in @('queued', 'running')) {
            Write-Log "    $name 采集进行中（已等待 $($i+10)秒）"
        } else {
            Write-Log "    $name 采集结束：$status"
            $sourceDone = $true
            break
        }
    }
    if (-not $sourceDone) { Write-Log "  ✗ $name 等待超时（${CollectWaitTimeout}秒），继续下一个" "WARN" }
}

if ($triggered.Count -eq 0) { Write-Log "  ✗ 没有触发任何任务" "ERROR"; Release-CollectLock; exit 1 }
Write-Log "  成功触发 $($triggered.Count) 个任务"

# 5. 等待采集完成
Write-Log "`n[5/6] 等待采集完成..."
for ($i = 0; $i -lt $CollectWaitTimeout; $i += 10) {
    Start-Sleep -Seconds 10
    $running = 0; $completed = 0; $partial = 0; $failed = 0; $unknown = 0
    foreach ($source in $triggered) {
        try {
            $resp = Invoke-LoopbackWebRequest -Uri "$DashboardUrl/api/collect/log/$source" -UseBasicParsing -TimeoutSec 5
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
#     注意：本步骤位于「等待采集完成」之后，脚本一旦被中断就静默不跑
#     （2026-10-02 实测 LastTaskResult=0xC000013A），store_daily_facts 会悄悄
#     落后。因此另有独立计划任务 TmallDashboard-Aggregate-Daily 兜底，两个入口
#     都带 --skip-if-current：先跑的一方真正聚合，后跑的一方零成本跳过。
Write-Log "`n[5b] 聚合店铺日汇总..."
$aggScript = Join-Path $ProjectRoot "scripts\aggregate_store_daily.py"
$aggregateFailed = $false
if (Test-Path $aggScript) {
    $backupDir = if ($env:TMALL_BACKUP_DIR) { $env:TMALL_BACKUP_DIR } else { Join-Path $ProjectRoot 'data\backups' }
    if (-not (Test-Path -LiteralPath $backupDir)) {
        New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
    }
    $aggBackup = Join-Path $backupDir "aggregate-store-daily-$(Get-Date -Format 'yyyyMMdd-HHmmss').db"
    $aggOutput = & $PythonPath $aggScript --apply --skip-if-current --backup-destination $aggBackup 2>&1
    foreach ($line in $aggOutput) { Write-Log "  $line" }
    if ($LASTEXITCODE -ne 0) { Write-Log "  ✗ 聚合脚本退出码: $LASTEXITCODE" "ERROR"; $aggregateFailed = $true }
} else {
    Write-Log "  ✗ 聚合脚本不存在: $aggScript" "ERROR"
    $aggregateFailed = $true
}


# 6. 输出最终状态
Write-Log "`n[6/6] 最终状态:"
$successCount = 0; $failCount = 0; $skippedCount = 0
# 运行结果契约：outcome 与 exit code 分离（见 scripts\collect_result.ps1）。
. (Join-Path $PSScriptRoot 'collect_result.ps1')
$runResult = New-CollectRunResult -Sources $Sources -Chain 'auto_collect'

# 请求了但没能触发的来源：修复前它们只是不出现在 $triggered 里，
# 既不计数也不报错，结果文件看不出少采了。
foreach ($source in $Sources) {
    if ($triggered -notcontains $source) {
        Write-Log "  ✗ $($sourceNames[$source]) : 未触发"
        Add-CollectSourceResult -Result $runResult -Source $source `
            -Outcome 'failed' -ExitCode 1 -Reason 'not_triggered'
    }
}

foreach ($source in $triggered) {
    $name = $sourceNames[$source]
    try {
        $resp = Invoke-LoopbackWebRequest -Uri "$DashboardUrl/api/collect/log/$source" -UseBasicParsing -TimeoutSec 5
        $data = $resp.Content | ConvertFrom-Json
        if ($data.data.status -eq 'completed') {
            Write-Log "  ✓ $name : 成功"; $successCount++
            Add-CollectSourceResult -Result $runResult -Source $source -Outcome 'succeeded'
        }
        elseif ($data.data.status -eq 'partial') {
            Write-Log "  ⚠ $name : 部分成功 - $($data.data.error)"; $failCount++
            Add-CollectSourceResult -Result $runResult -Source $source `
                -Outcome 'partial' -Reason 'partial_coverage' -Detail ([string]$data.data.error)
        }
        elseif ($data.data.status -eq 'skipped') {
            Write-Log "  ⚠ $name : 跳过（租约被占）"; $skippedCount++
            Add-CollectSourceResult -Result $runResult -Source $source `
                -Outcome 'skipped' -Reason 'lease_held_by_other_chain'
        }
        elseif ($data.data.status -in @('failed', 'auth_required', 'blocked', 'cancelled', 'timed_out')) {
            Write-Log "  ✗ $name : $($data.data.status) - $($data.data.error)"; $failCount++
            $outcome = if ($data.data.status -in @('auth_required', 'blocked')) { 'blocked' } else { 'failed' }
            Add-CollectSourceResult -Result $runResult -Source $source `
                -Outcome $outcome -Reason ([string]$data.data.status) -Detail ([string]$data.data.error)
        }
        else {
            Write-Log "  ✗ $name : 未完成（$($data.data.status)）"; $failCount++
            Add-CollectSourceResult -Result $runResult -Source $source `
                -Outcome 'failed' -Reason 'incomplete' -Detail ([string]$data.data.status)
        }
    } catch {
        Write-Log "  ✗ $name : 无法查询"; $failCount++
        Add-CollectSourceResult -Result $runResult -Source $source `
            -Outcome 'failed' -Reason 'status_unavailable' -Detail $_.Exception.Message
    }
}

if ($aggregateFailed) {
    Add-CollectSourceResult -Result $runResult -Source 'aggregate' `
        -Outcome 'failed' -ExitCode 1 -Reason 'aggregate_failed'
}

Write-Log "========================================"
Write-Log "  成功: $successCount, 失败: $failCount, 跳过: $skippedCount"
Set-CollectRunOutcome -Result $runResult
Write-Log "  运行结论: $($runResult['outcome'])（$($runResult['reason'])）"
Write-Log "========================================"

# 计划任务/健康检查按这份结果文件判断实际覆盖，而不是只看进程退出码。
try {
    $resultPath = Join-Path $LogDir ("auto-collect-result-{0}.json" -f (Get-Date -Format 'yyyyMMdd-HHmmss'))
    Write-CollectRunResult -Result $runResult -Path $resultPath | Out-Null
    Write-Log "  结果文件: $resultPath"
} catch {
    Write-Log "  结果文件写入失败: $($_.Exception.Message)" "WARN"
}

Release-CollectLock
if ($failCount -gt 0 -or $aggregateFailed) {
    exit (Get-CollectRunExitCode -Result $runResult)
}
exit 0
