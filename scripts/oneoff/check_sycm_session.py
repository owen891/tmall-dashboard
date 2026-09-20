"""检查采集专用 Chrome 的生意参谋登录态，必要时打开页面。

零依赖（只用标准库 + venv 的 websocket-client）。
输出一行结论：SESSION_OK / SESSION_INVALID / NO_SYCM_TAB / CDP_DOWN
"""
import json
import sys
import time
import urllib.request

sys.path.insert(0, __file__.rsplit('\\', 1)[0])
sys.path.insert(0, __file__.replace('\\', '/').rsplit('/', 1)[0])

CDP_PORT = 9223
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
TOKEN = 'df5be3e45'


def cdp(path):
    return json.loads(OPENER.open('http://127.0.0.1:%d%s' % (CDP_PORT, path), timeout=6).read())


def list_tabs():
    return [t for t in cdp('/json/list') if t.get('type') == 'page']


def get_cookies():
    from websocket import create_connection
    tabs = cdp('/json/list')
    page = next((t for t in tabs if 'sycm.taobao.com' in t.get('url', '')), None)
    if not page:
        page = next((t for t in tabs if 'taobao.com' in t.get('url', '')), None)
    if not page:
        return ''
    ws = create_connection(page['webSocketDebuggerUrl'], suppress_origin=True)
    try:
        ws.send(json.dumps({'id': 1, 'method': 'Network.enable'}))
        ws.recv()
        ws.send(json.dumps({'id': 2, 'method': 'Network.getAllCookies'}))
        cookies = json.loads(ws.recv()).get('result', {}).get('cookies', [])
    finally:
        ws.close()
    return '; '.join('%s=%s' % (c['name'], c['value']) for c in cookies
                     if any(d in c.get('domain', '') for d in ('taobao', 'tmall', 'sycm')))


def session_valid(cookie):
    if not cookie:
        return False, 'no cookie'
    day = time.strftime('%Y-%m-%d', time.localtime(time.time() - 86400))
    url = ('https://sycm.taobao.com/flow/new/monitor/item/tops/rank.json'
           '?dateRange={d}%7C{d}&dateType=day&pageSize=1&page=1&order=desc&orderBy=uv'
           '&device=2&indexCode=uv&_={ts}&token={tok}').format(
        d=day, ts=int(time.time() * 1000), tok=TOKEN)
    req = urllib.request.Request(url, headers={
        'User-Agent': UA,
        'Referer': 'https://sycm.taobao.com/flow/monitor/itemsource',
        'Cookie': cookie,
    })
    try:
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}),
            urllib.request.HTTPCookieProcessor())
        with opener.open(req, timeout=20) as resp:
            body = json.loads(resp.read().decode('utf-8', 'replace'))
        return body.get('code') == 0, json.dumps(body, ensure_ascii=False)[:200]
    except Exception as exc:
        return False, 'request error: %s' % exc


def main():
    try:
        cdp('/json/version')
    except Exception as exc:
        print('CDP_DOWN %s' % exc)
        return 2

    tabs = list_tabs()
    print('tabs=%d' % len(tabs))
    for t in tabs:
        print('   %s' % (t.get('url') or '')[:100])

    sycm_tab = next((t for t in tabs if 'sycm.taobao.com' in t.get('url', '')), None)
    if not sycm_tab:
        print('NO_SYCM_TAB（需要先用 sycm_url.txt 里的地址打开）')
        cookie = get_cookies()
        ok, detail = session_valid(cookie)
        print('cookie_len=%d 复用 taobao 域 cookie 探测: %s' % (len(cookie), detail))
        print('SESSION_OK' if ok else 'SESSION_INVALID')
        return 0 if ok else 1

    cookie = get_cookies()
    print('cookie_len=%d' % len(cookie))
    ok, detail = session_valid(cookie)
    print('probe: %s' % detail)
    print('SESSION_OK' if ok else 'SESSION_INVALID')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
