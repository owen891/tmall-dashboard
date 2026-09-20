"""检视单品流量来源备份 JSON 的结构（只读）。

用来确认生意参谋「全程来源(belong=all)」报表到底提供几层渠道、
raw_data 里有没有父子关系字段。

用法：
    .venv\\Scripts\\python.exe scripts\\inspect_item_flow_backup.py <json_path>
"""

import collections
import json
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_PATH = os.path.join(PROJECT_ROOT, 'data',
                            'sycm_item_flow_0916_belong_all_backup_20260920.json')


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PATH
    with open(path, encoding='utf-8') as fh:
        payload = json.load(fh)

    if isinstance(payload, dict):
        print('顶层是 dict，keys=%s' % list(payload.keys())[:20])
        rows = payload.get('rows') or payload.get('data') or []
    else:
        rows = payload
    print('文件: %s' % os.path.basename(path))
    print('行数: %s' % len(rows))
    if not rows:
        return 0

    print('行字段: %s' % list(rows[0].keys()))
    print('样例: %s' % json.dumps(rows[0], ensure_ascii=False)[:600])

    for key in ('belong', 'level', 'page_level', 'channel_type'):
        counter = collections.Counter(str(r.get(key)) for r in rows)
        print('%s 分布: %s' % (key, dict(counter.most_common(10))))

    items = {str(r.get('item_id')) for r in rows}
    print('商品数=%s 平均行/商品=%.1f' % (len(items), len(rows) / max(1, len(items))))

    names = collections.Counter(r.get('channel_name') for r in rows)
    print('渠道名种类=%s' % len(names))
    for name, count in names.most_common(20):
        print('   %-24s %s' % (name, count))

    raw = rows[0].get('raw_data')
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError:
            raw = None
    if isinstance(raw, dict):
        print('raw_data 字段: %s' % list(raw.keys()))

    for level in sorted({r.get('level') for r in rows}, key=lambda v: (v is None, v)):
        subset = [r for r in rows if r.get('level') == level]
        parents = collections.Counter(r.get('parent_channel') for r in subset)
        print('level=%s 行数=%s parent分布=%s' % (level, len(subset), dict(parents.most_common(5))))
        for row in subset[:6]:
            print('     %-24s parent=%-12s type=%s page_id=%s'
                  % (row.get('channel_name'), row.get('parent_channel'),
                     row.get('channel_type'), row.get('page_id')))
    return 0


if __name__ == '__main__':
    sys.exit(main())
