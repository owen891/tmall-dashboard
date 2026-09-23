from datetime import datetime
from services.category_mode_service import category_filters_from_request, shop_label_filter
"""Overview Legacy API - 概览相关接口（旧版）

从 data_api.py 拆分出来的独立模块，包含：
- KPI 指标
- 趋势数据
- 星标商品
- 健康检查
"""

from flask import Blueprint, jsonify, request
from api.data_api import DIMENSION_MAP, _aov_expression, _reject_legacy_shop_scope, _validate_period_arg, cached_api

from db import get_db, get_shop_id, load_config
from api.api_response import failure, json_object, success


overview_legacy_bp = Blueprint('overview_legacy', __name__)


@overview_legacy_bp.route('/api/kpi', methods=['GET'])
@cached_api('kpi', 60)
def get_kpi():
    """KPI卡片数据"""
    dimension = request.args.get('dim', 'weekly')
    period = request.args.get('period', '')
    prev_period = request.args.get('prev_period', '')
    unsupported = _reject_legacy_shop_scope(dimension)
    if unsupported:
        return unsupported
    shop_id = get_shop_id()
    with get_db() as conn:

        dim_cfg = DIMENSION_MAP.get(dimension)
        if not dim_cfg:
            return failure('VALIDATION_ERROR', 'invalid dimension', {'dim': dimension}, status=422)
        for field, value in (('period', period), ('prev_period', prev_period)):
            invalid = _validate_period_arg(dimension, value, field)
            if invalid:
                return invalid
        table = dim_cfg['table']
        date_col = dim_cfg['date_col']
        visitors_col = dim_cfg['visitors_col']
        _label_clause, _label_params = shop_label_filter(category_filters_from_request())
        _join_sql = f' JOIN products p ON p.product_id = {table}.product_id' if _label_clause else ''
        _kpi_where = (' AND ' + _label_clause) if _label_clause else ''

        def query_period(p):
            if not p:
                return None
            scope_sql = 'shop_id = ? AND ' if table == 'daily_data' else ''
            scope_params = (shop_id,) if table == 'daily_data' else ()
            row = conn.execute(f'''
                SELECT
                    COUNT(*) as row_count,
                    COALESCE(SUM(payment_amount),0) as gmv,
                    COALESCE(SUM(refund_amount),0) as refund_amount,
                    COALESCE(SUM(payment_amount),0) - COALESCE(SUM(refund_amount),0) as net_sales,
                    COALESCE(SUM({visitors_col}),0) as visitors,
                    {_aov_expression(dimension)} as aov,
                    CASE WHEN SUM(payment_amount) > 0 THEN SUM(refund_amount) * 1.0 / SUM(payment_amount) ELSE 0 END as refund_rate,
                    COALESCE(SUM(ad_spend),0) as ad_spend,
                    CASE WHEN SUM(ad_spend) > 0 THEN SUM(payment_amount) * 1.0 / SUM(ad_spend) ELSE 0 END as roi,
                    AVG(payment_conversion) as conversion
                FROM {table}{_join_sql} WHERE {scope_sql}{date_col} = ?{_kpi_where}
            ''', (*scope_params, p, *_label_params)).fetchone()
            result = dict(row) if row else None
            if result and not result.pop('row_count', 0):
                return None
            return result

        current = query_period(period)
        previous = query_period(prev_period)

        # 计算环比
        changes = {}
        anomalies = []
        config = load_config()
        anomaly_decline = config.get('thresholds', {}).get('anomaly_decline', 0.20)

        if current and previous:
            for key in ['gmv', 'net_sales', 'visitors', 'aov', 'ad_spend', 'conversion', 'roi']:
                prev_val = previous.get(key) or 0
                if prev_val > 0:
                    changes[key] = round(((current.get(key) or 0) - prev_val) / prev_val * 100, 1)
                else:
                    changes[key] = None
            for key in ['refund_rate']:
                prev_val = previous.get(key) or 0
                changes[key] = round(((current.get(key) or 0) - prev_val) * 100, 1) if prev_val else None

            # 异常检测：环比下降超过阈值
            metric_labels = {'gmv': '总销售额', 'net_sales': '净销售额', 'visitors': '总访客', 'aov': '客单价'}
            for key in ['gmv', 'net_sales', 'visitors', 'aov']:
                change_val = changes.get(key)
                if change_val is not None and change_val < 0 and abs(change_val) > anomaly_decline * 100:
                    severity = 'high' if abs(change_val) > 40 else 'warning'
                    anomalies.append({
                        'metric': key,
                        'label': metric_labels.get(key, key),
                        'change': change_val,
                        'current': current.get(key, 0),
                        'previous': previous.get(key, 0),
                        'direction': 'decline',
                        'severity': severity
                    })

    return jsonify({
        'current': current,
        'previous': previous,
        'changes': changes,
        'anomalies': anomalies,
        'availability': 'available' if current and previous else 'partial' if current or previous else 'no-data',
    })

