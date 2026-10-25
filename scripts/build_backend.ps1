[CmdletBinding()]
param(
    [switch]$SkipInstall
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$specPath = Join-Path $projectRoot 'packaging\tmall_dashboard_backend.spec'
$distPath = Join-Path $projectRoot 'build\desktop'
$workPath = Join-Path $projectRoot 'build\pyinstaller'
$executable = Join-Path $projectRoot 'build\desktop\backend\TmallDashboardServer.exe'

# `py -3` resolves to the newest registered interpreter, which on a CI image is
# not necessarily the one setup-python provisioned (and installed PyInstaller
# into). Prefer an explicit interpreter: $env:TMALL_PYTHON, then the `python`
# already on PATH, and only fall back to the launcher.
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

if (-not $SkipInstall) {
    & $pythonExe @pythonArgs -m pip install -r (Join-Path $projectRoot 'requirements-desktop.txt')
    if ($LASTEXITCODE -ne 0) {
        throw "Desktop dependency installation failed with exit code $LASTEXITCODE."
    }
}

& $pythonExe @pythonArgs -m PyInstaller `
    '--clean' `
    '--noconfirm' `
    "--distpath=$distPath" `
    "--workpath=$workPath" `
    $specPath

if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed with exit code $LASTEXITCODE."
}
if (-not (Test-Path -LiteralPath $executable -PathType Leaf)) {
    throw "Packaged backend executable was not created: $executable"
}

Write-Output $executable
