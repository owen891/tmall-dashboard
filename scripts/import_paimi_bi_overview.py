from __future__ import annotations

"""Import Primeet monthly 商品总览 workbooks without losing source-only fields.

The importer replaces the supplied months in ``monthly_data`` and stores every
non-empty source cell in ``monthly_source_payload``.  It never fabricates
missing values as zero.  A timestamped SQLite backup and JSON audit report are
created before changes are applied.
"""

import argparse
import hashlib
import json
import re
import shutil
import sqlite3
import sys
import uuid
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any

from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db import get_db_path, init_db  # noqa: E402

DEFAULT_SOURCE = Path(r"E:\派米\BI数据源25.4-26.7")
MISSING_MARKERS = {'', '-', '--', '—', '－', 'none', 'null', 'nan', 'n/a'}
TEXT_SOURCE_COLUMNS = {
    '商品id', '商品', '商品主图', '商品标签', '渠道', '店铺', '商品状态', '上架时间',
    '发货仓库', '负责人', '商品类目', '商品分类', '类目', '商品编码', '货品编码',
}
# Columns represented by the pre-existing product/monthly schema.  They are
# still retained in the raw payload, but do not create duplicate choice fields.
MAPPED_SOURCE_COLUMNS = TEXT_SOURCE_COLUMNS | {
    '净销售额(支付)', '支付金额(支付)', '普通单退款金额', '退款金额', '确认退款金额',
    '普通单退款率(按金额)', '访客数', '浏览量', '商品浏览量', '访客价值', '搜索访客数',
    '搜索访客占比', '支付转化率', '搜索转化率', '加购率', '收藏率', '推广花费(账单)',
    '支付人数', '销售件数(支付)', '加购件数', '收藏人数', '商品点击率', '付费占比',
    '推广ROI(账单)', '推广投产(账单)', '推广ROI', '实际客单价', '真实客单价', '客单价',
}

MONTHLY_SPECS = {
    'payment_amount': ('支付金额(支付)',),
    'refund_amount': ('普通单退款金额', '退款金额', '确认退款金额'),
    'net_sales': ('净销售额(支付)',),
    'visitors': ('访客数',),
    'page_views': ('浏览量', '商品浏览量'),
    'uv_value': ('访客价值',),
    'search_visitors': ('搜索访客数',),
    'search_ratio': ('搜索访客占比',),
    'payment_conversion': ('支付转化率',),
    'search_conversion': ('搜索转化率',),
    'cart_rate': ('加购率',),
    'fav_rate': ('收藏率',),
    'ad_spend': ('推广花费(账单)',),
    'ad_roi': ('推广ROI(账单)', '推广投产(账单)', '推广ROI'),
    'paid_ratio': ('付费占比',),
    'refund_rate': ('普通单退款率(按金额)',),
    'buyers': ('支付人数',),
    'avg_order_value': ('真实客单价', '实际客单价', '客单价'),
    'payment_qty': ('销售件数(支付)',),
    'cart_qty': ('加购件数',),
    'fav_users': ('收藏人数',),
    'click_rate': ('商品点击率',),
}
MONTHLY_COLUMNS = [
    'product_id', 'month', 'payment_amount', 'refund_amount', 'net_sales',
    'visitors', 'page_views', 'uv_value', 'search_visitors', 'search_ratio',
    'payment_conversion', 'search_conversion', 'cart_rate', 'fav_rate',
    'bounce_rate', 'avg_stay_duration', 'ad_spend', 'ad_roi', 'overall_roi',
    'paid_ratio', 'refund_paid_ratio', 'keyword_spend', 'keyword_sales',
    'keyword_roi', 'keyword_visitors', 'keyword_ppc', 'crowd_spend',
    'crowd_sales', 'crowd_roi', 'crowd_visitors', 'crowd_ppc', 'site_spend',
    'site_sales', 'site_roi', 'site_visitors', 'site_ppc', 'refund_rate',
    'repurchase_rate', 'cross_sell_rate', 'buyers', 'avg_order_value',
    'payment_qty', 'cart_qty', 'fav_users', 'click_rate', 'score',
    'data_source',
]
MONTHLY_SQL = f"""
INSERT INTO monthly_data ({', '.join(MONTHLY_COLUMNS)})
VALUES ({', '.join('?' for _ in MONTHLY_COLUMNS)})
ON CONFLICT(product_id, month) DO UPDATE SET
{', '.join(f'{column}=excluded.{column}' for column in MONTHLY_COLUMNS if column not in {'product_id', 'month'})}
"""
PAYLOAD_SQL = """
INSERT INTO monthly_source_payload (product_id, month, source_filename, source_hash, payload_json)
VALUES (?, ?, ?, ?, ?)
ON CONFLICT(product_id, month) DO UPDATE SET
 source_filename=excluded.source_filename, source_hash=excluded.source_hash,
 payload_json=excluded.payload_json, imported_at=CURRENT_TIMESTAMP
"""
PRODUCT_SQL = """
INSERT INTO products (product_id, title, category, list_date, status, image_url, source_status, product_tags, updated_at)
VALUES (?, ?, ?, ?, 'active', ?, ?, ?, CURRENT_TIMESTAMP)
ON CONFLICT(product_id) DO UPDATE SET
 title=COALESCE(NULLIF(excluded.title, ''), products.title),
 category=COALESCE(NULLIF(excluded.category, ''), products.category),
 list_date=COALESCE(NULLIF(excluded.list_date, ''), products.list_date),
 image_url=COALESCE(NULLIF(excluded.image_url, ''), products.image_url),
 source_status=COALESCE(NULLIF(excluded.source_status, ''), products.source_status),
 product_tags=COALESCE(NULLIF(excluded.product_tags, ''), products.product_tags),
 updated_at=CURRENT_TIMESTAMP
"""