@overview_legacy_bp.route('/api/trend', methods=['GET'])
@cached_api('trend', 60)
def get_trend():
    """趋势数据"""
    dimension = request.args.get('dim', 'weekly')
    start = request.args.get('start', '')
    end = request.args.get('end', '')
    unsupported = _reject_legacy_shop_scope(dimension)
    if unsupported:
        return unsupported
    shop_id = get_shop_id()

    dim_cfg = DIMENSION_MAP.get(dimension)
    if not dim_cfg:
        return failure('VALIDATION_ERROR', 'invalid dimension', {'dim': dimension}, status=422)
    if dimension == 'daily':
        for field, value in (('start', start), ('end', end)):
            invalid = _validate_period_arg(dimension, value, field)
            if invalid:
                return invalid
    table = dim_cfg['table']
    date_col = dim_cfg['date_col']

    period_format = '%Y-%m' if dimension == 'monthly' else '%Y-%m-%d'
    parsed_ranges = {}
    for field, value in (('start', start), ('end', end)):
        if not value:
            continue
        try:
            parsed = datetime.strptime(value, period_format)
        except (TypeError, ValueError):
            return failure('VALIDATION_ERROR', f'{field} must use {period_format.replace("%Y", "YYYY").replace("%m", "MM").replace("%d", "DD")}', {'dim': dimension, field: value}, status=422)
        if parsed.strftime(period_format) != value:
            return failure('VALIDATION_ERROR', f'{field} must use {period_format.replace("%Y", "YYYY").replace("%m", "MM").replace("%d", "DD")}', {'dim': dimension, field: value}, status=422)
        parsed_ranges[field] = parsed
    if parsed_ranges.get('start') and parsed_ranges.get('end') and parsed_ranges['start'] > parsed_ranges['end']:
        return failure('VALIDATION_ERROR', 'start must not be later than end', {'dim': dimension, 'start': start, 'end': end}, status=422)

    with get_db() as conn:
        visitors_col = dim_cfg['visitors_col']
        # daily_data carries payment_qty; weekly_data predates that field.
        payment_qty_expr = 'SUM(payment_qty)' if dimension in {'monthly', 'daily'} else '0'
        scope_sql = ' AND shop_id = ?' if table == 'daily_data' else ''
        _label_clause, _label_params = shop_label_filter(category_filters_from_request())
        _join_sql = f' JOIN products p ON p.product_id = {table}.product_id' if _label_clause else ''
        _trend_where = (' AND ' + _label_clause) if _label_clause else ''
        query = f'''
            SELECT {date_col} as period,
                   SUM(payment_amount) as gmv,
                   SUM(refund_amount) as refund,
                   SUM(payment_amount) - SUM(refund_amount) as net_sales,
                   SUM({visitors_col}) as visitors,
                   SUM(ad_spend) as ad_spend,
                   AVG(payment_conversion) as conversion,
                   {payment_qty_expr} as payment_count,
                   AVG(cart_rate) as cart_rate,
                   AVG(fav_rate) as fav_rate
            FROM {table}{_join_sql}
             WHERE 1=1{scope_sql}{_trend_where}
         '''
        params = [shop_id] if table == 'daily_data' else []
        params = [*params, *_label_params]
        if start:
            query += f' AND {date_col} >= ?'
            params.append(start)
        if end:
            query += f' AND {date_col} <= ?'
            params.append(end)
        query += f' GROUP BY {date_col} ORDER BY {date_col}'

        rows = [dict(r) for r in conn.execute(query, params).fetchall()]
        # 前端趋势图默认取 payment_amount；接口历史字段为 gmv，两者同义。
        for row in rows:
            row['payment_amount'] = row.get('gmv')

    return jsonify(rows)

# ==================== 星标收藏 ====================

@overview_legacy_bp.route('/api/star', methods=['POST'])
def toggle_star():
    """切换商品星标状态"""
    data = json_object(request)
    product_id = str(data.get('product_id') or '').strip()
    if not product_id:
        return failure('VALIDATION_ERROR', '缺少 product_id', status=422)
    with get_db() as conn:
        row = conn.execute('SELECT starred FROM products WHERE product_id = ?', (product_id,)).fetchone()
        if not row:
            return failure('NOT_FOUND', '商品不存在', status=404)
        if 'starred' in data:
            raw_starred = data.get('starred')
            if isinstance(raw_starred, bool):
                new_val = int(raw_starred)
            elif isinstance(raw_starred, int) and raw_starred in {0, 1}:
                new_val = raw_starred
            elif isinstance(raw_starred, str) and raw_starred.strip() in {'0', '1'}:
                new_val = int(raw_starred.strip())
            else:
                return failure('VALIDATION_ERROR', 'starred 必须是布尔值或 0/1', status=422)
        else:
            new_val = 0 if (row[0] or 0) else 1
        conn.execute('UPDATE products SET starred = ?, updated_at = datetime("now") WHERE product_id = ?', (new_val, product_id))
        conn.commit()
    return jsonify({'starred': new_val})

# ==================== 行内快速编辑 ====================

@overview_legacy_bp.route('/api/health', methods=['GET'])
@cached_api('get_health', ttl=60)
def get_health():
    """商品健康度（12维度）"""
    period = request.args.get('period', '')
    level = request.args.get('level', '')
    invalid = _validate_period_arg('monthly', period)
    if invalid:
        return invalid
    with get_db() as conn:

        query = '''SELECT h.*,
                   p.title, p.tier, p.style, p.image_url
                   FROM product_health h
                   JOIN products p ON h.product_id = p.product_id
                   WHERE h.period = ?'''
        params = [period]
        if level:
            query += ' AND h.health_level = ?'
            params.append(level)
        query += ' ORDER BY h.health_score ASC'

        rows = [dict(r) for r in conn.execute(query, params).fetchall()]

        # 解析 alert_dimensions JSON
        for r in rows:
            if r.get('alert_dimensions'):
                try:
                    r['alert_dimensions'] = json.loads(r['alert_dimensions'])
                except (json.JSONDecodeError, TypeError):
                    r['alert_dimensions'] = []
            else:
                r['alert_dimensions'] = []

        # 统计各等级数量
        stats = [dict(r) for r in conn.execute('''
            SELECT health_level, COUNT(*) as count FROM product_health WHERE period = ? GROUP BY health_level
        ''', (period,)).fetchall()]

    return jsonify({
        'products': rows,
        'stats': stats,
        'availability': 'available' if rows else 'no-data',
    })

# ==================== 评价数据 API ====================

