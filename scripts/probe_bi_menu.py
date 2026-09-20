"""在 BI 工作台页面上找出「商品总览」入口并点击进去。

背景：collect_overview_*.py 要求浏览器已打开 URL 含 productOverview 的标签页，
但该 URL 未硬编码、Chrome 历史里也没有。BI 是 SPA，只能现场点菜单进去。
先用 --probe 打印菜单文本，再用 --click 点击目标菜单。
"""
import argparse
import json
import os
import sys
import time
import urllib.request

from websocket import create_connection

CDP_PORT = int(os.environ.get('TMALL_CDP_PORT', '9223'))


def bi_tab():
    tabs = json.loads(urllib.request.urlopen(f'http://127.0.0.1:{CDP_PORT}/json').read())
    for t in tabs:
        if t.get('type') == 'page' and 'primeet.ecbis.cn' in t.get('url', ''):
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


PROBE_JS = r"""
(function () {
  const seen = [];
  const walk = (root) => {
    root.querySelectorAll('*').forEach(el => {
      if (el.children.length > 0) return;
      const txt = (el.textContent || '').trim();
      if (!txt || txt.length > 20) return;
      if (/总览|商品|分析|流量|榜单/.test(txt)) {
        seen.push({tag: el.tagName, text: txt, cls: (el.className || '').toString().slice(0, 60)});
      }
    });
  };
  walk(document);
  document.querySelectorAll('iframe').forEach(f => {
    try { walk(f.contentDocument); } catch (e) {}
  });
  return {url: location.href, title: document.title, candidates: seen.slice(0, 80)};
})()
"""

CLICK_JS = r"""
(function (label) {
  const norm = (s) => (s || '').replace(/\s+/g, '');
  const target = norm(label);
  const all = [];
  const collect = (root) => root.querySelectorAll('*');
  const tryClick = (el) => {
    const txt = norm(el.textContent);
    if (txt === target || (txt.includes(target) && txt.length <= target.length + 6)) {
      el.click();
      return txt;
    }
    return null;
  };
  let hit = null;
  for (const el of collect(document)) {
    if (el.children.length > 0) continue;
    hit = tryClick(el);
    if (hit) break;
  }
  document.querySelectorAll('iframe').forEach(f => {
    if (hit) return;
    try {
      for (const el of collect(f.contentDocument)) {
        if (el.children.length > 0) continue;
        hit = tryClick(el);
        if (hit) break;
      }
    } catch (e) {}
  });
  return hit;
})(%s)
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--probe', action='store_true')
    ap.add_argument('--click', default='')
    args = ap.parse_args()

    tab = bi_tab()
    if not tab:
        print('未找到 BI 标签页')
        return 1
    ws = create_connection(tab['webSocketDebuggerUrl'])
    try:
        if args.probe:
            res = evaluate(ws, PROBE_JS)
            if isinstance(res, str):
                res = json.loads(res)
            print('URL:', res.get('url'))
            print('标题:', res.get('title'))
            for c in res.get('candidates', []):
                print(f"  <{c['tag']}> {c['text']:<18} | {c['cls']}")
        if args.click:
            label = json.dumps(args.click, ensure_ascii=False)
            hit = evaluate(ws, CLICK_JS % label)
            print('点击命中:', hit)
            time.sleep(4)
            tabs = json.loads(urllib.request.urlopen(f'http://127.0.0.1:{CDP_PORT}/json').read())
            print('--- 当前页面 ---')
            for t in tabs:
                if t.get('type') == 'page':
                    print('  -', (t.get('title', '') or '')[:38], '|', (t.get('url', '') or '')[:95])
    finally:
        ws.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
