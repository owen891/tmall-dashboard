from __future__ import annotations

"""Import dated Primeet BI 商品总览 workbooks as product-day facts.

The source filenames carry an exact reporting day (``..._YYYY-MM-DD.xlsx``).
They must be imported into the daily fact pipeline rather than monthly_data;
otherwise multiple files from one month would overwrite one another.

Only the dashboard's standardized daily fields are materialized.  The original
source workbooks remain local and are never copied into the repository.
"""

import argparse
import hashlib
import json
import re
import sqlite3
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db import get_db_path, init_db  # noqa: E402
from services.source_resolution_service import record_daily_observation  # noqa: E402
from scripts.import_paimi_bi_overview import (  # noqa: E402
    clean_text,
    file_hash,
    first_value,
    numeric,
    source_rows,
)

DEFAULT_SOURCE = Path(r'E:\派米\8月数据源-bi')
SOURCE_TYPE = 'paimi_bi_product_day'
SOURCE_SYSTEM = 'business_advisor'

# The workbook contains hundreds of BI columns.  These are the fields that map
# exactly to the daily dashboard contract; the rest are intentionally left in
# the source workbook and are not fabricated into dashboard metrics.
DAILY_SPECS: dict[str, tuple[str, ...]] = {
    'payment_amount': ('支付金额(支付)',),
    'successful_refund_amount': ('普通单退款金额', '退款金额', '确认退款金额'),
    'net_sales': ('净销售额(支付)',),
    'payment_items': ('销售件数(支付)',),
    'product_visitors': ('访客数',),
    'page_views': ('浏览量', '商品浏览量'),
    'payment_conversion': ('支付转化率', '真实支付转化率'),
    'favorite_cart_rate': ('加购率',),
    'payment_buyers': ('支付人数',),
    'payment_unit_price': ('真实客单价', '实际客单价', '客单价'),
    'uv_value': ('访客价值',),
    'cart_items': ('加购件数',),
    'favorite_users': ('收藏人数',),
    'cart_users': ('加购人数',),
    'search_visitors': ('搜索访客数',),
    'search_conversion': ('搜索转化率',),
    'ad_spend': ('推广花费(账单)',),
    'ad_roi': ('推广ROI(账单)', '推广投产(账单)', '推广ROI'),
    'repurchase_rate': ('复购率',),
}


def date_from_file(path: Path) -> str:
    match = re.search(r'(20\d{2}-\d{2}-\d{2})(?:\.xlsx)?$', path.name)
    if not match:
        raise ValueError(f'无法从文件名识别日度日期: {path.name}')
    return match.group(1)


def source_value(payload: dict[str, Any], aliases: tuple[str, ...]) -> float | None:
    value = first_value(payload, aliases)
    return numeric(value) if value is not None else None


def observation_from_payload(product_id: str, stat_date: str, payload: dict[str, Any]) -> dict[str, Any]:
    observation: dict[str, Any] = {'product_id': product_id, 'date': stat_date}
    for field_key, aliases in DAILY_SPECS.items():
        value = source_value(payload, aliases)
        if value is not None:
            observation[field_key] = value
    return observation


def product_values(product_id: str, payload: dict[str, Any]) -> tuple[str, str, str, str, str, str]:
    return (
        product_id,
        clean_text(payload.get('商品')),
        clean_text(first_value(payload, ('所属类目', '商品类目', '商品分类', '导购类目', '类目'))),
        clean_text(payload.get('上架时间')),
        clean_text(payload.get('商品主图')),
        clean_text(payload.get('商品状态')),
    )


PRODUCT_SQL = """
INSERT INTO products (product_id, title, category, list_date, image_url, source_status, status)
VALUES (?, ?, ?, ?, ?, ?, 'active')
ON CONFLICT(product_id) DO UPDATE SET
  title=CASE WHEN excluded.title <> '' THEN excluded.title ELSE products.title END,
  category=CASE WHEN excluded.category <> '' THEN excluded.category ELSE products.category END,
  list_date=CASE WHEN excluded.list_date <> '' THEN excluded.list_date ELSE products.list_date END,
  image_url=CASE WHEN excluded.image_url <> '' THEN excluded.image_url ELSE products.image_url END,
  source_status=CASE WHEN excluded.source_status <> '' THEN excluded.source_status ELSE products.source_status END,
  updated_at=CURRENT_TIMESTAMP
"""


