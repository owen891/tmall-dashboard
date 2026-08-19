"""Field-level source precedence and lineage for product-day facts."""

import json
import math
from contextlib import contextmanager

from db import get_db


SOURCE_SYSTEMS = {
    'business_advisor': '生意参谋',
    'promotion_tool': '推广工具',
    'dmp_product_day': 'DMP 全店单品日度',
    'other_report': '其他报表',
}

DAILY_FIELD_COLUMNS = {
    'payment_amount': 'payment_amount',
    'successful_refund_amount': 'refund_amount',
    'net_sales': 'net_sales',
    'payment_items': 'payment_qty',
    'product_visitors': 'ipv',
    'page_views': 'pv',
    'search_visitors': 'search_ipv',
    'recommend_visitors': 'recommend_ipv',
    'paid_visitors': 'paid_ipv',
    'organic_visitors': 'organic_ipv',
    'payment_conversion': 'payment_conversion',
    'bounce_rate': 'bounce_rate',
    'avg_stay_duration': 'avg_stay_duration',
    'favorite_cart_rate': 'favorite_cart_rate',
    'repurchase_rate': 'repurchase_rate',
    'ad_spend': 'ad_spend',
    'ad_roi': 'ad_roi',
    # Kept in observations for deterministic promotion ROI derivation; it is
    # not a physical daily_data column.
    'attributed_payment_amount': None,
    'payment_buyers': 'buyers',
    'payment_unit_price': 'avg_order_value',
    'uv_value': 'uv_value',
    'cart_items': 'cart_qty',
    'favorite_users': 'fav_users',
    'cart_users': 'cart_users',
    'search_conversion': 'search_conversion',
    'search_click_rate': 'search_click_rate',
    'order_buyers': 'order_buyers',
    'order_items': 'order_items',
    'order_amount': 'order_amount',
    'order_conversion': 'order_conversion',
    'new_payment_buyers': 'new_payment_buyers',
    'returning_payment_buyers': 'returning_payment_buyers',
    'returning_payment_amount': 'returning_payment_amount',
    'juhuasuan_payment_amount': 'juhuasuan_payment_amount',
    'competitiveness_score': 'competitiveness_score',
    'year_to_date_payment_amount': 'year_to_date_payment_amount',
    'month_to_date_payment_amount': 'month_to_date_payment_amount',
    'month_to_date_payment_items': 'month_to_date_payment_items',
    'search_payment_buyers': 'search_payment_buyers',
    'structured_detail_conversion': 'structured_detail_conversion',
    'structured_detail_payment_ratio': 'structured_detail_payment_ratio',
    'presale_amount': 'presale_amount',
    'presale_qty': 'presale_qty',
    'cross_sell_qty': 'cross_sell_qty',
    'cross_sell_rate': 'cross_sell_rate',
    'cross_sell_categories': 'cross_sell_categories',
    'category_width': 'category_width',
    'repurchase_users': 'repurchase_users',
}

PRIMARY_SOURCES = {
    'product_id': 'business_advisor',
    'title': 'business_advisor',
    'payment_amount': 'business_advisor',
    'payment_items': 'business_advisor',
    'product_visitors': 'business_advisor',
    'page_views': 'business_advisor',
    'payment_buyers': 'business_advisor',
    'payment_conversion': 'business_advisor',
    'paid_visitors': 'promotion_tool',
    'ad_spend': 'promotion_tool',
    'ad_roi': 'promotion_tool',
    'promotion_payment_amount': 'promotion_tool',
    'attributed_payment_amount': 'promotion_tool',
}

DMP_UNIQUE_FIELDS = {
    'search_visitors', 'recommend_visitors', 'organic_visitors', 'search_click_rate',
    'presale_amount', 'presale_qty', 'repurchase_rate', 'repurchase_users',
    'cross_sell_qty', 'cross_sell_rate', 'cross_sell_categories', 'category_width',
}

