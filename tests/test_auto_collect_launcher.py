"""Exercise the scheduled Windows launcher with fake browser/API boundaries."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


@unittest.skipUnless(os.name == 'nt' and shutil.which('powershell.exe'), 'Windows launcher')
class AutoCollectLauncherTests(unittest.TestCase):
    def run_launcher(self, sources, login_exit=0):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'scripts').mkdir()
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
            launcher = Path(__file__).resolve().parents[1] / 'scripts' / 'auto-collect.ps1'
            harness = root / 'harness.ps1'
            harness.write_text('''param([string]$Sources)
function Start-Sleep {}
function Invoke-WebRequest {
    param($Uri, $Method, $Body, $ContentType, [switch]$UseBasicParsing, $TimeoutSec)
    if ($Uri -like '*/api/collect/trigger') {
        Add-Content -LiteralPath $env:TEST_REQUESTS -Value $Body -Encoding UTF8
        return @{ Content = '{"ok":true}' }
    }
    if ($Uri -like '*/api/collect/log/*') {
        return @{ Content = '{"data":{"status":"completed"}}' }
    }
    return @{ StatusCode = 200 }
}
& $env:TEST_LAUNCHER -Sources $Sources
exit $LASTEXITCODE
''', encoding='utf-8-sig')
            requests = root / 'requests.jsonl'
            env = dict(os.environ, TMALL_PROJECT_ROOT=str(root),
                       TMALL_COLLECT_PYTHON=sys.executable, TMALL_LOG_DIR=str(root / 'logs'),
                       TMALL_CREDENTIAL_FILE=str(root / 'missing-credentials'),
                       BI_USERNAME='test', BI_PASSWORD='test', PYTHONIOENCODING='gbk',
                       TEST_REQUESTS=str(requests), TEST_LAUNCHER=str(launcher))
            result = subprocess.run(
                ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass',
                 '-File', str(harness), '-Sources', sources],
                env=env, capture_output=True, timeout=30,
            )
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
        self.assertEqual(code, 1, log)
        self.assertEqual(sources, [])
