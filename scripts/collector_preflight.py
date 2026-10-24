"""Fail-closed, credential-free runtime probe; optional read-only readiness probe.

runtime: interpreter/imports and exclusive temporary file write/read/delete only.
transport: runtime plus healthz/CDP; NOT permission to collect.
ready: all above plus positively verified source sessions. Unknown blocks.
No phase starts services, opens tabs, logs in or exports cookies.
"""
import argparse
from datetime import date, timedelta
import importlib
import ipaddress
import json
import os
from pathlib import Path
import sys
import tempfile
import urllib.parse
import urllib.request

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
from scripts.browser_runtime import resolve_browser, require_browser_identity

REQUIRED_IMPORTS = ('flask', 'waitress', 'pandas', 'openpyxl', 'xlrd',
                    'yaml', 'dateutil', 'websocket', 'cryptography')
SUPPORTED_SOURCES = {'bi_daily', 'bi_monthly', 'sycm_flow', 'sycm_item_flow',
                     'sycm_market', 'wanxiangtai'}


def probe_runtime():
    if sys.version_info < (3, 11):
        raise RuntimeError('Python >= 3.11 required')
    if not Path(sys.executable).is_file():
        raise RuntimeError('interpreter missing')
    for name in REQUIRED_IMPORTS:
        importlib.import_module(name)


def probe_directory(directory):
    """Do not mkdir, read real cookies or touch an existing file."""
    path = None
    try:
        fd, path = tempfile.mkstemp(prefix='.tmall-preflight-', dir=directory)
        with os.fdopen(fd, 'wb') as handle:
            handle.write(b'tmall-runtime-probe\n')
            handle.flush()
            os.fsync(handle.fileno())
        if Path(path).read_bytes() != b'tmall-runtime-probe\n':
            raise OSError('temporary probe readback mismatch')
    finally:
        if path is not None:
            Path(path).unlink()


def is_loopback(url):
    host = urllib.parse.urlsplit(url).hostname
    if host == 'localhost':
        return True
    try:
        return ipaddress.ip_address(host or '').is_loopback
    except ValueError:
        return False


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # A redirected loopback request must never turn into a proxy-free remote request.
        return None


def open_json(url):
    proxy = urllib.request.ProxyHandler({}) if is_loopback(url) else urllib.request.ProxyHandler()
    opener = urllib.request.build_opener(proxy, _NoRedirect())
    with opener.open(url, timeout=5) as response:
        return json.loads(response.read(1_048_576).decode('utf-8'))


def probe_session(source, cdp_url, fetch_json=open_json):
    """Only explicit server success proves login, never a tab URL or open port.

    BI/SYCM use the same read-only probe endpoints as existing login preparation.
    WXT's existing URL-only check is insufficient: remain unknown until a verified
    authenticated endpoint contract is available. No cookie values leave the browser.
    """
    if source == 'bi_monthly':
        return True  # Local aggregation, not a remote session.
    if source == 'wanxiangtai':
        return None
    if source == 'bi_daily':
        host = os.environ.get('TMALL_BI_HOST', '')
        endpoint = 'https://biprodapi.ecbis.cn/prod/base/getTableCustomView?tableKey=GoodsDataOverViewVo&showScmb=true'
    elif source.startswith('sycm_'):
        host = 'sycm.taobao.com'
        probe_token = os.environ.get('TMALL_SYCM_TOKEN', '')
        if not probe_token:
            # 2026-10-23 起探测 token 不再硬编码在公开仓库；未配置时返回
            # None（unknown，fail-closed），由调用方提示设置 TMALL_SYCM_TOKEN。
            return None
        day = (date.today() - timedelta(days=1)).isoformat()
        endpoint = ('https://sycm.taobao.com/flow/new/monitor/item/tops/rank.json'
                    f'?dateRange={day}%7C{day}&dateType=day&pageSize=1&page=1'
                    '&order=desc&orderBy=uv&device=2&indexCode=uv&token=' + probe_token)
    else:
        return None
    tabs = fetch_json(cdp_url + '/json')
    tab = next((tab for tab in tabs if tab.get('type') == 'page'
                and urllib.parse.urlsplit(tab.get('url', '')).hostname == host), None)
    if tab is None:
        return None
    ws_url = tab.get('webSocketDebuggerUrl', '')
    ws_endpoint = urllib.parse.urlsplit(ws_url)
    configured_endpoint = urllib.parse.urlsplit(cdp_url)
    if (ws_endpoint.scheme not in ('ws', 'wss') or ws_endpoint.hostname != configured_endpoint.hostname
            or ws_endpoint.port != configured_endpoint.port):
        return None
    import websocket
    expression = ("(async()=>{try{const r=await fetch(" + json.dumps(endpoint) +
                  ",{credentials:'include',signal:AbortSignal.timeout(5000)});"
                  "if(!r.ok)return null;const j=await r.json();"
                  "if(j.code===0)return true;if(j.code===5810)return false;return null;"
                  "}catch(e){return null}})()")
    ws = websocket.create_connection(ws_url, timeout=8, suppress_origin=True,
                                     http_no_proxy=['localhost', '127.0.0.1', '::1'])
    try:
        ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {
            'expression': expression, 'awaitPromise': True, 'returnByValue': True}}))
        # Bound messages as well as socket timeout; never wait forever on CDP events.
        for _ in range(32):
            result = json.loads(ws.recv())
            if result.get('id') == 1:
                value = result.get('result', {}).get('result', {}).get('value')
                return value if type(value) is bool else None
    finally:
        ws.close()
    return None


