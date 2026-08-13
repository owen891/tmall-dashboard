import hashlib
import io
import json
from datetime import date
from uuid import uuid4

import pandas as pd

from repos.import_repo import ImportRepo, ImportRevertConflictError


REQUIRED_FIELDS = {
    'date', 'product_id', 'payment_amount', 'successful_refund_amount',
    'product_visitors', 'payment_buyers', 'ad_spend',
}

SOURCE_REQUIREMENTS = {
    'product_day': REQUIRED_FIELDS,
    'store_day': {'date', 'payment_amount', 'successful_refund_amount', 'product_visitors', 'payment_buyers'},
    'product_week': REQUIRED_FIELDS,
    'product_month': REQUIRED_FIELDS,
    'promotion_channel_day': {'date', 'channel', 'ad_spend', 'attributed_payment_amount'},
    'promotion_campaign_day': {'date', 'channel', 'campaign_id', 'ad_spend', 'attributed_payment_amount'},
    'promotion_unit_day': {'date', 'channel', 'campaign_id', 'unit_id', 'ad_spend', 'attributed_payment_amount'},
    'promotion_product_day': {'date', 'channel', 'product_id', 'ad_spend', 'attributed_payment_amount'},
    'refund_day': {'date', 'successful_refund_amount'},
    'customer_day': {'date', 'payment_buyers', 'returning_payment_buyers'},
}

SOURCE_KEY_FIELDS = {
    'product_day': ('date', 'product_id'),
    'store_day': ('date',), 'refund_day': ('date',), 'customer_day': ('date',),
    'product_week': ('date', 'product_id'), 'product_month': ('date', 'product_id'),
    'promotion_channel_day': ('date', 'channel'),
    'promotion_campaign_day': ('date', 'channel', 'campaign_id'),
    'promotion_unit_day': ('date', 'channel', 'campaign_id', 'unit_id'),
    'promotion_product_day': ('date', 'channel', 'product_id'),
}

SOURCE_ALLOWED_FIELDS = {
    'product_day': REQUIRED_FIELDS | {'product_name'},
    'store_day': SOURCE_REQUIREMENTS['store_day'] | {'ad_spend', 'returning_payment_buyers'},
    'refund_day': SOURCE_REQUIREMENTS['refund_day'],
    'customer_day': SOURCE_REQUIREMENTS['customer_day'],
    'product_week': REQUIRED_FIELDS | {'product_name'},
    'product_month': REQUIRED_FIELDS | {'product_name'},
    'promotion_channel_day': SOURCE_REQUIREMENTS['promotion_channel_day'] | {'impressions', 'clicks', 'payment_buyers', 'direct_payment_amount', 'indirect_payment_amount'},
    'promotion_campaign_day': SOURCE_REQUIREMENTS['promotion_campaign_day'] | {'impressions', 'clicks', 'payment_buyers', 'direct_payment_amount', 'indirect_payment_amount'},
    'promotion_unit_day': SOURCE_REQUIREMENTS['promotion_unit_day'] | {'impressions', 'clicks', 'payment_buyers', 'direct_payment_amount', 'indirect_payment_amount'},
    'promotion_product_day': SOURCE_REQUIREMENTS['promotion_product_day'] | {'impressions', 'clicks', 'payment_buyers', 'direct_payment_amount', 'indirect_payment_amount'},
}

NUMERIC_FIELDS = {
    'payment_amount', 'successful_refund_amount', 'product_visitors', 'payment_buyers',
    'returning_payment_buyers', 'ad_spend', 'attributed_payment_amount', 'impressions',
    'clicks', 'direct_payment_amount', 'indirect_payment_amount',
}

