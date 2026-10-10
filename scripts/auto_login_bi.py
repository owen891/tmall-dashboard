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

# 独立脚本运行时保证能 import 项目内模块（services.credentials_crypto 等）
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from services.credentials_crypto import decrypt_password

# ==================== 配置 ====================
CDP_PORT = int(os.environ.get('TMALL_CDP_PORT', '9223'))
BI_URL = "https://primeet.ecbis.cn/workTable/workTableHome"
BI_LOGIN_URL = "https://primeet.ecbis.cn/login"
# collect_overview_daily.py / collect_overview_full.py 取数时要求浏览器里已打开
# URL 含 productOverview 的标签页，否则直接抛「未找到 productOverview 页面标签」。
# 登录脚本必须把这个页面准备好，日常自动采集才不会空跑。
BI_OVERVIEW_URL = "https://primeet.ecbis.cn/workTable/productOverview"
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
        return str(item.get('username') or '').strip(), decrypt_password(str(item.get('password') or ''))
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
        return str(item.get('username') or '').strip(), decrypt_password(str(item.get('password') or ''))
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


def get_taobao_cookies():
    """通过 CDP 取出 taobao/tmall/sycm 域下的 cookie 串。"""
    ws_url = get_page_ws('sycm.taobao.com') or get_page_ws('taobao.com')
    if not ws_url:
        return ''
    ws = websocket.create_connection(ws_url, suppress_origin=True)
    ws.settimeout(20)
    try:
        ws.send(json.dumps({"id": 1, "method": "Network.enable"}))
        ws.recv()
        ws.send(json.dumps({"id": 2, "method": "Network.getAllCookies"}))
        result = json.loads(ws.recv())
    finally:
        ws.close()
    cookies = result.get('result', {}).get('cookies', [])
    return "; ".join(
        f"{c['name']}={c['value']}"
        for c in cookies
        if any(d in c.get('domain', '') for d in ('taobao', 'tmall', 'sycm'))
    )


