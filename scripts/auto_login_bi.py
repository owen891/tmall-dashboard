"""
自动登录BI页面并打开所有采集所需页面
通过Chrome DevTools Protocol (CDP) 操作
用法: python auto_login_bi.py [--bi-username USER] [--bi-password PASS]
"""
import json
import sys
import time
import urllib.request
import websocket
import argparse
import os
import sqlite3
import subprocess
from pathlib import Path

# ==================== 配置 ====================
CDP_PORT = int(os.environ.get('TMALL_CDP_PORT', '9223'))
BI_URL = "https://primeet.ecbis.cn/workTable/workTableHome"
BI_LOGIN_URL = "https://primeet.ecbis.cn/login"
SYCM_URL = "https://sycm.taobao.com/"
WANXIANGTAI_URL = "https://one.alimama.com/"

# 凭据只能从环境变量或显式参数提供，禁止在源码中保留默认账号密码。
DEFAULT_BI_USERNAME = os.environ.get('BI_USERNAME', '')
DEFAULT_BI_PASSWORD = os.environ.get('BI_PASSWORD', '')


def load_saved_credentials():
    """Read credentials saved by the dashboard settings page, without logging them."""
    db_path = os.environ.get('TMALL_DB_PATH') or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'dashboard.db')
    try:
        with sqlite3.connect(db_path) as conn:
            row = conn.execute("SELECT setting_value FROM app_settings WHERE setting_key = 'collector_credentials'").fetchone()
        if not row:
            return '', ''
        payload = json.loads(row[0])
        if 'username' in payload or 'password' in payload: payload = {'bi': payload}
        item = payload.get('bi') or {}
        return str(item.get('username') or '').strip(), str(item.get('password') or '')
    except (OSError, sqlite3.Error, ValueError, TypeError):
        return '', ''


def load_platform_credentials(platform):
    db_path = os.environ.get('TMALL_DB_PATH') or os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'dashboard.db')
    try:
        with sqlite3.connect(db_path) as conn:
            row = conn.execute(
                "SELECT setting_value FROM app_settings WHERE setting_key = 'collector_credentials'"
            ).fetchone()
        payload = json.loads(row[0]) if row else {}
        if 'username' in payload or 'password' in payload:
            payload = {'bi': payload}
        item = payload.get(platform) or {}
        return str(item.get('username') or '').strip(), str(item.get('password') or '')
    except (OSError, sqlite3.Error, ValueError, TypeError):
        return '', ''


def get_browser_ws():
    """获取browser级别的WebSocket URL"""
    with urllib.request.urlopen(f"http://127.0.0.1:{CDP_PORT}/json/version") as resp:
        version = json.loads(resp.read().decode())
        return version['webSocketDebuggerUrl']


def ensure_browser():
    """Reuse the collector browser, or start an isolated background instance."""
    try:
        with urllib.request.urlopen(f'http://127.0.0.1:{CDP_PORT}/json/version', timeout=2):
            return
    except OSError:
        pass
    chrome = os.environ.get('TMALL_CHROME_PATH', r'C:\Program Files\Google\Chrome\Application\chrome.exe')
    profile = os.environ.get('TMALL_CHROME_PROFILE') or str(
        Path(os.environ['LOCALAPPDATA']) / 'TmallDashboard/CollectorChrome')
    args = [chrome, f'--remote-debugging-port={CDP_PORT}',
            f'--remote-allow-origins=http://localhost:{CDP_PORT},http://127.0.0.1:{CDP_PORT}',
            f'--user-data-dir={profile}', '--no-first-run', '--no-default-browser-check']
    if os.environ.get('TMALL_CHROME_HEADLESS', '1') == '1':
        args += ['--headless=new', '--window-size=1440,1000']
    subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(30):
        try:
            with urllib.request.urlopen(f'http://127.0.0.1:{CDP_PORT}/json/version', timeout=1):
                return
        except OSError:
            time.sleep(1)
    raise RuntimeError('采集专用 Chrome 启动超时，请检查独立用户目录是否被占用')


def create_target(browser_ws, url):
    """通过CDP创建新标签页"""
    ws = websocket.create_connection(browser_ws, suppress_origin=True)
    ws.settimeout(10)
    msg_id = int(time.time() * 1000) % 1000000
    msg = {"id": msg_id, "method": "Target.createTarget", "params": {"url": url, "background": True}}
    ws.send(json.dumps(msg))
    while True:
        result = json.loads(ws.recv())
        if result.get('id') == msg_id:
            ws.close()
            return result.get('result', {}).get('targetId')
    ws.close()
    return None


def get_page_ws(url_contains):
    """根据URL关键字查找页面的WebSocket URL"""
    with urllib.request.urlopen(f"http://127.0.0.1:{CDP_PORT}/json") as resp:
        tabs = json.loads(resp.read().decode())
    for tab in tabs:
        if tab.get('type') == 'page' and url_contains in tab.get('url', ''):
            return tab['webSocketDebuggerUrl']
    return None


