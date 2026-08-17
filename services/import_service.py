import hashlib
import io
import json
import math
import os
from html.parser import HTMLParser
from zipfile import BadZipFile, ZipFile
from datetime import date
from uuid import uuid4

import pandas as pd

from db import get_db
from repos.import_repo import ImportRepo, ImportRevertConflictError, ImportRevertScopeError


LEGACY_PRODUCT_REQUIRED_FIELDS = {
    'date', 'product_id', 'payment_amount', 'successful_refund_amount',
    'product_visitors', 'payment_buyers',
}

# DS keeps the base fact import usable when optional buyer/refund enrichments
# arrive in separate files. Keep the product/day grain and core measures here;
# mapped optional fields are still persisted without overwriting absent values.
PRODUCT_DAY_REQUIRED_FIELDS = {
    'date', 'product_id', 'payment_amount', 'product_visitors',
}

PRODUCT_DAY_OPTIONAL_FIELDS = {
    'successful_refund_amount', 'payment_buyers',
    'product_name', 'parent_product_id', 'product_type', 'sku_code', 'source_status', 'product_tags',
    'product_growth_stage',
    'page_views', 'avg_stay_duration', 'bounce_rate', 'favorite_users', 'cart_items', 'cart_users',
    'paid_visitors', 'organic_visitors', 'recommend_visitors', 'ad_roi', 'favorite_cart_rate',
    'repurchase_rate', 'presale_amount', 'presale_qty', 'search_click_rate', 'payment_unit_price',
    'cross_sell_qty', 'cross_sell_rate', 'cross_sell_categories', 'category_width', 'repurchase_users',
    'order_buyers', 'order_items', 'order_amount', 'order_conversion', 'payment_items',
    'payment_conversion', 'new_payment_buyers', 'returning_payment_buyers', 'returning_payment_amount',
    'juhuasuan_payment_amount', 'uv_value', 'competitiveness_score', 'year_to_date_payment_amount',
    'month_to_date_payment_amount', 'month_to_date_payment_items', 'search_conversion', 'search_visitors',
    'search_payment_buyers', 'structured_detail_conversion', 'structured_detail_payment_ratio', 'ad_spend',
}

SOURCE_REQUIREMENTS = {
    'product_day': PRODUCT_DAY_REQUIRED_FIELDS,
    'dmp_product_day': PRODUCT_DAY_REQUIRED_FIELDS,
    'store_day': {'date', 'payment_amount', 'successful_refund_amount', 'product_visitors', 'payment_buyers'},
    'product_week': LEGACY_PRODUCT_REQUIRED_FIELDS,
    'product_month': LEGACY_PRODUCT_REQUIRED_FIELDS,
    'promotion_channel_day': {'date', 'channel', 'ad_spend', 'attributed_payment_amount'},
    'promotion_campaign_day': {'date', 'channel', 'campaign_id', 'ad_spend', 'attributed_payment_amount'},
    'promotion_unit_day': {'date', 'channel', 'campaign_id', 'unit_id', 'ad_spend', 'attributed_payment_amount'},
    'promotion_product_day': {'date', 'channel', 'product_id', 'ad_spend', 'attributed_payment_amount'},
    'refund_day': {'date', 'successful_refund_amount'},
    'customer_day': {'date', 'payment_buyers', 'returning_payment_buyers'},
}

SOURCE_KEY_FIELDS = {
    'product_day': ('date', 'product_id'),
    'dmp_product_day': ('date', 'product_id'),
    'store_day': ('date',), 'refund_day': ('date',), 'customer_day': ('date',),
    'product_week': ('date', 'product_id'), 'product_month': ('date', 'product_id'),
    'promotion_channel_day': ('date', 'channel'),
    'promotion_campaign_day': ('date', 'channel', 'campaign_id'),
    'promotion_unit_day': ('date', 'channel', 'campaign_id', 'unit_id'),
    'promotion_product_day': ('date', 'channel', 'product_id'),
}

SOURCE_ALLOWED_FIELDS = {
    'product_day': PRODUCT_DAY_REQUIRED_FIELDS | PRODUCT_DAY_OPTIONAL_FIELDS,
    'dmp_product_day': PRODUCT_DAY_REQUIRED_FIELDS | PRODUCT_DAY_OPTIONAL_FIELDS,
    'store_day': SOURCE_REQUIREMENTS['store_day'] | {'ad_spend', 'returning_payment_buyers'},
    'refund_day': SOURCE_REQUIREMENTS['refund_day'],
    'customer_day': SOURCE_REQUIREMENTS['customer_day'],
    'product_week': LEGACY_PRODUCT_REQUIRED_FIELDS | {'product_name', 'ad_spend'},
    'product_month': LEGACY_PRODUCT_REQUIRED_FIELDS | {'product_name', 'ad_spend'},
    'promotion_channel_day': SOURCE_REQUIREMENTS['promotion_channel_day'] | {'impressions', 'clicks', 'payment_buyers', 'direct_payment_amount', 'indirect_payment_amount'},
    'promotion_campaign_day': SOURCE_REQUIREMENTS['promotion_campaign_day'] | {'impressions', 'clicks', 'payment_buyers', 'direct_payment_amount', 'indirect_payment_amount'},
    'promotion_unit_day': SOURCE_REQUIREMENTS['promotion_unit_day'] | {'impressions', 'clicks', 'payment_buyers', 'direct_payment_amount', 'indirect_payment_amount'},
    'promotion_product_day': SOURCE_REQUIREMENTS['promotion_product_day'] | {'impressions', 'clicks', 'payment_buyers', 'direct_payment_amount', 'indirect_payment_amount'},
}