SOURCE_PRIORITY = {
    'business_advisor': 30,
    'promotion_tool': 30,
    'dmp_product_day': 20,
    'other_report': 10,
}

def source_system_for(source_type, source_filename=''):
    text = f'{source_type} {source_filename}'.lower()
    # 智能选款 exports are full-shop, product-day performance snapshots.  They
    # include promotion fields, but are not a paid-media report: classifying
    # them as promotion_tool would incorrectly give their sales/refund fields
    # promotion-source precedence.  Treat them as the DMP supplement instead.
    if (source_type == 'dmp_product_day' or 'dmp' in text
            or '全店单品' in source_filename or '智能选款' in source_filename):
        return 'dmp_product_day'
    if source_type.startswith('promotion_') or any(token in text for token in ('推广', 'paid', 'promotion')):
        return 'promotion_tool'
    if source_type in {'product_day', 'product_week', 'product_month', 'store_day'}:
        return 'business_advisor'
    return 'other_report'


def _present(value):
    if value is None:
        return False
    if isinstance(value, float) and math.isnan(value):
        return False
    return str(value).strip() not in {'', '-', '--', 'nan', 'None'}


def _json_value(value):
    try:
        json.dumps(value)
        return value
    except TypeError:
        return str(value)


def _threshold(field_key, values):
    numbers = [float(v) for v in values if isinstance(v, (int, float)) and not isinstance(v, bool)]
    if not numbers:
        return None
    if field_key in {'payment_amount', 'ad_spend', 'presale_amount'}:
        return max(1.0, max(abs(v) for v in numbers) * 0.001)
    if field_key.endswith('_rate') or field_key in {'payment_conversion', 'search_click_rate'}:
        return 0.005
    if field_key == 'ad_roi':
        return max(0.1, max(abs(v) for v in numbers) * 0.05)
    return max(1.0, max(abs(v) for v in numbers) * 0.01)


def _candidate_source(row):
    return row['source_system'], row['source_type'], row['source_batch_id'], row['payload']


def _row_value(row, key, default=None):
    if row is None:
        return default
    if hasattr(row, 'keys'):
        return row[key] if key in row.keys() else default
    columns = getattr(row, '_fields', ())
    if key in columns:
        return row[columns.index(key)]
    return default


def _load_candidates(connection, product_id, stat_date, field_key, legacy=None, shop_id='default'):
    rows = connection.execute(
        '''SELECT source_system, source_type, source_batch_id, payload_json
           FROM daily_data_observations
           WHERE shop_id = ? AND product_id = ? AND date = ?
           ORDER BY observed_at DESC, id DESC''',
        (shop_id, product_id, stat_date),
    ).fetchall()
    candidates = []
    for row in rows:
        payload_json = row['payload_json'] if hasattr(row, 'keys') else row[3]
        source_system = row['source_system'] if hasattr(row, 'keys') else row[0]
        source_type = row['source_type'] if hasattr(row, 'keys') else row[1]
        source_batch_id = row['source_batch_id'] if hasattr(row, 'keys') else row[2]
        payload = json.loads(payload_json or '{}')
        if field_key in payload and _present(payload[field_key]):
            candidates.append((source_system, source_type, source_batch_id, payload[field_key]))
    if legacy and _present(legacy.get('value')):
        legacy_tuple = (legacy['source_system'], 'legacy', None, legacy['value'])
        if not any(item[0] == legacy_tuple[0] and item[3] == legacy_tuple[3] for item in candidates):
            candidates.append(legacy_tuple)
    return candidates


