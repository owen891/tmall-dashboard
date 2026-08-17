[CmdletBinding()]
param(
    [string]$Installer = ''
)

$ErrorActionPreference = 'Stop'
if ([string]::IsNullOrWhiteSpace($Installer)) {
    $version = (Get-Content -LiteralPath (Join-Path $PSScriptRoot '..\VERSION') -Raw).Trim()
    $Installer = Join-Path $PSScriptRoot "..\desktop\release\TmallDashboard-Setup-$version-x64.exe"
}
$installerPath = (Resolve-Path -LiteralPath $Installer).Path
$smokeRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("tmall-dashboard-smoke-" + [guid]::NewGuid().ToString('N'))
$installPath = Join-Path $smokeRoot 'installed'
$appDataPath = Join-Path $smokeRoot 'appdata'
$localAppDataPath = Join-Path $smokeRoot 'localappdata'
$appProcess = $null
$oldAppData = $env:APPDATA
$oldLocalAppData = $env:LOCALAPPDATA

function Wait-Until([scriptblock]$Condition, [int]$TimeoutSeconds = 30) {
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        if (& $Condition) { return $true }
        Start-Sleep -Milliseconds 500
    } while ((Get-Date) -lt $deadline)
    return $false
}

New-Item -ItemType Directory -Force -Path $installPath, $appDataPath, $localAppDataPath | Out-Null
$env:APPDATA = $appDataPath
$env:LOCALAPPDATA = $localAppDataPath

try {
    $installerProcess = Start-Process -FilePath $installerPath -ArgumentList @('/S', "/D=$installPath") -Wait -PassThru
    if ($installerProcess.ExitCode -ne 0) { throw "Installer exited with code $($installerProcess.ExitCode)." }

    $appExecutable = Get-ChildItem -LiteralPath $installPath -Filter '*.exe' -File | Where-Object { $_.Name -notlike 'Uninstall*' } | Select-Object -First 1
    if (-not $appExecutable) { throw "Installed desktop executable was not found under $installPath." }
    $appProcess = Start-Process -FilePath $appExecutable.FullName -PassThru

    $backendProcess = $null
    if (-not (Wait-Until {
        $script:backendProcess = Get-CimInstance Win32_Process -Filter "Name='TmallDashboardServer.exe'" | Where-Object { $_.CommandLine -like "*--parent-pid $($appProcess.Id)*" } | Select-Object -First 1
        return $null -ne $script:backendProcess
    })) { throw 'Packaged backend did not start.' }

    $listenPort = $null
    if (-not (Wait-Until {
        $connection = Get-NetTCPConnection -State Listen -OwningProcess $script:backendProcess.ProcessId -ErrorAction SilentlyContinue | Where-Object { $_.LocalAddress -eq '127.0.0.1' } | Select-Object -First 1
        if ($connection) { $script:listenPort = $connection.LocalPort; return $true }
        return $false
    })) { throw 'Packaged backend did not expose a loopback port.' }

    $health = Invoke-RestMethod -Uri "http://127.0.0.1:$listenPort/healthz" -TimeoutSec 10
    if (-not $health.ok) { throw 'Packaged backend health check failed.' }
    $overview = Invoke-WebRequest -Uri "http://127.0.0.1:$listenPort/" -UseBasicParsing -TimeoutSec 10
    $settings = Invoke-WebRequest -Uri "http://127.0.0.1:$listenPort/settings" -UseBasicParsing -TimeoutSec 10
    if ($overview.StatusCode -ne 200 -or $settings.StatusCode -ne 200) { throw 'Packaged frontend smoke check failed.' }
    $anomalies = Invoke-WebRequest -Uri "http://127.0.0.1:$listenPort/api/anomalies?dim=monthly&period=2026-08&prev_period=2026-07" -UseBasicParsing -TimeoutSec 10
    $report = Invoke-WebRequest -Uri "http://127.0.0.1:$listenPort/api/report?dim=monthly&period=2026-08" -UseBasicParsing -TimeoutSec 10
    if ($anomalies.StatusCode -ne 200 -or $report.StatusCode -ne 200) { throw 'Packaged runtime API smoke check failed.' }

    $databasePath = Join-Path $appDataPath 'TmallDashboard\data\dashboard.db'
    if (-not (Wait-Until { Test-Path -LiteralPath $databasePath -PathType Leaf })) { throw "Desktop database was not created at $databasePath." }
    $backendLogPath = Join-Path $localAppDataPath 'TmallDashboard\logs\backend.log'
    if (-not (Wait-Until { Test-Path -LiteralPath $backendLogPath -PathType Leaf })) { throw "Desktop backend.log was not created at $backendLogPath." }

    Stop-Process -Id $appProcess.Id -Force
    $appProcess = $null
    if (-not (Wait-Until { -not (Get-Process -Id $script:backendProcess.ProcessId -ErrorAction SilentlyContinue) })) { throw 'Backend did not stop after desktop process exit.' }

    $uninstaller = Get-ChildItem -LiteralPath $installPath -Filter 'Uninstall*.exe' -File | Select-Object -First 1
    if (-not $uninstaller) { throw 'Uninstaller was not created.' }
    $uninstallProcess = Start-Process -FilePath $uninstaller.FullName -ArgumentList '/S' -Wait -PassThru
    if ($uninstallProcess.ExitCode -ne 0) { throw "Uninstaller exited with code $($uninstallProcess.ExitCode)." }
    if (Test-Path -LiteralPath $installPath) { throw 'Temporary installation directory still exists after uninstall.' }
    if (-not (Test-Path -LiteralPath $databasePath -PathType Leaf)) { throw 'User database was removed by uninstall.' }

    Write-Output 'DESKTOP_SMOKE_OK'
}
finally {
    if ($appProcess) { Stop-Process -Id $appProcess.Id -Force -ErrorAction SilentlyContinue }
    $env:APPDATA = $oldAppData
    $env:LOCALAPPDATA = $oldLocalAppData
    if (Test-Path -LiteralPath $smokeRoot) { Remove-Item -LiteralPath $smokeRoot -Recurse -Force -ErrorAction SilentlyContinue }
}
