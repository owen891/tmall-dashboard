"""Exercise the scheduled Windows launcher with fake browser/API boundaries."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import secrets
import unittest


@unittest.skipUnless(os.name == 'nt' and shutil.which('powershell.exe'), 'Windows launcher')
class AutoCollectLauncherTests(unittest.TestCase):
    def run_launcher(self, sources, login_exit=0, preflight_block=None, launcher_path=None):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'scripts').mkdir()
            (root / 'logs').mkdir()
            # Explicit boundary fixture: no installed runtime, business DB, browser
            # or remote session is touched by this launcher orchestration test.
            (root / 'scripts' / 'collector_preflight.py').write_text(
                'import json, sys\n'
                'phase = sys.argv[sys.argv.index("--phase") + 1]\n'
                f'blocked = phase == {preflight_block!r}\n'
                'print(json.dumps({"ok": not blocked, "phase": phase, '
                '"collection_ready": not blocked and phase == "ready", '
                '"checks": [{"name": "fixture", "status": "blocked" if blocked else "ready", '
                '"code": "FIXTURE_BLOCKED" if blocked else "FIXTURE_READY", "message": "isolated test"}]}))\n'
                'sys.exit(20 if blocked else 0)\n', encoding='utf-8')
            (root / 'scripts' / 'browser_runtime.py').write_text(
                'import json,os,sys\n'
                'from pathlib import Path\n'
                'Path(os.environ["TEST_BROWSER_READS"]).write_text("fixture browser config read")\n'
                'action=sys.argv[sys.argv.index("--action")+1]\n'
                'print(json.dumps({"ok":True,"pid":123,"config":{'
                '"schema_version":1,"executable":os.environ["TMALL_CHROME_PATH"],'
                '"user_data_dir":os.environ["TMALL_CHROME_PROFILE"],'
                '"host":"127.0.0.1","port":int(os.environ["TMALL_CDP_PORT"]),'
                '"reuse_only":True}}))\n', encoding='utf-8')
            marker = '\u2713 \u2717 \u26a0 \u91c7\u96c6\u65e5\u5fd7'
            for name in ('auto_login_bi.py', 'auto_login_wanxiangtai.py'):
                (root / 'scripts' / name).write_text(
                    f'import sys\nprint({ascii(marker)})\nsys.exit({login_exit})\n',
                    encoding='utf-8',
                )
            (root / 'scripts' / 'aggregate_store_daily.py').write_text(
                'import sys\n'
                'sys.exit(0)\n',
                encoding='utf-8',
            )
            launcher = launcher_path or Path(__file__).resolve().parents[1] / 'scripts' / 'auto-collect.ps1'
            guarded_python = root / 'fixture-python.cmd'
            allowed_scripts = ['collector_preflight.py', 'browser_runtime.py', 'auto_login_bi.py',
                               'auto_login_wanxiangtai.py', 'aggregate_store_daily.py']
            guarded_python.write_text(
                '@echo off\n' + ''.join(
                    f'if /I "%~1"=="{root / "scripts" / name}" goto allowed\n'
                    for name in allowed_scripts) +
                f'echo NATIVE_COMMAND_DENIED>>"{root / "isolation-violations.txt"}"\n'
                'exit /b 97\n:allowed\n'
                f'"{sys.executable}" %*\nexit /b %errorlevel%\n', encoding='utf-8')
            fake_chrome = root / 'fixture-chrome.exe'
            fake_chrome.write_bytes(b'NOT AN EXECUTABLE: intercepted by harness')
            harness = root / 'harness.ps1'
            harness.write_text('''param([string]$Sources)
function global:Deny-Isolation([string]$Reason) {
    Add-Content -LiteralPath $env:TEST_VIOLATIONS -Value $Reason
    throw "ISOLATION_DENIED: $Reason"
}
function global:Start-Sleep {}
function global:Start-Process {
    param($FilePath, $ArgumentList, $WorkingDirectory, $WindowStyle)
    if ($FilePath -ne $env:TMALL_CHROME_PATH -or
        "$ArgumentList" -notlike "*$env:TMALL_CHROME_PROFILE*") {
        Deny-Isolation 'unexpected process launch'
    }
    Add-Content -LiteralPath $env:TEST_FAKE_STARTS -Value 'FAKE_CHROME_NOT_STARTED'
    # Deliberately no call to the native cmdlet, even for allowlisted requests.
}
function global:Get-Process {
    param($Name, $Id, $ErrorAction)
    if ($Name -and $Name -ne 'chrome') { Deny-Isolation 'unexpected process query' }
    return @()
}
function global:Stop-Process {
    [CmdletBinding()] param([Parameter(ValueFromPipeline=$true)]$InputObject, [int]$Id, [switch]$Force)
    process { if ($InputObject -or $PSBoundParameters.ContainsKey('Id')) { Deny-Isolation 'process stop' } }
}
function global:Invoke-RestMethod { Deny-Isolation 'unmocked REST request' }
$fixtureRequest = {
    param($Uri, $Method, $Body)
    $url = [Uri]$Uri
    if ($url.Host -ne '127.0.0.1' -or $url.Port -ne [int]$env:TEST_HTTP_PORT -or
        $url.Port -in @(5000,9223)) { Deny-Isolation 'request outside fixture origin' }
    if ($url.AbsolutePath -eq '/api/collect/trigger') {
        Add-Content -LiteralPath $env:TEST_REQUESTS -Value $Body -Encoding UTF8
        return @{ StatusCode = 200; Content = '{"ok":true}' }
    }
    if ($url.AbsolutePath -like '/api/collect/log/*') {
        return @{ StatusCode = 200; Content = '{"data":{"status":"completed"}}' }
    }
    if ($url.AbsolutePath -eq '/json') { return @{ StatusCode = 200; Content = '[]' } }
    if ($url.AbsolutePath -in @('/healthz','/api/health','/json/version')) {
        return @{ StatusCode = 200; Content = '{}' }
    }
    Deny-Isolation 'unknown fixture endpoint'
}
function global:Invoke-WebRequest {
    param($Uri, $Method, $Body, $ContentType, [switch]$UseBasicParsing, $TimeoutSec)
    # This is a no-network adapter solely for replaying the original launcher.
    if ($env:TEST_LEGACY_BASELINE -ne '1') { Deny-Isolation 'unmocked WebRequest' }
    $parsed = [Uri]$Uri
    if ($parsed.Host -ne '127.0.0.1' -or $parsed.Port -notin @(5000,[int]$env:TEST_HTTP_PORT)) {
        Deny-Isolation 'unexpected legacy endpoint'
    }
    return & $fixtureRequest ("http://127.0.0.1:" + $env:TEST_HTTP_PORT + $parsed.PathAndQuery) $Method $Body
}
if ($env:TEST_LEGACY_BASELINE -eq '1') {
    & $env:TEST_LAUNCHER -Sources $Sources
} else {
    & $env:TEST_LAUNCHER -Sources $Sources -LocalRequest $fixtureRequest
}
exit $LASTEXITCODE
''', encoding='utf-8-sig')
            requests = root / 'requests.jsonl'
            fixture_port = secrets.randbelow(20000) + 40000  # No socket/listener is created.
            env = dict(os.environ, TMALL_PROJECT_ROOT=str(root),
                       TMALL_COLLECT_PYTHON=str(guarded_python), TMALL_LOG_DIR=str(root / 'logs'),
                       TMALL_CHROME_PATH=str(fake_chrome), TMALL_CHROME_PROFILE=str(root / 'browser-fixture'),
                       TMALL_CREDENTIAL_FILE=str(root / 'missing-credentials'),
                       BI_USERNAME='test', BI_PASSWORD='test', PYTHONIOENCODING='gbk',
                       TEST_REQUESTS=str(requests), TEST_LAUNCHER=str(launcher),
                       TEST_HTTP_PORT=str(fixture_port), TEST_LEGACY_BASELINE='1' if launcher_path else '0',
                       TEST_VIOLATIONS=str(root / 'isolation-violations.txt'),
                       TEST_FAKE_STARTS=str(root / 'fake-starts.txt'),
                       TEST_BROWSER_READS=str(root / 'browser-reads.txt'),
                       TMALL_DASHBOARD_URL=f'http://127.0.0.1:{fixture_port}',
                       TMALL_CDP_PORT=str(fixture_port), HTTP_PROXY='http://127.0.0.1:1')
            result = subprocess.run(
                ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass',
                 '-File', str(harness), '-Sources', sources],
                env=env, capture_output=True, timeout=30,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
            )
            violations = root / 'isolation-violations.txt'
            self.assertFalse(violations.exists(), violations.read_text() if violations.exists() else '')
            self.assertFalse((root / 'fake-starts.txt').exists(), 'No browser start is allowed in collection preparation')
            if sources == 'bi_monthly':
                self.assertFalse((root / 'browser-reads.txt').exists(), 'Monthly aggregation must not require a browser')
            log = next((root / 'logs').glob('*.log')).read_text(encoding='utf-8-sig')
            payloads = []
            if requests.exists():
                # Each request is pretty-printed JSON by ConvertTo-Json.
                decoder = json.JSONDecoder()
                remaining = requests.read_text(encoding='utf-8-sig').strip()
                while remaining:
                    payload, end = decoder.raw_decode(remaining)
                    payloads.append(payload['source'])
                    remaining = remaining[end:].strip()
            if preflight_block not in ('runtime', 'transport') and sources != 'bi_monthly':
                self.assertIn(marker, log)
            self.assertNotIn('UnicodeEncodeError', log)
            return result.returncode, payloads, log

    def test_bi_sources_and_utf8_logs(self):
        code, sources, log = self.run_launcher('bi_daily,bi_monthly')
        self.assertEqual(code, 0, log)
        self.assertEqual(sources, ['bi_daily', 'bi_monthly'])

    def test_other_sources_and_utf8_logs(self):
        expected = ['sycm_flow', 'sycm_item_flow', 'sycm_market', 'wanxiangtai']
        code, sources, log = self.run_launcher(','.join(expected))
        self.assertEqual(code, 0, log)
        self.assertEqual(sources, expected)

    def test_failed_login_does_not_trigger_collection(self):
        code, sources, log = self.run_launcher('bi_daily,bi_monthly', login_exit=1)
        self.assertEqual(code, 22, log)  # Explicit manual-login classification, no UI fallback.
        self.assertEqual(sources, [])

    def test_runtime_preflight_failure_does_not_login_or_trigger(self):
        code, sources, log = self.run_launcher('bi_daily', preflight_block='runtime')
        self.assertEqual(code, 20, log)
        self.assertEqual(sources, [])
        self.assertNotIn('[3/6]', log)

    def test_monthly_only_does_not_require_or_prepare_browser(self):
        code, sources, log = self.run_launcher('bi_monthly')
        self.assertEqual(code, 0, log)
        self.assertEqual(sources, ['bi_monthly'])

    def test_unknown_session_blocks_before_cookie_export_and_trigger(self):
        code, sources, log = self.run_launcher('bi_daily', preflight_block='ready')
        self.assertEqual(code, 22, log)
        self.assertEqual(sources, [])
        self.assertNotIn('[3c]', log)
