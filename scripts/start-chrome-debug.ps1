# 启动 Chrome 调试模式（用于生意参谋和万相台采集）
# 使用方法：右键 -> 使用 PowerShell 运行

$chromePath = "C:\Program Files\Google\Chrome\Application\chrome.exe"
$debugPort = 9222
$userDataDir = "$env:LOCALAPPDATA\Google\Chrome\User Data Debug"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  启动 Chrome 调试模式" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 检查 Chrome 是否存在
if (-not (Test-Path $chromePath)) {
    Write-Host "✗ 未找到 Chrome，请检查安装路径" -ForegroundColor Red
    Write-Host "  预期路径: $chromePath" -ForegroundColor Red
    Read-Host "按回车键退出"
    exit 1
}

# 检查调试端口是否已被占用
try {
    $resp = Invoke-WebRequest -Uri "http://127.0.0.1:$debugPort/json/version" -UseBasicParsing -TimeoutSec 2
    Write-Host "✓ Chrome 调试模式已在运行 (端口 $debugPort)" -ForegroundColor Green
    Write-Host "  可以直接触发采集任务" -ForegroundColor Green
    Read-Host "按回车键退出"
    exit 0
} catch {
    Write-Host "  调试端口 $debugPort 未被占用，可以启动" -ForegroundColor Yellow
}

# 关闭所有 Chrome 窗口（避免端口冲突）
Write-Host ""
Write-Host "正在关闭所有 Chrome 窗口..." -ForegroundColor Yellow
Get-Process chrome -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 2

# 创建调试模式用户数据目录
if (-not (Test-Path $userDataDir)) {
    New-Item -ItemType Directory -Path $userDataDir -Force | Out-Null
}

# 启动 Chrome 调试模式
Write-Host ""
Write-Host "正在启动 Chrome 调试模式..." -ForegroundColor Green
Write-Host "  调试端口: $debugPort" -ForegroundColor Green
Write-Host "  用户数据目录: $userDataDir" -ForegroundColor Green
Write-Host ""

Start-Process -FilePath $chromePath -ArgumentList @(
    "--remote-debugging-port=$debugPort",
    "--remote-allow-origins=*",
    "--user-data-dir=$userDataDir",
    "--no-first-run",
    "--no-default-browser-check"
)

Start-Sleep -Seconds 3

# 验证是否启动成功
try {
    $resp = Invoke-WebRequest -Uri "http://127.0.0.1:$debugPort/json/version" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "  ✓ Chrome 调试模式启动成功！" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "下一步操作：" -ForegroundColor Cyan
    Write-Host "  1. 在打开的 Chrome 窗口中登录生意参谋和万相台" -ForegroundColor White
    Write-Host "  2. 登录完成后，回到数据采集页面" -ForegroundColor White
    Write-Host "  3. 点击'一键采集全部'或单个数据源的'立即采集'" -ForegroundColor White
    Write-Host ""
} catch {
    Write-Host "✗ Chrome 调试模式启动失败，请检查端口是否被占用" -ForegroundColor Red
}

Read-Host "按回车键退出"
