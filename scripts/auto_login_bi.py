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

# ==================== 配置 ====================
CDP_PORT = 9222
BI_URL = "https://primeet.ecbis.cn/workTable/workTableHome"
BI_LOGIN_URL = "https://primeet.ecbis.cn/login"
SYCM_URL = "https://sycm.taobao.com/"
WANXIANGTAI_URL = "https://one.alimama.com/"

# 凭据只能从环境变量或显式参数提供，禁止在源码中保留默认账号密码。
DEFAULT_BI_USERNAME = os.environ.get('BI_USERNAME', '')
DEFAULT_BI_PASSWORD = os.environ.get('BI_PASSWORD', '')


def get_browser_ws():
    """获取browser级别的WebSocket URL"""
    with urllib.request.urlopen(f"http://127.0.0.1:{CDP_PORT}/json/version") as resp:
        version = json.loads(resp.read().decode())
        return version['webSocketDebuggerUrl']


def create_target(browser_ws, url):
    """通过CDP创建新标签页"""
    ws = websocket.create_connection(browser_ws)
    ws.settimeout(10)
    msg_id = int(time.time() * 1000) % 1000000
    msg = {"id": msg_id, "method": "Target.createTarget", "params": {"url": url}}
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
    ws = websocket.create_connection(ws_url)
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
    ws = websocket.create_connection(ws_url)
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
            accountInput.value = '{username}';
            accountInput.dispatchEvent(new Event('input', {{bubbles: true}}));
            accountInput.dispatchEvent(new Event('change', {{bubbles: true}}));
        }}
        if (passwordInput) {{
            passwordInput.focus();
            passwordInput.value = '{password}';
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
    args = parser.parse_args()
    if not args.bi_username or not args.bi_password:
        parser.error('BI_USERNAME/BI_PASSWORD 环境变量或 --bi-username/--bi-password 参数必须提供')

    print("=" * 60)
    print("  自动登录 & 页面准备")
    print("=" * 60)

    # 检查Chrome调试模式
    print("\n[1/4] 检查Chrome调试模式...")
    try:
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
    print("  打开生意参谋...")
    create_target(browser_ws, SYCM_URL)
    time.sleep(3)

    # BI页面
    print("  打开BI页面...")
    create_target(browser_ws, BI_LOGIN_URL)
    time.sleep(3)

    # 万相台
    print("  打开万相台...")
    create_target(browser_ws, WANXIANGTAI_URL)
    time.sleep(3)

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
    login_success = login_bi(args.bi_username, args.bi_password)

    print("\n" + "=" * 60)
    if login_success:
        print("  ✓ 页面准备完成，可以开始采集")
        print("=" * 60)
        return 0
    else:
        print("  ⚠ BI页面登录失败，请手动检查")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
