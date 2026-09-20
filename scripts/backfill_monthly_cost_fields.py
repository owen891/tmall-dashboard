"""Backfill 成本/利润 columns on monthly_data from monthly_source_payload.

The monthly 商品总览 workbooks were always imported with their full Chinese
column set stored verbatim in ``monthly_source_payload.payload_json``, but the
``monthly_data`` fact table never received the cost / profit columns.  This
script maps those already-imported payload fields onto the new columns without
re-importing the workbooks.

口径（与 daily_data 完全一致，便于日/月口径对齐）：
    利润(支付预估) = 净销售额(支付) − 销售费用(支付预估) − 自定义费用
                     − 净货品成本(支付) − 发货费用(支付) − 其他费用(支付)

用法::

    python scripts/backfill_monthly_cost_fields.py            # dry-run
    python scripts/backfill_monthly_cost_fields.py --apply
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

from db import get_db_path, init_db  # noqa: E402

# 目标列 -> payload 中的中文列名（按优先级）
MONTHLY_COST_SPECS: dict[str, tuple[str, ...]] = {
    'net_sales': ('净销售额(支付)',),
    'product_cost': ('净货品成本(支付)', '普通单净货品成本(支付)', '净货品成本(发货)'),
    'sales_cost': ('销售费用(支付预估)', '销售费用(发货预估)', '销售费用(账单)'),
    'custom_cost': ('自定义费用',),
    'logistics_cost': ('发货费用(支付)', '普通单发货费用(支付)', '发货费用(发货)'),
    'other_cost': ('其他费用(支付)', '其他费用(发货)'),
    'platform_fee': ('平台花费(账单)', '平台花费(支付预估)', '天猫佣金(发货)'),
    'after_sales_loss': ('退款货品成本', '普通单退款货品成本'),
    'gross_profit': ('销售毛利(支付)', '预估销售毛利(支付)'),
    'operating_profit': ('利润(支付预估)',),
    'profit_rate': ('利润率(支付预估)',),
    'profit_target': ('利润目标',),
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


def pick(payload: dict, aliases: tuple[str, ...]) -> float | None:
    for alias in aliases:
        if alias in payload:
            number = to_number(payload[alias])
            if number is not None:
                return number
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description='Backfill monthly cost/profit columns.')
    parser.add_argument('--db', type=Path, default=Path(get_db_path()))
    parser.add_argument('--apply', action='store_true', help='Write changes (default is dry-run).')
    parser.add_argument('--months', nargs='*', help='Limit to YYYY-MM values.')
    args = parser.parse_args()

    db_path = args.db.resolve()
    init_db(str(db_path))
    connection = sqlite3.connect(db_path, timeout=300)
    connection.row_factory = sqlite3.Row
    connection.execute('PRAGMA busy_timeout=300000')

    query = 'SELECT product_id, month, payload_json FROM monthly_source_payload'
    params: list[str] = []
    if args.months:
        query += f' WHERE month IN ({",".join("?" for _ in args.months)})'
        params = list(args.months)
    rows = connection.execute(query, params).fetchall()

    filled = {column: 0 for column in MONTHLY_COST_SPECS}
    missing_target = 0
    updates: list[tuple] = []
    for row in rows:
        payload = json.loads(row['payload_json'])
        values = {column: pick(payload, aliases) for column, aliases in MONTHLY_COST_SPECS.items()}
        for column, value in values.items():
            if value is not None:
                filled[column] += 1
        # 利润缺失时用校验过的公式补，仅当全部扣减项都有值。
        if values['operating_profit'] is None and values['net_sales'] is not None:
            if all(values[column] is not None for column in DEDUCTION_COLUMNS):
                values['operating_profit'] = values['net_sales'] - sum(values[column] for column in DEDUCTION_COLUMNS)
                values['profit_rate'] = (values['operating_profit'] / values['net_sales']) if values['net_sales'] else None
        updates.append(tuple(
            values[column] for column in MONTHLY_COST_SPECS
        ) + (row['product_id'], row['month']))

    total = len(rows)
    print(f'payload 行数: {total}   月份: {sorted({row["month"] for row in rows})[:3]}...')
    print('各列命中:')
    for column, count in filled.items():
        print(f'  {column:<18} {count:>7}/{total}')

    if args.apply and updates:
        assignments = ', '.join(f'{column}=?' for column in MONTHLY_COST_SPECS)
        connection.execute('BEGIN IMMEDIATE')
        try:
            # 只更新已存在的 monthly_data 行；缺失行由原月度导入负责。
            for chunk_start in range(0, len(updates), 2000):
                chunk = updates[chunk_start:chunk_start + 2000]
                connection.executemany(
                    f'UPDATE monthly_data SET {assignments} WHERE product_id=? AND month=?',
                    chunk,
                )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        print(f'已应用 {len(updates)} 行更新')

    # 口径复核：利润 = 净销售额 − 各项扣减
    check = connection.execute(
        f"""SELECT COUNT(*) AS rows, SUM(net_sales) AS net, SUM(sales_cost) AS sales,
                   SUM(custom_cost) AS custom, SUM(product_cost) AS product,
                   SUM(logistics_cost) AS logistics, SUM(other_cost) AS other,
                   SUM(operating_profit) AS profit
            FROM monthly_data WHERE operating_profit IS NOT NULL"""
    ).fetchone()
    if check and check['rows']:
        derived = (check['net'] or 0) - sum(check[key] or 0 for key in ('sales', 'custom', 'product', 'logistics', 'other'))
        print()
        print(f"复核 {check['rows']} 行有利润的月度数据:")
        print(f"  公式算得 {derived:,.2f}   库中合计 {check['profit']:,.2f}   差 {derived - (check['profit'] or 0):,.2f}")

    missing_target = connection.execute(
        'SELECT COUNT(*) FROM monthly_data WHERE operating_profit IS NULL'
    ).fetchone()[0]
    print(f'仍无利润的 monthly_data 行: {missing_target}')
    connection.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
