#!/usr/bin/env python3
"""Backfill store-day facts from product-day facts safely.

This replaces the old import-time one-off script. It is read-only by default;
writing requires ``--apply`` and an explicit integrity-checked backup path.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = Path(os.environ.get('TMALL_DB_PATH', PROJECT_ROOT / 'data' / 'dashboard.db'))
DEFAULT_SHOP_ID = os.environ.get('TMALL_SHOP_ID', os.environ.get('TMALL_LEGACY_SHOP_ID', 'default'))


def main(argv=None):
    parser = argparse.ArgumentParser(description='Backfill store daily facts from daily product facts.')
    parser.add_argument('--db', default=str(DEFAULT_DB))
    parser.add_argument('--shop-id', default=DEFAULT_SHOP_ID)
    parser.add_argument('--lookback-days', type=int, default=None)
    parser.add_argument('--apply', action='store_true', help='Persist changes; default is preview only.')
    parser.add_argument('--backup-destination', help='Required with --apply: integrity-checked SQLite backup path')
    args = parser.parse_args(argv)
    if args.apply and not args.backup_destination:
        parser.error('--backup-destination is required with --apply')
    if args.lookback_days is not None and args.lookback_days < 1:
        parser.error('--lookback-days must be positive')

    db_path = Path(args.db).resolve()
    backup = None
    if args.apply:
        from scripts.backup_database import backup_database

        backup = backup_database(db_path, args.backup_destination)
        if not backup['ok']:
            raise RuntimeError('database backup integrity check failed')

    connection = sqlite3.connect(db_path, timeout=300)
    connection.row_factory = sqlite3.Row
    connection.execute('PRAGMA busy_timeout=300000')
    # 2026-10-08：本脚本按日期做全表聚合，SQLite 默认 temp_store=FILE 会把中间
    # 结果写到系统临时目录；Temp 不可写（磁盘满/受限账户）时抛误导性的
    # "unable to open database file"。实测该查询在 Temp 不可写时必失败、
    # 加此 pragma 后正常返回。与 db.get_connection 保持一致。
    connection.execute('PRAGMA temp_store=MEMORY')
    try:
        where = ['shop_id = ?']
        params: list[object] = [args.shop_id]
        if args.lookback_days is not None:
            where.append("date >= date('now', ?)")
            params.append(f'-{args.lookback_days} days')
        rows = connection.execute(
            f'''SELECT date,
                       ROUND(SUM(COALESCE(payment_amount, 0)), 2) AS payment_amount,
                       ROUND(SUM(COALESCE(refund_amount, 0)), 2) AS refund_amount,
                       SUM(COALESCE(ipv, 0)) AS product_visitors,
                       SUM(COALESCE(buyers, 0)) AS payment_buyers,
                       SUM(COALESCE(returning_payment_buyers, 0)) AS returning_payment_buyers,
                       ROUND(SUM(COALESCE(ad_spend, 0)), 2) AS ad_spend
                FROM daily_data
                WHERE {' AND '.join(where)}
                GROUP BY date ORDER BY date''',
            params,
        ).fetchall()

        inserted = 0
        updated = 0
        for row in rows:
            existing = connection.execute(
                'SELECT 1 FROM store_daily_facts WHERE shop_id=? AND date=?',
                (args.shop_id, row['date']),
            ).fetchone()
            values = (
                row['payment_amount'], row['refund_amount'], row['product_visitors'],
                row['payment_buyers'], row['returning_payment_buyers'], row['ad_spend'],
                args.shop_id, row['date'],
            )
            if existing:
                updated += 1
                if args.apply:
                    connection.execute(
                        '''UPDATE store_daily_facts SET payment_amount=?,
                               successful_refund_amount=?, product_visitors=?, payment_buyers=?,
                               returning_payment_buyers=?, ad_spend=?, source_batch_id=?
                           WHERE shop_id=? AND date=?''',
                        (*values[:6], 'aggregated_from_daily_data', *values[6:]),
                    )
            else:
                inserted += 1
                if args.apply:
                    connection.execute(
                        '''INSERT INTO store_daily_facts
                           (shop_id, date, payment_amount, successful_refund_amount,
                            product_visitors, payment_buyers, returning_payment_buyers,
                            ad_spend, source_batch_id)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                        (args.shop_id, row['date'], row['payment_amount'], row['refund_amount'],
                         row['product_visitors'], row['payment_buyers'],
                         row['returning_payment_buyers'], row['ad_spend'],
                         'aggregated_from_daily_data'),
                    )
        if args.apply:
            connection.commit()
        else:
            connection.rollback()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

    print(json.dumps({
        'mode': 'apply' if args.apply else 'dry-run',
        'database': str(db_path),
        'shop_id': args.shop_id,
        'lookback_days': args.lookback_days,
        'source_group_count': len(rows),
        'would_insert': inserted,
        'would_update': updated,
        'backup': backup,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
