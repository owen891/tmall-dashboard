"""验收单品流量来源接口（口径 / 范围 / 层级 / 商品维度对照）。

用法：
    .venv\\Scripts\\python.exe scripts\\verify_item_flow_api.py [item_id] [base_url]

注意：本机设置了 HTTP 代理，访问 127.0.0.1 必须显式禁用代理，
否则会拿到 502（PowerShell 的 Invoke-WebRequest 同样受影响）。
"""

import json
import sys
import urllib.request

ITEM_ID = sys.argv[1] if len(sys.argv) > 1 else '711021416206'
BASE = (sys.argv[2] if len(sys.argv) > 2 else 'http://127.0.0.1:5000').rstrip('/')
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def fetch(params):
    url = '%s/api/sycm/item-flow/summary?%s' % (BASE, params)
    try:
        with OPENER.open(url, timeout=20) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as exc:  # noqa: PERF203
        return {'ok': False, 'http': exc.code, 'body': exc.read().decode('utf-8', 'replace')[:300]}
    except Exception as exc:  # noqa: BLE001
        return {'ok': False, 'error': str(exc)}


def show(title, params, top=8):
    payload = fetch(params)
    print('\n== %s ==' % title)
    print('   %s' % params)
    if not payload.get('ok'):
        print('   FAILED: %s' % json.dumps(payload, ensure_ascii=False)[:400])
        return
    data = payload['data']
    days = data.get('data_days')
    print('   belong=%s 区间=%s ~ %s (%s 天)  渠道行=%s  levels=%s'
          % (data.get('belong'), data.get('start_date'), data.get('end_date'), days,
             len(data.get('channels') or []), data.get('levels')))
    product = data.get('product_totals') or {}
    channel = data.get('channel_totals') or {}
    print('   商品口径: 访客=%s 支付=%s 买家=%s (%s 天)'
          % (product.get('visitors'), product.get('payment_amount'),
             product.get('buyers'), product.get('days')))
    print('   渠道合计: 访客=%s 支付=%s 买家=%s'
          % (channel.get('uv'), channel.get('pay_amount'), channel.get('pay_buyer_count')))
    for row in (data.get('channels') or [])[:top]:
        print('      L%s parent=%-10s %-16s uv=%-6s pay=%-10s rate=%s'
              % (row.get('level'), (row.get('parent_channel') or '-')[:10],
                 (row.get('channel_name') or '')[:16], row.get('uv'),
                 row.get('pay_amount'), row.get('pay_rate')))


def main():
    show('全程来源 belong=all（9-16，唯一有层级树的一天）',
         'item_id=%s&belong=all&start=2026-09-16&end=2026-09-16' % ITEM_ID)
    show('第一次访问来源 belong=farthest（8-21 ~ 9-19 全范围）',
         'item_id=%s&belong=farthest&start=2026-08-21&end=2026-09-19' % ITEM_ID)
    show('默认调用（不带日期，取表内最新一天）', 'item_id=%s' % ITEM_ID, top=5)
    return 0


if __name__ == '__main__':
    sys.exit(main())
