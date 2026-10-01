[CmdletBinding()]

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root '.venv\Scripts\python.exe'

if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Project virtual environment not found: $python. Create .venv and install requirements.txt first."
}

Push-Location $root
try {
    # Some PowerShell hosts pass a lone "-" through when no script arguments
    # were supplied. Never forward that sentinel to unittest as a test path.
    $testArgs = @($args | Where-Object { $_ -and $_ -ne '-' })
    Write-Host '[1/5] Running Python tests...'
    & $python -W error::ResourceWarning -m unittest discover -s tests -v @testArgs
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    Write-Host '[2/5] Checking frontend JavaScript syntax...'
    $assets = Get-ChildItem -LiteralPath (Join-Path $root 'frontend\ui_demo\assets') -Filter '*.js' -File -Recurse
    foreach ($asset in $assets) {
        & node --check $asset.FullName
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }

    Write-Host '[3/5] Testing frontend runtime modules...'
    & node scripts/test_frontend_runtime.cjs
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    Write-Host '[4/5] Validating UI demo contracts...'
    & node scripts/validate_ui_demos.cjs
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    Write-Host '[5/5] Validating database audit contracts...'
    & $python -m unittest tests.test_db_inventory tests.test_db_quality_check tests.test_schema_baseline -v
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    Write-Host 'TEST_ALL_OK'
}
finally {
    Pop-Location
}