NUMERIC_FIELDS = {
    'payment_amount', 'successful_refund_amount', 'product_visitors', 'payment_buyers',
    'returning_payment_buyers', 'ad_spend', 'attributed_payment_amount', 'impressions',
    'clicks', 'direct_payment_amount', 'indirect_payment_amount',
    'page_views', 'avg_stay_duration', 'favorite_users', 'cart_items', 'cart_users',
    'order_buyers', 'order_items', 'order_amount', 'payment_items', 'new_payment_buyers',
    'returning_payment_amount', 'juhuasuan_payment_amount', 'uv_value', 'competitiveness_score',
    'year_to_date_payment_amount', 'month_to_date_payment_amount', 'month_to_date_payment_items',
    'search_visitors', 'search_payment_buyers',
    'paid_visitors', 'organic_visitors', 'recommend_visitors', 'ad_roi', 'presale_amount', 'presale_qty',
    'payment_unit_price', 'cross_sell_qty', 'cross_sell_categories', 'category_width', 'repurchase_users',
}

PERCENTAGE_FIELDS = {
    'bounce_rate', 'order_conversion', 'payment_conversion', 'search_conversion',
    'structured_detail_conversion', 'structured_detail_payment_ratio', 'favorite_cart_rate',
    'repurchase_rate', 'search_click_rate', 'cross_sell_rate',
}

FIELD_ALIASES = {
    'direct_payment_amount': {'直接成交金额', 'direct_payment_amount'},
    'indirect_payment_amount': {'间接成交金额', 'indirect_payment_amount'},
    'date': {'日期', '统计日期', '时间', 'stat_date', 'date', 'day'},
    'product_id': {'商品ID', '宝贝ID', '主体ID', 'product_id'},
    'product_name': {'商品名称', '宝贝名称', '主体名称', 'product_name'},
    'payment_amount': {'支付金额', '成交金额', 'GMV', 'payment_amount'},
    'successful_refund_amount': {'退款金额', '成功退款金额', 'refund_amount'},
    'product_visitors': {'商品访客数', '访客数', '访客人数', 'IPV', 'ipv'},
    'payment_buyers': {'支付买家数', '支付人数', '买家数', '成交人数', 'buyers'},
    'ad_spend': {'推广花费', '花费', '营销推广消耗', 'ad_spend'},
    'paid_visitors': {'营销推广IPV', '付费访客数', 'paid_ipv'},
    'organic_visitors': {'非推广IPV', '自然访客数', 'organic_ipv'},
    'recommend_visitors': {'推荐IPV', '推荐访客数', 'recommend_ipv'},
    'ad_roi': {'营销推广ROI', '推广ROI', '投产', 'ad_roi'},
    'favorite_cart_rate': {'收加率', '收藏加购率', 'favorite_cart_rate'},
    'repurchase_rate': {'复购率', 'repurchase_rate'},
    'presale_amount': {'预售支付金额', '预售金额', 'presale_amount'},
    'presale_qty': {'预售销量', '预售件数', 'presale_qty'},
    'search_click_rate': {'免费搜索点击率', '搜索点击率', 'search_click_rate'},
    'payment_unit_price': {'笔单价', '支付笔单价', '客单价', 'payment_unit_price'},
    'cross_sell_qty': {'连带购买量', '连带购买件数', 'cross_sell_qty'},
    'cross_sell_rate': {'连带购买率', '搭配购买率', 'cross_sell_rate'},
    'cross_sell_categories': {'连带购买叶子类目宽度', '连带购买类目数', 'cross_sell_categories'},
    'repurchase_users': {'复购用户数', '复购买家数', 'repurchase_users'},
    'product_growth_stage': {'货品成长阶段', '商品成长阶段', 'lifecycle_stage', 'growth_stage'},
    'channel': {'渠道', '推广渠道', '场景名字', '场景名称', 'channel'},
    'campaign_id': {'计划ID', '推广计划ID', 'campaign_id'},
    'unit_id': {'单元ID', '推广单元ID', 'unit_id'},
    'attributed_payment_amount': {'推广成交金额', '归因成交金额', '总成交金额', 'attributed_payment_amount'},
    'impressions': {'展现量', '曝光量', 'impressions'},
    'clicks': {'点击量', 'clicks'},
    'returning_payment_buyers': {'老客支付买家数', '老客买家数', '支付老买家数', 'returning_payment_buyers'},
    'parent_product_id': {'主商品ID', 'parent_product_id'},
    'product_type': {'商品类型', 'product_type'},
    'sku_code': {'货号', 'sku_code'},
    'source_status': {'商品状态', 'source_status'},
    'product_tags': {'商品标签', 'product_tags'},
    'page_views': {'商品浏览量', '浏览量', 'page_views', 'pv'},
    'avg_stay_duration': {'平均停留时长', 'avg_stay_duration'},
    'bounce_rate': {'商品详情页跳出率', '跳出率', 'bounce_rate'},
    'favorite_users': {'商品收藏人数', '收藏人数', 'favorite_users', 'fav_users'},
    'cart_items': {'商品加购件数', '加购件数', 'cart_items', 'cart_qty'},
    'cart_users': {'商品加购人数', '加购人数', 'cart_users'},
    'order_buyers': {'下单买家数', 'order_buyers'},
    'order_items': {'下单件数', 'order_items'},
    'order_amount': {'下单金额', 'order_amount'},
    'order_conversion': {'下单转化率', 'order_conversion'},
    'payment_items': {'支付件数', 'payment_items', 'payment_qty'},
    'payment_conversion': {'商品支付转化率', '支付转化率', 'payment_conversion'},
    'new_payment_buyers': {'支付新买家数', 'new_payment_buyers'},
    'returning_payment_amount': {'老买家支付金额', 'returning_payment_amount'},
    'juhuasuan_payment_amount': {'聚划算支付金额', 'juhuasuan_payment_amount'},
    'uv_value': {'访客平均价值', 'uv_value'},
    'competitiveness_score': {'竞争力评分', 'competitiveness_score'},
    'year_to_date_payment_amount': {'年累计支付金额', 'year_to_date_payment_amount'},
    'month_to_date_payment_amount': {'月累计支付金额', 'month_to_date_payment_amount'},
    'month_to_date_payment_items': {'月累计支付件数', 'month_to_date_payment_items'},
    'search_conversion': {'搜索引导支付转化率', 'search_conversion'},
    'search_visitors': {'搜索引导访客数', '搜索IPV', 'search_visitors'},
    'search_payment_buyers': {'搜索引导支付买家数', 'search_payment_buyers'},
    'structured_detail_conversion': {'结构化详情引导转化率', 'structured_detail_conversion'},
    'structured_detail_payment_ratio': {'结构化详情引导成交占比', 'structured_detail_payment_ratio'},
}


