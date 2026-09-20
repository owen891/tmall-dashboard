"""验证单品流量来源「全程来源(belong=all)」的层级口径能否安全汇总（只读）。

背景：业务上需要三级渠道下钻，而层级树只存在于 belong=all 批次。
本脚本回答两个问题：
    1. 各 level 的 uv 是多少（父子层级是否重复累加）
    2. level 0（一级渠道）按商品汇总后，是否与商品日度(daily_data.ipv)同口径

用法：
    .venv\\Scripts\\python.exe scripts\\verify_flow_hierarchy.py [backup_json] [date]
"""

import collections
import json
import os
import sqlite3
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, 'data', 'dashboard.db')
DEFAULT_BACKUP = os.path.join(PROJECT_ROOT, 'data',
                              'sycm_item_flow_0916_belong_all_backup_20260920.json')


def load_rows(path):
    with open(path, encoding='utf-8') as fh:
        payload = json.load(fh)
    if isinstance(payload, dict):
        return payload.get('rows') or payload.get('data') or []
    return payload


def main():
    backup = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_BACKUP
    date = sys.argv[2] if len(sys.argv) > 2 else '2026-09-16'
    rows = load_rows(backup)
    print('备份: %s  行数=%s  日期参数=%s' % (os.path.basename(backup), len(rows), date))

    levels = collections.defaultdict(lambda: [0, 0])
    for row in rows:
        bucket = levels[row.get('level')]
        bucket[0] += row.get('uv') or 0
        bucket[1] += 1
    print('\n== 各 level 的 uv / 行数（父子重复，不能相加）==')
    for level in sorted(levels, key=lambda v: (v is None, v)):
        total, count = levels[level]
        print('  level=%s uv=%-10s rows=%s' % (level, total, count))

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    print('\n== 与商品日度(daily_data.ipv) 对比 ==')
    for level in (0, 1, 2):
        per_item = collections.defaultdict(int)
        for row in rows:
            if row.get('level') == level:
                per_item[str(row.get('item_id'))] += row.get('uv') or 0
        flow_total = ipv_total = matched = 0
        for item_id, uv in per_item.items():
            hit = cursor.execute(
                'SELECT ipv FROM daily_data WHERE date = ? AND CAST(product_id AS TEXT) = ?',
                (date, item_id)).fetchone()
            if not hit:
                continue
            flow_total += uv
            ipv_total += hit[0] or 0
            matched += 1
        ratio = flow_total / ipv_total if ipv_total else 0
        print('  level=%s 匹配商品=%s  flow_uv=%s  BI_ipv=%s  比值=%.3f'
              % (level, matched, flow_total, ipv_total, ratio))

    existing = cursor.execute(
        'SELECT belong, ROUND(SUM(uv), 0), COUNT(*) FROM sycm_item_flow_source_daily '
        'WHERE stat_date = ? GROUP BY belong', (date,)).fetchall()
    print('\n== 库内现存 %s ==' % date)
    for belong, uv_sum, count in existing:
        print('  belong=%-9s uv=%s rows=%s' % (belong, uv_sum, count))
    conn.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
