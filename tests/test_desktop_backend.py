import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request
from unittest.mock import patch


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(('127.0.0.1', 0))
        return listener.getsockname()[1]


class DesktopBackendTests(unittest.TestCase):
    def test_parser_requires_loopback_port_and_parent_pid(self):
        from desktop_backend import parse_args

        args = parse_args(['--port', '49152', '--parent-pid', '321'])

        self.assertEqual(args.host, '127.0.0.1')
        self.assertEqual(args.port, 49152)
        self.assertEqual(args.parent_pid, 321)

    def test_parser_rejects_privileged_or_invalid_ports(self):
        from desktop_backend import parse_args

        for value in ('0', '1023', '65536', 'not-a-port'):
            with self.subTest(value=value), self.assertRaises(SystemExit):
                parse_args(['--port', value, '--parent-pid', '321'])

    def test_build_config_uses_desktop_user_paths(self):
        from desktop_backend import build_app_config
        from desktop_runtime import DesktopPaths

        paths = DesktopPaths('D:/db/dashboard.db', 'D:/uploads', 'D:/inbox', 'D:/logs')
        # Keep the default-path contract independent of operator-level shell config.
        with patch.dict(os.environ, {'IMPORT_SCAN_ALLOWED_ROOTS': ''}):
            config = build_app_config(paths)

        self.assertEqual(config['DATABASE_PATH'], 'D:/db/dashboard.db')
        self.assertEqual(config['SQLALCHEMY_DATABASE_URI'], 'sqlite:///D:/db/dashboard.db')
        self.assertEqual(config['UPLOAD_FOLDER'], 'D:/uploads')
        self.assertEqual(config['IMPORT_SCAN_ALLOWED_ROOTS'], ['D:/inbox'])
        self.assertEqual(config['TMALL_DESKTOP_MODE'], '1')

    def test_build_config_preserves_configured_scan_roots(self):
        from desktop_backend import build_app_config
        from desktop_runtime import DesktopPaths

        paths = DesktopPaths('D:/db/dashboard.db', 'D:/uploads', 'D:/inbox', 'D:/logs')
        with patch.dict(os.environ, {'IMPORT_SCAN_ALLOWED_ROOTS': os.pathsep.join(['D:/shared', 'E:/archive'])}):
            config = build_app_config(paths)

        self.assertEqual(
            config['IMPORT_SCAN_ALLOWED_ROOTS'],
            ['D:/inbox', 'D:/shared', 'E:/archive'],
        )

    def test_real_backend_serves_health_and_overview_on_loopback(self):
        port = free_port()
        with tempfile.TemporaryDirectory() as roaming, tempfile.TemporaryDirectory() as local:
            environment = os.environ.copy()
            environment.update({
                'APPDATA': roaming,
                'LOCALAPPDATA': local,
                'IMPORT_SCAN_ALLOWED_ROOTS': '',
                'PYTHONIOENCODING': 'utf-8',
            })
            process = subprocess.Popen(
                [
                    sys.executable,
                    os.path.join(PROJECT_ROOT, 'desktop_backend.py'),
                    '--port', str(port),
                    '--parent-pid', str(os.getpid()),
                ],
                cwd=PROJECT_ROOT,
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
            )
            try:
                deadline = time.monotonic() + 20
                health = None
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        output = process.stdout.read() if process.stdout else ''
                        self.fail(f'desktop backend exited early: {output}')
                    try:
                        with urllib.request.urlopen(f'http://127.0.0.1:{port}/healthz', timeout=1) as response:
                            health = json.loads(response.read().decode('utf-8'))
                        break
                    except OSError:
                        time.sleep(0.1)

                self.assertIsNotNone(health, 'desktop backend did not become ready')
                self.assertTrue(health['ok'])
                with urllib.request.urlopen(f'http://127.0.0.1:{port}/', timeout=3) as response:
                    page = response.read()
                self.assertIn('天猫'.encode('utf-8'), page)
                self.assertTrue(os.path.exists(os.path.join(roaming, 'TmallDashboard', 'data', 'dashboard.db')))
                log_path = os.path.join(local, 'TmallDashboard', 'logs', 'backend.log')
                self.assertTrue(os.path.isfile(log_path))
                with open(log_path, encoding='utf-8') as handle:
                    self.assertIn('桌面后端已启动', handle.read())
            finally:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
                if process.stdout:
                    process.stdout.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
