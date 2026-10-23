param([switch]$Headless)
$ErrorActionPreference = 'Stop'
$projectRoot = if ($env:TMALL_PROJECT_ROOT) { $env:TMALL_PROJECT_ROOT } else { Split-Path -Parent $PSScriptRoot }
. (Join-Path $PSScriptRoot 'resolve_runtime.ps1')
$python = Resolve-CollectorPython -ProjectRoot $projectRoot
$browser = Resolve-CollectorBrowser -ProjectRoot $projectRoot -PythonPath $python
try {
    $identity = Resolve-CollectorBrowser -ProjectRoot $projectRoot -PythonPath $python -Action identity
    Write-Host "BROWSER_REUSED: verified listener owner pid=$($identity.pid); profile/mode unchanged."
    exit 0
} catch {
    if ($browser.reuse_only -or $_.Exception.Message -notlike '*BROWSER_NOT_RUNNING*') {
        Write-Output 'BROWSER_NOT_READY: open the explicitly selected browser manually; no fallback.'
        exit 21
    }
}
$chromeArgs = @(
    "--remote-debugging-address=$($browser.host)",
    "--remote-debugging-port=$($browser.port)",
    "--remote-allow-origins=http://$($browser.host):$($browser.port)",
    "--user-data-dir=`"$($browser.user_data_dir)`"",
    '--no-first-run', '--no-default-browser-check', '--window-size=1440,1000'
)
if ($Headless) { $chromeArgs += '--headless=new' }
Start-Process -FilePath $browser.executable -ArgumentList $chromeArgs -WindowStyle Hidden
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 1
    try {
        $null = Resolve-CollectorBrowser -ProjectRoot $projectRoot -PythonPath $python -Action identity
        Write-Host 'BROWSER_READY: selected executable/profile owns the listener.'
        exit 0
    } catch {}
}
throw 'BROWSER_NOT_READY: selected browser did not expose its verified listener.'
