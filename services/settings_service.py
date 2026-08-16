from copy import deepcopy

from repos.settings_repo import SettingsRepo
from repos.audit_repo import AuditRepo
from services.import_service import SOURCE_ALLOWED_FIELDS
from db import get_db
from services.classification_service import (
    ClassificationValidationError,
    default_dictionaries,
    merged_dictionaries,
    normalize_dictionaries,
)
from services.field_catalog import get_field_catalog


DEFAULTS = {
    'shop_name': '', 'timezone': 'Asia/Shanghai', 'currency': 'CNY',
    'week_starts_on': 'monday', 'annual_target_default': 0.0,
    'growth_multiplier': 1.0, 'overachievement_threshold': 1.0,
    'lifecycle_thresholds': {'continuous_days': 60, 'seasonal_months': 12},
    'field_mappings': {}, 'mapping_templates': {},
    'classification_dictionaries': default_dictionaries(),
    'product_view_template': 'operate', 'view_templates': {
        'operate': {'label': '基础运营', 'columns': ['product_id', 'title', 'payment_amount', 'net_sales', 'conversion', 'refund_rate', 'roi', 'paid_ipv', 'organic_ipv', 'search_ipv', 'recommend_ipv', 'repurchase_rate']},
        'select': {'label': '选款分析', 'columns': ['product_id', 'title', 'tier', 'style', 'conversion', 'payment_amount', 'refund_rate', 'score']},
        'paid': {'label': '推广效率', 'columns': ['product_id', 'title', 'ad_spend', 'roi', 'overall_roi', 'paid_ratio']},
        'refund': {'label': '退款售后', 'columns': ['product_id', 'title', 'payment_amount', 'refund_amount', 'refund_rate', 'score']},
        'lifecycle': {'label': '生命周期', 'columns': ['product_id', 'title', 'lifecycle_stage', 'seasonality', 'has_pending_action']},
    },
    'promotion_view_templates': {
        'products': {
            'products-diagnosis': {'label': '经营诊断', 'columns': ['product', 'ad_spend', 'attributed_payment_amount', 'link_net_sales', 'expense_ratio', 'roi', 'ctr', 'cvr', 'cart_cost', 'new_customer_cost', 'action']},
            'products-traffic': {'label': '流量转化', 'columns': ['product', 'impressions', 'clicks', 'ctr', 'cpm', 'payment_buyers', 'cvr', 'cart_adds', 'cart_rate', 'cart_cost']},
            'products-acquisition': {'label': '拉新经营', 'columns': ['product', 'ad_spend', 'attributed_payment_amount', 'new_buyers', 'new_buyer_ratio', 'new_customer_cost', 'roi', 'paid_share']},
            'products-attribution': {'label': '成交归因', 'columns': ['product', 'ad_spend', 'attributed_payment_amount', 'direct_payment_amount', 'indirect_payment_amount', 'direct_cart_adds', 'indirect_cart_adds', 'paid_share', 'roi']},
            'products-complete': {'label': '完整明细', 'columns': ['product', 'ad_spend', 'attributed_payment_amount', 'link_gsv', 'link_net_sales', 'expense_ratio', 'roi', 'impressions', 'clicks', 'ctr', 'cpm', 'payment_buyers', 'cvr', 'cpc', 'cart_adds', 'cart_rate', 'cart_cost', 'new_buyers', 'new_buyer_ratio', 'new_customer_cost', 'total_orders', 'favs', 'direct_payment_amount', 'indirect_payment_amount', 'paid_share', 'action']},
            'products-efficiency': {'label': '\u6295\u653e\u6548\u7387', 'columns': ['product', 'ad_spend', 'attributed_payment_amount', 'link_gsv', 'link_net_sales', 'expense_ratio', 'roi', 'paid_share', 'cart_cost', 'new_customer_cost']},
            'products-action': {'label': '\u4f18\u5316\u52a8\u4f5c', 'columns': ['product', 'roi', 'ctr', 'cvr', 'ad_spend', 'action']},
        },
        'keywords': {
            'keywords-overview': {'label': '关键词概览', 'columns': ['product', 'spend', 'sales', 'roi', 'visitors', 'ppc']},
            'keywords-efficiency': {'label': '关键词投产', 'columns': ['product', 'spend', 'sales', 'roi']},
            'keywords-traffic': {'label': '\u5173\u952e\u8bcd\u5f15\u6d41', 'columns': ['product', 'visitors', 'spend', 'ppc']},
            'keywords-scale': {'label': '\u5173\u952e\u8bcd\u89c4\u6a21', 'columns': ['product', 'visitors', 'sales', 'roi']},
        },
        'crowd': {
            'crowd-overview': {'label': '人群概览', 'columns': ['product', 'spend', 'sales', 'roi', 'visitors', 'ppc']},
            'crowd-efficiency': {'label': '人群投产', 'columns': ['product', 'spend', 'sales', 'roi']},
            'crowd-reach': {'label': '\u4eba\u7fa4\u89e6\u8fbe', 'columns': ['product', 'visitors', 'spend', 'ppc']},
            'crowd-value': {'label': '\u4eba\u7fa4\u4ef7\u503c', 'columns': ['product', 'sales', 'roi', 'ppc']},
        },
        'site': {
            'site-overview': {'label': '渠道概览', 'columns': ['product', 'spend', 'sales', 'roi', 'visitors', 'ppc']},
            'site-efficiency': {'label': '渠道投产', 'columns': ['product', 'spend', 'sales', 'roi']},
            'site-reach': {'label': '\u6e20\u9053\u5f15\u6d41', 'columns': ['product', 'visitors', 'spend', 'ppc']},
            'site-cost': {'label': '\u6e20\u9053\u6210\u672c', 'columns': ['product', 'spend', 'sales', 'ppc']},
        },
        'creative': {
            'creative-overview': {'label': '创意概览', 'columns': ['product', 'spend', 'sales', 'roi', 'visitors', 'ppc']},
            'creative-efficiency': {'label': '创意投产', 'columns': ['product', 'spend', 'sales', 'roi']},
            'creative-reach': {'label': '\u521b\u610f\u5f15\u6d41', 'columns': ['product', 'visitors', 'spend', 'ppc']},
            'creative-test': {'label': '\u521b\u610f\u5bf9\u6bd4', 'columns': ['product', 'spend', 'sales', 'roi', 'visitors']},
        },
    },
    'lifecycle_view_templates': {
        'complete': {'label': '\u5b8c\u6574\u6708\u5ea6\u660e\u7ec6', 'columns': ['month', 'gsv', 'net_sales', 'payment_qty', 'buyers', 'avg_order_value', 'visitors', 'payment_conversion', 'cart_rate', 'fav_rate', 'bounce_rate', 'avg_stay_duration', 'uv_value', 'search_visitors', 'search_ratio', 'refund_amount', 'refund_rate', 'repurchase_rate', 'cross_sell_rate', 'ad_spend', 'ad_roi']},
        'scale': {'label': '\u7ecf\u8425\u89c4\u6a21', 'columns': ['month', 'gsv', 'net_sales', 'payment_qty', 'buyers', 'avg_order_value']},
        'traffic': {'label': '\u6d41\u91cf\u8f6c\u5316', 'columns': ['month', 'visitors', 'payment_conversion', 'cart_rate', 'fav_rate', 'bounce_rate', 'uv_value', 'search_visitors', 'search_ratio']},
        'efficiency': {'label': '\u6295\u653e\u6548\u7387', 'columns': ['month', 'gsv', 'net_sales', 'ad_spend', 'ad_roi']},
        'afterSales': {'label': '\u552e\u540e\u590d\u8d2d', 'columns': ['month', 'refund_amount', 'refund_rate', 'repurchase_rate', 'cross_sell_rate']},
    },
}