def remove_absent_products_for_date(connection: sqlite3.Connection, stat_date: str, product_ids: set[str]) -> dict[str, int]:
    """Replace a BI reporting day's product scope without deleting products themselves.

    A dated 商品总览 export is a complete snapshot for that day.  Keeping older
    product-day rows that are absent from the snapshot would double-count the
    store totals, so only the facts, observations, and reconciliation records
    for those absent products are removed.  Product catalog metadata is kept.
    """
    if not product_ids:
        raise ValueError(f'{stat_date} 没有有效商品 ID，不能替换该日期数据')
    connection.execute('CREATE TEMP TABLE IF NOT EXISTS paimi_bi_import_scope (product_id TEXT PRIMARY KEY)')
    connection.execute('DELETE FROM paimi_bi_import_scope')
    connection.executemany(
        'INSERT INTO paimi_bi_import_scope (product_id) VALUES (?)',
        [(product_id,) for product_id in product_ids],
    )
    result: dict[str, int] = {}
    for table in ('reconciliation_results', 'fact_field_lineage', 'daily_data_observations', 'daily_data'):
        cursor = connection.execute(
            f"DELETE FROM {table} WHERE date = ? AND product_id NOT IN (SELECT product_id FROM paimi_bi_import_scope)",
            (stat_date,),
        )
        result[table] = max(0, int(cursor.rowcount or 0))
    return result


def _insert_batch(connection: sqlite3.Connection, path: Path, source_hash: str, stat_date: str) -> str:
    batch_id = hashlib.sha256(f'{SOURCE_TYPE}:{path.name}:{source_hash}'.encode('utf-8')).hexdigest()[:32]
    connection.execute(
        """INSERT INTO import_batches (id, source_type, source_filename, source_hash, status, quality_summary)
           VALUES (?, ?, ?, ?, 'running', ?)
           ON CONFLICT(id) DO UPDATE SET source_hash=excluded.source_hash, status='running',
             quality_summary=excluded.quality_summary, completed_at=NULL""",
        (batch_id, SOURCE_TYPE, str(path), source_hash, json.dumps({'date': stat_date}, ensure_ascii=False)),
    )
    return batch_id


def import_file(connection: sqlite3.Connection, path: Path, dry_run: bool = False) -> dict[str, Any]:
    stat_date = date_from_file(path)
    source_hash = file_hash(path)
    source_batch_id = path.name
    batch_id = None if dry_run else _insert_batch(connection, path, source_hash, stat_date)
    rows = 0
    invalid_rows = 0
    effective_fields = Counter()
    source_totals = Counter()
    product_ids: set[str] = set()

    try:
        for product_id, payload, progress in source_rows(path, stat_date):
            if product_id is None:
                invalid_rows = int(progress.get('invalid') or 0)
                if not progress.get('done'):
                    raise RuntimeError(f'{path.name} 未正常完成读取')
                break
            observation = observation_from_payload(product_id, stat_date, payload)
            if len(observation) == 2:
                continue
            product_ids.add(product_id)
            rows += 1
            for metric in ('payment_amount', 'successful_refund_amount', 'net_sales', 'product_visitors', 'payment_buyers', 'ad_spend'):
                if observation.get(metric) is not None:
                    source_totals[metric] += observation[metric]
            if dry_run:
                continue
            connection.execute(PRODUCT_SQL, product_values(product_id, payload))
            result = record_daily_observation(
                connection,
                observation,
                SOURCE_TYPE,
                source_filename=path.name,
                source_batch_id=source_batch_id,
                source_system=SOURCE_SYSTEM,
            )
            effective_fields.update(result.get('effective_fields') or [])

        if not rows:
            raise ValueError(f'{path.name} 没有可导入的有效日度商品数据')

        removed_records: dict[str, int] = {}
        if not dry_run:
            removed_records = remove_absent_products_for_date(connection, stat_date, product_ids)
            quality = {
                'date': stat_date,
                'valid_rows': rows,
                'invalid_rows': invalid_rows,
                'source_totals': dict(source_totals),
                'effective_fields': dict(effective_fields),
                'removed_absent_records': removed_records,
            }
            connection.execute(
                """UPDATE import_batches SET status='completed', total_rows=?, valid_rows=?, invalid_rows=?,
                   inserted_count=?, updated_count=?, quality_summary=?, completed_at=CURRENT_TIMESTAMP WHERE id=?""",
                (rows + invalid_rows, rows, invalid_rows, rows, 0, json.dumps(quality, ensure_ascii=False), batch_id),
            )
        return {
            'file': path.name,
            'date': stat_date,
            'rows': rows,
            'invalid_rows': invalid_rows,
            'source_hash': source_hash,
            'source_totals': dict(source_totals),
            'effective_fields': dict(effective_fields),
            'removed_absent_records': removed_records,
        }
    except Exception as error:
        if not dry_run and batch_id:
            connection.execute(
                "UPDATE import_batches SET status='failed', quality_summary=?, completed_at=CURRENT_TIMESTAMP WHERE id=?",
                (json.dumps({'date': stat_date, 'error': str(error)}, ensure_ascii=False), batch_id),
            )
        raise