def _choose(field_key, candidates):
    if not candidates:
        return None
    primary = PRIMARY_SOURCES.get(field_key)
    preferred = [item for item in candidates if item[0] == primary] if primary else []
    pool = preferred or candidates
    pool = sorted(pool, key=lambda item: SOURCE_PRIORITY.get(item[0], 0), reverse=True)
    selected = pool[0]
    distinct = []
    for item in candidates:
        if item[3] not in distinct:
            distinct.append(item[3])
    threshold = _threshold(field_key, distinct)
    conflict = 'none'
    if len(distinct) > 1:
        try:
            delta = max(float(v) for v in distinct) - min(float(v) for v in distinct)
            conflict = 'warning' if threshold is not None and delta > threshold else 'minor'
        except (TypeError, ValueError):
            conflict = 'warning'
    source = selected[0]
    role = (
        'effective_unique'
        if source == 'dmp_product_day' and (field_key in DMP_UNIQUE_FIELDS or not primary)
        else ('fallback_filled' if source == 'dmp_product_day' else 'primary')
    )
    fallback_used = bool(source == 'dmp_product_day' and primary)
    return {
        'source_system': source,
        'source_type': selected[1],
        'source_batch_id': selected[2],
        'value': selected[3],
        'source_role': role,
        'fallback_used': fallback_used,
        'conflict_status': conflict,
        'resolution_status': role if role != 'primary' else 'primary_kept',
        'distinct': distinct,
        'threshold': threshold,
    }


def _derive_formula_fields(row):
    """Prefer deterministic ratios when their numerator and denominator exist."""
    derived = dict(row)
    buyers = derived.get('payment_buyers')
    visitors = derived.get('product_visitors')
    payment = derived.get('payment_amount')
    spend = derived.get('ad_spend')
    attributed = derived.get('attributed_payment_amount')
    if _present(buyers) and _present(visitors) and float(visitors) != 0:
        derived['payment_conversion'] = float(buyers) / float(visitors)
    if _present(payment) and _present(buyers) and float(buyers) != 0:
        derived['payment_unit_price'] = float(payment) / float(buyers)
    if _present(attributed) and _present(spend) and float(spend) != 0:
        derived['ad_roi'] = float(attributed) / float(spend)
    return derived


