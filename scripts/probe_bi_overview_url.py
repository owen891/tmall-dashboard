"""在 BI 工作台页面里找出「商品总览」的真实入口 URL。

用途：collect_overview_full.py / collect_overview_daily.py 都要求浏览器里
已打开 URL 含 productOverview 的标签页，但该 URL 在仓库里没有硬编码，
只能从 BI 工作台的菜单/链接里现场抓取。
"""
import json
import sys
import time
import urllib.request

from websocket import create_connection

CDP_PORT = int(__import__('os').environ.get('TMALL_CDP_PORT', '9223'))


def ws_for(host_key):
    tabs = json.loads(urllib.request.urlopen(f'http://127.0.0.1:{CDP_PORT}/json').read())
    for t in tabs:
        if t.get('type') == 'page' and host_key in t.get('url', ''):
            return t
    return None


def evaluate(ws, expr, await_promise=False):
    ws.send(json.dumps({
        'id': 1, 'method': 'Runtime.evaluate',
        'params': {'expression': expr, 'returnByValue': True, 'awaitPromise': await_promise},
    }))
    while True:
        resp = json.loads(ws.recv())
        if resp.get('id') == 1:
            r = resp.get('result', {}).get('result', {})
            return r.get('value') if isinstance(r, dict) else r


JS = r"""
(function () {
  const out = {hrefs: [], iframe_srcs: [], router_hint: []};
  const push = (arr, v) => { if (v && !arr.includes(v)) arr.push(v); };
  document.querySelectorAll('a[href]').forEach(a => {
    const h = a.getAttribute('href') || '';
    if (/overview|goods|product|item/i.test(h)) push(out.hrefs, h);
  });
  document.querySelectorAll('iframe').forEach(f => push(out.iframe_srcs, f.src));
  // SPA 路由痕迹
  const html = document.documentElement.innerHTML;
  const m = html.match(/[A-Za-z0-9_\-\/]*productOverview[A-Za-z0-9_\-\/\?=]*/gi) || [];
  m.slice(0, 10).forEach(x => push(out.router_hint, x));
  out.title = document.title;
  out.url = location.href;
  return out;
})()
"""


def main():
    tab = ws_for('primeet.ecbis.cn')
    if not tab:
        print('未找到 BI 标签页')
        return 1
    print('连接:', tab['url'][:100])
    ws = create_connection(tab['webSocketDebuggerUrl'])
    try:
        res = evaluate(ws, JS)
        if isinstance(res, str):
            try:
                res = json.loads(res)
            except Exception:
                pass
        print(json.dumps(res, ensure_ascii=False, indent=2)[:4000])
    finally:
        ws.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