_NATIVE_FIELD_ALIASES = {
    'date': {'\u65e5\u671f'},
    'product_id': {'\u5b9d\u8d1dID'},
    'product_name': {'\u5b9d\u8d1d\u540d\u79f0'},
    'product_growth_stage': {'\u8d27\u54c1\u6210\u957f\u9636\u6bb5'},
    'payment_amount': {'\u652f\u4ed8\u91d1\u989d'},
    'product_visitors': {'IPV'},
    'paid_visitors': {'\u8425\u9500\u63a8\u5e7fIPV'},
    'organic_visitors': {'\u975e\u63a8\u5e7fIPV'},
    'recommend_visitors': {'\u63a8\u8350IPV'},
    'ad_spend': {'\u8425\u9500\u63a8\u5e7f\u6d88\u8017'},
    'ad_roi': {'\u8425\u9500\u63a8\u5e7fROI'},
    'favorite_cart_rate': {'\u6536\u85cf\u7387'},
    'payment_conversion': {'\u652f\u4ed8\u8f6c\u5316\u7387'},
    'repurchase_rate': {'\u590d\u8d2d\u7387'},
    'presale_amount': {'\u9884\u552e\u652f\u4ed8\u91d1\u989d'},
    'presale_qty': {'\u9884\u552e\u9500\u91cf'},
    'search_click_rate': {'\u514d\u8d39\u641c\u7d22\u70b9\u51fb\u7387'},
    'payment_unit_price': {'\u7b14\u5355\u4ef7'},
    'cross_sell_qty': {'\u8fde\u5e26\u8d2d\u4e70\u91cf'},
    'cross_sell_rate': {'\u8fde\u5e26\u8d2d\u4e70\u7387'},
    'cross_sell_categories': set(),
    'category_width': {'\u8fde\u5e26\u8d2d\u4e70\u53f6\u5b50\u7c7b\u76ee\u5bbd\u5ea6'},
    'repurchase_users': {'\u590d\u8d2d\u7528\u6237\u6570'},
}
for _field, _aliases in _NATIVE_FIELD_ALIASES.items():
    FIELD_ALIASES[_field] = set(FIELD_ALIASES.get(_field, set())) | _aliases


class ImportValidationError(ValueError):
    pass


class ImportScopeError(ImportValidationError):
    """Raised when a legacy single-shop import is attempted for another shop."""


class _HtmlTableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tables = []
        self.table = None
        self.row = None
        self.cell = None

    def handle_starttag(self, tag, attrs):
        if tag == 'table':
            self.table = []
        elif tag == 'tr' and self.table is not None:
            self.row = []
        elif tag in {'td', 'th'} and self.row is not None:
            self.cell = []

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if tag in {'td', 'th'} and self.cell is not None:
            self.row.append(''.join(self.cell).strip())
            self.cell = None
        elif tag == 'tr' and self.row is not None:
            self.table.append(self.row)
            self.row = None
        elif tag == 'table' and self.table is not None:
            if self.table:
                self.tables.append(self.table)
            self.table = None