def _materialize_daily_fact(connection, product_id, stat_date, source_system=None,
                            source_filename='', shop_id='default', preserve_legacy=True):
    existing = connection.execute(
        'SELECT * FROM daily_data WHERE shop_id = ? AND product_id = ? AND date = ?',
        (shop_id, product_id, stat_date),
    ).fetchone()
    legacy_values = {}
    if preserve_legacy and existing is not None:
        rows = connection.execute(
            '''SELECT field_key, effective_source_system, effective_value_json
               FROM fact_field_lineage WHERE shop_id = ? AND product_id = ? AND date = ?''',
            (shop_id, product_id, stat_date),
        ).fetchall()
        legacy_values = {
            row['field_key']: {'source_system': row['effective_source_system'],
                               'value': json.loads(row['effective_value_json'])}
            for row in rows if row['effective_value_json'] is not None
        }
    connection.execute(
        'DELETE FROM fact_field_lineage WHERE shop_id = ? AND product_id = ? AND date = ?',
        (shop_id, product_id, stat_date),
    )
    connection.execute(
        'DELETE FROM reconciliation_results WHERE shop_id = ? AND product_id = ? AND date = ?',
        (shop_id, product_id, stat_date),
    )
    effective = {}
    fallback_fields = []
    reference_fields = []
    conflict_fields = []
    primary_fields = []
    unique_fields = []
    for field_key, daily_column in DAILY_FIELD_COLUMNS.items():
        candidates = _load_candidates(
            connection, product_id, stat_date, field_key,
            legacy_values.get(field_key), shop_id=shop_id,
        )
        chosen = _choose(field_key, candidates)
        if not chosen:
            continue
        if daily_column:
            effective[daily_column] = chosen['value']
        else:
            effective[field_key] = chosen['value']
        if field_key == 'search_visitors':
            effective['search_visitors'] = chosen['value']
        if chosen['fallback_used']:
            fallback_fields.append(field_key)
        if chosen['source_role'] == 'effective_unique':
            unique_fields.append(field_key)
        elif chosen['source_role'] == 'primary':
            primary_fields.append(field_key)
        if source_system == 'dmp_product_day' and chosen['source_system'] != source_system:
            reference_fields.append(field_key)
        if chosen['conflict_status'] in {'warning', 'minor'}:
            conflict_fields.append(field_key)
        observed = [
            {'source_system': item[0], 'source_type': item[1],
             'source_batch_id': item[2], 'value': item[3]}
            for item in candidates
        ]
        connection.execute(
            '''INSERT INTO fact_field_lineage
               (shop_id, product_id, date, field_key, effective_source_system, effective_source_type, source_batch_id,
                source_role, fallback_used, conflict_status, observed_sources_json, effective_value_json, reason)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(shop_id, product_id, date, field_key) DO UPDATE SET
                effective_source_system=excluded.effective_source_system,
                effective_source_type=excluded.effective_source_type, source_batch_id=excluded.source_batch_id,
                source_role=excluded.source_role, fallback_used=excluded.fallback_used,
                conflict_status=excluded.conflict_status, observed_sources_json=excluded.observed_sources_json,
                effective_value_json=excluded.effective_value_json, reason=excluded.reason,
                updated_at=CURRENT_TIMESTAMP''',
            (shop_id, product_id, stat_date, field_key, chosen['source_system'], chosen['source_type'], chosen['source_batch_id'],
             chosen['source_role'], int(chosen['fallback_used']),
             ('conflict' if chosen['conflict_status'] == 'warning' else chosen['conflict_status']),
             json.dumps(observed, ensure_ascii=False), json.dumps(chosen['value'], ensure_ascii=False),
             'DMP fallback' if chosen['fallback_used'] else ('DMP unique field' if chosen['source_role'] == 'effective_unique' else 'source precedence')),
        )
        if chosen['conflict_status'] in {'warning', 'minor'}:
            connection.execute(
                '''INSERT INTO reconciliation_results
                   (shop_id, product_id, date, field_key, status, primary_source, effective_source_system, values_json, threshold, details_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(shop_id, product_id, date, field_key) DO UPDATE SET
                    status=excluded.status, primary_source=excluded.primary_source,
                    effective_source_system=excluded.effective_source_system, values_json=excluded.values_json,
                    threshold=excluded.threshold, details_json=excluded.details_json, created_at=CURRENT_TIMESTAMP''',
                (shop_id, product_id, stat_date, field_key,
                 ('conflict' if chosen['conflict_status'] == 'warning' else chosen['conflict_status']),
                 PRIMARY_SOURCES.get(field_key), chosen['source_system'],
                 json.dumps(chosen['distinct'], ensure_ascii=False), chosen['threshold'],
                 json.dumps({'reason': 'multiple non-null source values'}, ensure_ascii=False)),
            )
    # Formula metrics are derived from the effective numerator/denominator,
    # never selected as an independent source value when inputs are complete.
    derived_fields = {}
    if effective.get('buyers') is not None and effective.get('ipv') not in (None, 0):
        derived_fields['payment_conversion'] = round(float(effective['buyers']) / float(effective['ipv']), 6)
    if effective.get('payment_amount') is not None and effective.get('buyers') not in (None, 0):
        derived_fields['payment_unit_price'] = round(float(effective['payment_amount']) / float(effective['buyers']), 2)
    if effective.get('attributed_payment_amount') is not None and effective.get('ad_spend') not in (None, 0):
        derived_fields['ad_roi'] = round(float(effective['attributed_payment_amount']) / float(effective['ad_spend']), 6)
    for field_key, value in derived_fields.items():
        daily_column = DAILY_FIELD_COLUMNS[field_key]
        effective[daily_column] = value
        connection.execute(
            '''UPDATE fact_field_lineage
               SET effective_value_json = ?, reason = 'derived from effective numerator and denominator',
                   updated_at = CURRENT_TIMESTAMP
               WHERE shop_id = ? AND product_id = ? AND date = ? AND field_key = ?''',
            (json.dumps(value, ensure_ascii=False), shop_id, product_id, stat_date, field_key),
        )
    if not effective:
        if existing is not None:
            connection.execute(
                'DELETE FROM daily_data WHERE shop_id = ? AND product_id = ? AND date = ?',
                (shop_id, product_id, stat_date),
            )
        return {
            'inserted': existing is None, 'effective_fields': [], 'fallback_fields': [],
            'reference_fields': [], 'conflict_fields': [], 'conflicts': 0,
            'primary_fields': [], 'unique_fields': [],
        }
    # Observation-only numerators are retained in lineage/payload, not copied
    # into the physical daily fact table.
    effective.pop('attributed_payment_amount', None)
    columns = {'shop_id': shop_id, 'product_id': product_id, 'date': stat_date, **effective}
    if existing is None or not _row_value(existing, 'data_source'):
        columns['data_source'] = source_filename or source_system or 'source_resolution'
    names = list(columns)
    updates = ', '.join(
        f'{name}=excluded.{name}' for name in names if name not in {'shop_id', 'product_id', 'date'}
    )
    connection.execute(
        f'''INSERT INTO daily_data ({', '.join(names)}) VALUES ({', '.join('?' for _ in names)})
            ON CONFLICT(shop_id, product_id, date) DO UPDATE SET {updates or 'product_id=excluded.product_id'}, imported_at=CURRENT_TIMESTAMP''',
        [columns[name] for name in names],
    )
    return {
        'inserted': existing is None, 'effective_fields': list(effective),
        'fallback_fields': fallback_fields, 'reference_fields': reference_fields,
        'conflict_fields': conflict_fields, 'conflicts': len(conflict_fields),
        'primary_fields': primary_fields, 'unique_fields': unique_fields,
    }


