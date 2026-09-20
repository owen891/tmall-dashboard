"""探测生意参谋「单品流量来源」接口的原始返回结构（判断能否取到渠道层级）。

为什么需要它：库里只有 9-16 一天带层级树（level 0~3 + parent_channel），
而当前采集器写死了 belong=farthest 且只取 pageLevel，拿不到父子关系。
要把层级补进 sycm_item_flow_source_daily，必须先看清接口在 belong=all 时
到底返回树（带 children）还是扁平数组（要靠 pageId 推导父级）。

前置：Chrome 调试实例（默认 9223）在跑，且其中已登录生意参谋标签页。

用法：
    .venv\\Scripts\\python.exe scripts\\probe_item_flow_raw.py [item_id] [date]

输出：结构摘要 + 原始 JSON 落到 logs/probe_item_flow_raw_<时间戳>.json
"""

import json
import os
import sys
import time
import urllib.request

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CDP_PORT = os.environ.get('TMALL_CDP_PORT', '9223')
TOKEN = 'df5be3e45'
ITEM_ID = sys.argv[1] if len(sys.argv) > 1 else '711021416206'
DATE = sys.argv[2] if len(sys.argv) > 2 else '2026-09-16'

# 本地 CDP 必须绕过系统代理，否则会拿到 502
LOCAL_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
BROWSER_UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'


def get_cookies_from_cdp():
    with LOCAL_OPENER.open('http://127.0.0.1:%s/json' % CDP_PORT, timeout=5) as resp:
        tabs = json.loads(resp.read())
    page = next((t for t in tabs if 'sycm.taobao.com' in t.get('url', '')
                 and t.get('type') == 'page'), None)
    if not page:
        raise RuntimeError('SYCM_PAGE_REQUIRED: 请先在 Chrome(%s) 打开并登录生意参谋页面' % CDP_PORT)

    import websocket  # 项目 venv 已装（采集器同款依赖）
    ws = websocket.create_connection(page['webSocketDebuggerUrl'], suppress_origin=True)
    ws.send(json.dumps({'id': 1, 'method': 'Network.enable'}))
    ws.recv()
    ws.send(json.dumps({'id': 2, 'method': 'Network.getAllCookies'}))
    cookies = json.loads(ws.recv()).get('result', {}).get('cookies', [])
    ws.close()
    return '; '.join('%s=%s' % (c['name'], c['value']) for c in cookies
                     if any(d in c.get('domain', '') for d in ('taobao', 'tmall', 'sycm')))


def call(cookie, belong, item_id, date_str):
    date_range = '%s%%7C%s' % (date_str, date_str)
    url = ('https://sycm.taobao.com/flow/v6/item/crowdtype/source/v3.json'
           '?belong=%s&dateRange=%s&dateType=day&pageSize=50&page=1'
           '&order=desc&orderBy=uv&itemId=%s&device=2'
           '&indexCode=uv%%2Cpv%%2CpayAmt%%2CpayByrCnt%%2CpayRate'
           '&_=%d&token=%s' % (belong, date_range, item_id, int(time.time() * 1000), TOKEN))
    req = urllib.request.Request(url, headers={
        'User-Agent': BROWSER_UA,
        'Referer': 'https://sycm.taobao.com/cc/item_archives?itemId=%s&activeKey=flow' % item_id,
        'Cookie': cookie,
    })
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode('utf-8'))


def describe(payload, belong):
    print('\n===== belong=%s =====' % belong)
    print('code=%s message=%s' % (payload.get('code'), payload.get('message')))
    content = payload.get('content', payload.get('data'))
    print('content 类型=%s' % type(content).__name__)
    records = content.get('data') if isinstance(content, dict) else content
    if not isinstance(records, list) or not records:
        print('  无记录: %s' % json.dumps(payload, ensure_ascii=False)[:300])
        return
    print('记录数=%s' % len(records))
    first = records[0]
    print('首条字段: %s' % list(first.keys()))
    for key in ('pageName', 'pageLevel', 'pageId', 'channelType', 'parentPageId', 'parentPageName', 'children'):
        if key in first:
            value = first[key]
            if isinstance(value, dict):
                value = value.get('value')
            print('  %s = %s' % (key, json.dumps(value, ensure_ascii=False)[:160]))
    has_children = any(isinstance(r.get('children'), list) and r['children'] for r in records)
    print('是否返回树形(children): %s' % has_children)
    print('前 5 条的 pageName / pageLevel / pageId:')
    for row in records[:5]:
        name = row.get('pageName', {})
        level = row.get('pageLevel', {})
        page_id = row.get('pageId', {})
        print('   %-16s level=%-4s pageId=%s'
              % (name.get('value') if isinstance(name, dict) else name,
                 level.get('value') if isinstance(level, dict) else level,
                 page_id.get('value') if isinstance(page_id, dict) else page_id))


def main():
    cookie = get_cookies_from_cdp()
    print('cookie 长度=%s' % len(cookie))
    dumps = {}
    for belong in ('all', 'farthest'):
        payload = call(cookie, belong, ITEM_ID, DATE)
        describe(payload, belong)
        dumps[belong] = payload
    path = os.path.join(PROJECT_ROOT, 'logs',
                        'probe_item_flow_raw_%s.json' % time.strftime('%Y%m%d_%H%M%S'))
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump(dumps, fh, ensure_ascii=False, indent=2)
    print('\n原始返回已保存: %s' % path)
    return 0


if __name__ == '__main__':
    sys.exit(main())