def clean_text(value: Any) -> str:
    if value is None:
        return ''
    return str(value).strip()


def clean_product_id(value: Any) -> str:
    text = clean_text(value)
    if re.fullmatch(r'\d+\.0+', text):
        return text.split('.', 1)[0]
    return text


def missing(value: Any) -> bool:
    return value is None or (isinstance(value, str) and value.strip().lower() in MISSING_MARKERS)


def value_for_payload(value: Any, column: str) -> Any:
    if missing(value):
        return None
    if isinstance(value, (datetime, date)):
        return value.isoformat(sep=' ') if isinstance(value, datetime) else value.isoformat()
    if column == '商品id':
        return clean_product_id(value)
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    text = clean_text(value)
    if column in TEXT_SOURCE_COLUMNS:
        return text
    compact = text.replace(',', '').replace('¥', '').replace('￥', '').strip()
    if compact.endswith('%'):
        try:
            return float(compact[:-1]) / 100
        except ValueError:
            return text
    try:
        return float(compact)
    except ValueError:
        return text


def numeric(value: Any) -> float | None:
    value = value_for_payload(value, '')
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def first_value(payload: dict[str, Any], columns: tuple[str, ...]) -> Any:
    for column in columns:
        value = payload.get(column)
        if value is not None:
            return value
    return None


def month_from_file(path: Path) -> str:
    match = re.search(r'(20\d{2}-\d{2})-\d{2}', path.name)
    if not match:
        raise ValueError(f'无法从文件名识别月份: {path.name}')
    return match.group(1)


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def field_key(source_column: str) -> str:
    return 'bi_' + hashlib.sha1(source_column.encode('utf-8')).hexdigest()[:12]


def field_format(source_column: str, numeric_seen: int, text_seen: int) -> tuple[str, str]:
    if not numeric_seen or text_seen > numeric_seen:
        return 'text', 'text'
    label = source_column.lower()
    if any(token in source_column for token in ('率', '占比', '环比', '达成')) and 'roi' not in label:
        return 'number', 'percent'
    if 'roi' in label or '投产' in source_column or '效率' in source_column:
        return 'number', 'decimal'
    if any(token in source_column for token in ('金额', '销售额', '花费', '成本', '利润', '费用', '客单价', '单价', '售价', '收入', '支出', '佣金', '运费', '毛利')):
        return 'number', 'money'
    if any(token in source_column for token in ('人数', '件数', '单数', '数量', '访客', '点击', '曝光', '库存', '订单', '次数', '排名', '天数', 'pv', 'uv')):
        return 'number', 'number'
    return 'number', 'decimal'


