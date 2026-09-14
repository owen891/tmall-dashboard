# -*- coding: utf-8 -*-
"""Import the BI 商品标签 (product label) from monthly payloads AND daily workbooks
into products.shop_label.

Each product keeps the label of its latest non-empty observation (daily beats monthly,
newer date beats older). Labels like 标品袜子 / 非标袜子女 / 专业运动系列 / 儿童袜 power
the global category mode on the dashboard.
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from typing import Any

from openpyxl import load_workbook

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = PROJECT_ROOT / 'data' / 'dashboard.db'

LABEL_KEY = '商品标签'
DAILY_FILENAME_DATE = re.compile(r'_(\d{4})-(\d{2})-(\d{2})\.xlsx$', re.IGNORECASE)


def _clean_label(value: Any) -> str:
    if value is None:
        return ''
    label = str(value).strip()
    if label.lower() in {'nan', 'none', 'null'}:
        return ''
    return label


def _row_label(row: Any) -> str:
    if isinstance(row, dict):
        return _clean_label(row.get(LABEL_KEY))
    if isinstance(row, (list, tuple)):
        for item in row:
            if isinstance(item, dict) and item.get(LABEL_KEY):
                return _clean_label(item.get(LABEL_KEY))
    return ''


def _parse_month(month: str) -> date:
    try:
        return datetime.strptime(month, '%Y-%m').date()
    except ValueError:
        return date(1970, 1, 1)


def load_monthly_labels(connection: sqlite3.Connection) -> dict[str, tuple[date, str]]:
    """product_id -> (sort_date, label) from monthly payloads."""
    out: dict[str, tuple[date, str]] = {}
    rows = connection.execute(
        "SELECT product_id, month, payload_json FROM monthly_source_payload"
    ).fetchall()
    for product_id, month, payload_json in rows:
        if not product_id or not payload_json:
            continue
        if isinstance(payload_json, str):
            try:
                payload = json.loads(payload_json)
            except (ValueError, TypeError):
                continue
        else:
            payload = payload_json
        label = _row_label(payload)
        if not label:
            continue
        sort_date = _parse_month(month)
        prev = out.get(product_id)
        if prev is None or sort_date > prev[0]:
            out[product_id] = (sort_date, label)
    return out


def load_daily_labels(source_dirs: list[Path]) -> dict[str, tuple[date, str]]:
    """product_id -> (sort_date, label) from daily BI workbooks (col 商品标签)."""
    out: dict[str, tuple[date, str]] = {}
    if not source_dirs:
        return out
    seen_files = 0
    for source_dir in source_dirs:
        if not source_dir.is_dir():
            print(f'  [跳过] 目录不存在: {source_dir}')
            continue
        for xlsx in sorted(source_dir.glob('*.xlsx')):
            m = DAILY_FILENAME_DATE.search(xlsx.name)
            if not m:
                continue
            sort_date = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            wb = load_workbook(xlsx, read_only=True)
            try:
                ws = wb[wb.sheetnames[0]]
                for row in ws.iter_rows(min_row=2, values_only=True):
                    if not row or row[0] is None:
                        continue
                    product_id = str(row[0]).strip()
                    if not product_id:
                        continue
                    label = _clean_label(row[3]) if len(row) > 3 else ''
                    if not label:
                        continue
                    prev = out.get(product_id)
                    if prev is None or sort_date > prev[0]:
                        out[product_id] = (sort_date, label)
            finally:
                wb.close()
            seen_files += 1
    print(f'  已扫描日度文件: {seen_files}')
    return out


def apply_labels(connection: sqlite3.Connection, label_map: dict[str, str]) -> tuple[int, Counter]:
    cursor = connection.cursor()
    updated = 0
    distribution: Counter = Counter()
    for product_id, label in label_map.items():
        cursor.execute("UPDATE products SET shop_label = ? WHERE product_id = ?", (label, product_id))
        if cursor.rowcount > 0:
            updated += 1
            distribution[label] += 1
    return updated, distribution


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', default=str(DEFAULT_DB), help='SQLite database path')
    parser.add_argument('--dry-run', action='store_true', help='report without writing')
    parser.add_argument('--daily-sources', nargs='*', default=[], help='daily BI source dirs to merge labels from')
    args = parser.parse_args()

    connection = sqlite3.connect(args.db)
    connection.row_factory = sqlite3.Row
    try:
        monthly = load_monthly_labels(connection)
        daily = load_daily_labels([Path(d) for d in args.daily_sources]) if args.daily_sources else {}

        merged: dict[str, tuple[date, str]] = dict(monthly)
        for product_id, (sort_date, label) in daily.items():
            prev = merged.get(product_id)
            if prev is None or sort_date > prev[0]:
                merged[product_id] = (sort_date, label)

        label_map = {pid: label for pid, (_dt, label) in merged.items()}
        print(f'月度来源商品数: {len(monthly)}, 日度来源商品数: {len(daily)}, 合并去重: {len(label_map)}')

        total_products = connection.execute('SELECT COUNT(*) AS c FROM products').fetchone()['c']
        print(f'products 表商品数: {total_products}')

        if args.dry_run:
            dist = Counter(label_map.values())
            print('DRY RUN - 不写入')
        else:
            updated, dist = apply_labels(connection, label_map)
            connection.commit()
            print(f'已更新商品数: {updated}')

        print('== 标签分布 ==')
        for label, count in dist.most_common():
            print(f'  {label or "(空)"}: {count}')

        labeled = sum(count for label, count in dist.items() if label)
        print(f'== 摘要: 有标签商品 {labeled} / {total_products}, 未打标 {total_products - labeled} ==')
    finally:
        connection.close()


if __name__ == '__main__':
    main()
