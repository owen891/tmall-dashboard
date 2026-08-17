from collections import OrderedDict

from db import get_db
from services.metric_definitions import metric_metadata


AVAILABILITIES = (
    'available', 'no-data', 'insufficient-data', 'missing-fields',
    'calculation-failed', 'source-unavailable', 'partial',
)


def _evidence_level(availability):
    if availability == 'available':
        return 'full'
    if availability in {'partial', 'missing-fields'}:
        return 'partial'
    return 'insufficient'


DOMAIN_DEFINITIONS = OrderedDict([
    ('store_daily', {
        'label': '\u5e97\u94fa\u65e5\u5e38',
        'source_tables': ('store_daily_facts',),
        'grain': ('shop_id', 'date'),
        'date_column': 'date',
        'entity_column': 'shop_id',
        'raw_fields': ('payment_amount', 'successful_refund_amount', 'product_visitors', 'payment_buyers', 'returning_payment_buyers', 'ad_spend'),
        'required_fields': ('payment_amount', 'successful_refund_amount', 'product_visitors', 'payment_buyers'),
        'metric_keys': ('net_sales', 'refund_rate', 'payment_conversion_rate', 'average_order_value', 'expense_ratio', 'returning_buyer_ratio'),
        'consumer_pages': ('overview', 'goals', 'compare'),
        'capabilities_when_available': ('trend', 'matrix', 'export'),
    }),
    ('product_master', {
        'label': '\u5546\u54c1\u4e3b\u6570\u636e',
        'source_tables': ('products',),
        'grain': ('product_id',),
        'date_column': None,
        'entity_column': 'product_id',
        'raw_fields': ('product_id', 'title', 'category', 'tier', 'style', 'scene', 'status', 'manager'),
        'required_fields': ('product_id', 'title'),
        'metric_keys': (),
        'consumer_pages': ('products', 'product-detail', 'lifecycle'),
        'capabilities_when_available': ('search', 'filter', 'export'),
    }),
    ('product_daily', {
        'label': '\u5546\u54c1\u65e5\u5e38\u4e8b\u5b9e',
        'source_tables': ('daily_data',),
        'grain': ('product_id', 'date'),
        'date_column': 'date',
        'entity_column': 'product_id',
        'raw_fields': ('product_id', 'date', 'payment_amount', 'refund_amount', 'net_sales', 'ipv', 'pv', 'ad_spend', 'ad_roi', 'buyers', 'avg_order_value'),
        'required_fields': ('product_id', 'date', 'payment_amount'),
        'metric_keys': ('net_sales', 'refund_rate', 'payment_conversion_rate', 'average_order_value', 'expense_ratio', 'ad_roi'),
        'metric_evidence': {
            'net_sales': ('net_sales',),
            'refund_rate': ('refund_amount', 'payment_amount'),
            'payment_conversion_rate': ('payment_conversion',),
            'average_order_value': ('avg_order_value',),
            'ad_roi': ('ad_roi',),
        },
        'consumer_pages': ('products', 'product-detail', 'overview'),
        'capabilities_when_available': ('trend', 'ranking', 'export'),
    }),
    ('product_weekly', {
        'label': '\u5546\u54c1\u5468\u671f\u4e8b\u5b9e',
        'source_tables': ('weekly_data',),
        'grain': ('product_id', 'week_start'),
        'date_column': 'week_start',
        'entity_column': 'product_id',
        'raw_fields': ('product_id', 'week_start', 'payment_amount', 'refund_amount', 'net_sales', 'ipv', 'payment_conversion', 'ad_spend', 'ad_roi'),
        'required_fields': ('product_id', 'week_start', 'payment_amount'),
        'metric_keys': ('net_sales', 'refund_rate', 'payment_conversion_rate', 'average_order_value', 'expense_ratio', 'ad_roi'),
        'metric_evidence': {
            'net_sales': ('net_sales',),
            'refund_rate': ('refund_amount', 'payment_amount'),
            'payment_conversion_rate': ('payment_conversion',),
            'average_order_value': ('avg_order_value',),
            'ad_roi': ('ad_roi',),
        },
        'consumer_pages': ('compare', 'reviews', 'product-detail'),
        'capabilities_when_available': ('trend', 'compare', 'export'),
    }),
    ('product_monthly', {
        'label': '\u5546\u54c1\u6708\u5ea6\u4e8b\u5b9e',
        'source_tables': ('monthly_data',),
        'grain': ('product_id', 'month'),
        'date_column': 'month',
        'entity_column': 'product_id',
        'raw_fields': ('product_id', 'month', 'payment_amount', 'refund_amount', 'net_sales', 'visitors', 'payment_conversion', 'ad_spend', 'ad_roi', 'buyers', 'avg_order_value'),
        'required_fields': ('product_id', 'month', 'payment_amount'),
        'metric_keys': ('net_sales', 'refund_rate', 'payment_conversion_rate', 'average_order_value', 'expense_ratio', 'ad_roi'),
        'metric_evidence': {
            'net_sales': ('net_sales',),
            'refund_rate': ('refund_rate',),
            'payment_conversion_rate': ('payment_conversion',),
            'average_order_value': ('avg_order_value',),
            'ad_roi': ('ad_roi',),
        },
        'consumer_pages': ('products', 'lifecycle', 'promotion', 'product-detail'),
        'capabilities_when_available': ('trend', 'ranking', 'export'),
    }),
    ('promotion_daily', {
        'label': '\u63a8\u5e7f\u65e5\u5e38\u4e8b\u5b9e',
        'source_tables': ('promotion_daily_facts',),
        'grain': ('shop_id', 'date', 'channel', 'campaign_id', 'unit_id', 'product_id'),
        'date_column': 'date',
        'entity_column': 'product_id',
        'raw_fields': ('date', 'channel', 'campaign_id', 'unit_id', 'product_id', 'ad_spend', 'attributed_payment_amount', 'impressions', 'clicks', 'payment_buyers', 'direct_payment_amount', 'indirect_payment_amount'),
        'required_fields': ('date', 'channel', 'ad_spend'),
        'metric_keys': ('ad_roi', 'payment_conversion_rate'),
        'consumer_pages': ('promotion', 'overview', 'product-detail'),
        'capabilities_when_available': ('trend', 'drilldown', 'export'),
    }),
    ('reviews', {
        'label': '\u8bc4\u4ef7\u4e8b\u5b9e',
        'source_tables': ('reviews', 'review_summary'),
        'grain': ('product_id', 'review_date'),
        'date_column': 'review_date',
        'entity_column': 'product_id',
        'raw_fields': ('product_id', 'review_date', 'content', 'rating', 'sentiment', 'positive_dims', 'negative_dims', 'scenes'),
        'required_fields': ('product_id', 'content'),
        'metric_keys': (),
        'consumer_pages': ('reviews', 'product-detail'),
        'capabilities_when_available': ('sentiment', 'dimension_summary', 'export'),
    }),
    ('product_health', {
        'label': '\u5546\u54c1\u5065\u5eb7\u5ea6',
        'source_tables': ('product_health',),
        'grain': ('product_id', 'period'),
        'date_column': 'period',
        'entity_column': 'product_id',
        'raw_fields': ('product_id', 'period', 'health_score', 'health_level', 'sales_score', 'conversion_score', 'roi_score', 'refund_score', 'alert_dimensions'),
        'required_fields': ('product_id', 'period', 'health_score'),
        'metric_keys': (),
        'consumer_pages': ('products', 'overview'),
        'capabilities_when_available': ('health_score', 'alerts', 'export'),
    }),
    ('lifecycle', {
        'label': '\u751f\u547d\u5468\u671f',
        'source_tables': ('lifecycle_profiles', 'lifecycle_history'),
        'grain': ('product_id',),
        'date_column': 'updated_at',
        'entity_column': 'product_id',
        'raw_fields': ('product_id', 'recommended_stage', 'manual_stage', 'stage_locked', 'seasonal_attribute', 'confidence', 'rationale', 'next_key_date'),
        'required_fields': ('product_id', 'recommended_stage'),
        'metric_keys': (),
        'consumer_pages': ('lifecycle', 'product-detail'),
        'capabilities_when_available': ('assessment', 'history', 'export'),
    }),
    ('actions', {
        'label': '\u8fd0\u8425\u52a8\u4f5c',
        'source_tables': ('product_actions', 'operation_actions'),
        'grain': ('product_id', 'action_date'),
        'date_column': 'planned_at',
        'entity_column': 'product_id',
        'raw_fields': ('id', 'product_id', 'purpose_type', 'action_type', 'target_metric', 'status', 'planned_at', 'observer_window_days', 'before_metric_value', 'after_metric_value', 'review_conclusion'),
        'required_fields': ('product_id', 'status'),
        'metric_keys': (),
        'consumer_pages': ('reviews', 'product-detail', 'overview'),
        'capabilities_when_available': ('workflow', 'review', 'audit'),
    }),
    ('goals', {
        'label': '\u7ecf\u8425\u76ee\u6807',
        'source_tables': ('shop_targets', 'goal_versions', 'daily_goals', 'goal_adjustments', 'goal_locks'),
        'grain': ('period',),
        'date_column': 'period',
        'entity_column': None,
        'raw_fields': ('period', 'target_gsv', 'target_ad_spend', 'target_ad_ratio', 'target_conversion', 'target_refund_rate'),
        'required_fields': ('period',),
        'metric_keys': (),
        'consumer_pages': ('goals', 'overview'),
        'capabilities_when_available': ('progress', 'lock', 'adjustment', 'export'),
    }),
    ('imports', {
        'label': '\u5bfc\u5165\u6279\u6b21',
        'source_tables': ('import_batches', 'import_batch_changes', 'import_previews'),
        'grain': ('id',),
        'date_column': 'created_at',
        'entity_column': 'id',
        'raw_fields': ('id', 'source_type', 'source_filename', 'source_hash', 'status', 'total_rows', 'valid_rows', 'invalid_rows', 'completed_at'),
        'required_fields': ('id', 'source_type', 'status'),
        'metric_keys': (),
        'consumer_pages': ('data-center',),
        'capabilities_when_available': ('preview', 'confirm', 'revert', 'audit'),
    }),
    ('market', {
        'label': '\u5e02\u573a\u548c\u5173\u952e\u8bcd',
        'source_tables': ('market_analysis', 'market_keyword_opportunities', 'keyword_metrics'),
        'grain': ('analysis_date', 'keyword'),
        'date_column': 'analysis_date',
        'entity_column': 'keyword',
        'raw_fields': ('analysis_date', 'keyword', 'pop_30d', 'ctr_7d', 'cvr_30d', 'opportunity_score'),
        'required_fields': ('analysis_date',),
        'metric_keys': (),
        'consumer_pages': ('data-center',),
        'capabilities_when_available': ('keyword_summary', 'trend'),
        'limitations': ('\u5f53\u524d\u4e0d\u627f\u8bfa\u5b8c\u6574\u5e02\u573a\u673a\u4f1a\u5206\u6790',),
    }),
])