class ImportService:
    PREVIEW_TTL_SECONDS = 24 * 60 * 60

    def __init__(self):
        self.previews = {}

    def cleanup_expired_previews(self, ttl_seconds=None):
        """Remove abandoned preview payloads from memory and persistent storage."""
        ttl = self.PREVIEW_TTL_SECONDS if ttl_seconds is None else max(0, int(ttl_seconds))
        modifier = f'-{ttl} seconds'
        with get_db() as connection:
            expired_ids = [row['id'] for row in connection.execute(
                "SELECT id FROM import_previews WHERE created_at < datetime('now', ?)",
                (modifier,),
            ).fetchall()]
            if expired_ids:
                placeholders = ','.join('?' for _ in expired_ids)
                connection.execute(
                    f'DELETE FROM import_previews WHERE id IN ({placeholders})',
                    expired_ids,
                )
            active_ids = {
                row['id'] for row in connection.execute('SELECT id FROM import_previews').fetchall()
            }
            connection.commit()
        memory_ids = set(self.previews)
        stale_memory_ids = memory_ids - active_ids
        for preview_id in stale_memory_ids:
            self.previews.pop(preview_id, None)
        return len(set(expired_ids) | stale_memory_ids)

    @staticmethod
    def _load_preview(preview_id, shop_id=None):
        if shop_id is None:
            from db import get_shop_id
            shop_id = get_shop_id()
        with get_db() as connection:
            row = connection.execute(
                '''SELECT id, shop_id, source_type, source_filename, source_hash, content, mapping_json, quality_summary
                   FROM import_previews WHERE id = ? AND shop_id = ?''',
                (preview_id, shop_id),
            ).fetchone()
        if row is None:
            return None
        preview = dict(row)
        preview['frame'] = ImportService._read_workbook(preview.pop('content'), preview['source_filename'])
        preview['mapping'] = json.loads(preview.pop('mapping_json'))
        preview['quality'] = json.loads(preview.pop('quality_summary'))
        return preview

    @staticmethod
    def _delete_preview(preview_id, shop_id=None):
        if shop_id is None:
            from db import get_shop_id
            shop_id = get_shop_id()
        with get_db() as connection:
            connection.execute('DELETE FROM import_previews WHERE id = ? AND shop_id = ?', (preview_id, shop_id))
            connection.commit()

    @staticmethod
    def _infer_type(series):
        series = series.dropna()
        if series.empty:
            return 'empty'
        normalized = series.map(lambda value: str(value).replace(',', '').replace('，', '').replace('%', '').strip())
        numeric = pd.to_numeric(normalized, errors='coerce')
        if numeric.notna().all():
            return 'integer' if (numeric % 1 == 0).all() else 'decimal'
        parsed = pd.to_datetime(series, format='mixed', errors='coerce')
        return 'date' if parsed.notna().all() else 'text'

    @staticmethod
    def _mapping(columns):
        mapping = {}
        for field, aliases in FIELD_ALIASES.items():
            normalized_aliases = {
                ImportService._normalize_column(alias)
                for alias in aliases | {field}
            }
            match = next(
                (
                    column for column in columns
                    if ImportService._normalize_column(str(column)) in normalized_aliases
                ),
                None,
            )
            if match is not None:
                mapping[field] = str(match)
        # The DMP export's leaf-category width used to be treated as the
        # broader cross-sell category count. Keep the native field distinct.
        if mapping.get('category_width') and mapping.get('cross_sell_categories') == mapping.get('category_width'):
            mapping.pop('category_width', None)
        return mapping

    @staticmethod
    def _detect_source_type(mapping):
        mapped = set(mapping)
        dmp_signature = {
            'paid_visitors', 'organic_visitors', 'recommend_visitors',
            'repurchase_rate', 'presale_amount', 'search_click_rate',
            'cross_sell_qty', 'repurchase_users',
        }
        if SOURCE_REQUIREMENTS['dmp_product_day'] <= mapped and len(mapped & dmp_signature) >= 2:
            return 'dmp_product_day'
        candidates = (
            'promotion_unit_day',
            'promotion_campaign_day',
            'promotion_product_day',
            'promotion_channel_day',
            'product_day',
            'dmp_product_day',
            'store_day',
            'refund_day',
            'customer_day',
        )
        detected = next(
            (candidate for candidate in candidates if SOURCE_REQUIREMENTS[candidate] <= mapped),
            None,
        )
        if detected is None:
            raise ImportValidationError('无法自动识别报表类型，请手动选择正确的报表类型')
        return detected

    @staticmethod
    def _normalize_column(value):
        return ''.join(
            character for character in str(value).strip().lower()
            if not character.isspace() and character not in '()（）_-/ '
        )

    @staticmethod
    def _drop_summary_rows(frame):
        if frame.empty or frame.shape[1] == 0:
            return frame
        summary_markers = {'总计', '合计', '汇总', '总和', '\u603b\u8ba1', '\u5408\u8ba1', '\u6c47\u603b', '\u603b\u548c'}
        first_column = frame.iloc[:, 0].map(lambda value: str(value).strip())
        filtered = frame.loc[~first_column.isin(summary_markers)].reset_index(drop=True)
        filtered.attrs.update(frame.attrs)
        filtered.attrs['raw_total_rows'] = len(frame.index)
        filtered.attrs['excluded_summary_rows'] = len(frame.index) - len(filtered.index)
        return filtered

    @staticmethod
    def _date(value):
        text = str(value).strip()
        if text.endswith('.0'):
            text = text[:-2]
        if len(text) == 8 and text.isdigit():
            return pd.to_datetime(text, format='%Y%m%d').date().isoformat()
        return pd.to_datetime(value).date().isoformat()

    @staticmethod
    def _read_csv(content):
        for encoding in ('utf-8-sig', 'gb18030', 'gbk'):
            try:
                return pd.read_csv(io.BytesIO(content), dtype=object, encoding=encoding)
            except UnicodeDecodeError:
                continue
            except pd.errors.ParserError as error:
                raise ImportValidationError('CSV 文件格式不正确') from error
        raise ImportValidationError('无法识别 CSV 文件编码')

    @staticmethod
    def _read_html_xls(content):
        for encoding in ('utf-8-sig', 'gb18030', 'gbk'):
            try:
                parser = _HtmlTableParser()
                parser.feed(content.decode(encoding))
            except UnicodeDecodeError:
                continue
            if not parser.tables:
                continue
            header, *rows = parser.tables[0]
            if header:
                return pd.DataFrame(rows, columns=header, dtype=object)
        raise ImportValidationError('无法读取表格文件')

    @staticmethod
    def _promote_header(frame):
        """Business-advisor exports often put title rows before the real header."""
        aliases = set().union(*FIELD_ALIASES.values())
        for index in range(min(len(frame), 15)):
            row = frame.iloc[index]
            matches = sum(str(value).strip() in aliases for value in row if not pd.isna(value))
            if matches >= 2:
                promoted = frame.iloc[index + 1:].copy()
                promoted.columns = [str(value).strip() for value in row]
                return promoted.reset_index(drop=True)
        return frame

    @staticmethod
    def _read_workbook(content, filename=''):
        suffix = os.path.splitext(filename)[1].lower()
        try:
            if suffix == '.csv':
                frame = ImportService._read_csv(content)
            elif suffix == '.zip':
                with ZipFile(io.BytesIO(content)) as archive:
                    entries = [
                        entry for entry in archive.infolist()
                        if not entry.is_dir() and os.path.splitext(entry.filename)[1].lower() in {'.xlsx', '.xls', '.csv'}
                    ]
                    for entry in entries:
                        archive_name = entry.filename.replace('\\', '/')
                        if archive_name.startswith('/') or any(part == '..' for part in archive_name.split('/')):
                            raise ImportValidationError('ZIP 内部文件路径不安全')
                        if entry.file_size > 25 * 1024 * 1024:
                            raise ImportValidationError('ZIP 内部文件解压后超过 25 MB 限制')
                    if not entries:
                        raise ImportValidationError('ZIP 压缩包中没有 .xlsx、.xls 或 .csv 文件')
                    if len(entries) != 1:
                        raise ImportValidationError('数据中心一次预览一个数据源；ZIP 压缩包请只包含一份 .xlsx、.xls 或 .csv 文件')
                    entry = entries[0]
                    return ImportService._read_workbook(archive.read(entry), entry.filename)
            else:
                try:
                    frame = pd.read_excel(io.BytesIO(content), dtype=object)
                except Exception:
                    if suffix != '.xls':
                        raise
                    frame = ImportService._read_html_xls(content)
        except ImportValidationError:
            raise
        except BadZipFile as error:
            raise ImportValidationError('ZIP 压缩包已损坏或格式不正确') from error
        except Exception as error:
            raise ImportValidationError('无法读取表格文件') from error
        if frame.empty:
            raise ImportValidationError('表格文件没有数据行')
        return ImportService._drop_summary_rows(ImportService._promote_header(frame))

    @staticmethod
    def _quality(frame, mapping, source_type):
        required = SOURCE_REQUIREMENTS[source_type]
        key_fields = SOURCE_KEY_FIELDS[source_type]
        keys = []
        dates = []
        product_ids = set()
        invalid_details = []
        field_warnings = []
        invalid_field_rows = []
        invalid_field_count = 0
        invalid_rows = 0
        for index, row in frame.iterrows():
            values = {}
            try:
                stat_date = ImportService._date(row[mapping['date']])
                values = {'date': stat_date}
                for field in required:
                    if field == 'date':
                        continue
                    value = row[mapping[field]]
                    if pd.isna(value) or (isinstance(value, str) and not value.strip()):
                        raise ValueError(f'{field} 不能为空')
                    if field in NUMERIC_FIELDS:
                        ImportService._number(value, field)
                        float(str(value).replace(',', '').replace('，', '').strip())
                    values[field] = str(value).strip()
                for field, column in mapping.items():
                    raw = row[column]
                    if pd.isna(raw) or str(raw).strip() in {'', '-', '--'}:
                        continue
                    if field in PERCENTAGE_FIELDS and source_type != 'dmp_product_day':
                        normalized = ImportService._optional_number(raw, percentage=True)
                        if normalized is None or not 0 <= normalized <= 1:
                            raise ValueError(f'{field} 超出 0 到 1 的比例范围')
                if source_type == 'dmp_product_day':
                    for field, column in mapping.items():
                        raw = row[column]
                        if pd.isna(raw) or str(raw).strip() in {'', '-', '--'}:
                            continue
                        if field in PERCENTAGE_FIELDS or (field in NUMERIC_FIELDS and field not in required):
                            try:
                                ImportService._optional_number(raw, percentage=field in PERCENTAGE_FIELDS)
                                if field in PERCENTAGE_FIELDS:
                                    normalized = ImportService._optional_number(raw, percentage=True)
                                    if normalized is None or not 0 <= normalized <= 1:
                                        raise ValueError(f'{field} out of range 0..1')
                            except (TypeError, ValueError) as error:
                                if field in required:
                                    raise
                                invalid_field_count += 1
                                invalid_field_rows.append({'row_number': int(index) + 2, 'standard_field': field})
                                if len(field_warnings) < 200:
                                    field_warnings.append({'row_number': int(index) + 2,
                                        'standard_field': field,
                                        'raw_value': str(raw),
                                        'reason': str(error) or f'{field} value is invalid'})
                keys.append(tuple(values[field] for field in key_fields))
                dates.append(stat_date)
                if values.get('product_id'):
                    product_ids.add(values['product_id'])
            except Exception as error:
                invalid_rows += 1
                if len(invalid_details) < 25:
                    invalid_details.append({
                        'row_number': int(index) + 2,
                        'standard_field': 'date' if 'date' in mapping else next(iter(required), None),
                        'raw_value': row[mapping['date']] if 'date' in mapping else None,
                        'reason': str(error) or '日期或必填字段无效',
                    })
        duplicates = len(keys) - len(set(keys))
        return {
            'total_rows': len(frame.index),
            'raw_total_rows': int(frame.attrs.get('raw_total_rows', len(frame.index))),
            'excluded_summary_rows': int(frame.attrs.get('excluded_summary_rows', 0)),
            'valid_rows': len(frame.index) - invalid_rows,
            'invalid_rows': invalid_rows,
            'date_range': {'start': min(dates) if dates else None, 'end': max(dates) if dates else None},
            'product_count': len(product_ids),
            'duplicate_keys': duplicates,
            'invalid_details': invalid_details,
            'invalid_field_count': invalid_field_count,
            'field_warnings': field_warnings,
            'invalid_field_rows': invalid_field_rows,
        }

    def _source_comparisons(self, frame, mapping, source_type, limit=100, shop_id='default'):
        if source_type != 'dmp_product_day':
            return []
        from services.source_resolution_service import DAILY_FIELD_COLUMNS, _choose, _load_candidates

        fields = [field for field in mapping if field in DAILY_FIELD_COLUMNS]
        comparisons = []
        with get_db() as connection:
            for _, source in frame.head(limit).iterrows():
                try:
                    product_id = str(source[mapping['product_id']]).strip()
                    stat_date = self._date(source[mapping['date']])
                except (KeyError, TypeError, ValueError, ImportValidationError):
                    continue
                for field in fields:
                    raw = source[mapping[field]]
                    if pd.isna(raw) or str(raw).strip() in {'', '-', '--'}:
                        dmp_value = None
                    else:
                        try:
                            dmp_value = self._optional_number(raw, percentage=field in PERCENTAGE_FIELDS)
                        except (TypeError, ValueError):
                            dmp_value = str(raw)
                    candidates = _load_candidates(
                        connection, product_id, stat_date, field, shop_id=shop_id,
                    )
                    if dmp_value is not None:
                        candidates.append(('dmp_product_day', 'dmp_product_day', None, dmp_value))
                    chosen = _choose(field, candidates)
                    if not chosen:
                        continue
                    by_source = {}
                    for candidate in candidates:
                        by_source.setdefault(candidate[0], candidate[3])
                    comparisons.append({
                        'product_id': product_id, 'date': stat_date, 'field_key': field,
                        'business_advisor_value': by_source.get('business_advisor'),
                        'promotion_tool_value': by_source.get('promotion_tool'),
                        'dmp_value': dmp_value, 'effective_value': chosen['value'],
                        'resolution_status': chosen['resolution_status'],
                        'reason': 'DMP fallback' if chosen['fallback_used'] else (
                            'DMP unique field' if chosen['source_role'] == 'effective_unique' else 'source precedence'
                        ),
                    })
        return comparisons

    def preview(self, filename, content, source_type='product_day', mapping_template=None):
        self.cleanup_expired_previews()
        if source_type != 'auto' and source_type not in SOURCE_REQUIREMENTS:
            raise ImportValidationError('不支持的 source_type')
        frame = self._read_workbook(content, filename)
        columns = [str(column).strip() for column in frame.columns]
        mapping = self._mapping(columns)
        if source_type == 'auto':
            source_type = self._detect_source_type(mapping)
        elif source_type == 'product_day':
            # Keep the legacy selector compatible while routing DMP exports
            # through the field-level source precedence path.
            source_type = self._detect_source_type(mapping) if (
                SOURCE_REQUIREMENTS['dmp_product_day'] <= set(mapping)
                and len(set(mapping) & {'paid_visitors', 'organic_visitors', 'recommend_visitors', 'repurchase_rate', 'presale_amount', 'search_click_rate'}) >= 2
            ) else source_type
        from db import get_shop_id
        shop_id = get_shop_id()
        if source_type in {'product_week', 'product_month'} and get_shop_id() != 'default':
            raise ImportScopeError(
                f'{source_type} 当前仍使用单店旧表，不支持非 default 店铺；请先完成周/月表店铺迁移'
            )
        template_keys = set()
        if mapping_template:
            for standard_key, source_column in mapping_template.items():
                if standard_key in SOURCE_ALLOWED_FIELDS[source_type] and str(source_column).strip() in columns:
                    mapping[standard_key] = str(source_column).strip()
                    template_keys.add(standard_key)
        required = SOURCE_REQUIREMENTS[source_type]
        quality = self._quality(frame, mapping, source_type) if required <= mapping.keys() else {
            'total_rows': len(frame.index), 'raw_total_rows': int(frame.attrs.get('raw_total_rows', len(frame.index))),
            'excluded_summary_rows': int(frame.attrs.get('excluded_summary_rows', 0)),
            'valid_rows': 0, 'invalid_rows': len(frame.index),
            'date_range': {'start': None, 'end': None}, 'product_count': 0, 'duplicate_keys': 0,
            'invalid_field_count': 0, 'field_warnings': [], 'invalid_field_rows': [],
             'invalid_details': [{'row_number': None, 'standard_field': sorted(required - set(mapping)), 'raw_value': None, 'reason': f'缺少必填映射：{", ".join(sorted(required - set(mapping)))}'}],
        }
        preview_id = uuid4().hex
        source_hash = hashlib.sha256(content).hexdigest()
        self.previews[preview_id] = {
            'id': preview_id,
            'shop_id': shop_id,
            'source_type': source_type,
            'source_filename': filename,
            'source_hash': source_hash,
            'frame': frame,
            'mapping': mapping,
            'quality': quality,
        }
        with get_db() as connection:
            connection.execute(
                '''INSERT INTO import_previews (
                       id, shop_id, source_type, source_filename, source_hash, content, mapping_json, quality_summary
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                (
                    preview_id, shop_id, source_type, filename, source_hash, content,
                    json.dumps(mapping, ensure_ascii=False), json.dumps(quality, ensure_ascii=False),
                ),
            )
            connection.commit()
        fields = []
        for column in columns:
            standard_key = next((key for key, source in mapping.items() if source == column), None)
            sample = frame[column].dropna().iloc[0] if not frame[column].dropna().empty else None
            series = frame[column].dropna()
            inferred_type = self._infer_type(series)
            match_status = 'unmatched'
            if standard_key:
                match_status = 'template' if standard_key in template_keys else ('exact' if column == standard_key else ('alias' if column in FIELD_ALIASES.get(standard_key, set()) else 'template'))
            fields.append({
                'source_column': column,
                'standard_key': standard_key,
                'sample_value': None if sample is None else str(sample),
                'inferred_type': inferred_type,
                'match_status': match_status,
                'matched': standard_key is not None,
            })
        quality['estimated_changes'] = self._estimate_changes(source_type, frame, mapping)
        if source_type == 'dmp_product_day':
            from services.source_resolution_service import DMP_UNIQUE_FIELDS, PRIMARY_SOURCES
            mapped_fields = set(mapping)
            primary_overlap = sorted(mapped_fields & set(PRIMARY_SOURCES))
            dmp_unique = sorted(mapped_fields & set(DMP_UNIQUE_FIELDS))
            field_modes = {}
            for field in sorted(mapped_fields):
                if field in DMP_UNIQUE_FIELDS:
                    field_modes[field] = {
                        'dmp_value_column': mapping[field],
                        'primary_source': None,
                        'dmp_role': 'effective_unique',
                    }
                elif field in PRIMARY_SOURCES:
                    field_modes[field] = {
                        'dmp_value_column': mapping[field],
                        'primary_source': PRIMARY_SOURCES[field],
                        'dmp_role': 'reference_only',
                    }
                else:
                    field_modes[field] = {
                        'dmp_value_column': mapping[field],
                        'primary_source': None,
                        'dmp_role': 'dmp_only',
                    }
            quality['source_resolution'] = {
                'policy': 'business_advisor_and_promotion_tool_primary',
                'primary_overlap_fields': primary_overlap,
                'dmp_unique_fields': dmp_unique,
                'reference_only_fields': primary_overlap,
                'field_modes': field_modes,
                'fallback_filled': 0,
                'conflicts': 0,
                'note': '预览阶段按字段口径分类；实际回退与冲突以导入后的字段血缘为准',
            }
        with get_db() as connection:
            if source_type == 'dmp_product_day':
                quality['source_resolution']['field_comparisons'] = self._source_comparisons(
                    frame, mapping, source_type, shop_id=shop_id,
                )
            connection.execute(
                'UPDATE import_previews SET quality_summary = ? WHERE id = ?',
                (json.dumps(quality, ensure_ascii=False), preview_id),
            )
            connection.commit()
        return {
            'id': preview_id,
            'source_type': source_type,
            'source_filename': filename,
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
        from db import get_db, get_shop_id
        shop_id = get_shop_id()
        target = {
            'product_day': ('daily_data', ('shop_id', 'product_id', 'date')),
            'dmp_product_day': ('daily_data', ('shop_id', 'product_id', 'date')),
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
                    if key == 'shop_id': value = shop_id
                    elif key in {'date', 'week_start', 'month'}:
                        raw = row[mapping['date']]
                        value = ImportService._date(raw)
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
                query_params = list(dates)
                if 'shop_id' in keys and table in {'daily_data', 'store_daily_facts', 'promotion_daily_facts'}:
                    query += ' AND shop_id = ?'
                    query_params.append(shop_id)
                rows = connection.execute(query, query_params)
            else:
                rows = connection.execute(f'SELECT {", ".join(keys)} FROM {table} WHERE 1=0')
            for row in rows:
                existing.add(tuple(str(value) for value in row))
        return {'available': True, 'inserted': len(incoming - existing), 'updated': len(incoming & existing)}

    @staticmethod
    def _number(value, field):
        if str(value).strip().lower() in {
            'nan', '+nan', '-nan', 'inf', '+inf', '-inf',
            'infinity', '+infinity', '-infinity',
        }:
            raise ImportValidationError(f'{field} must be a finite number')
        try:
            number = float(str(value).replace(',', '').replace('，', '').strip())
        except (TypeError, ValueError) as error:
            raise ImportValidationError(f'{field} 必须是数字') from error
        if not math.isfinite(number):
            raise ImportValidationError(f'{field} must be a finite number')
        return number

    @staticmethod
    def _optional_number(value, percentage=False):
        if value is None or pd.isna(value) or str(value).strip().lower() in {'', '-', '--', 'nan', 'none'}:
            return None
        text = str(value).replace(',', '').replace('，', '').strip()
        has_percent = text.endswith('%')
        number = float(text.rstrip('%'))
        if not math.isfinite(number):
            raise ValueError('numeric value must be finite')
        if percentage:
            return number / 100 if has_percent or abs(number) > 1 else number
        return number

    def confirm(self, preview_id, mapping):
        self.cleanup_expired_previews()
        from db import get_shop_id
        shop_id = get_shop_id()
        preview = self.previews.get(preview_id)
        if preview is not None and str(preview.get('shop_id') or 'default') != shop_id:
            raise ImportScopeError('导入预览不属于当前店铺')
        preview = preview or self._load_preview(preview_id, shop_id)
        if preview is None:
            raise ImportValidationError('导入预览不存在或已过期')
        if not isinstance(mapping, dict):
            raise ImportValidationError('字段映射格式错误')
        source_type = preview['source_type']
        if source_type in {'product_week', 'product_month'} and shop_id != 'default':
            raise ImportScopeError(
                f'{source_type} 当前仍使用单店旧表，不支持 shop_id={shop_id}；请先完成周/月表店铺迁移'
            )
        missing = SOURCE_REQUIREMENTS[source_type] - set(mapping)
        if missing:
            raise ImportValidationError(f'缺少必填字段映射：{", ".join(sorted(missing))}')
        unknown = set(mapping) - SOURCE_ALLOWED_FIELDS[source_type]
        if unknown:
            raise ImportValidationError(f'不允许映射字段：{", ".join(sorted(unknown))}')
        for field, column in mapping.items():
            if column not in preview['frame'].columns:
                raise ImportValidationError(f'映射列不存在：{column}')

        mapped_columns = list(mapping.values())
        duplicates = sorted({column for column in mapped_columns if mapped_columns.count(column) > 1})
        if duplicates:
            raise ImportValidationError(f'同一原始列不能映射多个标准字段：{", ".join(duplicates)}')
        quality = self._quality(preview['frame'], mapping, source_type)
        if quality['invalid_rows']:
            detail = quality['invalid_details'][0].get('reason', '存在无效行') if quality['invalid_details'] else '存在无效行'
            raise ImportValidationError(f'导入前质量校验未通过：{quality["invalid_rows"]} 行无效；首项：{detail}')
        if quality['duplicate_keys']:
            raise ImportValidationError(f'导入前质量校验未通过：发现 {quality["duplicate_keys"]} 个重复业务键')
        preview['quality'] = quality

        if source_type not in {'product_day', 'dmp_product_day'}:
            return self._confirm_generic(preview, mapping, shop_id)
        rows = []
        invalid_fields_by_row = {}
        for warning in quality.get('invalid_field_rows', quality.get('field_warnings', [])):
            row_number = int(warning['row_number']) - 2
            invalid_fields_by_row.setdefault(row_number, set()).add(warning['standard_field'])
        for row_index, source in preview['frame'].iterrows():
            try:
                product_id = str(source[mapping['product_id']]).strip()
                if not product_id:
                    raise ImportValidationError('商品 ID 不能为空')
                stat_date = self._date(source[mapping['date']])
                payment_amount = self._number(source[mapping['payment_amount']], '支付金额')
                row = {
                    'shop_id': shop_id,
                    'product_id': product_id,
                    'date': stat_date,
                    'payment_amount': payment_amount,
                    'product_visitors': int(self._number(source[mapping['product_visitors']], '商品访客数')),
                }
                text_fields = {
                    'product_name', 'parent_product_id', 'product_type', 'sku_code',
                    'source_status', 'product_tags', 'product_growth_stage',
                }
                for field in text_fields:
                    if mapping.get(field):
                        row[field] = str(source[mapping[field]]).strip()
                integer_fields = {
                    'payment_buyers', 'payment_items', 'page_views', 'favorite_users',
                    'cart_items', 'cart_users', 'order_buyers', 'order_items',
                    'new_payment_buyers', 'month_to_date_payment_items', 'search_visitors',
                    'search_payment_buyers', 'paid_visitors', 'organic_visitors',
                    'recommend_visitors', 'presale_qty', 'cross_sell_qty',
                    'cross_sell_categories', 'repurchase_users',
                }
                for field in PRODUCT_DAY_OPTIONAL_FIELDS - text_fields:
                    if not mapping.get(field):
                        continue
                    if source_type == 'dmp_product_day' and field in invalid_fields_by_row.get(row_index, set()):
                        continue
                    value = self._optional_number(
                        source[mapping[field]], percentage=field in PERCENTAGE_FIELDS,
                    )
                    if value is not None:
                        row[field] = int(value) if field in integer_fields else value
                if 'successful_refund_amount' in row and 'payment_amount' in row:
                    row['net_sales'] = payment_amount - row['successful_refund_amount']
                if 'payment_amount' in row and 'successful_refund_amount' not in row:
                    row.pop('net_sales', None)
                rows.append(row)
            except (TypeError, ValueError, ImportValidationError) as error:
                raise ImportValidationError(f'导入行无效：{error}') from error

        batch = {
            'id': uuid4().hex,
            'shop_id': shop_id,
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
        self._delete_preview(preview_id, shop_id)
        return self._report(batch, inserted_count, updated_count)

    def _confirm_generic(self, preview, mapping, shop_id=None):
        if shop_id is None:
            from db import get_shop_id
            shop_id = get_shop_id()
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
            stat_date = self._date(value('date'))
            if table_name == 'store_daily_facts':
                row = {'shop_id': shop_id, 'date': stat_date, 'source_batch_id': preview['id']}
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
                    'shop_id':shop_id,'date':stat_date,'channel':str(value('channel')).strip(),
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
        batch = {'id': uuid4().hex, 'shop_id': shop_id, 'source_type': source_type, 'source_filename': preview['source_filename'], 'source_hash': preview['source_hash'], 'total_rows':preview['quality']['total_rows'], 'valid_rows':len(rows), 'invalid_rows':0, 'quality_summary':json.dumps(preview['quality'],ensure_ascii=False)}
        for row in rows:
            if 'source_batch_id' in row:
                row['source_batch_id'] = batch['id']
        inserted_count, updated_count = ImportRepo.complete_generic_batch(batch, table_name, key_columns, rows)
        self.previews.pop(preview['id'], None)
        self._delete_preview(preview['id'], shop_id)
        return self._report(batch, inserted_count, updated_count)

    @staticmethod
    def _report(batch, inserted_count, updated_count):
        from db import get_db
        with get_db() as connection:
            completed = connection.execute(
                'SELECT completed_at, quality_summary FROM import_batches WHERE id = ?', (batch['id'],)
            ).fetchone()
        stored_quality = completed['quality_summary'] if completed else None
        quality = json.loads(stored_quality or '{}') if stored_quality else (
            json.loads(batch['quality_summary']) if isinstance(batch.get('quality_summary'), str)
            else batch.get('quality_summary', {})
        )
        invalid_count = int(batch.get('invalid_rows') or quality.get('invalid_rows') or 0)
        return {
            'id': batch['id'],
            'source_type': batch['source_type'],
            'source_filename': batch['source_filename'],
            'source_hash': batch['source_hash'],
            'date_range': quality.get('date_range', {'start': None, 'end': None}),
            'total_rows': int(quality.get('total_rows') or 0),
            'raw_total_rows': int(quality.get('raw_total_rows') or quality.get('total_rows') or 0),
            'excluded_summary_rows': int(quality.get('excluded_summary_rows') or 0),
            'valid_rows': int(quality.get('valid_rows') or 0),
            'invalid_rows': invalid_count,
            'duplicate_keys': int(quality.get('duplicate_keys') or 0),
            'product_count': int(quality.get('product_count') or 0),
            'quality_summary': quality,
            'source_resolution': quality.get('source_resolution') or {},
            'inserted_count': int(inserted_count or 0),
            'updated_count': int(updated_count or 0),
            'skipped_count': 0,
            'invalid_count': invalid_count,
            'quality_conclusion': 'passed' if invalid_count == 0 and not quality.get('duplicate_keys') else 'failed',
            'completed_at': completed['completed_at'] if completed else None,
            'audit_url': f"/api/imports/{batch['id']}/audit",
        }

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
        from db import get_db, get_shop_id
        shop_id = get_shop_id()
        with get_db() as connection:
            batches = [dict(row) for row in connection.execute(
                '''SELECT id, shop_id, source_type, source_filename, source_hash, status,
                          total_rows, valid_rows, invalid_rows, inserted_count,
                          updated_count, quality_summary, created_at, completed_at
                   FROM import_batches WHERE shop_id = ? ORDER BY created_at DESC LIMIT 100''',
                (shop_id,)
            ).fetchall()]
        for batch in batches:
            quality = json.loads(batch['quality_summary'])
            batch['quality_summary'] = quality
            batch.update(self._report(batch, batch['inserted_count'], batch['updated_count']))
        return batches

    def revert(self, batch_id):
        try:
            from db import get_shop_id
            result = ImportRepo.revert_batch(batch_id, shop_id=get_shop_id())
        except ImportRevertScopeError as error:
            raise ImportScopeError(str(error)) from error
        except ImportScopeError:
            raise
        except ImportRevertConflictError as error:
            raise ImportConflictError(str(error)) from error
        if result is None:
            raise ImportValidationError('导入批次不存在')
        if result is False:
            raise ImportValidationError('导入批次已撤销')
        return {
            'id': batch_id, 'reverted': result['skipped_count'] == 0,
            'restored_count': result['restored_count'],
            'skipped_count': result['skipped_count'],
        }


class ImportConflictError(ImportValidationError):
    pass


import_service = ImportService()
