"""Reconcile legacy daily facts against an exact raw workbook match.

The command is read-only unless ``--apply`` is supplied.  It only considers
facts that currently have no observation/lineage and refuses to write when a
source row is missing, duplicated, or disagrees with an existing core value.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db import get_db, get_db_path
from services.import_service import ImportService, ImportValidationError
from services.source_resolution_service import record_daily_observation


class LegacySourceMatchError(ValueError):
    pass


CORE_FIELDS = {
    'payment_amount': 'payment_amount',
    'successful_refund_amount': 'refund_amount',
    'product_visitors': 'ipv',
    'payment_buyers': 'buyers',
    'page_views': 'pv',
    'payment_conversion': 'payment_conversion',
    'bounce_rate': 'bounce_rate',
    'avg_stay_duration': 'avg_stay_duration',
    'payment_items': 'payment_qty',
    'payment_unit_price': 'avg_order_value',
    'net_sales': 'net_sales',
}


def _clean_id(value):
    if value is None or pd.isna(value):
        return ''
    text = str(value).strip()
    if text.endswith('.0') and text[:-2].isdigit():
        text = text[:-2]
    return text


def _optional(value, percentage=False):
    if value is None or pd.isna(value) or str(value).strip() in {'', '-', '--', 'nan', 'None'}:
        return None
    try:
        return ImportService._optional_number(value, percentage=percentage)
    except (TypeError, ValueError, ImportValidationError) as error:
        raise LegacySourceMatchError(f'原始字段无法解析为数字：{value!r}') from error


def _date(value):
    try:
        parsed = ImportService._date(value)
        if parsed == 'NaT':
            raise ValueError('NaT is not a date')
        return parsed
    except (TypeError, ValueError, ImportValidationError) as error:
        raise LegacySourceMatchError(f'原始日期无法解析：{value!r}') from error


def _find_daily_frames(source_path):
    frames = []
    with pd.ExcelFile(source_path) as workbook:
        for sheet_name in workbook.sheet_names:
            raw = pd.read_excel(workbook, sheet_name=sheet_name, header=None, dtype=object)
            header_index = None
            for index in range(min(len(raw), 15)):
                headers = {_clean_id(value) for value in raw.iloc[index].tolist()}
                if ({'统计日期', '日期'} & headers) and ({'商品ID', '宝贝ID', '主体ID'} & headers):
                    header_index = index
                    break
            if header_index is None:
                continue
            headers = [str(value).strip() for value in raw.iloc[header_index].tolist()]
            frame = raw.iloc[header_index + 1:].copy()
            frame.columns = headers
            frames.append((sheet_name, frame.reset_index(drop=True)))
    if not frames:
        raise LegacySourceMatchError('原始工作簿中没有可识别的生意参谋日度页')
    return frames


def _column(frame, *names):
    for name in names:
        if name in frame.columns:
            return name
    return None


def _payload(row, columns):
    def value(*names):
        column = _column(row.to_frame().T, *names)
        return row[column] if column else None

    product_id = _clean_id(value(*columns['product_id']))
    stat_date = _date(value(*columns['date']))
    if not product_id:
        return None
    payment = _optional(value(*columns['payment_amount']))
    refund = _optional(value(*columns['refund_amount']))
    payload = {
        'product_id': product_id,
        'date': stat_date,
        'payment_amount': payment,
        'successful_refund_amount': refund,
        'payment_items': _optional(value(*columns['payment_items'])),
        'product_visitors': _optional(value(*columns['product_visitors'])),
        'page_views': _optional(value(*columns['page_views'])),
        'payment_conversion': _optional(value(*columns['payment_conversion']), percentage=True),
        # The historical importer used the product add-to-cart rate for this
        # field; preserve that mapping for an exact legacy reconciliation.
        'favorite_cart_rate': _optional(value(*columns['favorite_cart_rate']), percentage=True),
        'bounce_rate': _optional(value(*columns['bounce_rate']), percentage=True),
        'avg_stay_duration': _optional(value(*columns['avg_stay_duration'])),
        'payment_buyers': _optional(value(*columns['payment_buyers'])),
        'payment_unit_price': _optional(value(*columns['payment_unit_price'])),
        'uv_value': _optional(value(*columns['uv_value'])),
        'cart_items': _optional(value(*columns['cart_items'])),
        'favorite_users': _optional(value(*columns['favorite_users'])),
        'search_conversion': _optional(value(*columns['search_conversion']), percentage=True),
        'search_visitors': _optional(value(*columns['search_visitors'])),
        'cart_users': _optional(value(*columns['cart_users'])),
    }
    if payment is not None and refund is not None:
        payload['net_sales'] = payment - refund
    return payload


def _source_rows(source_path, target_dates):
    rows = {}
    duplicate_keys = []
    column_aliases = {
        'product_id': ('商品ID', '宝贝ID', '主体ID'),
        'date': ('统计日期', '日期'),
        'payment_amount': ('支付金额',),
        'refund_amount': ('成功退款金额', '退款金额'),
        'payment_items': ('支付件数',),
        'product_visitors': ('商品访客数', '访客数'),
        'page_views': ('商品浏览量', '浏览量'),
        'payment_conversion': ('商品支付转化率', '支付转化率'),
        'favorite_cart_rate': ('商品加购率', '加购率'),
        'bounce_rate': ('商品详情页跳出率', '跳失率'),
        'avg_stay_duration': ('平均停留时长',),
        'payment_buyers': ('支付买家数', '支付人数'),
        'payment_unit_price': ('客单价',),
        'uv_value': ('访客平均价值',),
        'cart_items': ('商品加购件数',),
        'favorite_users': ('商品收藏人数',),
        'search_conversion': ('搜索引导支付转化率',),
        'search_visitors': ('搜索引导支付买家数',),
        'cart_users': ('商品加购人数',),
    }
    for _, frame in _find_daily_frames(source_path):
        if not _column(frame, *column_aliases['product_id']) or not _column(frame, *column_aliases['date']):
            continue
        for _, row in frame.iterrows():
            try:
                payload = _payload(row, column_aliases)
            except LegacySourceMatchError:
                continue
            if not payload or payload['date'] not in target_dates:
                continue
            key = (payload['product_id'], payload['date'])
            if key in rows:
                duplicate_keys.append(key)
            else:
                rows[key] = payload
    if duplicate_keys:
        raise LegacySourceMatchError(f'原始工作簿存在重复业务键：{len(duplicate_keys)} 个')
    return rows


def _equal(left, right):
    if left is None or right is None:
        return left is right or (left in (None, 0, 0.0) and right in (None, 0, 0.0))
    try:
        return math.isclose(float(left), float(right), rel_tol=1e-7, abs_tol=1e-7)
    except (TypeError, ValueError):
        return str(left) == str(right)


def plan(database_path, source_path):
    source_path = Path(source_path).resolve()
    if not source_path.is_file():
        raise LegacySourceMatchError(f'原始文件不存在：{source_path}')
    with get_db(database_path) as connection:
        facts = connection.execute(
            '''SELECT d.* FROM daily_data d
               WHERE NOT EXISTS (
                   SELECT 1 FROM daily_data_observations o
                   WHERE o.shop_id=d.shop_id AND o.product_id=d.product_id AND o.date=d.date
               )
               ORDER BY d.date, d.product_id'''
        ).fetchall()
    target_dates = {str(fact['date']) for fact in facts}
    source_rows = _source_rows(source_path, target_dates) if target_dates else {}
    source_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
    missing = []
    mismatches = []
    matches = []
    for fact in facts:
        key = (str(fact['product_id']), str(fact['date']))
        payload = source_rows.get(key)
        if payload is None:
            missing.append(key)
            continue
        row_mismatches = []
        for field, column in CORE_FIELDS.items():
            if payload.get(field) is None:
                continue
            if not _equal(fact[column], payload[field]):
                row_mismatches.append({
                    'field': field, 'current': fact[column], 'source': payload[field],
                })
        if row_mismatches:
            mismatches.append({'key': key, 'fields': row_mismatches})
        else:
            matches.append({'key': key, 'payload': payload})
    return {
        'database': str(Path(database_path).resolve()),
        'source_file': str(source_path),
        'source_hash': source_hash,
        'source_rows': len(source_rows),
        'untraceable_rows': len(facts),
        'exact_matches': len(matches),
        'missing_source_rows': missing,
        'mismatches': mismatches,
        # An already reconciled database is a successful no-op.  This keeps
        # scheduled audits idempotent instead of reporting a false failure.
        'eligible': not facts or (not missing and not mismatches),
        'matches': matches,
    }


def apply_plan(report):
    batch_id = f"legacy-reconcile-{report['source_hash'][:16]}"
    with get_db(report['database']) as connection:
        existing = connection.execute(
            'SELECT id FROM import_batches WHERE id = ?', (batch_id,)
        ).fetchone()
    if existing:
        return {'batch_id': batch_id, 'written': 0, 'already_applied': True}
    if report['untraceable_rows'] == 0:
        return {'batch_id': None, 'written': 0, 'already_applied': False, 'no_op': True}
    if not report['eligible']:
        raise LegacySourceMatchError('精确匹配未通过，拒绝写入')
    quality = {
        'total_rows': report['exact_matches'],
        'valid_rows': report['exact_matches'],
        'invalid_rows': 0,
        'duplicate_keys': 0,
        'date_range': {
            'start': min(item['key'][1] for item in report['matches']),
            'end': max(item['key'][1] for item in report['matches']),
        },
        'conclusion': 'exact legacy source reconciliation',
        'source_rows': report['source_rows'],
    }
    with get_db(report['database']) as connection:
        connection.execute(
            '''INSERT INTO import_batches
               (id, shop_id, source_type, source_filename, source_hash, status,
                total_rows, valid_rows, invalid_rows, inserted_count, updated_count,
                quality_summary, completed_at)
               VALUES (?, 'default', 'product_day', ?, ?, 'completed', ?, ?, 0, 0, ?, ?, CURRENT_TIMESTAMP)''',
            (batch_id, Path(report['source_file']).name, report['source_hash'],
             report['exact_matches'], report['exact_matches'], report['exact_matches'],
             json.dumps(quality, ensure_ascii=False)),
        )
        for item in report['matches']:
            record_daily_observation(
                connection,
                item['payload'],
                source_type='product_day',
                source_filename=Path(report['source_file']).name,
                source_batch_id=batch_id,
                shop_id='default',
            )
        connection.commit()
    return {'batch_id': batch_id, 'written': report['exact_matches'], 'already_applied': False}


def main(argv=None):
    parser = argparse.ArgumentParser(description='按原始工作簿精确恢复历史日事实血缘。')
    parser.add_argument('--database', default=get_db_path())
    parser.add_argument('--source-file', required=True)
    parser.add_argument('--apply', action='store_true', help='精确匹配通过后写入批次、观察和血缘')
    args = parser.parse_args(argv)
    report = plan(os.path.abspath(args.database), args.source_file)
    output = {key: value for key, value in report.items() if key != 'matches'}
    if args.apply:
        output['apply'] = apply_plan(report)
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if report['eligible'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