def record_daily_observation(connection, row, source_type, source_filename='', source_batch_id=None,
                             source_system=None, shop_id='default'):
    """Persist one source observation and materialize the effective daily row."""
    source_system = source_system or source_system_for(source_type, source_filename)
    row = _derive_formula_fields(row)
    product_id, stat_date = str(row['product_id']), row['date']
    payload = {key: _json_value(value) for key, value in row.items()
               if key not in {'product_id', 'date'} and _present(value)}
    fields = {key: value for key, value in payload.items() if key in DAILY_FIELD_COLUMNS}
    if not fields:
        return {'inserted': False, 'effective_fields': [], 'fallback_fields': [],
                'reference_fields': [], 'conflict_fields': [], 'conflicts': 0,
                'primary_fields': [], 'unique_fields': []}
    presence = {key: True for key in fields}
    previous = connection.execute(
        '''SELECT payload_json FROM daily_data_observations
           WHERE shop_id = ? AND product_id = ? AND date = ? AND source_system = ?
             AND source_type = ? AND source_batch_id IS ?''',
        (shop_id, product_id, stat_date, source_system, source_type, source_batch_id),
    ).fetchone()
    if previous and previous['payload_json']:
        old_fields = json.loads(previous['payload_json'])
        old_fields.update(fields)
        fields = old_fields
        presence = {key: True for key in fields}
    connection.execute(
        '''INSERT INTO daily_data_observations
           (shop_id, product_id, date, source_system, source_type, source_batch_id, source_filename, payload_json, field_presence_json)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(shop_id, product_id, date, source_system, source_type, source_batch_id)
           DO UPDATE SET payload_json=excluded.payload_json, field_presence_json=excluded.field_presence_json,
                         source_filename=excluded.source_filename, observed_at=CURRENT_TIMESTAMP''',
        (shop_id, product_id, stat_date, source_system, source_type, source_batch_id, source_filename,
         json.dumps(fields, ensure_ascii=False), json.dumps(presence, ensure_ascii=False)),
    )
    return _materialize_daily_fact(
        connection, product_id, stat_date, source_system=source_system,
        source_filename=source_filename, shop_id=shop_id,
    )


