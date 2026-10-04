"""通过CDP关闭挂死的生意参谋页面并重新打开"""
import json, urllib.request, time, sys

# 1. 找到生意参谋页面
req = urllib.request.Request('http://127.0.0.1:9223/json')
tabs = json.loads(urllib.request.urlopen(req, timeout=10).read().decode())
sycm_tabs = [t for t in tabs if 'sycm.taobao.com' in t.get('url', '')]
print(f"找到 {len(sycm_tabs)} 个生意参谋页面")

import websocket

# 2. 关闭挂死的生意参谋页面
for tab in sycm_tabs:
    tab_id = tab['id']
    print(f"关闭页面: {tab_id}")
    # 用browser级WS关闭
    req = urllib.request.Request('http://127.0.0.1:9223/json/version')
    ver = json.loads(urllib.request.urlopen(req, timeout=10).read().decode())
    ws = websocket.create_connection(ver['webSocketDebuggerUrl'], suppress_origin=True, timeout=15)
    ws.send(json.dumps({"id": 1, "method": "Target.closeTarget", "params": {"targetId": tab_id}}))
    # 读取响应
    try:
        while True:
            msg = json.loads(ws.recv())
            if msg.get('id') == 1:
                print(f"  关闭结果: {msg.get('result', {}).get('success', False)}")
                break
    except Exception as e:
        print(f"  读取响应失败（页面可能已关闭）: {e}")
    ws.close()
    time.sleep(2)

# 3. 验证已关闭
time.sleep(2)
req = urllib.request.Request('http://127.0.0.1:9223/json')
tabs = json.loads(urllib.request.urlopen(req, timeout=10).read().decode())
sycm_left = [t for t in tabs if 'sycm.taobao.com' in t.get('url', '')]
print(f"剩余生意参谋页面: {len(sycm_left)}")

# 4. 重新打开生意参谋首页
print("重新打开生意参谋页面...")
req = urllib.request.Request('http://127.0.0.1:9223/json/version')
ver = json.loads(urllib.request.urlopen(req, timeout=10).read().decode())
ws = websocket.create_connection(ver['webSocketDebuggerUrl'], suppress_origin=True, timeout=15)
ws.send(json.dumps({
    "id": 2,
    "method": "Target.createTarget",
    "params": {"url": "https://sycm.taobao.com/portal/home.htm"}
}))
try:
    while True:
        msg = json.loads(ws.recv())
        if msg.get('id') == 2:
            new_id = msg.get('result', {}).get('targetId')
            print(f"新页面ID: {new_id}")
            break
except Exception as e:
    print(f"创建页面响应失败: {e}")
ws.close()

# 5. 等待页面加载，然后测试WS连通性
print("等待页面加载...")
time.sleep(10)

req = urllib.request.Request('http://127.0.0.1:9223/json')
tabs = json.loads(urllib.request.urlopen(req, timeout=10).read().decode())
sycm_new = [t for t in tabs if 'sycm.taobao.com' in t.get('url', '')]
print(f"生意参谋页面数: {len(sycm_new)}")
for t in sycm_new:
    print(f"  [{t.get('title','')[:40]}] {t.get('url','')[:80]}")

# 测试新页面WS
if sycm_new:
    import websocket as ws2
    try:
        w = ws2.create_connection(sycm_new[0]['webSocketDebuggerUrl'], suppress_origin=True, timeout=10)
        w.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {"expression": "document.title", "returnByValue": True}}))
        while True:
            msg = json.loads(w.recv())
            if msg.get('id') == 1:
                print(f"✓ 新页面WS正常, 标题: {msg.get('result', {}).get('result', {}).get('value', '')}")
                break
        w.close()
    except Exception as e:
        print(f"✗ 新页面WS测试失败: {e}")