def backup_database(db_path: Path) -> Path:
    backup_dir = ROOT / 'data' / 'backups'
    backup_dir.mkdir(parents=True, exist_ok=True)
    target = backup_dir / f'dashboard-before-paimi-bi-daily-{datetime.now():%Y%m%d-%H%M%S}.db'
    source = sqlite3.connect(db_path)
    destination = sqlite3.connect(target)
    try:
        source.backup(destination)
    finally:
        destination.close()
        source.close()
    return target


def database_summary(connection: sqlite3.Connection, dates: list[str]) -> list[dict[str, Any]]:
    result = []
    for stat_date in dates:
        row = connection.execute(
            """SELECT date, COUNT(*) AS rows, COUNT(DISTINCT product_id) AS products,
                      SUM(payment_amount) AS payment_amount, SUM(net_sales) AS net_sales,
                      SUM(ipv) AS visitors, SUM(buyers) AS buyers, SUM(ad_spend) AS ad_spend
               FROM daily_data WHERE date = ? GROUP BY date""",
            (stat_date,),
        ).fetchone()
        result.append(dict(row) if row else {'date': stat_date, 'rows': 0, 'products': 0})
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description='Import dated Primeet BI 商品总览 workbooks as product-day facts.')
    parser.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    parser.add_argument('--db', type=Path, default=Path(get_db_path()))
    parser.add_argument('--dates', nargs='*', help='Only import these YYYY-MM-DD dates.')
    parser.add_argument('--dry-run', action='store_true', help='Validate files without changing the database.')
    args = parser.parse_args()

    source = args.source.resolve()
    db_path = args.db.resolve()
    if not source.is_dir():
        raise SystemExit(f'数据源目录不存在: {source}')
    files = sorted(source.glob('*.xlsx'), key=date_from_file)
    if args.dates:
        requested = set(args.dates)
        files = [path for path in files if date_from_file(path) in requested]
    if not files:
        raise SystemExit('没有匹配的 .xlsx 数据源文件')

    init_db(str(db_path))
    backup = None if args.dry_run else backup_database(db_path)
    connection = sqlite3.connect(db_path, timeout=300)
    connection.row_factory = sqlite3.Row
    connection.execute('PRAGMA foreign_keys=ON')
    connection.execute('PRAGMA busy_timeout=300000')
    results: list[dict[str, Any]] = []
    try:
        if not args.dry_run:
            connection.execute('BEGIN IMMEDIATE')
        for index, path in enumerate(files, start=1):
            print(f'[{index}/{len(files)}] 导入 {path.name}', flush=True)
            result = import_file(connection, path, dry_run=args.dry_run)
            results.append(result)
            print(json.dumps(result, ensure_ascii=False), flush=True)
        summaries = [] if args.dry_run else database_summary(connection, [item['date'] for item in results])
        if not args.dry_run:
            connection.commit()
    except Exception:
        if not args.dry_run:
            connection.rollback()
        raise
    finally:
        connection.close()

    report = {
        'generated_at': datetime.now().isoformat(timespec='seconds'),
        'source': str(source), 'database': str(db_path), 'dry_run': args.dry_run,
        'backup': str(backup) if backup else None, 'files': results,
        'database_summary': summaries,
    }
    report_path = ROOT / 'data' / f'paimi_bi_daily_import_{datetime.now():%Y%m%d_%H%M%S}.json'
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print('SUMMARY', json.dumps(report, ensure_ascii=False), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