UNSUPPORTED_CAPABILITIES = (
    {'key': 'profit', 'label': '\u5229\u6da6', 'prerequisite': '\u6210\u672c\u3001\u6bdb\u5229\u548c\u8d39\u7528\u660e\u7ec6'},
    {'key': 'inventory', 'label': '\u5e93\u5b58\u4e0e\u5468\u8f6c', 'prerequisite': '\u5e93\u5b58\u3001\u5165\u5e93\u3001\u51fa\u5e93\u548c\u91c7\u8d2d\u4e8b\u5b9e'},
    {'key': 'customer_cohort', 'label': '\u7528\u6237 cohort', 'prerequisite': '\u7528\u6237\u7ea7\u8ba2\u5355\u548c\u7559\u5b58\u4e8b\u5b9e'},
    {'key': 'causal_attribution', 'label': '\u4e25\u683c\u56e0\u679c\u5f52\u56e0', 'prerequisite': '\u5b9e\u9a8c\u6216\u53ef\u8bc6\u522b\u7684\u5bf9\u7167\u8bbe\u8ba1'},
    {'key': 'market_opportunity', 'label': '\u5b8c\u6574\u5e02\u573a\u673a\u4f1a', 'prerequisite': '\u5e02\u573a\u4e8b\u5b9e\u3001\u884c\u4e1a benchmark \u548c\u5e02\u573a\u8986\u76d6'},
)