VIEW_COLUMNS = {
    'product_id', 'title', 'tier', 'style', 'scene', 'status', 'manager', 'remark',
    'category', 'list_date', 'payment_amount', 'payment_count', 'net_sales',
    'conversion', 'refund_amount', 'refund_rate', 'ad_spend', 'roi', 'overall_roi',
    'paid_ratio', 'refund_paid_ratio', 'expense_ratio', 'score', 'lifecycle_stage',
    'seasonality', 'has_pending_action', 'visitors', 'page_views', 'uv_value',
    'search_visitors', 'search_ratio', 'search_conversion', 'cart_rate', 'fav_rate',
    'bounce_rate', 'avg_stay_duration', 'paid_ipv', 'organic_ipv', 'search_ipv',
    'recommend_ipv', 'buyers', 'avg_order_value', 'payment_count', 'cart_qty',
    'cart_users', 'fav_users', 'trend_change', 'repurchase_rate', 'repurchase_users',
    'cross_sell_rate', 'cross_sell_qty', 'cross_sell_categories', 'new_buyers',
    'new_buyer_ratio', 'guide_visits', 'guide_visitors', 'guide_potential',
    'guide_potential_ratio', 'keyword_spend', 'keyword_sales', 'keyword_roi',
    'keyword_visitors', 'keyword_ppc', 'crowd_spend', 'crowd_sales', 'crowd_roi',
    'crowd_visitors', 'crowd_ppc', 'site_spend', 'site_sales', 'site_roi',
    'site_visitors', 'site_ppc', 'impressions', 'clicks', 'cost', 'ctr', 'cpc',
    'cpm', 'direct_gmv', 'indirect_gmv', 'total_gmv', 'total_orders',
    'direct_orders', 'indirect_orders', 'click_conversion', 'presale_roi',
    'total_cost', 'cart_adds', 'direct_cart_adds', 'indirect_cart_adds', 'favs',
    'store_favs', 'store_fav_cost', 'total_fav_cart', 'total_fav_cart_cost',
    'item_fav_cart', 'item_fav_cart_cost', 'total_favs', 'item_fav_cost',
    'item_fav_rate', 'cart_cost', 'industry_ctr', 'click_rate',
    'presale_amount', 'presale_qty', 'search_click_rate', 'category_width',
}


