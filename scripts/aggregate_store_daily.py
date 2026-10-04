#!/usr/bin/env python3
"""Aggregate product-day facts into store-day facts safely.

The command is read-only by default. ``--apply`` requires an integrity-checked
SQLite online backup before any store summary row is changed.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
# 确保项目根目录在 sys.path 中，以便导入 scripts 包
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_DB = Path(os.environ.get('TMALL_DB_PATH', PROJECT_ROOT / 'data' / 'dashboard.db'))
DEFAULT_LOOKBACK_DAYS = 14

# 源侧聚合表达式：写入与「是否已同步」判定必须用同一段 SQL，否则两边口径漂移
# 会导致 --skip-if-current 永远认为不一致（或更糟：认为一致而漏更新）。
AGGREGATE_SOURCE_SQL = '''
    SELECT shop_id, date,
           ROUND(SUM(payment_amount), 2) AS sales,
           ROUND(SUM(refund_amount), 2) AS refund,
           ROUND(SUM(ipv), 0) AS visitors,
           ROUND(SUM(buyers), 0) AS buyers,
           ROUND(SUM(returning_payment_buyers), 0) AS returning_buyers,
           ROUND(SUM(ad_spend), 2) AS ad_spend
    FROM daily_data
    WHERE date >= date('now', '-{lookback_days} days')
    GROUP BY shop_id, date
    ORDER BY shop_id, date
'''

# 金额字段容差 0.01（ROUND 到分），计数字段容差 0.5（ROUND 到整数）。
# 用容差而非精确相等：SUM 的浮点累加顺序不同会带来 ULP 级差异。
_MONEY_KEYS = ('sales', 'refund', 'ad_spend')
_COUNT_KEYS = ('visitors', 'buyers', 'returning_buyers')
_FACT_COLUMNS = ('payment_amount', 'successful_refund_amount', 'product_visitors',
                 'payment_buyers', 'returning_payment_buyers', 'ad_spend')


def is_current(connection, lookback_days):
    """判断 store_daily_facts 是否已与 daily_data 在回看窗口内一致。

    一致 => 无需重新聚合（也无需付出一份全量备份的代价）。只比较回看窗口
    内的行；窗口外的历史不参与判断。
    """
    source = {}
    for row in connection.execute(
        AGGREGATE_SOURCE_SQL.format(lookback_days=lookback_days)
    ):
        source[(row['shop_id'], row['date'])] = (
            row['sales'], row['refund'] or 0, row['visitors'],
            row['buyers'], row['returning_buyers'], row['ad_spend'] or 0)

    stored = {}
    for row in connection.execute(
        f'''SELECT shop_id, date, {', '.join(_FACT_COLUMNS)}
            FROM store_daily_facts
            WHERE date >= date('now', '-{lookback_days} days')'''
    ):
        stored[(row['shop_id'], row['date'])] = tuple(
            row[column] for column in _FACT_COLUMNS)

    if set(source) != set(stored):
        return False

    for key, wanted in source.items():
        actual = stored[key]
        for index, column in enumerate(_FACT_COLUMNS):
            left, right = wanted[index], actual[index]
            if left is None and right is None:
                continue
            tolerance = 0.01 if column in (
                'payment_amount', 'successful_refund_amount', 'ad_spend') else 0.5
            if left is None or right is None or abs(left - right) > tolerance:
                return False
    return True


def main(argv=None):
    parser = argparse.ArgumentParser(description='Aggregate daily product facts into store daily facts.')
    parser.add_argument('--db', default=str(DEFAULT_DB))
    parser.add_argument('--lookback-days', type=int, default=DEFAULT_LOOKBACK_DAYS)
    parser.add_argument('--apply', action='store_true', help='Persist changes; default is preview only.')
    parser.add_argument('--backup-destination', help='Required with --apply: integrity-checked SQLite backup path')
    parser.add_argument('--skip-if-current', action='store_true',
                        help='Skip backup and writes when store_daily_facts already matches '
                             'daily_data inside the lookback window (idempotent schedulers)')
    args = parser.parse_args(argv)
    if args.apply and not args.backup_destination:
        parser.error('--backup-destination is required with --apply')
    if args.lookback_days < 1:
        parser.error('--lookback-days must be positive')

    db_path = Path(args.db).resolve()

    # 2026-10-02：聚合现在有两个入口（auto-collect.ps1 [5b] 与独立的
    # TmallDashboard-Aggregate-Daily 计划任务）。先跑的一方真正聚合，后跑的一方
    # 在这里直接跳过——否则每天会白白产生两份 2.9GB 的全量备份。
    if args.skip_if_current:
        probe = sqlite3.connect(db_path, timeout=300)
        probe.row_factory = sqlite3.Row
        probe.execute('PRAGMA busy_timeout=300000')
        try:
            current = is_current(probe, args.lookback_days)
        finally:
            probe.close()
        if current:
            print(json.dumps({
                'mode': 'skipped',
                'database': str(db_path),
                'lookback_days': args.lookback_days,
                'reason': 'store_daily_facts 已与 daily_data 一致，跳过备份与写入',
                'backup': None,
            }, ensure_ascii=False, indent=2))
            return 0

    backup = None
    if args.apply:
        from scripts.backup_database import backup_database

        backup = backup_database(db_path, args.backup_destination)
        if not backup['ok']:
            raise RuntimeError('database backup integrity check failed')

    connection = sqlite3.connect(db_path, timeout=300)
    connection.row_factory = sqlite3.Row
    connection.execute('PRAGMA busy_timeout=300000')
    try:
        rows = connection.execute(
            AGGREGATE_SOURCE_SQL.format(lookback_days=args.lookback_days)
        ).fetchall()

        inserted = 0
        updated = 0
        for row in rows:
            existing = connection.execute(
                'SELECT 1 FROM store_daily_facts WHERE shop_id=? AND date=?',
                (row['shop_id'], row['date']),
            ).fetchone()
            if existing:
                updated += 1
                if args.apply:
                    connection.execute(
                        '''UPDATE store_daily_facts SET
                               payment_amount=?, successful_refund_amount=?, product_visitors=?,
                               payment_buyers=?, returning_payment_buyers=?, ad_spend=?
                           WHERE shop_id=? AND date=?''',
                        (row['sales'], row['refund'] or 0, row['visitors'], row['buyers'],
                         row['returning_buyers'], row['ad_spend'], row['shop_id'], row['date']),
                    )
            else:
                inserted += 1
                if args.apply:
                    connection.execute(
                        '''INSERT INTO store_daily_facts
                           (shop_id, date, payment_amount, successful_refund_amount,
                            product_visitors, payment_buyers, returning_payment_buyers, ad_spend)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                        (row['shop_id'], row['date'], row['sales'], row['refund'] or 0,
                         row['visitors'], row['buyers'], row['returning_buyers'], row['ad_spend']),
                    )

        if args.apply:
            connection.commit()
        else:
            connection.rollback()

        latest = connection.execute(
            '''SELECT date, payment_amount, product_visitors, payment_buyers, ad_spend
               FROM store_daily_facts ORDER BY date DESC LIMIT 5'''
        ).fetchall()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

    print(json.dumps({
        'mode': 'apply' if args.apply else 'dry-run',
        'database': str(db_path),
        'lookback_days': args.lookback_days,
        'source_group_count': len(rows),
        'would_insert': inserted,
        'would_update': updated,
        'backup': backup,
        'latest': [dict(row) for row in latest],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