_FIELD_LABELS = {
    'payment_amount': '\u9500\u552e\u989d',
    'successful_refund_amount': '\u6210\u529f\u9000\u6b3e\u91d1\u989d',
    'product_visitors': '\u5546\u54c1\u8bbf\u5ba2',
    'payment_buyers': '\u652f\u4ed8\u4e70\u5bb6',
    'returning_payment_buyers': '\u8001\u5ba2\u652f\u4ed8\u4e70\u5bb6',
    'ad_spend': '\u63a8\u5e7f\u82b1\u8d39',
}


def _table_columns(connection, table):
    exists = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table,),
    ).fetchone()
    if not exists:
        return None
    return {row['name'] for row in connection.execute(f'PRAGMA table_info("{table}")')}


def _coverage(connection, table, definition, columns):
    date_column = definition.get('date_column')
    if date_column not in columns:
        date_column = next((field for field in ('date', 'created_at', 'updated_at', 'imported_at') if field in columns), None)
    entity_column = definition.get('entity_column')
    updated_column = 'updated_at' if 'updated_at' in columns else ('imported_at' if 'imported_at' in columns else None)
    selections = ['COUNT(*) AS row_count']
    if entity_column and entity_column in columns:
        selections.append(f'COUNT(DISTINCT "{entity_column}") AS entity_count')
    else:
        selections.append('0 AS entity_count')
    if date_column and date_column in columns:
        selections.extend([f'MIN("{date_column}") AS start_date', f'MAX("{date_column}") AS end_date'])
    else:
        selections.extend(['NULL AS start_date', 'NULL AS end_date'])
    if updated_column:
        selections.append(f'MAX("{updated_column}") AS latest_update')
    else:
        selections.append('NULL AS latest_update')
    row = connection.execute(f'SELECT {", ".join(selections)} FROM "{table}"').fetchone()
    return {
        'row_count': int(row['row_count'] or 0),
        'entity_count': int(row['entity_count'] or 0),
        'start': row['start_date'],
        'end': row['end_date'],
        'latest_update': row['latest_update'],
    }


