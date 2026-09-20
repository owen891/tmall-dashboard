"""查看采集专用 Chrome 当前持有的 taobao/sycm cookie（名称 + 过期时间 + 是否会话级）。

为什么不用读 Cookies 数据库：Chrome 运行时会独占该文件（WinError 32），
而采集器本来就是走 CDP 取 cookie 的，这里用同一通道（Storage.getCookies）
既能拿到权威结果，也顺带验证了「采集器的 cookie 通道是通的」。

用法: .venv\\Scripts\\python.exe scripts/inspect_chrome_cookies.py
"""
import json
import os
import sys
import time
import urllib.request
from datetime import datetime

CDP_PORT = int(os.environ.get('TMALL_CDP_PORT', '9223'))
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))

KEY_COOKIES = ('_tb_token_', 'cookie2', '_l_g_', 'sgcookie', 'unb', 'cna',
               't', '_nk_', 'lgc', 'tracknick', 'uc1', 'uc3', 'uc4',
               'csg', 'skt', 'existShop', 'xlly_s')


def browser_ws():
    info = json.loads(OPENER.open(
        'http://127.0.0.1:%d/json/version' % CDP_PORT, timeout=5).read())
    return info['webSocketDebuggerUrl']


def get_all_cookies():
    from websocket import create_connection
    ws = create_connection(browser_ws(), suppress_origin=True)
    ws.settimeout(20)
    try:
        # Chrome 111+ 支持浏览器级 Storage.getCookies
        ws.send(json.dumps({'id': 1, 'method': 'Storage.getCookies'}))
        while True:
            msg = json.loads(ws.recv())
            if msg.get('id') == 1:
                return msg.get('result', {}).get('cookies', [])
    finally:
        ws.close()
    return []


def main():
    try:
        cookies = get_all_cookies()
    except Exception as exc:  # noqa: BLE001
        print('CDP 取 cookie 失败: %s' % exc)
        return 2

    now = time.time()
    rows = [c for c in cookies
            if any(d in c.get('domain', '') for d in ('taobao', 'tmall', 'sycm'))]
    print('CDP 端口 %d，taobao/tmall/sycm 域 cookie 共 %d 个\n' % (CDP_PORT, len(rows)))

    alive = expired = session = 0
    key_missing = []
    for c in sorted(rows, key=lambda x: x['name']):
        exp = c.get('expires', -1)
        if exp in (-1, None):
            when, state = '会话级', 'session'
            session += 1
        else:
            dt = datetime.fromtimestamp(exp)
            if dt.timestamp() > now:
                when, state = dt.strftime('%Y-%m-%d %H:%M'), '有效'
                alive += 1
            else:
                when, state = dt.strftime('%Y-%m-%d %H:%M'), '已过期'
                expired += 1
        print('  %-26s %-16s 截止=%-17s %s' % (c['domain'], c['name'], when, state))

    names = {c['name'] for c in rows}
    key_missing = [n for n in KEY_COOKIES if n not in names]
    print('\n有效=%d 会话级=%d 已过期=%d' % (alive, session, expired))
    print('登录关键 cookie 缺失: %s' % (key_missing or '无'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
