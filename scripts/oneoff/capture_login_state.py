"""抓取淘宝/生意参谋登录页当前状态（文本 + 截图），用于判断卡点。

用法: .venv\\Scripts\\python.exe scripts\\capture_login_state.py
输出: logs/login_state_<ts>.png 与 logs/login_state_<ts>.txt
"""
import base64
import json
import os
import time
import urllib.request

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CDP_PORT = int(os.environ.get('TMALL_CDP_PORT', '9223'))
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def send(ws_url, method, params=None, timeout=25):
    from websocket import create_connection
    ws = create_connection(ws_url, suppress_origin=True)
    ws.settimeout(timeout)
    mid = int(time.time() * 1000) % 1000000
    ws.send(json.dumps({'id': mid, 'method': method, 'params': params or {}}))
    try:
        while True:
            msg = json.loads(ws.recv())
            if msg.get('id') == mid:
                return msg
    finally:
        ws.close()


def main():
    tabs = json.loads(OPENER.open('http://127.0.0.1:%d/json/list' % CDP_PORT, timeout=6).read())
    pages = [t for t in tabs if t.get('type') == 'page' and 'chrome://' not in t.get('url', '')]
    if not pages:
        print('no page tab')
        return 1

    ts = time.strftime('%Y%m%d_%H%M%S')
    log_dir = os.path.join(PROJECT_ROOT, 'logs')
    os.makedirs(log_dir, exist_ok=True)
    lines = []
    shots = []

    for idx, tab in enumerate(pages):
        url = tab.get('url', '')
        lines.append('=' * 70)
        lines.append('[tab %d] %s' % (idx, url[:150]))
        expr = ('JSON.stringify({'
                'title: document.title,'
                'url: location.href,'
                'text: (document.body ? document.body.innerText : "").replace(/\\s+/g," ").slice(0,600),'
                'iframes: [...document.querySelectorAll("iframe")].map(f=>f.src).slice(0,6),'
                'inputs: [...document.querySelectorAll("input")].map(i=>({id:i.id,ph:i.placeholder,type:i.type,vis:!!i.offsetParent})).slice(0,10)'
                '})')
        res = send(tab['webSocketDebuggerUrl'], 'Runtime.evaluate',
                   {'expression': expr, 'returnByValue': True})
        val = (res.get('result', {}) or {}).get('result', {}).get('value')
        lines.append(val or '(no value)')

        shot = send(tab['webSocketDebuggerUrl'], 'Page.captureScreenshot', {'format': 'png'})
        data = (shot.get('result', {}) or {}).get('data')
        if data:
            path = os.path.join(log_dir, 'login_state_%s_tab%d.png' % (ts, idx))
            with open(path, 'wb') as fh:
                fh.write(base64.b64decode(data))
            shots.append(path)
            lines.append('screenshot -> %s' % path)

    txt = os.path.join(log_dir, 'login_state_%s.txt' % ts)
    with open(txt, 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(lines))
    print('\n'.join(lines))
    print('\ntxt -> %s' % txt)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