def source_rows(path: Path, month: str):
    """Yield normalized report rows and field observations using read-only streaming."""
    workbook = load_workbook(path, read_only=True, data_only=True, keep_links=False)
    try:
        sheet = workbook['商品总览'] if '商品总览' in workbook.sheetnames else workbook[workbook.sheetnames[0]]
        rows = sheet.iter_rows(values_only=True)
        raw_headers = list(next(rows, ()))
        # The second row repeats header labels in this export and is intentionally skipped.
        next(rows, None)
        header_indexes: dict[str, int] = {}
        for index, raw in enumerate(raw_headers):
            header = clean_text(raw)
            if header and header not in header_indexes:
                header_indexes[header] = index
        if '商品id' not in header_indexes:
            raise ValueError(f'{path.name} 缺少 商品id 列')

        seen_ids: set[str] = set()
        stats = defaultdict(Counter)
        total = valid = invalid = 0
        for row_number, row in enumerate(rows, start=3):
            total += 1
            product_id = clean_product_id(row[header_indexes['商品id']] if header_indexes['商品id'] < len(row) else None)
            if not product_id or product_id.lower() in {'合计', '总计', '汇总', 'none', 'nan'}:
                invalid += 1
                continue
            if product_id in seen_ids:
                raise ValueError(f'{path.name} 第 {row_number} 行商品id重复: {product_id}')
            seen_ids.add(product_id)
            valid += 1
            payload: dict[str, Any] = {}
            for header, index in header_indexes.items():
                raw = row[index] if index < len(row) else None
                normalized = value_for_payload(raw, header)
                if normalized is None:
                    continue
                payload[header] = normalized
                stats[header]['nonempty'] += 1
                stats[header]['numeric' if isinstance(normalized, (int, float)) and not isinstance(normalized, bool) else 'text'] += 1
            yield product_id, payload, {'total': total, 'valid': valid, 'invalid': invalid, 'stats': stats}
        yield None, None, {'total': total, 'valid': valid, 'invalid': invalid, 'stats': stats, 'done': True}
    finally:
        workbook.close()


def backup_database(db_path: Path, backup_dir: Path) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    target = backup_dir / f'dashboard-before-paimi-bi-overview-{datetime.now():%Y%m%d-%H%M%S}.db'
    source = sqlite3.connect(db_path)
    destination = sqlite3.connect(target)
    try:
        source.backup(destination)
    finally:
        destination.close()
        source.close()
    return target


def values_for_monthly(product_id: str, month: str, payload: dict[str, Any], source_name: str) -> tuple[Any, ...]:
    values: dict[str, Any] = {column: None for column in MONTHLY_COLUMNS}
    values.update({'product_id': product_id, 'month': month, 'data_source': f'paimi-bi-overview:{month}:{source_name}'})
    for destination, sources in MONTHLY_SPECS.items():
        value = first_value(payload, sources)
        values[destination] = numeric(value) if value is not None else None
    # The BI file does not consistently ship a standalone ROI field.  This is
    # a transparent derived value using the same-row payment amount/spend.
    if values['ad_roi'] is None and values['payment_amount'] is not None and values['ad_spend'] not in (None, 0):
        values['ad_roi'] = values['payment_amount'] / values['ad_spend']
    if values['avg_order_value'] is None and values['payment_amount'] is not None and values['buyers'] not in (None, 0):
        values['avg_order_value'] = values['payment_amount'] / values['buyers']
    return tuple(values[column] for column in MONTHLY_COLUMNS)


def product_values(product_id: str, payload: dict[str, Any]) -> tuple[str, str, str, str, str, str, str]:
    category = first_value(payload, ('商品类目', '商品分类', '类目')) or ''
    return (
        product_id,
        clean_text(payload.get('商品')),
        clean_text(category),
        clean_text(payload.get('上架时间')),
        clean_text(payload.get('商品主图')),
        clean_text(payload.get('商品状态')),
        clean_text(payload.get('商品标签')),
    )


