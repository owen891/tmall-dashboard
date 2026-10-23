#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
万相台自动登录脚本（CDP 方式）

流程：
1. 检查 Chrome 调试模式是否运行
2. 打开万相台页面，检查登录态
3. 如未登录，打开淘宝登录页，自动填入账密并提交
4. 遇到滑块验证时提示用户手动完成
5. 登录成功后 cookie 自动保存在 Chrome 用户数据目录中

凭据从环境变量读取：
  WXT_USERNAME  - 万相台/淘宝账号
  WXT_PASSWORD  - 万相台/淘宝密码
"""

import json
import os
import sys
import time
import subprocess
import urllib.request
import websocket
from pathlib import Path

# 独立脚本运行时保证能 import 项目内模块（services.credentials_crypto 等）
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from services.credentials_crypto import decrypt_password
from scripts.browser_runtime import resolve_browser, require_browser_identity, BrowserConfigurationError
from scripts.collector_preflight import open_json, probe_session
from scripts.runtime_paths import loopback_proxy_env

CDP_PORT = int(os.environ.get('TMALL_CDP_PORT', '9223'))
WXT_URL = 'https://one.alimama.com/'
TAOBAO_LOGIN_URL = 'https://login.taobao.com/member/login.jhtml?redirectURL=https%3A%2F%2Fone.alimama.com%2F&style=mini&newMini2=true'

USERNAME = os.environ.get('WXT_USERNAME', '')
PASSWORD = os.environ.get('WXT_PASSWORD', '')

def load_credentials():
    global USERNAME, PASSWORD
    if not USERNAME or not PASSWORD:
        try:
            db_path = os.environ.get('TMALL_DB_PATH') or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'dashboard.db')
            with __import__('sqlite3').connect(db_path) as _conn:
                _row = _conn.execute("SELECT setting_value FROM app_settings WHERE setting_key = 'collector_credentials'").fetchone()
            if _row:
                _payload = json.loads(_row[0])
                if 'username' in _payload or 'password' in _payload: _payload = {'bi': _payload}
                _item = _payload.get('wanxiangtai') or {}
                USERNAME = USERNAME or str(_item.get('username') or '').strip()
                PASSWORD = PASSWORD or decrypt_password(str(_item.get('password') or ''))
        except Exception:
            pass

    # Backward-compatible fallback for the legacy local credential file.
    if not USERNAME or not PASSWORD:
        try:
            with open(os.environ.get('TMALL_CREDENTIAL_FILE', r'E:\桌面\AI\BI.txt'), encoding='utf-8') as handle:
                _lines = handle.read().splitlines()
            for _i, _line in enumerate(_lines[:-1]):
                if _line.startswith(('账号：', '账号:')) and _lines[_i + 1].startswith(('密码：', '密码:')):
                    USERNAME = USERNAME or _line[3:].lstrip('：:').strip()
                    PASSWORD = PASSWORD or _lines[_i + 1][3:].lstrip('：:').strip()
                    break
        except (OSError, UnicodeError):
            pass

def get_tabs():
    return open_json(f'http://127.0.0.1:{CDP_PORT}/json')


def get_browser_ws():
    ver = open_json(f'http://127.0.0.1:{CDP_PORT}/json/version')
    return ver['webSocketDebuggerUrl']


def create_tab(url):
    ws = websocket.create_connection(get_browser_ws(), timeout=10, suppress_origin=True)
    ws.send(json.dumps({'id': 1, 'method': 'Target.createTarget', 'params': {'url': url, 'background': True}}))
    while True:
        msg = json.loads(ws.recv())
        if msg.get('id') == 1:
            target_id = msg.get('result', {}).get('targetId')
            ws.close()
            return target_id


def find_tab(url_contains):
    for t in get_tabs():
        if t.get('type') == 'page' and url_contains in t.get('url', ''):
            return t
    return None


def cdp_eval(ws_url, expression, timeout=15):
    ws = websocket.create_connection(ws_url, timeout=timeout, suppress_origin=True)
    ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {
        'expression': expression, 'returnByValue': True, 'awaitPromise': True
    }}))
    while True:
        msg = json.loads(ws.recv())
        if msg.get('id') == 1:
            ws.close()
            return msg.get('result', {}).get('result', {}).get('value')


def check_login():
    """An existing tab URL alone is never proof of an authenticated session."""
    return probe_session('wanxiangtai', f'http://127.0.0.1:{CDP_PORT}') is True


def do_login():
    """走淘宝账密登录流程。"""
    load_credentials()
    if not USERNAME or not PASSWORD:
        print('[错误] 未设置 WXT_USERNAME / WXT_PASSWORD 环境变量')
        return False

    # 打开淘宝登录页
    print('[登录] 打开淘宝登录页...')
    tab = find_tab('login.taobao.com')
    if not tab:
        create_tab(TAOBAO_LOGIN_URL)
        time.sleep(5)
        tab = find_tab('login.taobao.com')
        if not tab:
            print('[错误] 无法打开淘宝登录页')
            return False

    # 填账密
    print('[登录] 填入账密...')
    result = cdp_eval(tab['webSocketDebuggerUrl'], f'''
        (function() {{
            var user = document.getElementById('fm-login-id');
            var pass = document.getElementById('fm-login-password');
            if (!user || !pass) return 'inputs_not_found';
            user.focus(); user.value = {json.dumps(USERNAME)};
            user.dispatchEvent(new Event('input', {{bubbles: true}}));
            pass.focus(); pass.value = {json.dumps(PASSWORD)};
            pass.dispatchEvent(new Event('input', {{bubbles: true}}));
            return 'filled';
        }})()
    ''')
    print(f'  填写: {result}')
    time.sleep(1)

    # 点登录
    result = cdp_eval(tab['webSocketDebuggerUrl'], '''
        (function() {
            var btns = document.querySelectorAll('button, a, input[type=submit]');
            for (var i = 0; i < btns.length; i++) {
                var b = btns[i];
                if (b.offsetParent && b.innerText && b.innerText.trim() === '登录' && b.children.length === 0) {
                    b.click(); return 'clicked';
                }
            }
            return 'no_button';
        })()
    ''')
    print(f'  点击登录: {result}')
    time.sleep(5)

    # 检查是否出现滑块/验证码/扫码等需要人工操作的场景
    result = cdp_eval(tab['webSocketDebuggerUrl'], '''
        (function() {
            // 检测滑块验证iframe
            var iframes = document.querySelectorAll('iframe');
            for (var i = 0; i < iframes.length; i++) {
                var src = iframes[i].src || '';
                if (src.indexOf('punish') >= 0 || src.indexOf('captcha') >= 0) return 'need_slider';
            }
            // 检测页面上的滑块元素
            if (document.querySelector('.nc_iconfont, .btn_slide, .nc-lang-cnt, [class*="slider"], [class*="captcha"]')) {
                return 'need_slider';
            }
            // 检测是否出现扫码登录提示（页面上有二维码图片）
            if (document.querySelector('.qrcode-img, .qrcode, [class*="qrcode"], [class*="qr-code"]')) {
                return 'need_qrcode';
            }
            return 'no_verify';
        })()
    ''')

    if result in ('need_slider', 'need_qrcode'):
        print('MANUAL_LOGIN_REQUIRED: captcha/interactive login; selected browser is not killed or restarted')
        return False

    # Only an authoritative session response can prove success.
    return check_login()


def main():
    global CDP_PORT
    try:
        browser = resolve_browser(_PROJECT_ROOT)
        require_browser_identity(browser)
    except BrowserConfigurationError as exc:
        print(str(exc))
        return 21
    CDP_PORT = browser['port']
    os.environ.update(loopback_proxy_env())
    if browser['reuse_only']:
        if probe_session('wanxiangtai', f'http://127.0.0.1:{CDP_PORT}') is not True:
            print('MANUAL_LOGIN_REQUIRED: WXT authoritative session check unavailable; no browser action taken')
            return 22
        return 0
    print('=' * 50)
    print('  万相台自动登录')
    print('=' * 50)

    # 检查 Chrome 调试模式
    try:
        urllib.request.urlopen(f'http://127.0.0.1:{CDP_PORT}/json/version', timeout=3)
        print(f'[1/3] Chrome 调试模式运行中 (端口 {CDP_PORT})')
    except Exception as e:
        print(f'[1/3] Chrome 调试模式未启动: {e}')
        return 1

    # 检查登录态
    print('[2/3] 检查万相台登录态...')
    if check_login():
        print('[3/3] 无需登录，cookie 有效')
        return 0

    # 需要登录
    print('[3/3] 开始自动登录...')
    if do_login():
        print('\n✓ 登录成功，cookie 已保存')
        return 0
    else:
        print('\n✗ 登录失败')
        return 1


if __name__ == '__main__':
    sys.exit(main())
