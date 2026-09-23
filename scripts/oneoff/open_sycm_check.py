"""Open sycm tab and check login status via CDP."""
import json
import time
import urllib.request

CDP_PORT = 9223

# List existing tabs
with urllib.request.urlopen(f"http://127.0.0.1:{CDP_PORT}/json") as f:
    tabs = json.loads(f.read())

sycm_tab = None
for t in tabs:
    if 'sycm.taobao.com' in t.get('url', ''):
        sycm_tab = t
        break

if sycm_tab:
    print("已有生意参谋 tab:", sycm_tab['url'])
else:
    # Open new tab to sycm (PUT method for newer Chrome)
    req = urllib.request.Request(
        f"http://127.0.0.1:{CDP_PORT}/json/new?https://sycm.taobao.com/portal/home.htm",
        method="PUT",
    )
    with urllib.request.urlopen(req) as f:
        new_tab = json.loads(f.read())
    print("新开生意参谋 tab:", new_tab['url'])
    time.sleep(10)
    sycm_tab = new_tab

# Check login: evaluate JS to see if we're on login page or portal
import websocket
ws = websocket.create_connection(sycm_tab['webSocketDebuggerUrl'], timeout=20)
mid = 1
ws.send(json.dumps({
    "id": mid,
    "method": "Runtime.evaluate",
    "params": {"expression": "({url: location.href, title: document.title, hasLoginBtn: !!document.querySelector('.login-btn, #J_Login, .sn-login')})", "returnByValue": True}
}))
while True:
    msg = json.loads(ws.recv())
    if msg.get('id') == mid:
        val = msg.get('result', {}).get('result', {}).get('value')
        print("页面状态:", val)
        break
ws.close()
