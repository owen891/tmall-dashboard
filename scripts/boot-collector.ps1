# ============================================================
# 开机/登录自启编排：把采集前置条件一次性拉齐
#
# 背景（2026-10-22）：
#   这台机器每天关机重启。重启后 DSH 宿主、看板服务(5000)、CloakBrowser(9223)
#   都不会自动起来，导致 09:00 的分批采集要么不触发，要么因
#   BROWSER_NOT_READY / IMPORT_ERROR 失败。
#
#   本脚本只做「环境准备」，不跑采集本身：
#     1. 等网络可用
#     2. 拉起看板服务 127.0.0.1:5000（万相台导入依赖它）
#     3. 拉起 CloakBrowser 并开放 CDP 9223（复用 data/collector-browser.json 指定
#        的 exe/profile，绝不自建第二套 profile）
#     4. 补齐各采集器需要的标签页（域名见 data/collector-browser.json）
#
#   采集仍由 09:00 的 automation 触发；本脚本幂等，重复执行只是校验。
#
# 用法：
#   .\scripts\boot-collector.ps1
#   .\scripts\boot-collector.ps1 -NetworkWaitSeconds 300
#   .\scripts\boot-collector.ps1 -SkipBrowser -SkipService
# ============================================================

param(
    [int]$NetworkWaitSeconds = 180,
    [int]$ServiceWaitSeconds = 60,
    [switch]$SkipService,
    [switch]$SkipBrowser,
    [switch]$SkipTabs,
    [switch]$SkipCookies
)

$ErrorActionPreference = 'Continue'

$ProjectRoot = if ($env:TMALL_PROJECT_ROOT) { $env:TMALL_PROJECT_ROOT } else { Split-Path -Parent $PSScriptRoot }
$LogDir = if ($env:TMALL_LOG_DIR) { $env:TMALL_LOG_DIR } else { Join-Path $ProjectRoot 'logs' }
if (-not (Test-Path -LiteralPath $LogDir)) { New-Item -ItemType Directory -Path $LogDir -Force | Out-Null }
$LogFile = Join-Path $LogDir ("boot-collector-{0}.log" -f (Get-Date -Format 'yyyyMMdd-HHmmss'))

$env:PYTHONIOENCODING = 'utf-8'
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = $OutputEncoding

function Write-Log {
    param([string]$Message, [string]$Level = 'INFO')
    $line = "[{0}] [{1}] {2}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Level, $Message
    Write-Output $line
    Add-Content -LiteralPath $LogFile -Value $line -Encoding UTF8
}

function Test-Healthz {
    try {
        $r = Invoke-WebRequest -Uri 'http://127.0.0.1:5000/healthz' -UseBasicParsing -TimeoutSec 3
        return ($r.StatusCode -eq 200)
    } catch { return $false }
}

Write-Log "=== 开机编排开始 ==="
Write-Log "日志文件: $LogFile"

# ---------- 1. 等网络 ----------
$deadline = (Get-Date).AddSeconds($NetworkWaitSeconds)
$networkOk = $false
while ((Get-Date) -lt $deadline) {
    try {
        $c = New-Object System.Net.Sockets.TcpClient
        $iar = $c.BeginConnect('223.5.5.5', 443, $null, $null)
        if ($iar.AsyncWaitHandle.WaitOne(2000) -and $c.Connected) { $networkOk = $true; $c.Close(); break }
        $c.Close()
    } catch {}
    Start-Sleep -Seconds 3
}
if ($networkOk) { Write-Log '网络可用' } else { Write-Log "网络在 $NetworkWaitSeconds 秒内未就绪，继续尝试后续步骤" 'WARN' }

# ---------- 2. 看板服务 ----------
if (-not $SkipService) {
    if (Test-Healthz) {
        Write-Log '看板服务已在运行 (127.0.0.1:5000)'
    } else {
        try {
            . (Join-Path $PSScriptRoot 'resolve_runtime.ps1')
            $python = Resolve-CollectorPython -ProjectRoot $ProjectRoot
            Write-Log "启动看板服务: $python scripts\start_dashboard.py --port 5000"
            # 必须走 start_dashboard.py：中文部署 env（TMALL_CATEGORY_LABEL）经
            # PowerShell 传递会被 ANSI 解码成乱码，品类筛选随之归零。
            Start-Process -FilePath $python `
                -ArgumentList @('scripts\start_dashboard.py', '--port', '5000') `
                -WorkingDirectory $ProjectRoot -WindowStyle Hidden
            $svcDeadline = (Get-Date).AddSeconds($ServiceWaitSeconds)
            $svcOk = $false
            while ((Get-Date) -lt $svcDeadline) {
                if (Test-Healthz) { $svcOk = $true; break }
                Start-Sleep -Seconds 2
            }
            if ($svcOk) { Write-Log '看板服务已就绪' } else { Write-Log '看板服务未在预期时间内就绪' 'ERROR' }
        } catch {
            Write-Log "看板服务启动失败: $($_.Exception.Message)" 'ERROR'
        }
    }
}

