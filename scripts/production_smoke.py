"""Exercise the real Waitress/WSGI process over HTTP and clean it up."""

import argparse
import base64
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request


def _request(url, headers=None):
    request = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, dict(response.headers), response.read()
    except urllib.error.HTTPError as error:
        return error.code, dict(error.headers), error.read()


def run_smoke(*, port=8790, username=None, password=None, database_path=None):
    if not username or not password:
        raise ValueError('username and password are required for production smoke')
    environment = os.environ.copy()
    environment['DASHBOARD_USERNAME'] = username
    environment['DASHBOARD_PASSWORD'] = password
    if database_path:
        environment['TMALL_DB_PATH'] = os.path.abspath(database_path)
    # Waitress strips proxy headers unless the immediate proxy is explicitly
    # trusted. Keep this aligned with the production launch command so the
    # application cannot mistake a forwarded external request for loopback.
    command = [
        sys.executable, '-m', 'waitress',
        '--host=127.0.0.1', f'--port={port}',
        '--trusted-proxy=127.0.0.1',
        '--trusted-proxy-headers=x-forwarded-for',
        'wsgi:application',
    ]
    process = subprocess.Popen(
        command,
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    base_url = f'http://127.0.0.1:{port}'
    proxy_headers = {'X-Forwarded-For': '192.168.10.20'}
    credentials = base64.b64encode(f'{username}:{password}'.encode('utf-8')).decode('ascii')
    authenticated_headers = {**proxy_headers, 'Authorization': f'Basic {credentials}'}
    try:
        deadline = time.time() + 15
        last_error = None
        while time.time() < deadline:
            try:
                _request(f'{base_url}/healthz', proxy_headers)
                break
            except OSError as error:
                last_error = error
                if process.poll() is not None:
                    output = process.stdout.read() if process.stdout else ''
                    raise RuntimeError(f'Waitress exited with code {process.returncode}: {output}') from error
                time.sleep(0.25)
        else:
            raise RuntimeError(f'Waitress did not become ready: {last_error}')

        unauth_status, _, _ = _request(f'{base_url}/healthz', proxy_headers)
        health_status, health_headers, health_body = _request(f'{base_url}/healthz', authenticated_headers)
        page_status, page_headers, page_body = _request(f'{base_url}/products', authenticated_headers)
        report = {
            'ok': (
                unauth_status == 401
                and health_status == 200
                and page_status == 200
                and b'"database":"ok"' in health_body
                and b'<!doctype html>' in page_body.lower()
                and health_headers.get('X-Content-Type-Options') == 'nosniff'
                and page_headers.get('X-Frame-Options') == 'SAMEORIGIN'
            ),
            'unauthenticated_health_status': unauth_status,
            'authenticated_health_status': health_status,
            'products_status': page_status,
            'security_headers': {
                'health_x_content_type_options': health_headers.get('X-Content-Type-Options'),
                'products_x_frame_options': page_headers.get('X-Frame-Options'),
            },
        }
        if not report['ok']:
            raise RuntimeError(report)
        return report
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def main():
    parser = argparse.ArgumentParser(description='Run the production Waitress/WSGI HTTP smoke')
    parser.add_argument('--port', type=int, default=8790)
    parser.add_argument('--database', default=None)
    args = parser.parse_args()
    report = run_smoke(
        port=args.port,
        username=os.environ.get('DASHBOARD_USERNAME'),
        password=os.environ.get('DASHBOARD_PASSWORD'),
        database_path=args.database,
    )
    print(report)


if __name__ == '__main__':
    main()
