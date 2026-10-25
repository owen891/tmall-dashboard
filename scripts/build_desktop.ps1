[CmdletBinding()]
param(
    [switch]$SkipInstall,
    [switch]$SkipPythonTests
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$desktopRoot = Join-Path $projectRoot 'desktop'
$releaseRoot = Join-Path $desktopRoot 'release'
$version = (Get-Content -LiteralPath (Join-Path $projectRoot 'VERSION') -Raw).Trim()

# `py -3` resolves to the newest registered interpreter, which on a CI image is
# not necessarily the one setup-python provisioned. Prefer $env:TMALL_PYTHON,
# then the `python` already on PATH, and only fall back to the launcher.
$pythonExe = $env:TMALL_PYTHON
$pythonArgs = @()
if (-not $pythonExe) {
    $onPath = Get-Command python -ErrorAction SilentlyContinue
    if ($onPath) {
        $pythonExe = $onPath.Source
    } else {
        $pythonExe = 'py'
        $pythonArgs = @('-3')
    }
}

Push-Location $projectRoot
try {
    & $pythonExe @pythonArgs scripts\sync_desktop_version.py
    if ($LASTEXITCODE -ne 0) { throw "Desktop version synchronization failed with exit code $LASTEXITCODE." }
    & $pythonExe @pythonArgs -c "from scripts.build_backend import assert_release_version_contract; assert_release_version_contract()"
    if ($LASTEXITCODE -ne 0) { throw "Desktop version contract validation failed with exit code $LASTEXITCODE." }

    if (-not $SkipInstall) {
        & $pythonExe @pythonArgs -m pip install -r requirements-desktop.txt
        if ($LASTEXITCODE -ne 0) { throw "Python dependency installation failed with exit code $LASTEXITCODE." }
        & npm ci --prefix desktop
        if ($LASTEXITCODE -ne 0) { throw "Desktop dependency installation failed with exit code $LASTEXITCODE." }
    }

    if (-not $SkipPythonTests) {
        & $pythonExe @pythonArgs -m unittest discover -s tests
        if ($LASTEXITCODE -ne 0) { throw "Python tests failed with exit code $LASTEXITCODE." }
    }

    & powershell -NoProfile -ExecutionPolicy Bypass -File scripts\build_backend.ps1 -SkipInstall
    if ($LASTEXITCODE -ne 0) { throw "Backend packaging failed with exit code $LASTEXITCODE." }

    & npm test --prefix desktop
    if ($LASTEXITCODE -ne 0) { throw "Desktop tests failed with exit code $LASTEXITCODE." }
    & npm run build --prefix desktop
    if ($LASTEXITCODE -ne 0) { throw "Desktop TypeScript build failed with exit code $LASTEXITCODE." }

    $env:CSC_IDENTITY_AUTO_DISCOVERY = 'false'
    & npm run dist --prefix desktop
    if ($LASTEXITCODE -ne 0) { throw "NSIS packaging failed with exit code $LASTEXITCODE." }

    $installer = Join-Path $releaseRoot "TmallDashboard-Setup-$version-x64.exe"
    $blockmap = Join-Path $releaseRoot "TmallDashboard-Setup-$version-x64.exe.blockmap"
    $metadata = Join-Path $releaseRoot 'latest.yml'
    foreach ($artifact in ($installer, $blockmap, $metadata)) {
        if (-not (Test-Path -LiteralPath $artifact -PathType Leaf)) {
            throw "Required desktop release artifact was not created: $artifact"
        }
    }

    Write-Output "DESKTOP_BUILD_OK"
    Write-Output $installer
    Write-Output $blockmap
    Write-Output $metadata
}
finally {
    Pop-Location
}