def sycm_session_valid():
    """真正验证生意参谋登录态。

    只看页面是否存在会误判：SSO 完成后 sycm 标签常驻在
    /custom/login.htm，页面在并不代表 cookie 有效；失效时接口返回
    {"code":5810,"msg":"You must login system first."}。
    """
    cookie_str = get_taobao_cookies()
    if not cookie_str:
        return False
    probe = (
        'https://sycm.taobao.com/flow/new/monitor/item/tops/rank.json'
        '?dateRange={d}%7C{d}&dateType=day&pageSize=1&page=1'
        '&order=desc&orderBy=uv&device=2&indexCode=uv'
        '&_={ts}&token=df5be3e45'
    ).format(d=time.strftime('%Y-%m-%d', time.localtime(time.time() - 86400)),
              ts=int(time.time() * 1000))
    req = urllib.request.Request(probe, headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://sycm.taobao.com/flow/monitor/itemsource',
        'Cookie': cookie_str,
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode('utf-8', 'replace'))
        return data.get('code') == 0
    except Exception:
        return False


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
    """Fill the shared Taobao login page used by SYCM, if it is present.

    历史坑（2026-09-20 实测）：光填账号密码点「登录」不会成功——
      1. 页面会先弹「服务协议及隐私保护」浮层，必须点【同意】；
      2. 下方「已阅读并同意以下协议」复选框默认未勾选，登录按钮点了也会被拦回。
    因此这里按「关弹窗 → 勾协议 → 填账号密码 → 点登录」的顺序处理，
    并在点击后回读页面状态（是否出现图片验证码）以便上层给出准确提示。
    """
    ws_url = get_page_ws('login.taobao.com')
    if not ws_url:
        return False
    result = cdp_evaluate(ws_url, f'''(function() {{
        const log = [];
        const visible = el => !!(el && el.offsetParent);
        const clickByText = (text) => {{
            const el = [...document.querySelectorAll('button,a,input[type=submit],span,div')]
              .filter(e => visible(e) && (e.innerText || e.value || '').trim() === text)
              .pop();
            if (el) {{ el.click(); return true; }}
            return false;
        }};

        // 1) 关掉「服务协议及隐私保护」浮层
        if (clickByText('同意')) log.push('agreement_dialog_clicked');

        // 2) 勾选协议复选框
        const cb = document.getElementById('fm-agreement-checkbox');
        if (cb && !cb.checked) {{ cb.click(); log.push('checkbox_checked'); }}

        // 3) 填写账号密码
        const user = document.getElementById('fm-login-id');
        const pass = document.getElementById('fm-login-password');
        if (!user || !pass) return 'inputs_not_found|' + log.join(',');
        user.focus();
        user.value = {json.dumps(username)};
        user.dispatchEvent(new Event('input', {{bubbles:true}}));
        user.dispatchEvent(new Event('change', {{bubbles:true}}));
        pass.focus();
        pass.value = {json.dumps(password)};
        pass.dispatchEvent(new Event('input', {{bubbles:true}}));
        pass.dispatchEvent(new Event('change', {{bubbles:true}}));

        // 4) 再确认一次协议（部分版本点击密码框后会重绘）
        const cb2 = document.getElementById('fm-agreement-checkbox');
        if (cb2 && !cb2.checked) {{ cb2.click(); log.push('checkbox_rechecked'); }}

        // 5) 提交
        if (clickByText('登录')) log.push('login_clicked');
        else log.push('login_button_missing');
        return log.join(',');
    }})()''')
    print(f'  生意参谋登录表单: {result}')
    time.sleep(10)

    # 回读：仍在登录页 → 看是否出现图片验证码 / 错误提示
    ws_url = get_page_ws('login.taobao.com')
    if not ws_url:
        return True
    state = cdp_evaluate(ws_url, '''(function() {
        const code = document.getElementById('fm-login-checkcode');
        const err = [...document.querySelectorAll('.login-error,.error-msg,[class*=error]')]
          .map(e => (e.innerText || '').trim()).filter(Boolean).slice(0, 3);
        return JSON.stringify({
            captcha: !!(code && code.offsetParent),
            error: err,
            text: (document.body.innerText || '').replace(/\\s+/g, ' ').slice(0, 200)
        });
    })()''')
    print(f'  登录页状态: {state}')
    
    # 解析是否需要人工操作
    try:
        state_data = json.loads(state) if state else {}
        need_manual = state_data.get('captcha', False)
    except:
        need_manual = False
    
    # 进一步检测滑块/iframe验证
    slider_check = cdp_evaluate(ws_url, '''(function() {
        var iframes = document.querySelectorAll('iframe');
        for (var i = 0; i < iframes.length; i++) {
            var src = iframes[i].src || '';
            if (src.indexOf('punish') >= 0 || src.indexOf('captcha') >= 0) return true;
        }
        if (document.querySelector('.nc_iconfont, .btn_slide, .nc-lang-cnt, [class*="slider"], [class*="captcha"]')) {
            return true;
        }
        return false;
    })()''')
    if slider_check:
        need_manual = True

    if need_manual:
        wait_seconds = int(os.environ.get('TMALL_SLIDER_WAIT_SECONDS', '600'))
        
        # 检查是否headless模式
        try:
            version_info = json.loads(urllib.request.urlopen(f'http://127.0.0.1:{CDP_PORT}/json/version', timeout=3).read())
            is_headless = 'HeadlessChrome' in version_info.get('User-Agent', '')
        except:
            is_headless = False

        print('\n' + '='*60)
        print('⚠️  生意参谋登录需要人工操作（验证码/滑块）')
        if is_headless:
            print('⚠️  当前Chrome为无头模式，正在自动切换为有头窗口...')
            subprocess.run(['taskkill', '/F', '/IM', 'chrome.exe', '/FI', f'COMMANDLINE eq *--remote-debugging-port={CDP_PORT}*'], 
                         capture_output=True, shell=True)
            time.sleep(3)
            chrome_path = os.environ.get('TMALL_CHROME_PATH', r'C:\Program Files\Google\Chrome\Application\chrome.exe')
            profile = os.environ.get('TMALL_CHROME_PROFILE') or str(
                Path(os.environ['LOCALAPPDATA']) / 'TmallDashboard/CollectorChrome')
            subprocess.Popen([
                chrome_path, f'--remote-debugging-port={CDP_PORT}',
                f'--remote-allow-origins=http://localhost:{CDP_PORT},http://127.0.0.1:{CDP_PORT}',
                f'--user-data-dir={profile}', '--no-first-run', '--no-default-browser-check',
                'https://sycm.taobao.com/'
            ])
            time.sleep(5)
            print('✅ 已弹出Chrome窗口，请在浏览器中完成生意参谋登录')
        else:
            print('请在Chrome窗口中完成生意参谋登录')
        print(f'[等待] 最多等待 {wait_seconds} 秒，每10秒检测一次登录状态...')
        print('='*60 + '\n')

        for i in range(wait_seconds // 10):
            time.sleep(10)
            if sycm_session_valid():
                elapsed = (i+1) * 10
                print(f'\n✅ [登录] 生意参谋登录成功！（耗时 {elapsed} 秒）')
                return True
            if (i+1) % 3 == 0:
                remaining = wait_seconds - (i+1)*10
                print(f'  仍在等待生意参谋登录... 剩余 {remaining} 秒')
        
        print('\n❌ [超时] 等待生意参谋人工登录超时')
        return False
    
    return False


def login_bi(username, password):
    """自动登录BI页面"""
    print("  导航到BI登录页...")
    ws_url = get_page_ws("primeet.ecbis.cn")
    if not ws_url:
        print("  ✗ 未找到BI页面标签页")
        return False

    def _bi_session_alive():
        """用字段目录接口验证会话，页面壳还在不代表会话没被顶掉。"""
        alive = cdp_evaluate(
            ws_url,
            "(async function(){ try { const r = await fetch("
            "'https://biprodapi.ecbis.cn/prod/base/getTableCustomView?tableKey=GoodsDataOverViewVo&showScmb=true',"
            "{credentials: 'include'}); return (await r.json()).code === 0; } catch(e) { return false; } })()",
            await_promise=True,
        )
        return bool(alive)

    def _wait_login_form(seconds=20):
        for _ in range(seconds):
            time.sleep(1)
            state = cdp_evaluate(
                ws_url,
                "(function(){ return {url: location.href,"
                " hasForm: !!Array.from(document.querySelectorAll('input'))"
                ".find(i => i.placeholder === '请输入账号')}})()",
            )
            if isinstance(state, dict) and state.get('hasForm'):
                return True
        return False

    cdp_navigate(ws_url, BI_LOGIN_URL)

    if not _wait_login_form():
        # 表单没出现：要么真已登录，要么跳转还没完成。
        current_url = cdp_evaluate(ws_url, "window.location.href")
        if current_url and 'login' not in current_url and _bi_session_alive():
            print("  ✓ BI页面已登录（保持登录状态）")
            return True
        # 会话已失效但页面停在旧地址：回登录页重等表单
        print("  会话已失效（接口校验不过），重新走登录流程...")
        cdp_navigate(ws_url, BI_LOGIN_URL)
        if not _wait_login_form():
            print("  ✗ 登录表单未出现，放弃自动登录")
            return False

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

    # 轮询等登录完成（SPA 跳转有延迟，固定 8 秒偶发误判）
    for _ in range(10):
        time.sleep(2)
        current_url = cdp_evaluate(ws_url, "window.location.href")
        if current_url and 'login' not in current_url:
            break

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
        if login_success and not get_page_ws('productOverview'):
            print("  打开BI商品总览页...")
            create_target(get_browser_ws(), BI_OVERVIEW_URL)
            time.sleep(5)
            if not get_page_ws('productOverview'):
                print("  ✗ BI商品总览页未打开，商品日度采集将失败")
                login_success = False
    if any(source.startswith('sycm_') for source in sources):
        sycm_ws = get_page_ws('sycm.taobao.com')
        # 页面常在 /custom/login.htm（SSO 外壳），页面存在 ≠ 会话有效；
        # 必须真实调一次接口确认，否则会带着过期 cookie 空跑且静默"成功"。
        sycm_ok = sycm_session_valid()
        print(f"  生意参谋会话: {'有效' if sycm_ok else '已失效'}")
        if not sycm_ws or not sycm_ok:
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
