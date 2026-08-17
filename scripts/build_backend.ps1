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

if (-not $SkipInstall) {
    & py -3 -m pip install -r (Join-Path $projectRoot 'requirements-desktop.txt')
    if ($LASTEXITCODE -ne 0) {
        throw "Desktop dependency installation failed with exit code $LASTEXITCODE."
    }
}

& py -3 -m PyInstaller `
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