def preflight(*, root, sources, phase='runtime', directories=None, runtime_probe=probe_runtime,
              fetch_json=open_json, login_probe=None, service_url='http://127.0.0.1:5000',
              cdp_url='http://127.0.0.1:9223', browser_probe=None):
    checks = []
    def add(name, status, code, message):
        checks.append(dict(name=name, status=status, code=code, message=message))
    def result():
        ok = bool(checks) and all(item['status'] == 'ready' for item in checks)
        return {'schema_version': 1, 'phase': phase, 'ok': ok,
                'collection_ready': ok and phase == 'ready', 'checks': checks}
    if phase not in {'runtime', 'transport', 'ready'} or not sources or set(sources) - SUPPORTED_SOURCES:
        add('request', 'blocked', 'PREFLIGHT_INPUT_INVALID', 'Unknown phase or collection source')
        return result()
    try:
        runtime_probe()
        add('runtime', 'ready', 'RUNTIME_READY', 'Interpreter and required imports available')
    except Exception as exc:
        add('runtime', 'blocked', 'RUNTIME_IMPORT_FAILED', type(exc).__name__)
        return result()
    if directories is None:
        root = Path(root)
        # cookies 目录是部署私有配置（公开源码不携带路径），经 TMALL_COOKIE_DIR
        # 注入；未配置时退回仓库根（探测必然 blocked，保持 fail-closed）。
        cookies_dir = Path(os.environ.get('TMALL_COOKIE_DIR', root))
        directories = {'logs': Path(os.environ.get('TMALL_LOG_DIR', root / 'logs')),
                       'checkpoints': root / 'data'}
        if set(sources) != {'bi_monthly'}:
            directories['cookies'] = cookies_dir
    for name, directory in directories.items():
        try:
            probe_directory(directory)
            add(name, 'ready', 'DIRECTORY_WRITABLE', 'Exclusive temporary file write/read/delete verified')
        except OSError as exc:
            code = 'DIRECTORY_PERMISSION_DENIED' if isinstance(exc, PermissionError) else 'DIRECTORY_UNAVAILABLE'
            add(name, 'blocked', code, type(exc).__name__)
    if not result()['ok'] or phase == 'runtime':
        return result()
    if set(sources) != {'bi_monthly'}:
        try:
            if browser_probe is None:
                browser = resolve_browser(root)
                require_browser_identity(browser)
                cdp_url = f"http://{browser['host']}:{browser['port']}"
            else:
                browser_probe()
            add('browser_identity', 'ready', 'BROWSER_IDENTITY_VERIFIED', 'Configured listener owner and profile verified')
        except Exception as exc:
            add('browser_identity', 'blocked', 'BROWSER_IDENTITY_UNAVAILABLE', str(exc))
            return result()
    endpoints = [('service', service_url + '/healthz')]
    if set(sources) != {'bi_monthly'}:
        endpoints.append(('browser', cdp_url + '/json/version'))
    for name, url in endpoints:
        try:
            if not is_loopback(url):
                raise ValueError('Only loopback endpoints supported')
            payload = fetch_json(url)
            if not isinstance(payload, dict):
                raise ValueError('Invalid endpoint response')
            if name == 'browser' and not payload.get('webSocketDebuggerUrl'):
                raise ValueError('Missing CDP endpoint')
            if name == 'service' and (payload.get('ok') is not True or
                    payload.get('data', {}).get('service') != 'tmall-dashboard' or
                    payload.get('data', {}).get('database') != 'ok'):
                raise ValueError('Unhealthy service response')
            add(name, 'ready', name.upper() + '_REACHABLE', 'Endpoint reachable; does not prove login')
        except Exception as exc:
            add(name, 'blocked', name.upper() + '_UNAVAILABLE', type(exc).__name__)
    if not result()['ok'] or phase != 'ready':
        return result()
    for source in sources:
        if source == 'bi_monthly':
            add('login:' + source, 'ready', 'LOGIN_NOT_REQUIRED', 'Local aggregation; no remote session required')
            continue
        try:
            logged_in = login_probe(source) if login_probe else probe_session(source, cdp_url, fetch_json)
        except Exception:
            logged_in = None
        status, code = ('ready', 'LOGIN_VERIFIED') if logged_in is True else (
            ('blocked', 'LOGIN_REQUIRED') if logged_in is False else ('unknown', 'LOGIN_UNKNOWN'))
        add('login:' + source, status, code, 'Session verified' if logged_in is True else 'Session not verified; do not collect')
    return result()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--sources', required=True)
    parser.add_argument('--phase', choices=['runtime', 'transport', 'ready'], default='runtime')
    args = parser.parse_args(argv)
    report = preflight(root=args.root, sources=[part.strip() for part in args.sources.split(',') if part.strip()],
                       phase=args.phase, cdp_url='http://127.0.0.1:' + os.environ.get('TMALL_CDP_PORT', '9223'),
                       service_url=os.environ.get('TMALL_DASHBOARD_URL', 'http://127.0.0.1:5000').rstrip('/'))
    print(json.dumps(report, ensure_ascii=True))
    if report['ok']:
        return 0
    failed = [check for check in report['checks'] if check['status'] != 'ready']
    if any(check['code'].startswith(('RUNTIME_', 'DIRECTORY_', 'PREFLIGHT_')) for check in failed):
        return 20
    if any(check['name'] in ('service', 'browser', 'browser_identity') for check in failed):
        return 21
    return 22


if __name__ == '__main__':
    raise SystemExit(main())
