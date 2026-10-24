# Dot-source only: this file never starts a process or changes machine settings.
function Resolve-CollectorPython {
    param([Parameter(Mandatory=$true)][string]$ProjectRoot, [string]$Fallback)
    function Assert-RuntimePath([object]$Value, [string]$PathType) {
        if (($Value -isnot [string]) -or [string]::IsNullOrWhiteSpace($Value) -or
            -not [System.IO.Path]::IsPathRooted($Value) -or
            -not (Test-Path -LiteralPath $Value -PathType $PathType)) {
            throw 'RUNTIME_PATH_INVALID: expected an existing absolute path'
        }
        return [string]$Value
    }
    if (Test-Path Env:TMALL_COLLECT_PYTHON) {
        return Assert-RuntimePath $env:TMALL_COLLECT_PYTHON 'Leaf'
    }
    $recordPath = Join-Path $ProjectRoot 'data/runtime.json'
    if (Test-Path -LiteralPath $recordPath) {
        try {
            $record = Get-Content -LiteralPath $recordPath -Raw -Encoding UTF8 -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
            if (($record.schema_version -isnot [int] -and $record.schema_version -isnot [long]) -or $record.schema_version -ne 1) {
                throw 'RUNTIME_SCHEMA_INVALID: expected schema_version=1'
            }
            $python = Assert-RuntimePath $record.python 'Leaf'
            $runtimeRoot = Assert-RuntimePath $record.runtime_root 'Container'
            $prefix = [System.IO.Path]::GetFullPath($runtimeRoot).TrimEnd('\', '/') + [System.IO.Path]::DirectorySeparatorChar
            if (-not [System.IO.Path]::GetFullPath($python).StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)) {
                throw 'RUNTIME_PATH_INVALID: python is outside runtime_root'
            }
            return $python
        } catch {
            throw "RUNTIME_CONFIG_INVALID: $($_.Exception.Message)"
        }
    }
    if (-not $Fallback) { $Fallback = Join-Path $ProjectRoot '.venv/Scripts/python.exe' }
    return Assert-RuntimePath $Fallback 'Leaf'
}

function Resolve-CollectorBrowser {
    param([Parameter(Mandatory=$true)][string]$ProjectRoot, [string]$PythonPath,
          [ValidateSet('config','identity')][string]$Action = 'config')
    if (-not $PythonPath) { $PythonPath = Resolve-CollectorPython -ProjectRoot $ProjectRoot }
    $output = & $PythonPath (Join-Path $ProjectRoot 'scripts/browser_runtime.py') --root $ProjectRoot --action $Action
    $code = $LASTEXITCODE
    try { $result = ($output -join "`n") | ConvertFrom-Json -ErrorAction Stop }
    catch { throw 'BROWSER_CONFIG_PROTOCOL_INVALID' }
    if ($code -ne 0 -or $result.ok -ne $true) { throw "BROWSER_BLOCKED: $($result.code)" }
    if ($Action -eq 'identity') { return $result }
    return $result.config
}
