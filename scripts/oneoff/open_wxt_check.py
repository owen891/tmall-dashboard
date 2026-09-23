"""Open wanxiangtai tab and check login."""
import json
import time
import urllib.request

CDP_PORT = 9223

with urllib.request.urlopen(f"http://127.0.0.1:{CDP_PORT}/json") as f:
    tabs = json.loads(f.read())

wxt_tab = None
for t in tabs:
    if 'one.alimama.com' in t.get('url', '') and t.get('type') == 'page':
        wxt_tab = t
        break

if wxt_tab:
    print("已有万相台 tab:", wxt_tab['url'])
else:
    req = urllib.request.Request(
        f"http://127.0.0.1:{CDP_PORT}/json/new?https://one.alimama.com/index.html",
        method="PUT",
    )
    with urllib.request.urlopen(req) as f:
        wxt_tab = json.loads(f.read())
    print("新开万相台 tab")
    time.sleep(10)

import websocket
ws = websocket.create_connection(wxt_tab['webSocketDebuggerUrl'], timeout=20)
ws.send(json.dumps({
    "id": 1, "method": "Runtime.evaluate",
    "params": {"expression": "({url: location.href, title: document.title})", "returnByValue": True}
}))
while True:
    msg = json.loads(ws.recv())
    if msg.get('id') == 1:
        print("页面状态:", msg.get('result', {}).get('result', {}).get('value'))
        break
ws.close()
