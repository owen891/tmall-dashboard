# -*- coding: utf-8 -*-
"""Backfill 成本/利润 columns on monthly_data from daily_data aggregation.

背景：2026-08/09 的数据经 paimi_bi_product_day（按天Excel/JSON）链路导入，
月度工作簿链路未运行，因此 monthly_source_payload 无这两个月的 payload，
backfill_monthly_cost_fields.py 无源可回填，monthly_data 的成本/利润列为空。
daily_data 的利润口径已对账验证（2026-08 标品袜子 operating_profit -2.30万
与 BI 支付预估一致），故从日事实聚合回填月度事实。

仅适用于日粒度完整覆盖的已结束月份；进行中月份禁止回填。
后续月份建议在 backfill_rolling.py 的月度任务中于次月 3 日运行本脚本。

用法::

    python scripts/backfill_monthly_profit_from_daily.py                    # dry-run
    python scripts/backfill_monthly_profit_from_daily.py --apply \
        --backup-destination data/backups/dashboard-<ts>-before-profit-backfill.db
"""
from __future__ import annotations

import argparse
import calendar
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db import get_db_path, init_db  # noqa: E402

# 聚合列：daily_data 列名 -> monthly_data 列名（口径与 backfill_monthly_cost_fields 一致）
AGG_SPECS = {
    'product_cost': 'product_cost',
    'sales_cost': 'sales_cost',
    'custom_cost': 'custom_cost',
    'logistics_cost': 'logistics_cost',
    'other_cost': 'other_cost',
    'platform_fee': 'platform_fee',
    'after_sales_loss': 'after_sales_loss',
    'gross_profit': 'gross_profit',
    'operating_profit': 'operating_profit',
}


def main() -> int:
    parser = argparse.ArgumentParser(description='Backfill monthly cost/profit from daily_data.')
    parser.add_argument('--db', type=Path, default=Path(get_db_path()))
    parser.add_argument('--apply', action='store_true', help='Write changes (default dry-run).')
    parser.add_argument('--months', nargs='*', default=['2026-08', '2026-09'],
                        help='已结束且日粒度完整的月份（默认 2026-08 2026-09）')
    parser.add_argument('--backup-destination', help='Required with --apply.')
    args = parser.parse_args()
    if args.apply and not args.backup_destination:
        parser.error('--backup-destination is required with --apply')

    db_path = args.db.resolve()
    if args.apply:
        from scripts.backup_database import backup_database
        backup = backup_database(db_path, args.backup_destination)
        if not backup['ok']:
            raise RuntimeError('database backup integrity check failed')
        init_db(str(db_path))

    conn = sqlite3.connect(db_path, timeout=300)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA busy_timeout=300000')

    agg_cols = ', '.join(f'SUM(d.{c}) AS {c}' for c in AGG_SPECS)
    today = conn.execute("SELECT date('now')").fetchone()[0]
    total_updates = 0

    for month in args.months:
        y, m = int(month[:4]), int(month[5:7])
        expected_days = calendar.monthrange(y, m)[1]
        days = conn.execute(
            'SELECT COUNT(DISTINCT date) FROM daily_data WHERE substr(date,1,7)=?',
            (month,)).fetchone()[0]
        if month >= today[:7]:
            print(f'{month}: 跳过（进行中月份，禁止回填）')
            continue
        if days < expected_days:
            print(f'{month}: 跳过（日粒度 {days}/{expected_days} 天不完整，月度利润以原月度导入为准）')
            continue

        rows = conn.execute(f"""
            SELECT d.product_id, {agg_cols}, COUNT(*) n_days
            FROM daily_data d
            WHERE substr(d.date,1,7) = :month
              AND d.product_id IN (SELECT product_id FROM monthly_data WHERE substr(month,1,7) = :month)
            GROUP BY d.product_id
        """, {'month': month}).fetchall()

        nulled = conn.execute(
            'SELECT COUNT(*) FROM monthly_data WHERE substr(month,1,7)=? AND operating_profit IS NULL',
            (month,)).fetchone()[0]
        agg_profit = sum(r[9] or 0 for r in rows)
        print(f'{month}: 日粒度 {days}/{expected_days} 天 | daily聚合商品 {len(rows)} | '
              f'monthly缺利润行 {nulled} | 聚合利润合计 {agg_profit:,.2f}')

        if args.apply and rows:
            assignments = ', '.join(f'{col}=?' for col in AGG_SPECS)
            conn.execute('BEGIN IMMEDIATE')
            try:
                updates = [tuple(r[c] for c in AGG_SPECS) + (r['product_id'], month) for r in rows]
                for i in range(0, len(updates), 2000):
                    chunk = updates[i:i + 2000]
                    conn.executemany(
                        f'UPDATE monthly_data SET {assignments} WHERE product_id=? AND month=?',
                        chunk)
                conn.commit()
                total_updates += len(updates)
            except Exception:
                conn.rollback()
                raise

    if args.apply:
        print(f'已应用 {total_updates} 行月度成本/利润回填')

    # 口径复核：与 backfill_monthly_cost_fields 相同的公式交叉验证
    check = conn.execute("""
        SELECT COUNT(*) AS rows, SUM(net_sales) AS net, SUM(sales_cost) AS sales,
               SUM(custom_cost) AS custom, SUM(product_cost) AS product,
               SUM(logistics_cost) AS logistics, SUM(other_cost) AS other,
               SUM(operating_profit) AS profit
        FROM monthly_data WHERE operating_profit IS NOT NULL""").fetchone()
    if check and check['rows']:
        derived = (check['net'] or 0) - sum(
            check[k] or 0 for k in ('sales', 'custom', 'product', 'logistics', 'other'))
        print()
        print(f"复核 {check['rows']} 行有利润的月度数据:")
        print(f"  公式算得 {derived:,.2f}   库中合计 {check['profit']:,.2f}   差 {derived - (check['profit'] or 0):,.2f}")
    remaining = conn.execute(
        'SELECT COUNT(*) FROM monthly_data WHERE operating_profit IS NULL').fetchone()[0]
    print(f'仍无利润的 monthly_data 行: {remaining}')
    conn.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