def _source_batches(connection, table, columns):
    if 'source_batch_id' not in columns:
        return []
    rows = connection.execute(
        f'''SELECT DISTINCT source_batch_id FROM "{table}"
            WHERE source_batch_id IS NOT NULL AND TRIM(source_batch_id) <> ''
            ORDER BY source_batch_id''',
    ).fetchall()
    return [row['source_batch_id'] for row in rows]


def _metric_entries(definition, availability, columns):
    metadata = metric_metadata()
    entries = []
    for key in definition.get('metric_keys', ()):
        item = dict(metadata[key])
        evidence_fields = list(definition.get('metric_evidence', {}).get(key, item['dependencies']))
        missing = [field for field in evidence_fields if field not in columns]
        item['key'] = key
        item['evidence_fields'] = evidence_fields
        item['availability'] = availability if availability in {'no-data', 'source-unavailable'} else ('missing-fields' if missing else 'available')
        item['missing_fields'] = missing
        item['missing_inputs'] = missing
        item['evidence_level'] = _evidence_level(item['availability'])
        entries.append(item)
    return entries


def _domain(connection, key, definition):
    tables = [(table, _table_columns(connection, table)) for table in definition['source_tables']]
    missing_tables = [table for table, columns in tables if columns is None]
    missing_fields = []
    if missing_tables:
        availability = 'source-unavailable'
        columns = set()
        coverage = {'row_count': 0, 'entity_count': 0, 'start': None, 'end': None, 'latest_update': None}
        source_coverage = []
        source_batches = []
    else:
        source_coverage = [
            {'table': table, 'coverage': _coverage(connection, table, definition, table_columns)}
            for table, table_columns in tables
        ]
        table_coverages = [item['coverage'] for item in source_coverage]
        columns = set().union(*(table_columns for _, table_columns in tables))
        missing_fields = [field for field in definition['required_fields'] if field not in columns]
        starts = [item['start'] for item in table_coverages if item['start']]
        ends = [item['end'] for item in table_coverages if item['end']]
        updates = [item['latest_update'] for item in table_coverages if item['latest_update']]
        coverage = {
            'row_count': sum(item['row_count'] for item in table_coverages),
            'entity_count': max((item['entity_count'] for item in table_coverages), default=0),
            'start': min(starts) if starts else None,
            'end': max(ends) if ends else None,
            'latest_update': max(updates) if updates else None,
        }
        source_batches = sorted({
            batch
            for table, table_columns in tables
            for batch in _source_batches(connection, table, table_columns)
        })
        if not coverage['row_count']:
            availability = 'no-data'
        elif missing_fields:
            availability = 'missing-fields'
        elif len(tables) > 1 and any(not item['row_count'] for item in table_coverages):
            availability = 'partial'
        else:
            availability = 'available'
    raw_fields = [
        {
            'key': field,
            'label': _FIELD_LABELS.get(field, field),
            'availability': 'available' if field in columns else 'missing-fields',
        }
        for field in definition['raw_fields']
    ]
    metrics = _metric_entries(definition, availability, columns)
    capabilities = list(definition.get('capabilities_when_available', ())) if availability == 'available' else []
    limitations = list(definition.get('limitations', ()))
    if missing_tables:
        limitations.append(f'\u6570\u636e\u8868\u4e0d\u53ef\u7528: {", ".join(missing_tables)}')
    if missing_fields:
        limitations.append(f'\u7f3a\u5c11\u5fc5\u586b\u5b57\u6bb5: {", ".join(missing_fields)}')
    return {
        'key': key,
        'label': definition['label'],
        'source_tables': list(definition['source_tables']),
        'grain': list(definition['grain']),
        'raw_fields': raw_fields,
        'coverage': coverage,
        'source_coverage': source_coverage,
        'availability': availability,
        'evidence_level': _evidence_level(availability),
        'missing_inputs': missing_fields,
        'freshness': {
            'start': coverage['start'],
            'end': coverage['end'],
            'latest_update': coverage['latest_update'],
        },
        'derived_metrics': metrics,
        'consumer_pages': list(definition['consumer_pages']),
        'capabilities': capabilities,
        'limitations': limitations,
        'source_batches': source_batches,
    }


def build_catalog(db_path=None, *, domain=None, availability=None):
    if domain is not None and domain not in DOMAIN_DEFINITIONS:
        raise ValueError(f'unknown domain: {domain}')
    if availability is not None and availability not in AVAILABILITIES:
        raise ValueError(f'unknown availability: {availability}')
    with get_db(db_path) as connection:
        domains = [
            _domain(connection, key, definition)
            for key, definition in DOMAIN_DEFINITIONS.items()
            if domain is None or key == domain
        ]
    if availability is not None:
        domains = [item for item in domains if item['availability'] == availability]
    counts = {state: sum(item['availability'] == state for item in domains) for state in AVAILABILITIES}
    return {
        'summary': {
            'domain_count': len(domains),
            'available': counts['available'],
            'partial': counts['partial'],
            'no_data': counts['no-data'],
            'source_unavailable': counts['source-unavailable'],
            'missing_fields': counts['missing-fields'],
        },
        'domains': domains,
        'unsupported_capabilities': [dict(item) for item in UNSUPPORTED_CAPABILITIES],
    }
