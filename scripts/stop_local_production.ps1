param(
    [int]$Port = 5000
)

$ErrorActionPreference = 'Stop'

$listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if (-not $listener) {
    exit 0
}

$process = Get-CimInstance Win32_Process -Filter "ProcessId=$($listener[0].OwningProcess)"
if (-not $process.CommandLine -or $process.CommandLine -notmatch 'waitress.*wsgi:application') {
    throw "Port $Port is owned by a process that is not the dashboard Waitress service."
}

Stop-Process -Id $listener[0].OwningProcess -Force