def import_file(connection: sqlite3.Connection, path: Path, field_stats: dict[str, dict[str, Any]], dry_run: bool) -> dict[str, Any]:
    month = month_from_file(path)
    source_hash = file_hash(path)
    batch_id = str(uuid.uuid4())
    connection.execute(
        "INSERT INTO import_batches (id, source_type, source_filename, source_hash, status, quality_summary) VALUES (?, ?, ?, ?, 'running', ?)",
        (batch_id, 'paimi_bi_overview', str(path), source_hash, json.dumps({'month': month}, ensure_ascii=False)),
    )
    connection.commit()

    before = connection.execute('SELECT COUNT(*) FROM monthly_data WHERE month = ?', (month,)).fetchone()[0]
    rows: list[tuple[tuple[Any, ...], tuple[Any, ...], tuple[Any, ...]]] = []
    source_totals = Counter()
    final = {'total': 0, 'valid': 0, 'invalid': 0, 'stats': defaultdict(Counter)}
    try:
        for product_id, payload, progress in source_rows(path, month):
            if product_id is None:
                final = progress
                break
            monthly_values = values_for_monthly(product_id, month, payload, path.name)
            monthly_record = dict(zip(MONTHLY_COLUMNS, monthly_values))
            for metric in ('payment_amount', 'refund_amount', 'net_sales', 'visitors', 'buyers', 'ad_spend'):
                if monthly_record[metric] is not None:
                    source_totals[metric] += monthly_record[metric]
            rows.append((
                product_values(product_id, payload),
                monthly_values,
                (product_id, month, path.name, source_hash, json.dumps(payload, ensure_ascii=False, separators=(',', ':'))),
            ))
        if not final.get('done'):
            raise RuntimeError(f'{path.name} 未正常完成读取')
        if not rows:
            raise ValueError(f'{path.name} 没有有效商品数据')

        for source_column, counter in final['stats'].items():
            observed = field_stats.setdefault(source_column, {'months': set(), 'nonempty': 0, 'numeric': 0, 'text': 0})
            observed['months'].add(month)
            for key in ('nonempty', 'numeric', 'text'):
                observed[key] += int(counter[key])

        if not dry_run:
            connection.execute('BEGIN IMMEDIATE')
            connection.execute('DELETE FROM monthly_data WHERE month = ?', (month,))
            connection.execute('DELETE FROM monthly_source_payload WHERE month = ?', (month,))
            connection.executemany(PRODUCT_SQL, [item[0] for item in rows])
            connection.executemany(MONTHLY_SQL, [item[1] for item in rows])
            connection.executemany(PAYLOAD_SQL, [item[2] for item in rows])
            after = connection.execute('SELECT COUNT(*) FROM monthly_data WHERE month = ?', (month,)).fetchone()[0]
            payload_after = connection.execute('SELECT COUNT(*) FROM monthly_source_payload WHERE month = ?', (month,)).fetchone()[0]
            if after != len(rows) or payload_after != len(rows):
                raise RuntimeError(f'{month} 写入行数校验失败: monthly={after}, payload={payload_after}, expected={len(rows)}')
            quality = {'month': month, 'total_rows': final['total'], 'valid_rows': final['valid'], 'invalid_rows': final['invalid'], 'payload_rows': payload_after}
            connection.execute(
                """UPDATE import_batches SET status='completed', total_rows=?, valid_rows=?, invalid_rows=?,
                   inserted_count=?, updated_count=?, quality_summary=?, completed_at=CURRENT_TIMESTAMP WHERE id=?""",
                (final['total'], final['valid'], final['invalid'], max(0, len(rows) - before), min(before, len(rows)), json.dumps(quality, ensure_ascii=False), batch_id),
            )
            connection.commit()
            db_totals = dict(connection.execute(
                """SELECT SUM(payment_amount) payment_amount, SUM(refund_amount) refund_amount,
                          SUM(net_sales) net_sales, SUM(visitors) visitors, SUM(buyers) buyers,
                          SUM(ad_spend) ad_spend FROM monthly_data WHERE month = ?""", (month,)
            ).fetchone())
        else:
            db_totals = None
            connection.execute("UPDATE import_batches SET status='validated', total_rows=?, valid_rows=?, invalid_rows=?, completed_at=CURRENT_TIMESTAMP WHERE id=?", (final['total'], final['valid'], final['invalid'], batch_id))
            connection.commit()
        return {'file': path.name, 'month': month, 'before_rows': before, 'rows': len(rows), 'total_rows': final['total'], 'invalid_rows': final['invalid'], 'source_hash': source_hash, 'source_totals': dict(source_totals), 'db_totals': db_totals}
    except Exception as error:
        connection.rollback()
        connection.execute("UPDATE import_batches SET status='failed', quality_summary=?, completed_at=CURRENT_TIMESTAMP WHERE id=?", (json.dumps({'month': month, 'error': str(error)}, ensure_ascii=False), batch_id))
        connection.commit()
        raise


