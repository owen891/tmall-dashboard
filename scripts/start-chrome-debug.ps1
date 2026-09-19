param([switch]$Headless)
$ErrorActionPreference = 'Stop'
$chromePath = if ($env:TMALL_CHROME_PATH) { $env:TMALL_CHROME_PATH } else { 'C:\Program Files\Google\Chrome\Application\chrome.exe' }
$debugPort = if ($env:TMALL_CDP_PORT) { [int]$env:TMALL_CDP_PORT } else { 9223 }
$userDataDir = if ($env:TMALL_CHROME_PROFILE) { $env:TMALL_CHROME_PROFILE } else { "$env:LOCALAPPDATA\TmallDashboard\CollectorChrome" }
if (-not (Test-Path -LiteralPath $chromePath)) { throw "Chrome not found: $chromePath" }
try {
    $null = Invoke-WebRequest -Uri "http://127.0.0.1:$debugPort/json/version" -UseBasicParsing -TimeoutSec 2
    Write-Host "Collector Chrome already running on port $debugPort; existing mode retained."
    exit 0
} catch {}
$null = New-Item -ItemType Directory -Path $userDataDir -Force
$chromeArgs = @(
    "--remote-debugging-port=$debugPort",
    "--remote-allow-origins=http://127.0.0.1:$debugPort,http://localhost:$debugPort",
    "--user-data-dir=`"$userDataDir`"",
    '--no-first-run', '--no-default-browser-check', '--window-size=1440,1000'
)
if ($Headless) { $chromeArgs += '--headless=new' }
Start-Process -FilePath $chromePath -ArgumentList $chromeArgs -WindowStyle Hidden
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 1
    try {
        $null = Invoke-WebRequest -Uri "http://127.0.0.1:$debugPort/json/version" -UseBasicParsing -TimeoutSec 2
        Write-Host "Collector Chrome ready on port $debugPort (headless=$Headless)."
        exit 0
    } catch {}
}
throw 'Collector Chrome did not start within 30 seconds.'