def lineage_for_product_day(connection, product_id, stat_date, shop_id='default'):
    rows = connection.execute(
        '''SELECT field_key, effective_source_system, effective_source_type, source_batch_id,
                  source_role, fallback_used, conflict_status, observed_sources_json,
                  effective_value_json, reason,
                  (SELECT source_filename FROM daily_data_observations observation
                   WHERE observation.shop_id = fact_field_lineage.shop_id
                     AND observation.product_id = fact_field_lineage.product_id
                     AND observation.date = fact_field_lineage.date
                     AND observation.source_system = fact_field_lineage.effective_source_system
                     AND observation.source_batch_id = fact_field_lineage.source_batch_id
                   ORDER BY observation.id DESC LIMIT 1) AS source_filename
           FROM fact_field_lineage WHERE shop_id = ? AND product_id = ? AND date = ? ORDER BY field_key''',
        (shop_id, product_id, stat_date),
    ).fetchall()
    result = {}
    for row in rows:
        item = dict(row)
        item['observed_sources'] = json.loads(item.pop('observed_sources_json') or '[]')
        item['effective_value'] = json.loads(item.pop('effective_value_json')) if item.get('effective_value_json') is not None else None
        observed_systems = {source.get('source_system') for source in item['observed_sources'] if isinstance(source, dict)}
        if item['conflict_status'] == 'conflict':
            item['resolution_status'] = 'conflict'
        elif item['fallback_used']:
            item['resolution_status'] = 'fallback_filled'
        elif item['effective_source_system'] == 'dmp_product_day' and item['source_role'] == 'effective_unique':
            item['resolution_status'] = 'effective_unique'
        elif 'dmp_product_day' in observed_systems and item['effective_source_system'] != 'dmp_product_day' and PRIMARY_SOURCES.get(row['field_key']):
            item['resolution_status'] = 'reference_only'
        else:
            item['resolution_status'] = 'primary_kept'
        result[item.pop('field_key')] = item
    return result