# ---------- 3. CloakBrowser ----------
$browserCfg = $null
if (-not $SkipBrowser) {
    try {
        . (Join-Path $PSScriptRoot 'resolve_runtime.ps1')
        $python = Resolve-CollectorPython -ProjectRoot $ProjectRoot
        $browserCfg = Resolve-CollectorBrowser -ProjectRoot $ProjectRoot -PythonPath $python

        $running = $false
        try {
            $null = Resolve-CollectorBrowser -ProjectRoot $ProjectRoot -PythonPath $python -Action identity
            $running = $true
            Write-Log 'CloakBrowser 已在运行且 CDP 端口归属校验通过'
        } catch {
            Write-Log "CDP 端口未就绪: $($_.Exception.Message)"
        }

        if (-not $running) {
            if (-not (Test-Path -LiteralPath $browserCfg.executable)) {
                throw "浏览器可执行文件不存在: $($browserCfg.executable)"
            }
            $urls = @(
                'https://sycm.taobao.com/portal/home.htm',
                'https://one.alimama.com/index.html',
                "https://$env:TMALL_BI_HOST/workTable/productOverview"
            )
            $chromeArgs = @(
                "--remote-debugging-address=$($browserCfg.host)",
                "--remote-debugging-port=$($browserCfg.port)",
                "--remote-allow-origins=http://$($browserCfg.host):$($browserCfg.port)",
                "--user-data-dir=$($browserCfg.user_data_dir)",
                '--no-first-run', '--no-default-browser-check', '--window-size=1440,1000'
            ) + $urls
            Write-Log "启动 CloakBrowser: $($browserCfg.executable) (port $($browserCfg.port))"
            Start-Process -FilePath $browserCfg.executable -ArgumentList $chromeArgs
            $brDeadline = (Get-Date).AddSeconds(60)
            $brOk = $false
            while ((Get-Date) -lt $brDeadline) {
                Start-Sleep -Seconds 2
                try {
                    $null = Resolve-CollectorBrowser -ProjectRoot $ProjectRoot -PythonPath $python -Action identity
                    $brOk = $true; break
                } catch {}
            }
            if ($brOk) { Write-Log 'CloakBrowser CDP 已就绪' } else { Write-Log 'CloakBrowser 未在预期时间内开放 CDP' 'ERROR' }
        }
    } catch {
        Write-Log "CloakBrowser 处理失败: $($_.Exception.Message)" 'ERROR'
    }
}

# ---------- 兜底解析 Python ----------
# 上面两段各自在「需要动手」时才解析 $python；若服务已在跑且传了 -SkipBrowser，
# 走到这里 $python 会是空，第 4/5 步就会报「找不到命令」。
if (-not $python) {
    try {
        . (Join-Path $PSScriptRoot 'resolve_runtime.ps1')
        $python = Resolve-CollectorPython -ProjectRoot $ProjectRoot
    } catch {
        Write-Log "Python 解析失败: $($_.Exception.Message)" 'ERROR'
    }
}

# ---------- 4. 标签页 ----------
if (-not $SkipTabs) {
    try {
        $port = if ($browserCfg -and $browserCfg.port) { $browserCfg.port } else { 9223 }
        $tabsScript = Join-Path $PSScriptRoot 'ensure_collector_tabs.py'
        $tabOut = & $python $tabsScript --port $port 2>&1
        Write-Log ("标签页检查: " + ($tabOut -join ' '))
    } catch {
        Write-Log "标签页检查失败: $($_.Exception.Message)" 'ERROR'
    }
}

# ---------- 5. 刷新 cookie 缓存文件 ----------
# 2026-10-22 事故：cookie 文件未超 PLATFORM_MAX_AGE(7天) 时采集器只用文件、不回源，
# 而淘宝 cookie 实际 4 天内就会滚动，导致「浏览器已登录但采集报未登录」。
# 每次开机从同一个浏览器 profile 重新导出，消除这个盲区。
# BI 不在此列（cookie_store 对 bi 明确要求人工显式刷新）。
if (-not $SkipCookies) {
    try {
        $refreshScript = Join-Path $PSScriptRoot 'refresh_collector_cookies.py'
        $cookieOut = & $python $refreshScript --json 2>&1
        Write-Log ("cookie 刷新: " + ($cookieOut -join ' '))
    } catch {
        Write-Log "cookie 刷新失败（不影响采集，采集器会自行回退）: $($_.Exception.Message)" 'WARN'
    }
}

Write-Log '=== 开机编排结束 ==='
exit 0
