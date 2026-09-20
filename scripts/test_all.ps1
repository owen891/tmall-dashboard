[CmdletBinding()]

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root '.venv\Scripts\python.exe'

if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Project virtual environment not found: $python. Create .venv and install requirements.txt first."
}

Push-Location $root
try {
    $pytestArgs = if ($args.Count) { $args } else { @('-q') }
    Write-Host '[1/3] Running Python tests...'
    & $python -m pytest @pytestArgs
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    Write-Host '[2/3] Checking frontend JavaScript syntax...'
    $assets = Get-ChildItem -LiteralPath (Join-Path $root 'frontend\ui_demo\assets') -Filter '*.js' -File
    foreach ($asset in $assets) {
        & node --check $asset.FullName
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }

    Write-Host '[3/3] Validating UI demo contracts...'
    & node scripts/validate_ui_demos.cjs
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    Write-Host 'TEST_ALL_OK'
}
finally {
    Pop-Location
}
