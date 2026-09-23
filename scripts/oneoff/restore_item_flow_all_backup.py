"""把 belong=all（全程来源，含渠道层级树）的历史备份导回数据库。

背景：9-16 那批 level 0~3 的层级数据曾被当作「父子重复累加」删除，
但它同时是唯一带渠道层级树的批次 —— 前端的层级下钻要靠它。
farthest（第一次访问来源）只有扁平一层，两者互补，不是重复。

用法：
    .venv\\Scripts\\python.exe scripts\\restore_item_flow_all_backup.py --dry-run
    .venv\\Scripts\\python.exe scripts\\restore_item_flow_all_backup.py --apply

默认文件：data/sycm_item_flow_0916_belong_all_backup_20260920.json
apply 前会整库备份成 data/dashboard.db.bak_<时间戳>。
"""

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(PROJECT_ROOT, 'data', 'dashboard.db')
DEFAULT_JSON = os.path.join(PROJECT_ROOT, 'data',
                            'sycm_item_flow_0916_belong_all_backup_20260920.json')

COLUMNS = [
    'stat_date', 'item_id', 'channel_name', 'parent_channel', 'level', 'channel_type',
    'page_level', 'uv', 'pv', 'pay_amount', 'pay_buyer_count', 'pay_rate',
    'cart_buyer_count', 'collect_item_count', 'deal_buyer_count', 'pay_item_count',
    'new_uv', 'page_id', 'belong', 'raw_data', 'collect_count',
]
# 表上 UNIQUE(stat_date, item_id, channel_name, parent_channel) 不含 belong，
# 因此这里也必须按同一个键判冲突，避免静默覆盖别的口径。
CONFLICT_KEY = '(stat_date, item_id, channel_name, parent_channel)'


def load_rows(path):
    with open(path, encoding='utf-8') as fh:
        payload = json.load(fh)
    if isinstance(payload, dict):
        return payload.get('rows') or payload.get('data') or []
    return payload


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--json', default=DEFAULT_JSON)
    parser.add_argument('--belong', default='all')
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--backup-destination', help='Required with --apply: integrity-checked SQLite backup path')
    args = parser.parse_args()
    apply_changes = args.apply and not args.dry_run
    if apply_changes and not args.backup_destination:
        parser.error('--backup-destination is required with --apply')

    rows = load_rows(args.json)
    print('备份文件: %s' % os.path.basename(args.json))
    print('待导入行数: %s（belong=%s）' % (len(rows), args.belong))
    if not rows:
        return 1

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    dates = sorted({str(r.get('stat_date')) for r in rows})
    items = {str(r.get('item_id')) for r in rows}
    print('涉及日期: %s   商品数: %s' % (dates, len(items)))

    existing_same = cursor.execute(
        'SELECT belong, COUNT(*) FROM sycm_item_flow_source_daily '
        'WHERE stat_date IN (%s) GROUP BY belong'
        % ','.join('?' for _ in dates), dates).fetchall()
    print('库内同日期现有: %s' % (existing_same or '无'))

    conflicts = []
    for row in rows:
        hit = cursor.execute(
            'SELECT belong FROM sycm_item_flow_source_daily WHERE stat_date = ? AND item_id = ? '
            'AND channel_name = ? AND IFNULL(parent_channel, \'\') = ?',
            (row.get('stat_date'), str(row.get('item_id')), row.get('channel_name'),
             row.get('parent_channel') or '')).fetchone()
        if hit and hit[0] != args.belong:
            conflicts.append((row.get('stat_date'), row.get('item_id'),
                              row.get('channel_name'), hit[0]))
    if conflicts:
        print('\n发现 %s 条会覆盖其他口径的冲突（前 10 条）:' % len(conflicts))
        for item in conflicts[:10]:
            print('   %s' % (item,))
        print('建议先给表补上带 belong 的唯一约束再导入，避免覆盖。')
        conn.close()
        return 1
    print('冲突检查: 通过（不会覆盖其它 belong 的数据）')

    if not apply_changes:
        print('\n[dry-run] 未写入任何数据。加 --apply 执行。')
        conn.close()
        return 0

    conn.close()
    from scripts.backup_database import backup_database

    backup = backup_database(DB_PATH, args.backup_destination)
    if not backup['ok']:
        raise RuntimeError('database backup integrity check failed')
    print('已备份整库: %s' % os.path.basename(backup['destination']))

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    payload_rows = []
    for row in rows:
        payload_rows.append(tuple(
            json.dumps(row.get(col), ensure_ascii=False)
            if col == 'raw_data' else row.get(col) for col in COLUMNS))
    try:
        cursor.executemany(
            'INSERT OR REPLACE INTO sycm_item_flow_source_daily (%s) VALUES (%s)'
            % (', '.join(COLUMNS), ', '.join('?' for _ in COLUMNS)), payload_rows)
        integrity = conn.execute('PRAGMA integrity_check').fetchone()[0]
        if integrity != 'ok':
            raise RuntimeError('database integrity check failed before commit')
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    for date in dates:
        summary = cursor.execute(
            'SELECT belong, COUNT(*), ROUND(SUM(uv), 0) FROM sycm_item_flow_source_daily '
            'WHERE stat_date = ? GROUP BY belong ORDER BY belong', (date,)).fetchall()
        print('%s 导入后: %s' % (date, summary))
    conn.close()
    print('完成。')
    return 0


if __name__ == '__main__':
    sys.exit(main())