def cdp_evaluate(ws_url, expression, await_promise=False):
    """在指定页面执行JavaScript"""
    ws = websocket.create_connection(ws_url, suppress_origin=True)
    ws.settimeout(30)
    msg_id = int(time.time() * 1000) % 1000000
    msg = {
        "id": msg_id,
        "method": "Runtime.evaluate",
        "params": {
            "expression": expression,
            "returnByValue": True,
            "awaitPromise": await_promise
        }
    }
    ws.send(json.dumps(msg))
    while True:
        result = json.loads(ws.recv())
        if result.get('id') == msg_id:
            ws.close()
            return result.get('result', {}).get('result', {}).get('value')
    ws.close()
    return None


def cdp_navigate(ws_url, url):
    """导航到指定URL"""
    ws = websocket.create_connection(ws_url, suppress_origin=True)
    ws.settimeout(10)
    msg_id = int(time.time() * 1000) % 1000000
    msg = {"id": msg_id, "method": "Page.navigate", "params": {"url": url}}
    ws.send(json.dumps(msg))
    while True:
        result = json.loads(ws.recv())
        if result.get('id') == msg_id:
            ws.close()
            return True
    ws.close()
    return False


def login_taobao_tab(username, password):
    """Fill the shared Taobao login page used by SYCM, if it is present."""
    ws_url = get_page_ws('login.taobao.com')
    if not ws_url:
        return False
    result = cdp_evaluate(ws_url, f'''(function() {{
        const user = document.getElementById('fm-login-id');
        const pass = document.getElementById('fm-login-password');
        if (!user || !pass) return 'inputs_not_found';
        user.value = {json.dumps(username)};
        user.dispatchEvent(new Event('input', {{bubbles:true}}));
        pass.value = {json.dumps(password)};
        pass.dispatchEvent(new Event('input', {{bubbles:true}}));
        const btn = [...document.querySelectorAll('button,a,input[type=submit]')]
          .find(el => el.offsetParent && (el.innerText || '').trim() === '登录');
        if (btn) {{ btn.click(); return 'clicked'; }}
        return 'button_not_found';
    }})()''')
    print(f'  生意参谋登录表单: {result}')
    time.sleep(8)
    return not bool(get_page_ws('login.taobao.com'))


def login_bi(username, password):
    """自动登录BI页面"""
    print("  导航到BI登录页...")
    ws_url = get_page_ws("primeet.ecbis.cn")
    if not ws_url:
        print("  ✗ 未找到BI页面标签页")
        return False

    cdp_navigate(ws_url, BI_LOGIN_URL)
    time.sleep(5)

    # 检查是否已经登录
    current_url = cdp_evaluate(ws_url, "window.location.href")
    if current_url and 'login' not in current_url:
        print("  ✓ BI页面已登录（保持登录状态）")
        return True

    print("  输入账号密码...")
    js_code = f"""
    (function() {{
        const inputs = document.querySelectorAll('input');
        const accountInput = Array.from(inputs).find(i => i.placeholder === '请输入账号' && i.type === 'text');
        const passwordInput = Array.from(inputs).find(i => i.placeholder === '请输入密码' && i.type === 'password');
        const checkboxes = Array.from(inputs).filter(i => i.type === 'checkbox');
        
        if (accountInput) {{
            accountInput.focus();
            accountInput.value = {json.dumps(username)};
            accountInput.dispatchEvent(new Event('input', {{bubbles: true}}));
            accountInput.dispatchEvent(new Event('change', {{bubbles: true}}));
        }}
        if (passwordInput) {{
            passwordInput.focus();
            passwordInput.value = {json.dumps(password)};
            passwordInput.dispatchEvent(new Event('input', {{bubbles: true}}));
            passwordInput.dispatchEvent(new Event('change', {{bubbles: true}}));
        }}
        checkboxes.forEach(cb => {{ if (!cb.checked) cb.click(); }});
        
        // 点击登录按钮
        const allElements = document.querySelectorAll('*');
        for (const el of allElements) {{
            if (el.textContent.trim() === '登录' && el.children.length === 0) {{
                el.click();
                return '已点击登录按钮';
            }}
        }}
        return '未找到登录按钮';
    }})();
    """
    result = cdp_evaluate(ws_url, js_code)
    print(f"  {result}")

    time.sleep(8)

    # 检查登录结果
    current_url = cdp_evaluate(ws_url, "window.location.href")
    current_title = cdp_evaluate(ws_url, "document.title")
    print(f"  当前页面: {current_title}")
    print(f"  当前URL: {current_url}")

    if current_url and 'login' not in current_url:
        print("  ✓ BI页面登录成功！")
        return True
    else:
        print("  ✗ BI页面登录失败（可能需要验证码）")
        return False