class SettingsValidationError(ValueError):
    pass


class SettingsService:
    def get(self):
        values = deepcopy(DEFAULTS)
        persisted = SettingsRepo.get_all()
        values.update(persisted)
        stored_promotion_templates = persisted.get('promotion_view_templates')
        if isinstance(stored_promotion_templates, dict):
            merged_promotion_templates = deepcopy(DEFAULTS['promotion_view_templates'])
            for tab, templates in stored_promotion_templates.items():
                if tab in merged_promotion_templates and isinstance(templates, dict):
                    # Built-in promotion templates are code-owned. Do not let
                    # persisted pre-expansion defaults shadow the current
                    # field catalog after a frontend capability update.
                    merged_promotion_templates[tab].update({
                        key: deepcopy(value)
                        for key, value in templates.items()
                    })
            values['promotion_view_templates'] = merged_promotion_templates
        stored_lifecycle_templates = persisted.get('lifecycle_view_templates')
        if isinstance(stored_lifecycle_templates, dict):
            legacy_columns = {
                'complete': ['month', 'gsv', 'payment_qty', 'refund_amount', 'ad_spend', 'ad_roi'],
                'scale': ['month', 'gsv', 'payment_qty'],
                'efficiency': ['month', 'gsv', 'ad_spend', 'ad_roi'],
                'afterSales': ['month', 'gsv', 'refund_amount', 'payment_qty'],
            }
            merged_lifecycle_templates = deepcopy(DEFAULTS['lifecycle_view_templates'])
            for template_key, template in stored_lifecycle_templates.items():
                if template_key in legacy_columns and isinstance(template, dict) and template.get('columns') == legacy_columns[template_key]:
                    continue
                merged_lifecycle_templates[template_key] = deepcopy(template)
            values['lifecycle_view_templates'] = merged_lifecycle_templates
        values['classification_dictionaries'] = merged_dictionaries(
            values.get('classification_dictionaries')
        )
        values['field_catalog'] = get_field_catalog()
        return values

    def update(self, payload, operator='admin', reason='更新系统设置'):
        before = self.get()
        unknown = set(payload) - set(DEFAULTS)
        if unknown:
            raise SettingsValidationError(f'不允许修改配置：{", ".join(sorted(unknown))}')
        values = {key: payload[key] for key in payload}
        if 'classification_dictionaries' in values:
            try:
                values['classification_dictionaries'] = normalize_dictionaries(
                    values['classification_dictionaries'],
                    existing=before.get('classification_dictionaries'),
                )
            except ClassificationValidationError as error:
                raise SettingsValidationError(str(error)) from error
        if 'timezone' in values and values['timezone'] != 'Asia/Shanghai':
            raise SettingsValidationError('当前版本固定使用 Asia/Shanghai 时区')
        if 'currency' in values and values['currency'] != 'CNY':
            raise SettingsValidationError('当前版本固定使用 CNY 货币')
        if 'week_starts_on' in values and values['week_starts_on'] not in {'monday', 'sunday'}:
            raise SettingsValidationError('周起始日必须为 monday 或 sunday')
        if 'annual_target_default' in values:
            try:
                values['annual_target_default'] = float(values['annual_target_default'])
            except (TypeError, ValueError) as error:
                raise SettingsValidationError('年度目标默认值必须是数字') from error
        if 'annual_target_default' in values and values['annual_target_default'] < 0:
            raise SettingsValidationError('年度目标默认值不能为负数')
        for key in ('growth_multiplier', 'overachievement_threshold'):
            label = {'growth_multiplier': '增长倍率', 'overachievement_threshold': '超额完成阈值'}[key]
            if key in values:
                try:
                    values[key] = float(values[key])
                except (TypeError, ValueError) as error:
                    raise SettingsValidationError(f'{label}必须是数字') from error
                if values[key] <= 0:
                    raise SettingsValidationError(f'{label}必须大于 0')
        for key in ('lifecycle_thresholds', 'field_mappings', 'mapping_templates', 'view_templates', 'promotion_view_templates', 'lifecycle_view_templates'):
            if key in values and not isinstance(values[key], dict):
                raise SettingsValidationError('设置项格式错误')
        if 'mapping_templates' in values:
            for source_type, mapping in values['mapping_templates'].items():
                if source_type not in SOURCE_ALLOWED_FIELDS or not isinstance(mapping, dict):
                    raise SettingsValidationError('导入映射包含不支持的报表类型')
                if not set(mapping) <= SOURCE_ALLOWED_FIELDS[source_type]:
                    raise SettingsValidationError('导入映射包含不支持的业务字段')
                if not all(isinstance(column, str) and column.strip() for column in mapping.values()):
                    raise SettingsValidationError('导入映射的原始列名不能为空')
        if 'view_templates' in values:
            normalized = {}
            builtin = set(DEFAULTS['view_templates'])
            existing_templates = self.get().get('view_templates', {})
            for template_key, template in values['view_templates'].items():
                if isinstance(template, list):
                    template = {'label': template_key, 'columns': template}
                if not isinstance(template, dict) or not isinstance(template.get('columns'), list):
                    raise SettingsValidationError('商品视图必须包含显示字段')
                columns = template['columns']
                if not template.get('label') or not all(isinstance(column, str) and column in VIEW_COLUMNS for column in columns):
                    raise SettingsValidationError('商品视图包含不支持的字段')
                normalized[template_key] = {'label': template['label'], 'columns': columns}
            for key in builtin:
                if key not in normalized:
                    normalized[key] = existing_templates.get(key, DEFAULTS['view_templates'][key])
            values['view_templates'] = normalized
        if 'product_view_template' in values:
            templates = values.get('view_templates') or self.get().get('view_templates', {})
            if values['product_view_template'] not in templates:
                raise SettingsValidationError('当前商品视图必须引用已存在的模板')
        if 'promotion_view_templates' in values:
            current = self.get().get('promotion_view_templates', DEFAULTS['promotion_view_templates'])
            allowed_tabs = set(DEFAULTS['promotion_view_templates'])
            if not set(values['promotion_view_templates']) <= allowed_tabs:
                raise SettingsValidationError('推广字段模板包含不支持的 TAB')
            allowed_fields = {item['key'] for item in get_field_catalog()['promotion']}
            normalized_tabs = deepcopy(current)
            for tab, templates in values['promotion_view_templates'].items():
                if not isinstance(templates, dict):
                    raise SettingsValidationError('推广字段模板必须按栏目分组')
                builtins = set(DEFAULTS['promotion_view_templates'][tab])
                provided_builtins = builtins & set(templates)
                if provided_builtins and provided_builtins != builtins:
                    raise SettingsValidationError('内置推广模板不能删除')
                normalized = {}
                for template_key, template in templates.items():
                    if not isinstance(template, dict) or not isinstance(template.get('columns'), list):
                        raise SettingsValidationError('推广模板必须包含显示字段')
                    columns = template['columns']
                    if not template.get('label') or not columns or not all(isinstance(column, str) and column in allowed_fields for column in columns):
                        raise SettingsValidationError('推广模板包含不支持的字段')
                    normalized[template_key] = {
                        'label': str(template['label']),
                        'columns': list(dict.fromkeys(columns)),
                    }
                for builtin in builtins:
                    expected = current.get(tab, {}).get(builtin, DEFAULTS['promotion_view_templates'][tab][builtin])
                    if builtin not in normalized:
                        normalized[builtin] = expected
                normalized_tabs[tab] = normalized
            values['promotion_view_templates'] = normalized_tabs
        if 'lifecycle_view_templates' in values:
            current = self.get().get('lifecycle_view_templates', DEFAULTS['lifecycle_view_templates'])
            builtins = set(DEFAULTS['lifecycle_view_templates'])
            allowed_fields = {
                'month', 'gsv', 'net_sales', 'payment_qty', 'buyers', 'avg_order_value',
                'visitors', 'payment_conversion', 'cart_rate', 'fav_rate', 'bounce_rate',
                'avg_stay_duration', 'uv_value', 'search_visitors', 'search_ratio',
                'refund_amount', 'refund_rate', 'repurchase_rate', 'cross_sell_rate',
                'ad_spend', 'ad_roi',
            }
            normalized = {}
            for template_key, template in values['lifecycle_view_templates'].items():
                if not isinstance(template, dict) or not isinstance(template.get('columns'), list):
                    raise SettingsValidationError('生命周期字段模板必须包含显示字段')
                columns = list(dict.fromkeys(template['columns']))
                if not template.get('label') or not columns or not all(isinstance(column, str) and column in allowed_fields for column in columns):
                    raise SettingsValidationError('生命周期字段模板包含不支持的字段')
                normalized[template_key] = {'label': str(template['label']), 'columns': columns}
            for key in builtins:
                if key not in normalized:
                    normalized[key] = current.get(key, DEFAULTS['lifecycle_view_templates'][key])
            values['lifecycle_view_templates'] = normalized
        if 'lifecycle_thresholds' in values:
            thresholds = values['lifecycle_thresholds']
            if int(thresholds.get('continuous_days', 60)) < 60 or int(thresholds.get('seasonal_months', 12)) < 12:
                raise SettingsValidationError('生命周期阈值不能低于系统安全下限')
        with get_db() as connection:
            try:
                SettingsRepo.upsert(values, connection=connection)
                after = {**before, **values}
                AuditRepo.record('settings', 'global', 'update', operator, reason, before, after, connection=connection)
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return after


settings_service = SettingsService()
