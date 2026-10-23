[CmdletBinding()]
param(
    [ValidateSet('fast','integration','release')][string]$Tier = 'fast',
    [string]$Python = $env:TMALL_TEST_PYTHON,
    [switch]$List,
    [string]$LogDir
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
if (-not $Python) { $Python = 'python' }
$forward = @((Join-Path $PSScriptRoot 'run_quality_gates.py'), '--tier', $Tier)
if ($List) { $forward += '--list' }
if ($LogDir) { $forward += @('--log-dir', $LogDir) }
Push-Location $root
try {
    & $Python @forward
    exit $LASTEXITCODE
} finally { Pop-Location }