def write_field_catalog(connection: sqlite3.Connection, field_stats: dict[str, dict[str, Any]]) -> int:
    rows = []
    for source_column, observed in sorted(field_stats.items()):
        if source_column in MAPPED_SOURCE_COLUMNS:
            continue
        data_type, display_format = field_format(source_column, observed['numeric'], observed['text'])
        rows.append((
            field_key(source_column), source_column, source_column, 'BI 数据源字段', data_type, display_format,
            'bi_monthly_overview', json.dumps(sorted(observed['months']), ensure_ascii=False), observed['nonempty'],
        ))
    connection.execute('BEGIN IMMEDIATE')
    connection.execute("DELETE FROM source_field_catalog WHERE source_type = 'bi_monthly_overview'")
    connection.executemany(
        """INSERT INTO source_field_catalog
        (field_key, source_column, label, group_name, data_type, format, source_type, available_months_json, nonempty_count)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        rows,
    )
    connection.commit()
    return len(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description='Replace monthly data from Primeet BI 商品总览 Excel files.')
    parser.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    parser.add_argument('--db', type=Path, default=Path(get_db_path()))
    parser.add_argument('--months', nargs='*', help='Only import these YYYY-MM months.')
    parser.add_argument('--dry-run', action='store_true', help='Validate source files without replacing monthly facts.')
    args = parser.parse_args()

    source = args.source.resolve()
    db_path = args.db.resolve()
    if not source.is_dir():
        raise SystemExit(f'数据源目录不存在: {source}')
    files = sorted(source.glob('*.xlsx'))
    if args.months:
        wanted = set(args.months)
        files = [path for path in files if month_from_file(path) in wanted]
    if not files:
        raise SystemExit('没有匹配的 .xlsx 数据源文件')

    init_db(str(db_path))
    backup = None if args.dry_run else backup_database(db_path, ROOT / 'data' / 'backups')
    connection = sqlite3.connect(db_path, timeout=180)
    connection.execute('PRAGMA foreign_keys=ON')
    connection.execute('PRAGMA busy_timeout=180000')
    connection.row_factory = sqlite3.Row
    field_stats: dict[str, dict[str, Any]] = {}
    results = []
    try:
        for index, path in enumerate(files, start=1):
            print(f'[{index}/{len(files)}] 读取并导入 {path.name}', flush=True)
            result = import_file(connection, path, field_stats, args.dry_run)
            results.append(result)
            print(json.dumps(result, ensure_ascii=False), flush=True)
        catalog_count = 0 if args.dry_run else write_field_catalog(connection, field_stats)
    finally:
        connection.close()

    report = {
        'generated_at': datetime.now().isoformat(timespec='seconds'),
        'source': str(source), 'database': str(db_path), 'dry_run': args.dry_run,
        'backup': str(backup) if backup else None, 'files': results,
        'imported_months': [item['month'] for item in results],
        'catalog_fields': catalog_count,
    }
    report_path = ROOT / 'data' / f'paimi_bi_overview_import_{datetime.now():%Y%m%d_%H%M%S}.json'
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print('SUMMARY', json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
