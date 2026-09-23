"""Backfill daily_data 成本/利润 columns from bi_product_daily_raw.

Why this exists
---------------
The BI 「运营视窗」 interface returns 800+ fields per product-day, but the
collectors only mapped ~13-23 of them, so the cost / profit fields were written
into ``bi_product_daily_raw.raw_data`` and then dropped.  The collectors now map
them going forward; this script recovers the days that were already collected
before that fix.

pinyin → 中文 对照（口径：支付预估；商品成本=净货品成本(支付)）:
    netHpCost  = 净货品成本(支付)      saleCost   = 销售费用(支付预估)
    zdyFyAll   = 自定义费用            deliverCost= 发货费用(支付)
    otherCost  = 其他费用(支付)        ptCost     = 平台花费(账单)
    profit     = 利润(支付预估)        profitRate = 利润率(支付预估)

校验式（2026-09-14~19 六天逐商品回归，聚合误差 0.02%~0.06%）:
    利润(支付预估) = 净销售额(支付) − 销售费用 − 自定义费用
                     − 净货品成本 − 发货费用 − 其他费用

用法::

    python scripts/backfill_cost_from_bi_raw.py            # dry-run
    python scripts/backfill_cost_from_bi_raw.py --apply
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db import get_db_path, get_shop_id, init_db  # noqa: E402

# daily_data 列 -> BI raw_data 中的候选键（按优先级）
BI_RAW_COST_MAP: dict[str, tuple[str, ...]] = {
    'product_cost': ('netHpCost', 'jhpcb'),
    'sales_cost': ('saleCost', 'xshfZf'),
    'custom_cost': ('zdyFyAll',),
    'logistics_cost': ('deliverCost', 'fhfyZf'),
    'other_cost': ('otherCost', 'qtCost'),
    'platform_fee': ('ptCost',),
    'operating_profit': ('profit',),
    'profit_rate': ('profitRate',),
}
DEDUCTION_COLUMNS = ('sales_cost', 'custom_cost', 'product_cost', 'logistics_cost', 'other_cost')
MISSING_MARKERS = {'', '--', '-', 'nan', 'none', 'null', 'nat'}


def to_number(value) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(',', '').replace('¥', '').replace('￥', '')
    if text.lower() in MISSING_MARKERS:
        return None
    if text.endswith('%'):
        try:
            return float(text[:-1]) / 100
        except ValueError:
            return None
    try:
        return float(text)
    except ValueError:
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description='Backfill daily cost columns from BI raw payload.')
    parser.add_argument('--db', type=Path, default=Path(get_db_path()))
    parser.add_argument('--apply', action='store_true', help='Write changes (default is dry-run).')
    parser.add_argument('--dates', nargs='*', help='Limit to YYYY-MM-DD values.')
    parser.add_argument('--backup-destination', help='Required with --apply: integrity-checked SQLite backup path.')
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
    shop_id = get_shop_id()
    connection = sqlite3.connect(db_path, timeout=300)
    connection.row_factory = sqlite3.Row
    connection.execute('PRAGMA busy_timeout=300000')

    query = 'SELECT date, product_id, raw_data FROM bi_product_daily_raw'
    params: list[str] = []
    if args.dates:
        query += f' WHERE date IN ({",".join("?" for _ in args.dates)})'
        params = list(args.dates)
    rows = connection.execute(query, params).fetchall()

    filled = {column: 0 for column in BI_RAW_COST_MAP}
    derived = 0
    unmatched = 0
    updates: list[tuple] = []
    per_date: dict[str, list[int]] = {}
    for row in rows:
        payload = json.loads(row['raw_data'])
        values: dict[str, float | None] = {}
        for column, candidates in BI_RAW_COST_MAP.items():
            values[column] = None
            for key in candidates:
                if key in payload:
                    number = to_number(payload[key])
                    if number is not None:
                        values[column] = number
                        break
        # 利润缺失时用校验过的公式补，仅当净销售额与全部扣减项都有值。
        net_sales = to_number(payload.get('netGmv'))
        if values['operating_profit'] is None and net_sales is not None:
            if all(values[column] is not None for column in DEDUCTION_COLUMNS):
                values['operating_profit'] = net_sales - sum(values[column] for column in DEDUCTION_COLUMNS)
                values['profit_rate'] = (values['operating_profit'] / net_sales) if net_sales else None
                derived += 1
        if all(values[column] is None for column in BI_RAW_COST_MAP):
            unmatched += 1
            continue
        for column, value in values.items():
            if value is not None:
                filled[column] += 1
        stats = per_date.setdefault(row['date'], [0, 0])
        stats[0] += 1
        if values['operating_profit'] is not None:
            stats[1] += 1
        updates.append(tuple(values[column] for column in BI_RAW_COST_MAP)
                       + (shop_id, row['product_id'], row['date']))

    print(f'bi_product_daily_raw 行数: {len(rows)}   可回填: {len(updates)}   无成本字段: {unmatched}')
    print('各列命中:')
    for column, count in filled.items():
        print(f'  {column:<18} {count:>7}')
    print(f'其中利润由公式推导: {derived}')
    print('按日期:')
    for date in sorted(per_date):
        covered, with_profit = per_date[date]
        print(f'  {date}  可回填 {covered:>5} 行，其中含利润 {with_profit:>5} 行')

    if args.apply and updates:
        assignments = ', '.join(f'{column}=?' for column in BI_RAW_COST_MAP)
        connection.execute('BEGIN IMMEDIATE')
        try:
            for start in range(0, len(updates), 2000):
                connection.executemany(
                    f'UPDATE daily_data SET {assignments} WHERE shop_id=? AND product_id=? AND date=?',
                    updates[start:start + 2000],
                )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        print(f'已应用 {len(updates)} 行更新')

    check = connection.execute(
        f"""SELECT COUNT(*) AS rows, SUM(net_sales) AS net, SUM(sales_cost) AS sales,
                   SUM(custom_cost) AS custom, SUM(product_cost) AS product,
                   SUM(logistics_cost) AS logistics, SUM(other_cost) AS other,
                   SUM(operating_profit) AS profit
            FROM daily_data
            WHERE date >= '2026-09-14' AND operating_profit IS NOT NULL"""
    ).fetchone()
    if check and check['rows']:
        derived_total = (check['net'] or 0) - sum(check[key] or 0 for key in ('sales', 'custom', 'product', 'logistics', 'other'))
        print()
        print(f"复核 {check['rows']} 行（2026-09-14 起）:")
        print(f"  公式算得 {derived_total:,.2f}   库中合计 {check['profit']:,.2f}   差 {derived_total - (check['profit'] or 0):,.2f}")
    connection.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