FIELD_ALIASES = {
    'direct_payment_amount': {'direct_payment_amount'},
    'indirect_payment_amount': {'indirect_payment_amount'},
    'date': {'日期', '统计日期', 'stat_date'},
    'product_id': {'商品ID', '宝贝ID', '主体ID', 'product_id'},
    'product_name': {'商品名称', '宝贝名称', '主体名称', 'product_name'},
    'payment_amount': {'支付金额', '成交金额', 'GMV', 'payment_amount'},
    'successful_refund_amount': {'退款金额', '成功退款金额', 'refund_amount'},
    'product_visitors': {'商品访客数', '访客数', 'ipv'},
    'payment_buyers': {'支付买家数', '支付人数', '买家数', 'buyers'},
    'ad_spend': {'推广花费', '花费', '营销推广消耗', 'ad_spend'},
    'channel': {'渠道', '推广渠道', 'channel'},
    'campaign_id': {'计划ID', '推广计划ID', 'campaign_id'},
    'unit_id': {'单元ID', '推广单元ID', 'unit_id'},
    'attributed_payment_amount': {'推广成交金额', '归因成交金额', 'attributed_payment_amount'},
    'impressions': {'展现量', '曝光量', 'impressions'},
    'clicks': {'点击量', 'clicks'},
    'returning_payment_buyers': {'老客支付买家数', '老客买家数', 'returning_payment_buyers'},
}


class ImportValidationError(ValueError):
    pass