def main():
    parser = argparse.ArgumentParser(description='自动登录BI页面并打开采集所需页面')
    parser.add_argument('--bi-username', default=DEFAULT_BI_USERNAME, help='BI页面账号')
    parser.add_argument('--bi-password', default=DEFAULT_BI_PASSWORD, help='BI页面密码（建议使用 BI_PASSWORD 环境变量）')
    parser.add_argument('--skip-bi-login', action='store_true', help='只打开采集页面，不执行BI登录')
    parser.add_argument('--sources', default='', help='仅准备指定的数据源，逗号分隔')
    args = parser.parse_args()
    sources = set(args.sources.split(',')) if args.sources else {'bi_daily', 'sycm_flow', 'wanxiangtai'}
    needs_bi = 'bi_daily' in sources and not args.skip_bi_login
    saved_username, saved_password = load_saved_credentials()
    if not args.bi_username:
        args.bi_username = saved_username
    if not args.bi_password:
        args.bi_password = saved_password

    print("=" * 60)
    print("  自动登录 & 页面准备")
    print("=" * 60)

    # 检查Chrome调试模式
    print("\n[1/4] 检查Chrome调试模式...")
    try:
        ensure_browser()
        urllib.request.urlopen(f"http://127.0.0.1:{CDP_PORT}/json/version", timeout=3)
        print("  ✓ Chrome调试模式运行中")
    except Exception as e:
        print(f"  ✗ Chrome调试模式未启动: {e}")
        return 1

    browser_ws = get_browser_ws()
    print(f"  Browser WebSocket: {browser_ws}")

    # 打开所有需要的页面
    print("\n[2/4] 打开采集所需页面...")

    # 生意参谋
    if any(source.startswith('sycm_') for source in sources) and not get_page_ws('sycm.taobao.com'):
        print("  打开生意参谋...")
        create_target(browser_ws, SYCM_URL)
        time.sleep(5)

    # BI页面仅在需要登录时打开；其他采集源不应依赖BI账号
    if needs_bi and not get_page_ws('primeet.ecbis.cn'):
        print("  打开BI页面...")
        create_target(browser_ws, BI_URL)
        time.sleep(3)

    # 万相台
    if 'wanxiangtai' in sources and not get_page_ws('one.alimama.com'):
        print("  打开万相台...")
        create_target(browser_ws, WANXIANGTAI_URL)
        time.sleep(5)

    # 列出所有页面
    print("\n[3/4] 当前所有页面:")
    with urllib.request.urlopen(f"http://127.0.0.1:{CDP_PORT}/json") as resp:
        tabs = json.loads(resp.read().decode())
    for tab in tabs:
        if tab.get('type') == 'page':
            print(f"  - {tab.get('title', '')[:50]}")
            print(f"    URL: {tab.get('url', '')[:70]}")

    # 自动登录BI页面
    print("\n[4/4] 自动登录BI页面...")
    login_success = True
    if needs_bi:
        bi_ws = get_page_ws('primeet.ecbis.cn')
        current_url = cdp_evaluate(bi_ws, 'window.location.href') if bi_ws else ''
        if not current_url or 'login' in current_url:
            if not args.bi_username or not args.bi_password:
                print('BI_LOGIN_REQUIRED: 请在账号配置中保存BI账号密码或登录采集专用浏览器')
                login_success = False
            else:
                login_success = login_bi(args.bi_username, args.bi_password)
    if any(source.startswith('sycm_') for source in sources):
        sycm_ws = get_page_ws('sycm.taobao.com')
        sycm_url = cdp_evaluate(sycm_ws, 'window.location.href') if sycm_ws else ''
        # SYCM keeps the shell at /custom/login.htm even after SSO; the
        # collector validates the actual cookies through CDP.
        if not sycm_ws:
            sycm_user, sycm_password = load_platform_credentials('sycm')
            if not sycm_user or not sycm_password:
                print('SYCM_LOGIN_REQUIRED: 生意参谋账号配置为空')
                login_success = False
            else:
                if not get_page_ws('login.taobao.com'):
                    create_target(
                        browser_ws,
                        'https://login.taobao.com/member/login.jhtml?redirectURL=https%3A%2F%2Fsycm.taobao.com%2F',
                    )
                    time.sleep(5)
                login_success = login_taobao_tab(sycm_user, sycm_password)
                if not login_success:
                    print('SYCM_LOGIN_REQUIRED: 登录需要验证码或人工确认')
    if 'wanxiangtai' in sources:
        from auto_login_wanxiangtai import main as login_wxt
        wxt_ok = login_wxt() == 0
        login_success = wxt_ok and login_success

    print("\n" + "=" * 60)
    if login_success:
        print("  ✓ 页面准备完成，可以开始采集")
        print("=" * 60)
        return 0
    else:
        print("  ⚠ 页面登录准备失败，请手动检查")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