class SourceResolutionService:
    """Reusable field-level source observation and resolution boundary.

    The import layer can record one field at a time or a complete row without
    knowing the storage schema. Resolution is idempotent for a source batch.
    """

    def __init__(self, db_path=None, shop_id='default'):
        self.db_path = db_path
        self.shop_id = shop_id

    @contextmanager
    def connection(self):
        with get_db(self.db_path) as connection:
            yield connection

    def record_observation(
        self, product_id, stat_date, standard_key, value, source_system,
        source_batch_id=None, source_type=None, source_filename='',
    ):
        row = {'product_id': product_id, 'date': stat_date, standard_key: value}
        with self.connection() as connection:
            result = record_daily_observation(
                connection, row, source_type or source_system,
                source_filename=source_filename,
                source_batch_id=source_batch_id,
                source_system=source_system,
                shop_id=self.shop_id,
            )
            connection.commit()
        resolved = self.resolve_field(product_id, stat_date, standard_key)
        return {**resolved, 'record': result}

    def record_observations(self, observations):
        groups = {}
        for item in observations:
            data = dict(item)
            group_key = (
                data['product_id'], data['date'], data['source_system'],
                data.get('source_batch_id'), data.get('source_type') or data['source_system'],
                data.get('source_filename', ''),
            )
            group = groups.setdefault(group_key, {
                'product_id': data['product_id'], 'date': data['date'],
                'source_system': data['source_system'],
                'source_batch_id': data.get('source_batch_id'),
                'source_type': data.get('source_type') or data['source_system'],
                'source_filename': data.get('source_filename', ''),
            })
            group[data['standard_key']] = data['value']
        results = []
        with self.connection() as connection:
            for group in groups.values():
                results.append(record_daily_observation(
                    connection, group, group.pop('source_type'),
                    source_filename=group.pop('source_filename'),
                    source_batch_id=group.pop('source_batch_id'),
                    source_system=group.pop('source_system'), shop_id=self.shop_id,
                ))
            connection.commit()
        return results

    def record(self, *args, **kwargs):
        return self.record_observation(*args, **kwargs)

    def resolve_field(self, product_id, stat_date, standard_key):
        with self.connection() as connection:
            candidates = _load_candidates(connection, product_id, stat_date, standard_key, shop_id=self.shop_id)
            chosen = _choose(standard_key, candidates)
            if not chosen:
                return {
                    'product_id': product_id, 'date': stat_date,
                    'standard_key': standard_key, 'value': None,
                    'effective_source': None, 'source_role': None,
                    'fallback_used': False, 'conflict_status': 'none',
                    'status': 'missing', 'resolution_status': 'missing',
                    'observations': [],
                }
            conflict = 'conflict' if chosen['conflict_status'] == 'warning' else chosen['conflict_status']
            status = conflict if conflict == 'conflict' else chosen['resolution_status']
            return {
                'product_id': product_id, 'date': stat_date,
                'standard_key': standard_key, 'value': chosen['value'],
                'effective_source': chosen['source_system'],
                'source_system': chosen['source_system'],
                'source_type': chosen['source_type'],
                'source_batch_id': chosen['source_batch_id'],
                'source_role': chosen['source_role'],
                'fallback_used': chosen['fallback_used'],
                'conflict_status': conflict,
                'status': status,
                'resolution_status': chosen['resolution_status'],
                'observations': [
                    {'source_system': source, 'value': value}
                    for source, _, _, value in candidates
                ],
                'threshold': chosen['threshold'],
            }

    def resolve(self, product_id, stat_date, standard_key):
        return self.resolve_field(product_id, stat_date, standard_key)

    def resolve_product_day(self, product_id, stat_date, fields=None):
        keys = fields or tuple(DAILY_FIELD_COLUMNS)
        return {key: self.resolve_field(product_id, stat_date, key) for key in keys}

    def lineage(self, product_id, stat_date):
        with self.connection() as connection:
            return lineage_for_product_day(connection, product_id, stat_date, shop_id=self.shop_id)

    def list_observations(self, product_id=None, stat_date=None):
        with self.connection() as connection:
            clauses = ["shop_id = ?"]
            params = [self.shop_id]
            if product_id:
                clauses.append("product_id = ?"); params.append(product_id)
            if stat_date:
                clauses.append("date = ?"); params.append(stat_date)
            rows = connection.execute(
                f"SELECT * FROM daily_data_observations WHERE {' AND '.join(clauses)} ORDER BY observed_at DESC, id DESC",
                params,
            ).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def _normalize_dmp_value(value):
        if value is None or (isinstance(value, float) and math.isnan(value)):
            return None
        if isinstance(value, str) and value.strip() in {'', '-', '--', 'nan', 'None'}:
            return None
        return value

    def validate_dmp_rows(self, rows):
        from services.import_service import ImportService, PERCENTAGE_FIELDS

        summary_rows = invalid_rows = 0
        valid = []
        field_warnings = []
        for row_number, row in enumerate(rows, start=2):
            item = {key: self._normalize_dmp_value(value) for key, value in dict(row).items()}
            product_id = item.get('product_id')
            stat_date = item.get('date')
            if product_id in {'总计', '合计', '小计'}:
                summary_rows += 1
                continue
            if not product_id or not stat_date:
                invalid_rows += 1
                continue
            for field in PERCENTAGE_FIELDS & set(item):
                raw = item[field]
                if raw is None:
                    continue
                try:
                    normalized = ImportService._optional_number(raw, percentage=True)
                    if normalized is None or not 0 <= normalized <= 1:
                        raise ValueError(f'{field} out of range 0..1')
                    item[field] = normalized
                except (TypeError, ValueError) as error:
                    field_warnings.append({
                        'row_number': row_number,
                        'standard_field': field,
                        'raw_value': str(raw),
                        'reason': str(error) or f'{field} value is invalid',
                    })
                    item[field] = None
            valid.append(item)
        return {
            'summary_rows': summary_rows,
            'invalid_rows': invalid_rows,
            'valid_rows': len(valid),
            'valid_rows_detail': valid,
            'invalid_field_count': len(field_warnings),
            'field_warnings': field_warnings,
        }
