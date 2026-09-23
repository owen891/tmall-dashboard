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
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = Path(os.environ.get('TMALL_DB_PATH', PROJECT_ROOT / 'data' / 'dashboard.db'))
DEFAULT_LOOKBACK_DAYS = 14


def main(argv=None):
    parser = argparse.ArgumentParser(description='Aggregate daily product facts into store daily facts.')
    parser.add_argument('--db', default=str(DEFAULT_DB))
    parser.add_argument('--lookback-days', type=int, default=DEFAULT_LOOKBACK_DAYS)
    parser.add_argument('--apply', action='store_true', help='Persist changes; default is preview only.')
    parser.add_argument('--backup-destination', help='Required with --apply: integrity-checked SQLite backup path')
    args = parser.parse_args(argv)
    if args.apply and not args.backup_destination:
        parser.error('--backup-destination is required with --apply')
    if args.lookback_days < 1:
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
    try:
        rows = connection.execute(
            f'''SELECT shop_id, date,
                       ROUND(SUM(payment_amount), 2) AS sales,
                       ROUND(SUM(refund_amount), 2) AS refund,
                       ROUND(SUM(ipv), 0) AS visitors,
                       ROUND(SUM(buyers), 0) AS buyers,
                       ROUND(SUM(returning_payment_buyers), 0) AS returning_buyers,
                       ROUND(SUM(ad_spend), 2) AS ad_spend
                FROM daily_data
                WHERE date >= date('now', '-{args.lookback_days} days')
                GROUP BY shop_id, date
                ORDER BY shop_id, date'''
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