class ImportService:
    def __init__(self):
        self.previews = {}

    @staticmethod
    def _mapping(columns):
        mapping = {}
        for field, aliases in FIELD_ALIASES.items():
            match = next((column for column in columns if str(column).strip() == field or str(column).strip() in aliases), None)
            if match is not None:
                mapping[field] = str(match)
        return mapping

    @staticmethod
    def _read_workbook(content):
        try:
            frame = pd.read_excel(io.BytesIO(content), dtype=object)
        except Exception as error:
            raise ImportValidationError('无法读取 Excel 文件') from error
        if frame.empty:
            raise ImportValidationError('Excel 文件没有数据行')
        return frame

    @staticmethod
    def _quality(frame, mapping, source_type):
        required = SOURCE_REQUIREMENTS[source_type]
        key_fields = SOURCE_KEY_FIELDS[source_type]
        keys = []
        dates = []
        product_ids = set()
        invalid_details = []
        invalid_rows = 0
        for index, row in frame.iterrows():
            try:
                stat_date = pd.to_datetime(row[mapping['date']]).date().isoformat()
                values = {'date': stat_date}
                for field in required:
                    value = row[mapping[field]]
                    if pd.isna(value) or (isinstance(value, str) and not value.strip()):
                        raise ValueError(f'{field} 不能为空')
                    if field in NUMERIC_FIELDS:
                        float(value)
                    values[field] = str(value).strip()
                keys.append(tuple(values[field] for field in key_fields))
                dates.append(stat_date)
                if values.get('product_id'):
                    product_ids.add(values['product_id'])
            except Exception as error:
                invalid_rows += 1
                if len(invalid_details) < 25:
                    invalid_details.append({'row_number': int(index) + 2, 'message': str(error) or '日期或必填字段无效'})
        duplicates = len(keys) - len(set(keys))
        return {
            'total_rows': len(frame.index),
            'valid_rows': len(frame.index) - invalid_rows,
            'invalid_rows': invalid_rows,
            'date_range': {'start': min(dates) if dates else None, 'end': max(dates) if dates else None},
            'product_count': len(product_ids),
            'duplicate_keys': duplicates,
            'invalid_details': invalid_details,
        }

    def preview(self, filename, content, source_type='product_day'):
        if source_type not in SOURCE_REQUIREMENTS:
            raise ImportValidationError('不支持的 source_type')
        frame = self._read_workbook(content)
        columns = [str(column).strip() for column in frame.columns]
        mapping = self._mapping(columns)
        required = SOURCE_REQUIREMENTS[source_type]
        quality = self._quality(frame, mapping, source_type) if required <= mapping.keys() else {
            'total_rows': len(frame.index), 'valid_rows': 0, 'invalid_rows': len(frame.index),
            'date_range': {'start': None, 'end': None}, 'product_count': 0, 'duplicate_keys': 0,
            'invalid_details': [{'row_number': None, 'message': f'缺少必填映射：{", ".join(sorted(required - set(mapping)))}'}],
        }
        preview_id = uuid4().hex
        source_hash = hashlib.sha256(content).hexdigest()
        self.previews[preview_id] = {
            'id': preview_id,
            'source_type': source_type,
            'source_filename': filename,
            'source_hash': source_hash,
            'frame': frame,
            'mapping': mapping,
            'quality': quality,
        }
        fields = []
        for column in columns:
            standard_key = next((key for key, source in mapping.items() if source == column), None)
            sample = frame[column].dropna().iloc[0] if not frame[column].dropna().empty else None
            fields.append({
                'source_column': column,
                'standard_key': standard_key,
                'sample_value': None if sample is None else str(sample),
                'matched': standard_key is not None,
            })
        quality['estimated_changes'] = self._estimate_changes(source_type, frame, mapping)
        return {
            'id': preview_id,
            'source_type': source_type,
            'mapping': mapping,
            'required_unmapped': sorted(required - set(mapping)),
            'fields': fields,
            'mapping_schema': {
                'required': sorted(SOURCE_REQUIREMENTS[source_type]),
                'allowed': sorted(SOURCE_ALLOWED_FIELDS[source_type]),
            },
            **quality,
        }

    @staticmethod
    def _estimate_changes(source_type, frame, mapping):
        """Estimate upsert impact without mutating the database."""
        if source_type not in SOURCE_KEY_FIELDS or not set(SOURCE_KEY_FIELDS[source_type]) <= set(mapping):
            return {'available': False, 'reason': '业务键未完成映射'}
        from db import get_db
        target = {
            'product_day': ('daily_data', ('product_id', 'date')),
            'store_day': ('store_daily_facts', ('shop_id', 'date')),
            'refund_day': ('store_daily_facts', ('shop_id', 'date')),
            'customer_day': ('store_daily_facts', ('shop_id', 'date')),
            'product_week': ('weekly_data', ('product_id', 'week_start')),
            'product_month': ('monthly_data', ('product_id', 'month')),
            'promotion_channel_day': ('promotion_daily_facts', ('shop_id', 'date', 'channel', 'campaign_id', 'unit_id', 'product_id')),
            'promotion_campaign_day': ('promotion_daily_facts', ('shop_id', 'date', 'channel', 'campaign_id', 'unit_id', 'product_id')),
            'promotion_unit_day': ('promotion_daily_facts', ('shop_id', 'date', 'channel', 'campaign_id', 'unit_id', 'product_id')),
            'promotion_product_day': ('promotion_daily_facts', ('shop_id', 'date', 'channel', 'campaign_id', 'unit_id', 'product_id')),
        }.get(source_type)
        if not target:
            return {'available': False, 'reason': '该来源暂不支持影响预估'}
        table, keys = target
        incoming = set()
        for _, row in frame.iterrows():
            try:
                values = []
                for key in keys:
                    if key == 'shop_id': value = 'default'
                    elif key in {'date', 'week_start', 'month'}:
                        raw = row[mapping['date']]
                        value = pd.to_datetime(raw).date().isoformat()
                        if key == 'month': value = value[:7]
                    elif key == 'product_id': value = str(row[mapping['product_id']]).strip()
                    else: value = str(row[mapping[key]]).strip() if key in mapping else ''
                    values.append(value)
                incoming.add(tuple(values))
            except Exception:
                continue
        if not incoming:
            return {'available': True, 'inserted': 0, 'updated': 0}
        existing = set()
        with get_db() as connection:
            period_column = next((column for column in ('date', 'week_start', 'month') if column in keys), None)
            dates = sorted({key[keys.index(period_column)] for key in incoming}) if period_column else []
            if dates:
                placeholders = ','.join('?' for _ in dates)
                query = f'SELECT {", ".join(keys)} FROM {table} WHERE {period_column} IN ({placeholders})'
                rows = connection.execute(query, dates)
            else:
                rows = connection.execute(f'SELECT {", ".join(keys)} FROM {table} WHERE 1=0')
            for row in rows:
                existing.add(tuple(str(value) for value in row))
        return {'available': True, 'inserted': len(incoming - existing), 'updated': len(incoming & existing)}

    @staticmethod
    def _number(value, field):
        try:
            return float(value)
        except (TypeError, ValueError) as error:
            raise ImportValidationError(f'{field} 必须是数字') from error

    def confirm(self, preview_id, mapping):
        preview = self.previews.get(preview_id)
        if preview is None:
            raise ImportValidationError('导入预览不存在或已过期')
        if not isinstance(mapping, dict):
            raise ImportValidationError('字段映射格式错误')
        source_type = preview['source_type']
        missing = SOURCE_REQUIREMENTS[source_type] - set(mapping)
        if missing:
            raise ImportValidationError(f'缺少必填字段映射：{", ".join(sorted(missing))}')
        unknown = set(mapping) - SOURCE_ALLOWED_FIELDS[source_type]
        if unknown:
            raise ImportValidationError(f'不允许映射字段：{", ".join(sorted(unknown))}')
        for field, column in mapping.items():
            if column not in preview['frame'].columns:
                raise ImportValidationError(f'映射列不存在：{column}')

        quality = self._quality(preview['frame'], mapping, source_type)
        if quality['invalid_rows']:
            detail = quality['invalid_details'][0]['message'] if quality['invalid_details'] else '存在无效行'
            raise ImportValidationError(f'导入前质量校验未通过：{quality["invalid_rows"]} 行无效；首项：{detail}')
        if quality['duplicate_keys']:
            raise ImportValidationError(f'导入前质量校验未通过：发现 {quality["duplicate_keys"]} 个重复业务键')
        preview['quality'] = quality

        if source_type != 'product_day':
            return self._confirm_generic(preview, mapping)
        rows = []
        for _, source in preview['frame'].iterrows():
            try:
                product_id = str(source[mapping['product_id']]).strip()
                if not product_id:
                    raise ImportValidationError('商品 ID 不能为空')
                stat_date = pd.to_datetime(source[mapping['date']]).date().isoformat()
                payment_amount = self._number(source[mapping['payment_amount']], '支付金额')
                refund_amount = self._number(source[mapping['successful_refund_amount']], '成功退款金额')
                rows.append({
                    'product_id': product_id,
                    'product_name': str(source[mapping.get('product_name', '')]).strip() if mapping.get('product_name') else '',
                    'date': stat_date,
                    'payment_amount': payment_amount,
                    'successful_refund_amount': refund_amount,
                    'net_sales': payment_amount - refund_amount,
                    'product_visitors': int(self._number(source[mapping['product_visitors']], '商品访客数')),
                    'payment_buyers': int(self._number(source[mapping['payment_buyers']], '支付买家数')),
                    'ad_spend': self._number(source[mapping['ad_spend']], '推广花费'),
                })
            except (TypeError, ValueError, ImportValidationError) as error:
                raise ImportValidationError(f'导入行无效：{error}') from error

        batch = {
            'id': uuid4().hex,
            'source_type': preview['source_type'],
            'source_filename': preview['source_filename'],
            'source_hash': preview['source_hash'],
            'total_rows': preview['quality']['total_rows'],
            'valid_rows': len(rows),
            'invalid_rows': 0,
            'quality_summary': json.dumps(preview['quality'], ensure_ascii=False),
        }
        inserted_count, updated_count = ImportRepo.complete_product_daily_batch(batch, rows)
        self.previews.pop(preview_id, None)
        return {'id': batch['id'], 'inserted_count': inserted_count, 'updated_count': updated_count}

    def _confirm_generic(self, preview, mapping):
        source_type = preview['source_type']
        target = {
            'store_day': ('store_daily_facts', ('shop_id', 'date')),
            'refund_day': ('store_daily_facts', ('shop_id', 'date')),
            'customer_day': ('store_daily_facts', ('shop_id', 'date')),
            'product_week': ('weekly_data', ('product_id', 'week_start')),
            'product_month': ('monthly_data', ('product_id', 'month')),
            'promotion_channel_day': ('promotion_daily_facts', ('shop_id','date','channel','campaign_id','unit_id','product_id')),
            'promotion_campaign_day': ('promotion_daily_facts', ('shop_id','date','channel','campaign_id','unit_id','product_id')),
            'promotion_unit_day': ('promotion_daily_facts', ('shop_id','date','channel','campaign_id','unit_id','product_id')),
            'promotion_product_day': ('promotion_daily_facts', ('shop_id','date','channel','campaign_id','unit_id','product_id')),
        }.get(source_type)
        if not target:
            raise ImportValidationError('不支持的导入目标')
        table_name, key_columns = target
        rows = []
        for _, source in preview['frame'].iterrows():
            def value(name, default=None):
                column = mapping.get(name)
                return source[column] if column else default
            stat_date = pd.to_datetime(value('date')).date().isoformat()
            if table_name == 'store_daily_facts':
                row = {'shop_id': 'default', 'date': stat_date, 'source_batch_id': preview['id']}
                numeric = {
                    'payment_amount': ('payment_amount', '支付金额', float),
                    'successful_refund_amount': ('successful_refund_amount', '退款金额', float),
                    'product_visitors': ('product_visitors', '商品访客数', int),
                    'payment_buyers': ('payment_buyers', '支付买家数', int),
                    'returning_payment_buyers': ('returning_payment_buyers', '老客买家数', int),
                    'ad_spend': ('ad_spend', '推广花费', float),
                }
                for field, (mapped, label, cast) in numeric.items():
                    if mapped in mapping:
                        row[field] = cast(self._number(value(mapped), label))
                rows.append(row)
            elif table_name == 'promotion_daily_facts':
                rows.append({
                    'shop_id':'default','date':stat_date,'channel':str(value('channel')).strip(),
                    'campaign_id':str(value('campaign_id','')).strip(), 'unit_id':str(value('unit_id','')).strip(),
                    'product_id':str(value('product_id','')).strip(), 'ad_spend':self._number(value('ad_spend'), '推广花费'),
                    'attributed_payment_amount':self._number(value('attributed_payment_amount'), '推广成交金额'),
                    'impressions':int(self._number(value('impressions',0), '展现量')) if 'impressions' in mapping else None,
                    'clicks':int(self._number(value('clicks',0), '点击量')) if 'clicks' in mapping else None,
                    'payment_buyers':int(self._number(value('payment_buyers',0), '支付买家数')) if 'payment_buyers' in mapping else None,
                    'direct_payment_amount':self._number(value('direct_payment_amount'), 'direct_payment_amount') if 'direct_payment_amount' in mapping else None,
                    'indirect_payment_amount':self._number(value('indirect_payment_amount'), 'indirect_payment_amount') if 'indirect_payment_amount' in mapping else None,
                    'source_batch_id':preview['id'],
                })
            else:
                product_id = str(value('product_id')).strip()
                period_column = 'week_start' if table_name == 'weekly_data' else 'month'
                row = {'product_id': product_id, period_column: stat_date if period_column == 'week_start' else stat_date[:7],
                       'payment_amount': self._number(value('payment_amount'), '支付金额'),
                       'refund_amount': self._number(value('successful_refund_amount'), '退款金额'),
                       'net_sales': self._number(value('payment_amount'), '支付金额') - self._number(value('successful_refund_amount'), '退款金额'),
                       'ad_spend': self._number(value('ad_spend'), '推广花费')}
                row['ipv' if table_name == 'weekly_data' else 'visitors'] = int(self._number(value('product_visitors'), '商品访客数'))
                rows.append(row)
        if source_type in {'refund_day', 'customer_day'}:
            rows = self._merge_store_rows_with_existing(rows)
        batch = {'id': uuid4().hex, 'source_type': source_type, 'source_filename': preview['source_filename'], 'source_hash': preview['source_hash'], 'total_rows':preview['quality']['total_rows'], 'valid_rows':len(rows), 'invalid_rows':0, 'quality_summary':json.dumps(preview['quality'],ensure_ascii=False)}
        for row in rows:
            if 'source_batch_id' in row:
                row['source_batch_id'] = batch['id']
        inserted_count, updated_count = ImportRepo.complete_generic_batch(batch, table_name, key_columns, rows)
        self.previews.pop(preview['id'], None)
        return {'id':batch['id'], 'inserted_count':inserted_count, 'updated_count':updated_count}

    @staticmethod
    def _merge_store_rows_with_existing(rows):
        """Keep source-specific upserts from clearing fields supplied by earlier store facts."""
        from db import get_db
        with get_db() as connection:
            for row in rows:
                existing = connection.execute(
                    'SELECT * FROM store_daily_facts WHERE shop_id = ? AND date = ?',
                    (row['shop_id'], row['date']),
                ).fetchone()
                if existing:
                    for key, value in dict(existing).items():
                        if key not in row and key not in {'source_batch_id'}:
                            row[key] = value
        return rows

    def list_batches(self):
        batches = ImportRepo.list_batches()
        for batch in batches:
            batch['quality_summary'] = json.loads(batch['quality_summary'])
        return batches

    def revert(self, batch_id):
        try:
            result = ImportRepo.revert_batch(batch_id)
        except ImportRevertConflictError as error:
            raise ImportConflictError(str(error)) from error
        if result is None:
            raise ImportValidationError('导入批次不存在')
        if result is False:
            raise ImportValidationError('导入批次已撤销')
        return {'id': batch_id, 'reverted': True}


class ImportConflictError(ImportValidationError):
    pass


import_service = ImportService()
