from flask import Blueprint, current_app, jsonify, request, send_file
import sqlite3
import yaml
import os
import json
import io
import uuid
import time
import threading
import calendar
import glob as _glob
import ntpath
import openpyxl
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
from db import get_db, get_connection, get_shop_id, init_db, load_config
from api.api_response import evidence_level_for, failure, limitations_for, success
from repos.audit_repo import AuditRepo
from services.shop_scope_service import reject_legacy_shop_scope

# 获取项目根目录的绝对路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 安全设计：以下白名单确保table/date_col/visitors_col不会被SQL注入
# 所有SQL拼接仅使用此字典中的硬编码值，不接受用户输入
DIMENSION_MAP = {
    'monthly': {'table': 'monthly_data', 'date_col': 'month', 'visitors_col': 'visitors'},
    'weekly':  {'table': 'weekly_data',  'date_col': 'week_start', 'visitors_col': 'ipv'},
    'daily':   {'table': 'daily_data',   'date_col': 'date', 'visitors_col': 'ipv'},
}

UPLOAD_FOLDER = os.path.join(project_root, 'data/uploads/')


def _reject_legacy_shop_scope(dimension):
    """Weekly/monthly facts and targets are still single-shop legacy tables."""
    configured_shop = str(current_app.config.get('SHOP_ID') or os.environ.get('TMALL_SHOP_ID') or '').strip()
    requested_shop = (request.args.get('shop_id') or '').strip() or configured_shop
    if dimension in {'weekly', 'monthly'} and requested_shop and requested_shop != 'default':
        return failure(
            'UNSUPPORTED_SCOPE',
            f'{dimension} 维度当前不支持 shop_id；请使用日度事实，或先完成周/月表店铺迁移',
            status=422,
        )
    return None


def _validate_file_pattern(pattern):
    value = str(pattern or '*.xlsx').strip()
    normalized = value.replace('\\', '/')
    if not value or ntpath.isabs(value) or any(part == '..' for part in normalized.split('/')):
        raise ValueError('file_pattern 只能匹配 data/uploads 内的相对路径')
    return value


def _scheduled_matches(pattern):
    safe_pattern = _validate_file_pattern(pattern)
    upload_root = os.path.abspath(UPLOAD_FOLDER)
    matches = _glob.glob(os.path.join(upload_root, safe_pattern))
    return [
        path for path in matches
        if os.path.commonpath([upload_root, os.path.abspath(path)]) == upload_root
    ]


def _unique_upload_path(filename):
    """Keep the original name for file classification while avoiding overwrites."""
    safe_name = secure_filename(filename or '')
    stem, suffix = os.path.splitext(safe_name)
    candidate = os.path.join(UPLOAD_FOLDER, safe_name)
    if not os.path.exists(candidate):
        return safe_name, candidate
    safe_name = f'{stem}_{uuid.uuid4().hex[:8]}{suffix}'
    return safe_name, os.path.join(UPLOAD_FOLDER, safe_name)

# 导入进度追踪（进程内存储）
_import_progress = {}

data_bp = Blueprint('data', __name__)


# These compatibility endpoints read tables that have no shop_id. Keep them
# available for the default single-shop deployment, but never let a named
# shop receive a silently mixed response.
_LEGACY_SINGLE_SHOP_PATHS = {
    '/api/refund_alert', '/api/ad_performance', '/api/ad_alerts', '/api/ad_trend',
    '/api/traffic_structure', '/api/action_stats', '/api/anomalies',
    '/api/health', '/api/reviews/summary', '/api/reviews/list', '/api/reviews/products',
    '/api/review', '/api/customer_analysis', '/api/funnel', '/api/industry_benchmark',
    '/api/report', '/api/legacy/actions',
    '/api/market/summary', '/api/market/keywords', '/api/market/need_stats',
    '/api/market/rankings', '/api/market/histograms', '/api/market/opportunities',
    '/api/market/reports', '/api/upload/reviews', '/api/upload/data',
}


@data_bp.before_request
def reject_legacy_single_shop_scope():
    if request.path not in _LEGACY_SINGLE_SHOP_PATHS:
        return None
    return reject_legacy_shop_scope('历史兼容数据')


def get_prev_period(period, dim):
    """获取上一个周期的值"""
    try:
        if dim == 'monthly':
            y, m = period.split('-')
            m = int(m) - 1
            if m == 0:
                m, y = 12, str(int(y) - 1)
            return f"{y}-{m:02d}"
        elif dim == 'weekly':
            d = datetime.strptime(period, '%Y-%m-%d')
            prev = d - timedelta(days=7)
            return prev.strftime('%Y-%m-%d')
        else:  # daily
            d = datetime.strptime(period, '%Y-%m-%d')
            prev = d - timedelta(days=1)
            return prev.strftime('%Y-%m-%d')
    except (ValueError, IndexError, TypeError, AttributeError):
        return period


def _fmt_wan(val):
    """格式化金额为万元"""
    if val is None:
        return '--'
    n = float(val)
    if n == 0:
        return '0'
    if abs(n) < 10000:
        return f"{n:,.0f}"
    return f"{n / 10000:.1f}万"

@data_bp.route('/api/kpi', methods=['GET'])
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
            return jsonify({'error': 'invalid dimension'}), 400
        table = dim_cfg['table']
        date_col = dim_cfg['date_col']
        visitors_col = dim_cfg['visitors_col']

        def query_period(p):
            if not p:
                return None
            scope_sql = 'shop_id = ? AND ' if table == 'daily_data' else ''
            scope_params = (shop_id,) if table == 'daily_data' else ()
            row = conn.execute(f'''
                SELECT
                    COALESCE(SUM(payment_amount),0) as gmv,
                    COALESCE(SUM(refund_amount),0) as refund_amount,
                    COALESCE(SUM(payment_amount),0) - COALESCE(SUM(refund_amount),0) as net_sales,
                    COALESCE(SUM({visitors_col}),0) as visitors,
                    CASE WHEN SUM({visitors_col}) > 0 THEN SUM(payment_amount) * 1.0 / SUM({visitors_col}) ELSE 0 END as aov,
                    CASE WHEN SUM(payment_amount) > 0 THEN SUM(refund_amount) * 1.0 / SUM(payment_amount) ELSE 0 END as refund_rate,
                    COALESCE(SUM(ad_spend),0) as ad_spend,
                    CASE WHEN SUM(ad_spend) > 0 THEN SUM(payment_amount) * 1.0 / SUM(ad_spend) ELSE 0 END as roi,
                    AVG(payment_conversion) as conversion
                FROM {table} WHERE {scope_sql}{date_col} = ?
            ''', (*scope_params, p)).fetchone()
            return dict(row) if row else None

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
        'anomalies': anomalies
    })

@data_bp.route('/api/trend', methods=['GET'])
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
        return jsonify({'error': 'invalid dimension'}), 400
    table = dim_cfg['table']
    date_col = dim_cfg['date_col']

    with get_db() as conn:
        visitors_col = dim_cfg['visitors_col']
        payment_qty_expr = 'SUM(payment_qty)' if dimension == 'monthly' else '0'
        scope_sql = ' AND shop_id = ?' if table == 'daily_data' else ''
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
            FROM {table}
             WHERE 1=1{scope_sql}
         '''
        params = [shop_id] if table == 'daily_data' else []
        if start:
            query += f' AND {date_col} >= ?'
            params.append(start)
        if end:
            query += f' AND {date_col} <= ?'
            params.append(end)
        query += f' GROUP BY {date_col} ORDER BY {date_col}'

        rows = [dict(r) for r in conn.execute(query, params).fetchall()]

    return jsonify(rows)

# ==================== 星标收藏 ====================
@data_bp.route('/api/star', methods=['POST'])
def toggle_star():
    """切换商品星标状态"""
    data = request.get_json(force=True) or {}
    product_id = data.get('product_id', '')
    if not product_id:
        return jsonify({'error': '缺少product_id'}), 400
    with get_db() as conn:
        row = conn.execute('SELECT starred FROM products WHERE product_id = ?', (product_id,)).fetchone()
        if not row:
            return jsonify({'error': '商品不存在'}), 404
        if 'starred' in data:
            new_val = 1 if int(data.get('starred') or 0) else 0
        else:
            new_val = 0 if (row[0] or 0) else 1
        conn.execute('UPDATE products SET starred = ?, updated_at = datetime("now") WHERE product_id = ?', (new_val, product_id))
        conn.commit()
    return jsonify({'starred': new_val})

# ==================== 行内快速编辑 ====================
@data_bp.route('/api/products/<product_id>/field', methods=['PUT'])
def update_product_field(product_id):
    """行内快速编辑商品字段"""
    data = request.get_json(force=True) or {}
    field = data.get('field', '').strip()
    value = data.get('value', '').strip()

    # 安全设计：字段白名单防止SQL注入，仅允许以下字段通过f-string拼入SQL
    ALLOWED_FIELDS = ('tier', 'style', 'scene', 'manager', 'remark')
    if field not in ALLOWED_FIELDS:
        return jsonify({'error': f'不允许修改字段「{field}」'}), 400
    if not product_id:
        return jsonify({'error': '缺少product_id'}), 400

    with get_db() as conn:
        # 检查商品是否存在
        row = conn.execute('SELECT product_id FROM products WHERE product_id = ?', (product_id,)).fetchone()
        if not row:
            return jsonify({'error': '商品不存在'}), 404

        # 获取旧值用于日志
        old_row = conn.execute(f'SELECT {field} FROM products WHERE product_id = ?', (product_id,)).fetchone()
        old_value = old_row[0] if old_row else ''

        # 更新字段
        conn.execute(
            f'UPDATE products SET {field} = ?, updated_at = CURRENT_TIMESTAMP WHERE product_id = ?',
            (value, product_id)
        )
        conn.execute(
            'INSERT INTO operation_logs (action, detail, operator) VALUES (?, ?, ?)',
            (f'修改{field}', f'商品 {product_id}: {field}「{old_value}」→「{value}」', 'admin')
        )
        AuditRepo.record(
            'product', product_id, 'update_field', data.get('operator') or 'admin',
            data.get('reason') or f'修改商品{field}', {field: old_value}, {field: value},
            connection=conn,
        )
        conn.commit()

    return jsonify({'success': True, 'field': field, 'value': value})

# ==================== 批量更新 ====================
@data_bp.route('/api/batch_update', methods=['POST'])
def batch_update():
    data = request.get_json(force=True)
    field = data.get('field', '')
    value = data.get('value', '')
    ids = data.get('product_ids', [])
    if field not in ('tier', 'style') or not value or not ids:
        return jsonify({'error': 'invalid params'}), 400
    with get_db() as conn:
        placeholders = ','.join(['?'] * len(ids))
        conn.execute(f"UPDATE products SET {field} = ?, updated_at = CURRENT_TIMESTAMP WHERE product_id IN ({placeholders})", [value] + ids)
        conn.commit()
        # 记录操作日志
        conn.execute(
            'INSERT INTO operation_logs (action, detail, operator) VALUES (?, ?, ?)',
            (f'批量修改{field}', f'将 {len(ids)} 件商品的{field}修改为「{value}」', 'admin')
        )
        conn.commit()
    return jsonify({'success': True, 'updated': len(ids)})

# ==================== 周期对比分析 API ====================

@data_bp.route('/api/compare', methods=['GET'])
def compare_periods():
    """周期对比分析"""
    dim = request.args.get('dim', 'monthly')
    period_a = request.args.get('period_a', '')
    period_b = request.args.get('period_b', '')
    unsupported = _reject_legacy_shop_scope(dim)
    if unsupported:
        return unsupported

    if not period_a or not period_b:
        return jsonify({'error': 'period_a and period_b are required'}), 400

    if dim == 'monthly':
        table, date_col = 'monthly_data', 'month'
        visitors_col = 'visitors'
    elif dim == 'daily':
        table, date_col = 'daily_data', 'date'
        visitors_col = 'ipv'
    elif dim == 'weekly':
        table, date_col = 'weekly_data', 'week_start'
        visitors_col = 'ipv'
    else:
        return failure('VALIDATION_ERROR', 'dim must be monthly, weekly, or daily', status=400)

    shop_id = get_shop_id()
    scope_sql = 'shop_id = ? AND ' if table == 'daily_data' else ''
    scope_params = (shop_id,) if table == 'daily_data' else ()

    with get_db() as conn:

        def query_kpi(p):
            if not p:
                return None
            row = conn.execute(f'''
                SELECT
                    COALESCE(SUM(payment_amount),0) as gmv,
                    COALESCE(SUM(refund_amount),0) as refund,
                    COALESCE(SUM(payment_amount),0) - COALESCE(SUM(refund_amount),0) as net_sales,
                    COALESCE(SUM({visitors_col}),0) as visitors,
                    CASE WHEN SUM({visitors_col}) > 0 THEN SUM(payment_amount) * 1.0 / SUM({visitors_col}) ELSE 0 END as aov,
                    CASE WHEN SUM(payment_amount) > 0 THEN SUM(refund_amount) * 1.0 / SUM(payment_amount) ELSE 0 END as refund_rate,
                    COALESCE(SUM(ad_spend),0) as ad_spend,
                    CASE WHEN SUM(ad_spend) > 0 THEN SUM(payment_amount) * 1.0 / SUM(ad_spend) ELSE 0 END as roi,
                    AVG(payment_conversion) as conversion
                FROM {table} WHERE {scope_sql}{date_col} = ?
            ''', (*scope_params, p)).fetchone()
            return dict(row) if row else None

        def query_products(p):
            if not p:
                return []
            payment_qty_col = 'd.payment_qty' if dim == 'monthly' else '0'
            rows = conn.execute(f'''
                SELECT p.product_id, p.title, p.style,
                       COALESCE(d.payment_amount, 0) as payment_amount,
                       COALESCE({payment_qty_col}, 0) as payment_count,
                       COALESCE(d.ad_spend, 0) as ad_spend
                FROM products p
                LEFT JOIN {table} d ON p.product_id = d.product_id
                    AND {scope_sql.replace('shop_id', 'd.shop_id') if table == 'daily_data' else ''}d.{date_col} = ?
                WHERE p.status = 'active'
                ORDER BY d.payment_amount DESC
            ''', (*scope_params, p)).fetchall()
            return [dict(r) for r in rows]

        kpi_a = query_kpi(period_a)
        kpi_b = query_kpi(period_b)
        products_a = query_products(period_a)
        products_b = query_products(period_b)

        # KPI对比
        kpi_compare = {}
        if kpi_a and kpi_b:
            for key in ['gmv', 'net_sales', 'visitors', 'aov', 'ad_spend', 'roi', 'conversion']:
                va = kpi_a.get(key, 0) or 0
                vb = kpi_b.get(key, 0) or 0
                change = round((vb - va) / va * 100, 1) if va > 0 else None
                kpi_compare[key] = {
                    'period_a': va,
                    'period_b': vb,
                    'change_pct': change,
                }
            # 退款率特殊处理
            ra = kpi_a.get('refund_rate', 0) or 0
            rb = kpi_b.get('refund_rate', 0) or 0
            kpi_compare['refund_rate'] = {
                'period_a': ra,
                'period_b': rb,
                'change_pct': round((rb - ra) * 100, 1),
            }

        # 商品排名变化
        rank_a = {p['product_id']: i + 1 for i, p in enumerate(products_a) if p.get('payment_amount', 0) > 0}
        rank_b = {p['product_id']: i + 1 for i, p in enumerate(products_b) if p.get('payment_amount', 0) > 0}
        amount_a = {p['product_id']: p.get('payment_amount', 0) for p in products_a}
        amount_b = {p['product_id']: p.get('payment_amount', 0) for p in products_b}
        title_map = {p['product_id']: p.get('title', '') for p in products_a}
        style_map = {p['product_id']: p.get('style', '') for p in products_a}
        # 补充B中独有的商品
        for p in products_b:
            if p['product_id'] not in title_map:
                title_map[p['product_id']] = p.get('title', '')
                style_map[p['product_id']] = p.get('style', '')

        product_changes = []
        all_ids = set(rank_a.keys()) | set(rank_b.keys())
        for pid in all_ids:
            r_a = rank_a.get(pid)
            r_b = rank_b.get(pid)
            if r_a and r_b:
                diff = r_a - r_b  # 正数=排名上升
                if diff > 0:
                    status = 'up'
                elif diff < 0:
                    status = 'down'
                else:
                    status = 'flat'
                product_changes.append({
                    'product_id': pid,
                    'title': title_map.get(pid, ''),
                    'style': style_map.get(pid, ''),
                    'rank_a': r_a,
                    'rank_b': r_b,
                    'rank_diff': diff,
                    'amount_a': amount_a.get(pid, 0),
                    'amount_b': amount_b.get(pid, 0),
                    'status': status,
                })
            elif r_a and not r_b:
                product_changes.append({
                    'product_id': pid,
                    'title': title_map.get(pid, ''),
                    'style': style_map.get(pid, ''),
                    'rank_a': r_a,
                    'rank_b': None,
                    'rank_diff': None,
                    'amount_a': amount_a.get(pid, 0),
                    'amount_b': 0,
                    'status': 'exit',
                })
            else:
                product_changes.append({
                    'product_id': pid,
                    'title': title_map.get(pid, ''),
                    'style': style_map.get(pid, ''),
                    'rank_a': None,
                    'rank_b': r_b,
                    'rank_diff': None,
                    'amount_a': 0,
                    'amount_b': amount_b.get(pid, 0),
                    'status': 'new',
                })

        product_changes.sort(key=lambda x: x.get('rank_diff') or 0, reverse=True)

        # 获取两个周期各自的趋势数据
        trend_rows_a = conn.execute(f'''
            SELECT {date_col} as period, SUM(payment_amount) as gmv, SUM(refund_amount) as refund,
                   SUM(payment_amount) - SUM(refund_amount) as net_sales, SUM({visitors_col}) as visitors
            FROM {table}
            WHERE {scope_sql}{date_col} = ?
            GROUP BY product_id ORDER BY product_id
        ''', (*scope_params, period_a)).fetchall()

        trend_rows_b = conn.execute(f'''
            SELECT {date_col} as period, SUM(payment_amount) as gmv, SUM(refund_amount) as refund,
                   SUM(payment_amount) - SUM(refund_amount) as net_sales, SUM({visitors_col}) as visitors
            FROM {table}
            WHERE {scope_sql}{date_col} = ?
            GROUP BY product_id ORDER BY product_id
        ''', (*scope_params, period_b)).fetchall()

        trend_compare = {
            'labels': [period_a, period_b],
            'series_a': [sum(dict(r).get('gmv', 0) for r in trend_rows_a)],
            'series_b': [sum(dict(r).get('gmv', 0) for r in trend_rows_b)],
        }

    return jsonify({
        'period_a': period_a,
        'period_b': period_b,
        'kpi_compare': kpi_compare,
        'product_changes': product_changes,
        'trend_compare': trend_compare,
    })

# ==================== 数据导出 API ====================

@data_bp.route('/api/export', methods=['POST'])
def export_data():
    """导出数据为Excel"""
    data = request.get_json(force=True)
    export_type = data.get('type', 'products')
    period = data.get('period', '')
    dim = data.get('dim', 'monthly')
    export_shop = str(data.get('shop_id') or request.args.get('shop_id') or current_app.config.get('SHOP_ID') or os.environ.get('TMALL_SHOP_ID') or '').strip()
    if dim in {'weekly', 'monthly'} and export_shop and export_shop != 'default':
        return failure(
            'UNSUPPORTED_SCOPE',
            f'{dim} 维度当前不支持 shop_id；请先完成周/月表店铺迁移',
            status=422,
        )
    shop_id = get_shop_id()

    output = io.BytesIO()
    wb = openpyxl.Workbook()
    ws = wb.active

    if export_type == 'products':
        ws.title = '商品数据'
        dim_cfg = DIMENSION_MAP.get(dim)
        if not dim_cfg:
            return jsonify({'error': 'invalid dimension'}), 400
        table, date_col = dim_cfg['table'], dim_cfg['date_col']

        # 筛选参数
        search = data.get('search', '')
        tier = data.get('tier', '')
        style = data.get('style', '')
        status = data.get('status', '')
        lifecycle_stage = data.get('lifecycle_stage', '')
        seasonality = data.get('seasonality', '')
        has_pending_action = data.get('has_pending_action', '')
        product_id = data.get('product_id', '')
        star_only = data.get('star_only', False)
        export_cols = data.get('columns', [])
        start = data.get('start', '')
        end = data.get('end', '')
        sort_by = data.get('sort', 'payment_amount')
        order = data.get('order', 'desc')

        if shop_id != 'default' and (lifecycle_stage or seasonality or has_pending_action not in ('', None, False, 'false', '0', 0)):
            return failure('UNSUPPORTED_SCOPE', '非 default 店铺暂不支持生命周期/动作旧表筛选', status=422)
        legacy_lifecycle_join = (
            'LEFT JOIN lifecycle_profiles lp ON lp.product_id = p.product_id'
            if shop_id == 'default' else
            'LEFT JOIN (SELECT NULL AS product_id, NULL AS manual_stage, NULL AS recommended_stage, NULL AS seasonal_attribute) lp ON 1=0'
        )
        legacy_paid_join = (
            '''LEFT JOIN (
                SELECT pd.* FROM paid_detail pd
                INNER JOIN (
                    SELECT product_id, MAX(imported_at) as max_imported
                    FROM paid_detail GROUP BY product_id
                ) pd_max ON pd.product_id = pd_max.product_id AND pd.imported_at = pd_max.max_imported
            ) pd_latest ON p.product_id = pd_latest.product_id'''
            if shop_id == 'default' else
            'LEFT JOIN paid_detail pd_latest ON 1=0'
        )
        legacy_pending_action_expr = (
            "CASE WHEN EXISTS (SELECT 1 FROM product_actions pa WHERE pa.product_id = p.product_id AND pa.status IN ('pending_execution','executing','observing','pending_review','blocked')) THEN 1 ELSE 0 END"
            if shop_id == 'default' else '0'
        )

        where_clauses = []
        params = []
        if search:
            search_safe = search.replace('%', '\\%').replace('_', '\\_')
            where_clauses.append("(p.title LIKE ? ESCAPE '\\' OR p.product_id LIKE ? ESCAPE '\\')")
            params.extend([f'%{search_safe}%', f'%{search_safe}%'])
        if tier:
            where_clauses.append("p.tier = ?")
            params.append(tier)
        if style:
            where_clauses.append("p.style = ?")
            params.append(style)
        if status and status != 'all':
            where_clauses.append("p.status = ?")
            params.append(status)
        if star_only:
            where_clauses.append("p.starred = 1")
        if lifecycle_stage:
            where_clauses.append("COALESCE(lp.manual_stage, lp.recommended_stage, '') = ?")
            params.append(lifecycle_stage)
        if seasonality:
            where_clauses.append("COALESCE(lp.seasonal_attribute, '') = ?")
            params.append(seasonality)
        if has_pending_action in (True, 'true', '1', 1):
            where_clauses.append("EXISTS (SELECT 1 FROM product_actions pa WHERE pa.product_id = p.product_id AND pa.status IN ('pending_execution','executing','observing','pending_review','blocked'))")
        elif has_pending_action in (False, 'false', '0', 0):
            where_clauses.append("NOT EXISTS (SELECT 1 FROM product_actions pa WHERE pa.product_id = p.product_id AND pa.status IN ('pending_execution','executing','observing','pending_review','blocked'))")
        if product_id:
            where_clauses.append("p.product_id = ?")
            params.append(product_id)
        where_sql = (' AND ' + ' AND '.join(where_clauses)) if where_clauses else ''

        data_relation = table
        join_clause = f'p.product_id = d.product_id AND d.{date_col} = ?'
        join_params = [period]
        if dim == 'daily':
            join_clause = f'p.product_id = d.product_id AND d.shop_id = ? AND d.{date_col} = ?'
            join_params = [shop_id, period]
        if dim == 'daily' and start and end:
            data_relation = '''(
                SELECT current.product_id,
                       current.payment_amount,
                       current.refund_amount,
                       current.net_sales,
                       current.ipv,
                       current.payment_conversion,
                       current.cart_rate,
                       current.fav_rate,
                       current.bounce_rate,
                       current.avg_stay_duration,
                       current.ad_spend,
                       current.ad_roi,
                       current.buyers,
                       current.avg_order_value,
                       current.paid_ipv,
                       current.organic_ipv,
                       current.search_ipv,
                       current.recommend_ipv,
                       current.repurchase_rate,
                       current.repurchase_users,
                       current.presale_amount,
                       current.presale_qty,
                       current.search_click_rate,
                       current.cross_sell_qty,
                       current.cross_sell_rate,
                       current.category_width,
                       CASE WHEN previous.payment_amount != 0
                            THEN (current.payment_amount - previous.payment_amount) * 1.0 / previous.payment_amount
                            ELSE NULL END AS trend_change
                FROM (
                    SELECT product_id,
                           SUM(payment_amount) AS payment_amount,
                           SUM(refund_amount) AS refund_amount,
                           SUM(net_sales) AS net_sales,
                           SUM(ipv) AS ipv,
                           AVG(payment_conversion) AS payment_conversion,
                           AVG(cart_rate) AS cart_rate,
                           AVG(fav_rate) AS fav_rate,
                           AVG(bounce_rate) AS bounce_rate,
                           AVG(avg_stay_duration) AS avg_stay_duration,
                           SUM(ad_spend) AS ad_spend,
                           CASE WHEN SUM(ad_spend) > 0 THEN SUM(payment_amount) / SUM(ad_spend) ELSE 0 END AS ad_roi,
                           SUM(buyers) AS buyers,
                           CASE WHEN SUM(buyers) > 0 THEN SUM(payment_amount) / SUM(buyers) ELSE AVG(avg_order_value) END AS avg_order_value,
                           SUM(paid_ipv) AS paid_ipv,
                           SUM(organic_ipv) AS organic_ipv,
                           SUM(search_ipv) AS search_ipv,
                           SUM(recommend_ipv) AS recommend_ipv,
                           AVG(repurchase_rate) AS repurchase_rate,
                           SUM(repurchase_users) AS repurchase_users,
                           SUM(presale_amount) AS presale_amount,
                           SUM(presale_qty) AS presale_qty,
                           AVG(search_click_rate) AS search_click_rate,
                           SUM(cross_sell_qty) AS cross_sell_qty,
                           AVG(cross_sell_rate) AS cross_sell_rate,
                           AVG(category_width) AS category_width
                     FROM daily_data
                     WHERE shop_id = ? AND date BETWEEN ? AND ?
                    GROUP BY product_id
                ) current
                LEFT JOIN (
                    SELECT product_id, SUM(payment_amount) AS payment_amount
                     FROM daily_data
                     WHERE shop_id = ? AND date BETWEEN date(?, '-' || CAST((julianday(?) - julianday(?) + 1) AS INTEGER) || ' days') AND date(?, '-1 day')
                    GROUP BY product_id
                ) previous ON previous.product_id = current.product_id
            )'''
            join_clause = 'p.product_id = d.product_id'
            join_params = [shop_id, start, end, shop_id, start, end, start, start]

        # 如果指定了导出列，动态构建SELECT
        if export_cols:
            # 安全：只允许已知列名
            safe_cols = []
            base_cols = {
                'product_id': 'p.product_id', 'title': 'p.title', 'tier': 'p.tier',
                'style': 'p.style', 'scene': 'p.scene', 'status': 'p.status',
                'list_date': 'p.list_date', 'manager': 'p.manager', 'remark': 'p.remark',
                'lifecycle_stage': 'COALESCE(lp.manual_stage, lp.recommended_stage)',
                'seasonality': 'lp.seasonal_attribute',
                'has_pending_action': legacy_pending_action_expr,
            }
            visitors_col = dim_cfg['visitors_col']
            _monthly_only = dim == 'monthly'
            data_cols = {
                'payment_amount': 'COALESCE(d.payment_amount,0)', 'refund_amount': 'COALESCE(d.refund_amount,0)',
                'net_sales': 'COALESCE(d.net_sales,0)', 'visitors': f'COALESCE(d.{visitors_col},0)',
                'uv_value': 'COALESCE(d.uv_value,0)' if _monthly_only else '0',
                'search_visitors': 'COALESCE(d.search_visitors,0)' if _monthly_only else '0',
                'search_ratio': 'COALESCE(d.search_ratio,0)' if _monthly_only else '0',
                'search_conversion': 'COALESCE(d.search_conversion,0)' if _monthly_only else '0',
                'paid_ipv': 'COALESCE(d.paid_ipv,0)', 'organic_ipv': 'COALESCE(d.organic_ipv,0)',
                'search_ipv': 'COALESCE(d.search_ipv,0)', 'recommend_ipv': 'COALESCE(d.recommend_ipv,0)',
                'payment_conversion': 'COALESCE(d.payment_conversion,0)',
                'conversion': 'COALESCE(d.payment_conversion,0)',
                'cart_rate': 'COALESCE(d.cart_rate,0)',
                'fav_rate': 'COALESCE(d.fav_rate,0)',
                'bounce_rate': 'COALESCE(d.bounce_rate,0)', 'avg_stay_duration': 'COALESCE(d.avg_stay_duration,0)',
                'ad_spend': 'COALESCE(d.ad_spend,0)', 'ad_roi': 'COALESCE(d.ad_roi,0)',
                'roi': 'COALESCE(d.ad_roi,0)',
                'overall_roi': 'COALESCE(d.overall_roi,0)' if _monthly_only else '0',
                'paid_ratio': 'COALESCE(d.paid_ratio,0)' if _monthly_only else '0',
                'expense_ratio': 'CASE WHEN COALESCE(d.payment_amount,0) > 0 THEN COALESCE(d.ad_spend,0) * 1.0 / d.payment_amount ELSE NULL END',
                'refund_rate': 'COALESCE(d.refund_rate,0)' if _monthly_only else '0',
                'repurchase_rate': 'COALESCE(d.repurchase_rate,0)', 'repurchase_users': 'COALESCE(d.repurchase_users,0)',
                'presale_amount': 'COALESCE(d.presale_amount,0)' if not _monthly_only else '0',
                'presale_qty': 'COALESCE(d.presale_qty,0)' if not _monthly_only else '0',
                'search_click_rate': 'COALESCE(d.search_click_rate,0)' if not _monthly_only else '0',
                'cross_sell_qty': 'COALESCE(d.cross_sell_qty,0)', 'cross_sell_rate': 'COALESCE(d.cross_sell_rate,0)',
                'category_width': 'COALESCE(d.category_width,0)' if not _monthly_only else '0',
                'buyers': f"COALESCE(d.buyers,0)" if dim != 'weekly' else '0',
                'avg_order_value': 'COALESCE(d.avg_order_value,0)',
                'payment_qty': f"COALESCE(d.payment_qty,0)" if dim == 'monthly' else '0',
                'payment_count': f"COALESCE(d.payment_qty,0)" if dim == 'monthly' else '0',
                'cart_qty': f"COALESCE(d.cart_qty,0)" if _monthly_only else '0',
                'fav_users': f"COALESCE(d.fav_users,0)" if _monthly_only else '0',
                'score': f"COALESCE(d.score,0)" if _monthly_only else '0',
                'keyword_spend': 'COALESCE(d.keyword_spend,0)' if _monthly_only else '0',
                'keyword_roi': 'COALESCE(d.keyword_roi,0)' if _monthly_only else '0',
                'crowd_spend': 'COALESCE(d.crowd_spend,0)' if _monthly_only else '0',
                'crowd_roi': 'COALESCE(d.crowd_roi,0)' if _monthly_only else '0',
                'impressions': 'COALESCE(pd_latest.impressions,0)',
                'ctr': 'COALESCE(pd_latest.ctr,0)',
                'trend_change': 'd.trend_change' if dim == 'daily' and start and end else 'NULL',
            }
            col_labels = {
                'product_id': '商品ID', 'title': '商品名称', 'tier': '分层', 'style': '风格',
                'scene': '场景', 'status': '状态', 'list_date': '上架时间',
                'manager': '负责人', 'remark': '备注', 'lifecycle_stage': '生命周期阶段',
                'seasonality': '季节属性', 'has_pending_action': '待办动作',
                'payment_amount': '销售额', 'refund_amount': '退款金额', 'net_sales': '净销售额',
                'visitors': '访客数', 'uv_value': '客单价值', 'search_visitors': '搜索访客',
                'search_ratio': '搜索占比', 'payment_conversion': '转化率', 'bounce_rate': '跳出率',
                'conversion': '转化率',
                'avg_stay_duration': '停留时长', 'ad_spend': '推广花费', 'ad_roi': 'ROI',
                'roi': 'ROI',
                'overall_roi': '综合ROI', 'refund_rate': '退款率', 'buyers': '买家数',
                'avg_order_value': '客单价', 'payment_qty': '支付件数', 'payment_count': '支付件数', 'cart_qty': '加购件数',
                'fav_users': '收藏人数', 'score': '综合评分',
                'trend_change': '销售趋势变化',
            }
            col_labels.update({
                'paid_ipv': '\u4ed8\u8d39 IPV', 'organic_ipv': '\u81ea\u7136 IPV',
                'search_ipv': '\u641c\u7d22 IPV', 'recommend_ipv': '\u63a8\u8350 IPV',
                'repurchase_rate': '\u590d\u8d2d\u7387', 'repurchase_users': '\u590d\u8d2d\u7528\u6237\u6570',
                'presale_amount': '\u9884\u552e\u652f\u4ed8\u91d1\u989d', 'presale_qty': '\u9884\u552e\u9500\u91cf',
                'search_click_rate': '\u514d\u8d39\u641c\u7d22\u70b9\u51fb\u7387',
                'cross_sell_qty': '\u8fde\u5e26\u8d2d\u4e70\u91cf', 'cross_sell_rate': '\u8fde\u5e26\u8d2d\u4e70\u7387',
                'category_width': '\u8fde\u5e26\u8d2d\u4e70\u53f6\u5b50\u7c7b\u76ee\u5bbd\u5ea6',
            })
            for c in export_cols:
                if c in base_cols:
                    safe_cols.append(f"{base_cols[c]} as {c}")
                elif c in data_cols:
                    safe_cols.append(f"{data_cols[c]} as {c}")
            if not safe_cols:
                safe_cols = ['p.product_id', 'p.title', 'p.tier', 'p.style']
            select_clause = ', '.join(safe_cols)
            headers = [col_labels.get(c, c) for c in export_cols if c in base_cols or c in data_cols]
            if not headers:
                headers = ['商品ID', '商品名称', '分层', '风格']
        else:
            payment_qty_col = 'd.payment_qty' if dim == 'monthly' else '0'
            select_clause = f"""p.product_id, p.title, p.tier, p.style, p.scene, p.status,
                       COALESCE(d.payment_amount, 0) as payment_amount,
                       COALESCE(d.refund_amount, 0) as refund_amount,
                       COALESCE({payment_qty_col}, 0) as payment_count,
                       CASE WHEN COALESCE(d.payment_amount, 0) > 0 THEN COALESCE(d.refund_amount, 0) * 1.0 / d.payment_amount ELSE 0 END as refund_rate,
                       COALESCE(d.ad_spend, 0) as ad_spend,
                       COALESCE(d.ad_roi, 0) as roi"""
            headers = ['商品ID', '商品名称', '分层', '风格', '场景', '状态',
                       '销售额', '退款金额', '支付件数', '退款率', '推广花费', 'ROI']

        with get_db() as conn:
            sort_whitelist = {
                'product_id', 'title', 'tier', 'style', 'scene', 'status',
                'payment_amount', 'refund_amount', 'payment_count', 'refund_rate',
                'ad_spend', 'roi',
            }
            if export_cols:
                sort_whitelist.update(base_cols.keys())
                sort_whitelist.update(data_cols.keys())
            sort_col = sort_by if sort_by in sort_whitelist else 'payment_amount'
            order_sql = 'DESC' if order == 'desc' else 'ASC'
            sort_expression = 'p.product_id' if sort_col == 'product_id' else sort_col
            rows = conn.execute(f'''
            SELECT {select_clause}
                FROM products p
                {legacy_lifecycle_join}
                LEFT JOIN {data_relation} d ON {join_clause}
                {legacy_paid_join}
                WHERE 1=1{where_sql}
                ORDER BY {sort_expression} {order_sql}
            ''', join_params + params).fetchall()
        ws.append(headers)
        for r in rows:
            ws.append(list(r))

    elif export_type == 'refund':
        ws.title = '退款数据'
        with get_db() as conn:
            if dim == 'monthly':
                table, date_col = 'monthly_data', 'month'
                refund_rate_expr = 'd.refund_rate'
            else:
                table, date_col = 'weekly_data', 'week_start'
                refund_rate_expr = 'CASE WHEN d.payment_amount > 0 THEN d.refund_amount * 1.0 / d.payment_amount ELSE 0 END'

            rows = conn.execute(f'''
                SELECT p.product_id, p.title, p.style,
                       d.payment_amount, d.refund_amount, {refund_rate_expr} as refund_rate
                FROM products p
                JOIN {table} d ON p.product_id = d.product_id AND d.{date_col} = ?
                WHERE p.status = 'active' AND d.refund_amount > 0
                ORDER BY d.refund_amount DESC
            ''', (period,)).fetchall()

        headers = ['商品ID', '商品名称', '风格', '销售额', '退款金额', '退款率']
        ws.append(headers)
        for r in rows:
            ws.append(list(r))

    elif export_type == 'reviews':
        ws.title = '评价数据'
        with get_db() as conn:
            rows = conn.execute('''
                SELECT r.product_id, p.title, r.rating, r.sentiment, r.content, r.is_effective, r.has_image, r.imported_at
                FROM reviews r
                LEFT JOIN products p ON r.product_id = p.product_id
                ORDER BY r.imported_at DESC
            ''').fetchall()

        headers = ['商品ID', '商品名称', '评分', '情感', '评价内容', '有效评价', '带图', '导入时间']
        ws.append(headers)
        for r in rows:
            ws.append(list(r))

    wb.save(output)
    output.seek(0)

    filename = f'{export_type}_{period or "all"}.xlsx'
    return send_file(output,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     as_attachment=True,
                     download_name=filename)

def calc_score(row):
    """计算商品综合评分（0-100分）"""
    score = 50  # 基础分
    # 转化率加分（越高越好，上限+20）
    conv = row.get('conversion') or 0
    score += min(conv * 5, 20)
    # ROI加分（越高越好，上限+15）
    roi = row.get('overall_roi') or 0
    score += min(roi * 1.5, 15)
    # 退款率扣分（越低越好，上限-20）
    refund = row.get('refund_rate') or 0
    score -= min(refund * 1.5, 20)
    # UV价值加分（越高越好，上限+10）
    uv = row.get('uv_value') or 0
    score += min(uv * 0.5, 10)
    # 搜索占比加分（上限+5）
    search = row.get('search_ratio') or 0
    score += min(search * 5, 5)
    return round(max(0, min(100, score)), 1)

@data_bp.route('/api/products', methods=['GET'])
def get_products():
    """商品列表"""
    dimension = request.args.get('dim', 'monthly')
    period = request.args.get('period', '')
    start = request.args.get('start', '')
    end = request.args.get('end', '')
    sort_by = request.args.get('sort', 'payment_amount')
    order = request.args.get('order', 'desc')
    limit = max(1, min(request.args.get('limit', 20, type=int) or 20, 200))
    offset = max(0, request.args.get('offset', 0, type=int) or 0)
    tier = request.args.get('tier', '')
    style = request.args.get('style', '')
    search = request.args.get('search', '')
    product_id = request.args.get('product_id', '')
    status_filter = request.args.get('status', '')
    lifecycle_stage = request.args.get('lifecycle_stage', '')
    seasonality = request.args.get('seasonality', '')
    has_pending_action = request.args.get('has_pending_action', '')
    unsupported = _reject_legacy_shop_scope(dimension)
    if unsupported:
        return unsupported

    dim_cfg = DIMENSION_MAP.get(dimension)
    if not dim_cfg:
        return jsonify({'error': 'invalid dimension'}), 400
    table = dim_cfg['table']
    date_col = dim_cfg['date_col']
    visitors_col = dim_cfg['visitors_col']
    shop_id = get_shop_id()

    if shop_id != 'default' and (lifecycle_stage or seasonality or has_pending_action not in ('', None, False, 'false', '0', 0)):
        return failure('UNSUPPORTED_SCOPE', '非 default 店铺暂不支持生命周期/动作旧表筛选', status=422)
    legacy_lifecycle_join = (
        'LEFT JOIN lifecycle_profiles lp ON lp.product_id = p.product_id'
        if shop_id == 'default' else
        'LEFT JOIN (SELECT NULL AS product_id, NULL AS manual_stage, NULL AS recommended_stage, NULL AS seasonal_attribute) lp ON 1=0'
    )
    legacy_paid_join = (
        '''LEFT JOIN (
            SELECT pd.* FROM paid_detail pd
            INNER JOIN (
                SELECT product_id, MAX(imported_at) as max_imported
                FROM paid_detail GROUP BY product_id
            ) pd_max ON pd.product_id = pd_max.product_id AND pd.imported_at = pd_max.max_imported
        ) pd_latest ON p.product_id = pd_latest.product_id'''
        if shop_id == 'default' else
        'LEFT JOIN paid_detail pd_latest ON 1=0'
    )
    legacy_pending_action_expr = (
        "CASE WHEN EXISTS (SELECT 1 FROM product_actions pa WHERE pa.product_id = p.product_id AND pa.status IN ('pending_execution','executing','observing','pending_review','blocked')) THEN 1 ELSE 0 END"
        if shop_id == 'default' else '0'
    )

    with get_db() as conn:

        # monthly_data 独有的列（daily/weekly表不存在）
        _monthly_ad_cols = '''COALESCE(d.overall_roi, 0) as overall_roi,
                   COALESCE(d.paid_ratio, 0) as paid_ratio,
                   COALESCE(d.refund_paid_ratio, 0) as refund_paid_ratio,
                   COALESCE(d.keyword_spend, 0) as keyword_spend,
                   COALESCE(d.keyword_sales, 0) as keyword_sales,
                   COALESCE(d.keyword_roi, 0) as keyword_roi,
                   COALESCE(d.keyword_visitors, 0) as keyword_visitors,
                   COALESCE(d.keyword_ppc, 0) as keyword_ppc,
                   COALESCE(d.crowd_spend, 0) as crowd_spend,
                   COALESCE(d.crowd_sales, 0) as crowd_sales,
                   COALESCE(d.crowd_roi, 0) as crowd_roi,
                   COALESCE(d.crowd_visitors, 0) as crowd_visitors,
                   COALESCE(d.crowd_ppc, 0) as crowd_ppc,
                   COALESCE(d.site_spend, 0) as site_spend,
                   COALESCE(d.site_sales, 0) as site_sales,
                   COALESCE(d.site_roi, 0) as site_roi,
                   COALESCE(d.site_visitors, 0) as site_visitors,
                   COALESCE(d.site_ppc, 0) as site_ppc,'''

        _monthly_traffic_cols = '''COALESCE(d.paid_ipv, 0) as paid_ipv,
                   COALESCE(d.organic_ipv, 0) as organic_ipv,
                   COALESCE(d.search_ipv, 0) as search_ipv,
                   COALESCE(d.recommend_ipv, 0) as recommend_ipv,'''

        _monthly_extra_cols = '''COALESCE(d.industry_ctr, 0) as industry_ctr,
                   COALESCE(d.cross_sell_qty, 0) as cross_sell_qty,
                   COALESCE(d.cross_sell_categories, 0) as cross_sell_categories,
                   COALESCE(d.repurchase_users, 0) as repurchase_users,
                   COALESCE(d.guide_visits, 0) as guide_visits,
                   COALESCE(d.guide_visitors, 0) as guide_visitors,
                   COALESCE(d.guide_potential, 0) as guide_potential,
                   COALESCE(d.guide_potential_ratio, 0) as guide_potential_ratio,
                   COALESCE(d.new_buyers, 0) as new_buyers,
                   COALESCE(d.new_buyer_ratio, 0) as new_buyer_ratio,'''

        _zero_ad = ',\n               '.join([f'0 as {c}' for c in ['overall_roi','paid_ratio','refund_paid_ratio','keyword_spend','keyword_sales','keyword_roi','keyword_visitors','keyword_ppc','crowd_spend','crowd_sales','crowd_roi','crowd_visitors','crowd_ppc','site_spend','site_sales','site_roi','site_visitors','site_ppc']]) + ','
        _zero_traffic = ',\n               '.join([f'0 as {c}' for c in ['paid_ipv','organic_ipv','search_ipv','recommend_ipv']]) + ','
        _zero_extra = ',\n               '.join([f'0 as {c}' for c in ['industry_ctr','cross_sell_categories','guide_visits','guide_visitors','guide_potential','guide_potential_ratio','new_buyers','new_buyer_ratio']]) + ','

        monthly_only_cols = _monthly_ad_cols if dimension == 'monthly' else _zero_ad
        monthly_traffic_cols = _monthly_traffic_cols if dimension in {'monthly', 'daily', 'weekly'} else _zero_traffic
        monthly_extra_cols = _monthly_extra_cols if dimension == 'monthly' else _zero_extra
        dmp_cols = '''COALESCE(d.repurchase_users, 0) as repurchase_users,
                   COALESCE(d.presale_amount, 0) as presale_amount,
                   COALESCE(d.presale_qty, 0) as presale_qty,
                   COALESCE(d.search_click_rate, 0) as search_click_rate,
                   COALESCE(d.cross_sell_qty, 0) as cross_sell_qty,
                   COALESCE(d.category_width, 0) as category_width,'''
        dmp_zero_cols = '''0 as presale_amount, 0 as presale_qty,
                   0 as search_click_rate, 0 as category_width,'''
        dmp_metric_cols = dmp_cols if dimension in {'daily', 'weekly'} else dmp_zero_cols
        repurchase_cross_cols = "COALESCE(d.repurchase_rate, 0) as repurchase_rate,\n               COALESCE(d.cross_sell_rate, 0) as cross_sell_rate," if dimension in {'monthly', 'daily', 'weekly'} else "0 as repurchase_rate,\n               0 as cross_sell_rate,"
        click_score_cols = "COALESCE(d.click_rate, 0) as click_rate,\n               COALESCE(d.score, 0) as score," if dimension == 'monthly' else "0 as click_rate,\n               0 as score,"

        data_relation = table
        join_clause = f'p.product_id = d.product_id AND d.{date_col} = ?'
        params = [period]
        if dimension == 'daily':
            join_clause = f'p.product_id = d.product_id AND d.shop_id = ? AND d.{date_col} = ?'
            params = [shop_id, period]
        if dimension == 'daily' and start and end:
            data_relation = '''(
                SELECT current.product_id,
                       current.payment_amount,
                       current.refund_amount,
                       current.net_sales,
                       current.ipv,
                       current.pv,
                       current.payment_conversion,
                       current.cart_rate,
                       current.fav_rate,
                       current.bounce_rate,
                       current.avg_stay_duration,
                       current.ad_spend,
                       current.ad_roi,
                       current.buyers,
                       current.avg_order_value,
                       current.paid_ipv,
                       current.organic_ipv,
                       current.search_ipv,
                       current.recommend_ipv,
                       current.repurchase_rate,
                       current.repurchase_users,
                       current.presale_amount,
                       current.presale_qty,
                       current.search_click_rate,
                       current.cross_sell_qty,
                       current.cross_sell_rate,
                       current.category_width,
                       CASE WHEN previous.payment_amount != 0
                            THEN (current.payment_amount - previous.payment_amount) * 1.0 / previous.payment_amount
                            ELSE NULL END AS trend_change
                FROM (
                    SELECT product_id,
                           SUM(payment_amount) AS payment_amount,
                           SUM(refund_amount) AS refund_amount,
                           SUM(net_sales) AS net_sales,
                           SUM(ipv) AS ipv,
                           SUM(pv) AS pv,
                           AVG(payment_conversion) AS payment_conversion,
                           AVG(cart_rate) AS cart_rate,
                           AVG(fav_rate) AS fav_rate,
                           AVG(bounce_rate) AS bounce_rate,
                           AVG(avg_stay_duration) AS avg_stay_duration,
                           SUM(ad_spend) AS ad_spend,
                           CASE WHEN SUM(ad_spend) > 0 THEN SUM(payment_amount) / SUM(ad_spend) ELSE 0 END AS ad_roi,
                           SUM(buyers) AS buyers,
                           CASE WHEN SUM(buyers) > 0 THEN SUM(payment_amount) / SUM(buyers) ELSE AVG(avg_order_value) END AS avg_order_value,
                           SUM(paid_ipv) AS paid_ipv,
                           SUM(organic_ipv) AS organic_ipv,
                           SUM(search_ipv) AS search_ipv,
                           SUM(recommend_ipv) AS recommend_ipv,
                           AVG(repurchase_rate) AS repurchase_rate,
                           SUM(repurchase_users) AS repurchase_users,
                           SUM(presale_amount) AS presale_amount,
                           SUM(presale_qty) AS presale_qty,
                           AVG(search_click_rate) AS search_click_rate,
                           SUM(cross_sell_qty) AS cross_sell_qty,
                           AVG(cross_sell_rate) AS cross_sell_rate,
                           AVG(category_width) AS category_width
                     FROM daily_data
                     WHERE shop_id = ? AND date BETWEEN ? AND ?
                    GROUP BY product_id
                ) current
                LEFT JOIN (
                    SELECT product_id, SUM(payment_amount) AS payment_amount
                     FROM daily_data
                     WHERE shop_id = ? AND date BETWEEN date(?, '-' || CAST((julianday(?) - julianday(?) + 1) AS INTEGER) || ' days') AND date(?, '-1 day')
                    GROUP BY product_id
                ) previous ON previous.product_id = current.product_id
            )'''
            join_clause = 'p.product_id = d.product_id'
            params = [shop_id, start, end, shop_id, start, end, start, start]

        where_clauses = []
        where_params = []
        if status_filter and status_filter != 'all':
            where_clauses.append('p.status = ?')
            where_params.append(status_filter)
        elif status_filter != 'all':
            where_clauses.append("p.status = 'active'")
        if tier:
            where_clauses.append('p.tier = ?')
            where_params.append(tier)
        if style:
            where_clauses.append('p.style = ?')
            where_params.append(style)
        if lifecycle_stage:
            where_clauses.append("COALESCE(lp.manual_stage, lp.recommended_stage, '') = ?")
            where_params.append(lifecycle_stage)
        if seasonality:
            where_clauses.append("COALESCE(lp.seasonal_attribute, '') = ?")
            where_params.append(seasonality)
        if has_pending_action.lower() in {'true', '1', 'yes'}:
            where_clauses.append("EXISTS (SELECT 1 FROM product_actions pa WHERE pa.product_id = p.product_id AND pa.status IN ('pending_execution','executing','observing','pending_review','blocked'))")
        elif has_pending_action.lower() in {'false', '0', 'no'}:
            where_clauses.append("NOT EXISTS (SELECT 1 FROM product_actions pa WHERE pa.product_id = p.product_id AND pa.status IN ('pending_execution','executing','observing','pending_review','blocked'))")
        if search:
            search_safe = search.replace('%', '\\%').replace('_', '\\_')
            where_clauses.append("(p.title LIKE ? ESCAPE '\\' OR p.product_id LIKE ? ESCAPE '\\')")
            where_params.append(f'%{search_safe}%')
            where_params.append(f'%{search_safe}%')
        if product_id:
            where_clauses.append('p.product_id = ?')
            where_params.append(product_id)
        where_sql = ' AND '.join(where_clauses) or '1=1'

        query = f'''
            SELECT p.product_id, p.title, p.tier, p.style, p.scene, p.status, p.image_url,
                   p.category, p.list_date, p.remark, p.manager,
                   CASE WHEN d.product_id IS NOT NULL THEN 1 ELSE 0 END as has_data,
                   COALESCE(p.starred, 0) as starred,
                   COALESCE(lp.manual_stage, lp.recommended_stage) as lifecycle_stage,
                   lp.seasonal_attribute as seasonality,
                       {legacy_pending_action_expr} as has_pending_action,
                   COALESCE(d.payment_amount, 0) as payment_amount,
                   COALESCE(d.refund_amount, 0) as refund_amount,
                   COALESCE(d.payment_conversion, 0) as conversion,
                   COALESCE(d.ad_spend, 0) as ad_spend,
                   COALESCE(d.ad_roi, 0) as roi,
                   COALESCE(d.{('visitors' if dimension=='monthly' else 'ipv')}, 0) as visitors,
                   {('COALESCE(d.payment_qty, 0)' if dimension=='monthly' else '0')} as payment_count,
                   CASE WHEN COALESCE(d.payment_amount, 0) > 0 THEN COALESCE(d.refund_amount, 0) * 1.0 / d.payment_amount ELSE 0 END as refund_rate,
                   {('COALESCE(d.page_views, 0)' if dimension=='monthly' else ('COALESCE(d.pv, 0)' if dimension=='daily' else '0'))} as page_views,
                   {('COALESCE(d.uv_value, 0)' if dimension=='monthly' else '0')} as uv_value,
                   {('COALESCE(d.search_visitors, 0)' if dimension=='monthly' else '0')} as search_visitors,
                   {('COALESCE(d.search_ratio, 0)' if dimension=='monthly' else '0')} as search_ratio,
                   {('COALESCE(d.search_conversion, 0)' if dimension=='monthly' else '0')} as search_conversion,
                   COALESCE(d.cart_rate, 0) as cart_rate,
                   COALESCE(d.fav_rate, 0) as fav_rate,
                   COALESCE(d.bounce_rate, 0) as bounce_rate,
                   COALESCE(d.avg_stay_duration, 0) as avg_stay_duration,
                   {monthly_only_cols}
                   {repurchase_cross_cols}
                   {('COALESCE(d.buyers, 0)' if dimension!='weekly' else '0')} as buyers,
                   COALESCE(d.avg_order_value, 0) as avg_order_value,
                   {('COALESCE(d.cart_qty, 0)' if dimension=='monthly' else '0')} as cart_qty,
                   {('COALESCE(d.fav_users, 0)' if dimension=='monthly' else '0')} as fav_users,
                   {click_score_cols}
                   COALESCE(d.net_sales, 0) as net_sales,
                   CASE WHEN COALESCE(d.payment_amount, 0) > 0 THEN COALESCE(d.ad_spend, 0) * 1.0 / d.payment_amount ELSE NULL END as expense_ratio,
                   {('d.trend_change' if dimension == 'daily' and start and end else 'NULL')} as trend_change,
                   {monthly_traffic_cols}
                   {dmp_metric_cols}
                   {('COALESCE(d.cart_users, 0)' if dimension=='monthly' else '0')} as cart_users,
                   {monthly_extra_cols}
                   COALESCE(pd_latest.impressions, 0) as impressions,
                   COALESCE(pd_latest.clicks, 0) as clicks,
                   COALESCE(pd_latest.cost, 0) as cost,
                   COALESCE(pd_latest.ctr, 0) as ctr,
                   COALESCE(pd_latest.cpc, 0) as cpc,
                   COALESCE(pd_latest.cpm, 0) as cpm,
                   COALESCE(pd_latest.direct_gmv, 0) as direct_gmv,
                   COALESCE(pd_latest.indirect_gmv, 0) as indirect_gmv,
                   COALESCE(pd_latest.total_gmv, 0) as total_gmv,
                   COALESCE(pd_latest.total_orders, 0) as total_orders,
                   COALESCE(pd_latest.direct_orders, 0) as direct_orders,
                   COALESCE(pd_latest.indirect_orders, 0) as indirect_orders,
                   COALESCE(pd_latest.click_conversion, 0) as click_conversion,
                   COALESCE(pd_latest.presale_roi, 0) as presale_roi,
                   COALESCE(pd_latest.total_cost, 0) as total_cost,
                   COALESCE(pd_latest.cart_adds, 0) as cart_adds,
                   COALESCE(pd_latest.direct_cart_adds, 0) as direct_cart_adds,
                   COALESCE(pd_latest.indirect_cart_adds, 0) as indirect_cart_adds,
                   COALESCE(pd_latest.favs, 0) as favs,
                   COALESCE(pd_latest.store_favs, 0) as store_favs,
                   COALESCE(pd_latest.store_fav_cost, 0) as store_fav_cost,
                   COALESCE(pd_latest.total_fav_cart, 0) as total_fav_cart,
                   COALESCE(pd_latest.total_fav_cart_cost, 0) as total_fav_cart_cost,
                   COALESCE(pd_latest.item_fav_cart, 0) as item_fav_cart,
                   COALESCE(pd_latest.item_fav_cart_cost, 0) as item_fav_cart_cost,
                   COALESCE(pd_latest.total_favs, 0) as total_favs,
                   COALESCE(pd_latest.item_fav_cost, 0) as item_fav_cost,
                   COALESCE(pd_latest.item_fav_rate, 0) as item_fav_rate,
                   COALESCE(pd_latest.cart_cost, 0) as cart_cost
            FROM products p
            {legacy_lifecycle_join}
            LEFT JOIN {data_relation} d ON {join_clause}
            {legacy_paid_join}
            WHERE {where_sql}
        '''
        params.extend(where_params)

        sort_whitelist = [
            'payment_amount','payment_count','refund_amount','refund_rate','conversion',
            'ad_spend','roi','visitors','title','tier','style','scene',
            'page_views','uv_value','search_visitors','search_ratio','search_conversion',
            'cart_rate','fav_rate','bounce_rate','avg_stay_duration',
            'overall_roi','paid_ratio','refund_paid_ratio',
            'keyword_spend','keyword_sales','keyword_roi','keyword_visitors','keyword_ppc',
            'crowd_spend','crowd_sales','crowd_roi','crowd_visitors','crowd_ppc',
            'site_spend','site_sales','site_roi','site_visitors','site_ppc',
            'repurchase_rate','cross_sell_rate','buyers','avg_order_value',
            'cart_qty','fav_users','click_rate','score','net_sales',
            'category','list_date','product_id',
            'presale_amount','presale_qty','search_click_rate','category_width',
            'paid_ipv','organic_ipv','search_ipv','recommend_ipv',
            'cart_users','industry_ctr','cross_sell_qty','cross_sell_categories',
            'repurchase_users','guide_visits','guide_visitors','guide_potential',
            'guide_potential_ratio','new_buyers','new_buyer_ratio',
            'impressions','clicks','cost','ctr','cpc','cpm',
            'direct_gmv','indirect_gmv','total_gmv','total_orders',
            'direct_orders','indirect_orders','click_conversion','presale_roi',
            'total_cost','cart_adds','direct_cart_adds','indirect_cart_adds',
            'favs','store_favs','store_fav_cost','total_fav_cart','total_fav_cart_cost',
            'item_fav_cart','item_fav_cart_cost','total_favs','item_fav_cost',
            'item_fav_rate','cart_cost','manager',
            'expense_ratio','trend_change','lifecycle_stage','seasonality','has_pending_action',
        ]
        sort_col = sort_by if sort_by in sort_whitelist else 'payment_amount'
        # product_id exists on both products and the daily/monthly relation.
        # Qualify it so the public sort option cannot produce an ambiguous SQL error.
        sort_expression = 'p.product_id' if sort_col == 'product_id' else sort_col
        query += f' ORDER BY {sort_expression} {"DESC" if order=="desc" else "ASC"} LIMIT ? OFFSET ?'
        params.append(limit)
        params.append(offset)

        rows = [dict(r) for r in conn.execute(query, params).fetchall()]

        # 获取总数（用于服务端分页）- 与主查询使用完全相同的WHERE条件
        count_query = f'''SELECT COUNT(*) as total FROM products p
            LEFT JOIN lifecycle_profiles lp ON lp.product_id = p.product_id
            WHERE {where_sql}'''
        count_params = list(where_params)
        total_row = conn.execute(count_query, count_params).fetchone()
        total_count = total_row['total'] if total_row else 0

        facets = {}
        for facet_name, column in [('tiers', 'tier'), ('styles', 'style'), ('statuses', 'status')]:
            facets[facet_name] = [
                r[column] for r in conn.execute(
                    f"SELECT DISTINCT {column} FROM products WHERE {column} IS NOT NULL AND TRIM({column}) != '' ORDER BY {column}"
                ).fetchall()
            ]

        # 计算综合评分
        for row in rows:
            row['score'] = calc_score(row)

        # 月度维度下计算环比变化（批量查询上期数据）
        if dimension == 'monthly' and period:
            prev_period = get_prev_period(period, dimension)
            if prev_period != period:
                product_ids = [r['product_id'] for r in rows]
                if product_ids:
                    placeholders = ','.join(['?'] * len(product_ids))
                    prev_rows = conn.execute(f'''
                        SELECT product_id,
                               COALESCE(payment_amount, 0) as payment_amount,
                               COALESCE({visitors_col}, 0) as visitors,
                               COALESCE(payment_conversion, 0) as payment_conversion,
                               CASE WHEN COALESCE(payment_amount, 0) > 0 THEN COALESCE(refund_amount, 0) * 1.0 / payment_amount ELSE 0 END as refund_rate,
                               COALESCE(uv_value, 0) as uv_value
                        FROM {table}
                        WHERE {date_col} = ? AND product_id IN ({placeholders})
                    ''', [prev_period] + product_ids).fetchall()
                    prev_map = {r['product_id']: dict(r) for r in prev_rows}

                    for row in rows:
                        prev_data = prev_map.get(row['product_id'], {})
                        changes = {}
                        for metric in ['payment_amount', 'visitors', 'payment_conversion', 'refund_rate', 'uv_value']:
                            curr_val = row.get(metric, 0) or 0
                            prev_val = prev_data.get(metric, 0) or 0
                            if prev_val > 0:
                                changes[metric] = round((curr_val - prev_val) / prev_val * 100, 1)
                            else:
                                changes[metric] = None
                        row['changes'] = changes
            else:
                for row in rows:
                    row['changes'] = {m: None for m in ['payment_amount', 'visitors', 'payment_conversion', 'refund_rate', 'uv_value']}
        else:
            for row in rows:
                    row['changes'] = {}

    result = {'rows': rows, 'total': total_count, 'limit': limit, 'offset': offset, 'facets': facets}
    observed_rows = sum(int(row.get('has_data') or 0) for row in rows)
    availability = 'no-data' if not rows else 'available' if observed_rows == len(rows) else 'partial'
    missing_inputs = [] if observed_rows == len(rows) else ['product_daily']
    return success(
        result,
        availability=availability,
        evidence_level=evidence_level_for(availability, missing_inputs=missing_inputs),
        missing_inputs=missing_inputs,
        limitations=limitations_for(availability, missing_inputs=missing_inputs),
        freshness={'period': period or None, 'start': start or None, 'end': end or None},
        evidence=[{'source': 'products', 'row_count': len(rows), 'observed_fact_rows': observed_rows, 'total': total_count}],
    )

@data_bp.route('/api/refund_alert', methods=['GET'])
def get_refund_alert():
    """退款预警商品列表"""
    try:
        threshold = float(request.args.get('threshold', 0.20))
    except (ValueError, TypeError):
        threshold = 0.20
    dimension = request.args.get('dim', 'monthly')
    period = request.args.get('period', '')

    dim_cfg = DIMENSION_MAP.get(dimension)
    if not dim_cfg:
        return jsonify({'error': 'invalid dimension'}), 400
    table = dim_cfg['table']
    date_col = dim_cfg['date_col']

    with get_db() as conn:
        refund_rate_expr = 'd.refund_rate' if dimension == 'monthly' else 'CASE WHEN d.payment_amount > 0 THEN d.refund_amount * 1.0 / d.payment_amount ELSE 0 END'
        refund_filter = 'd.refund_rate' if dimension == 'monthly' else 'd.refund_amount'
        rows = [dict(r) for r in conn.execute(f'''
            SELECT p.product_id, p.title, p.image_url,
                   d.payment_amount, d.refund_amount,
                   {refund_rate_expr} as refund_rate,
                   {refund_rate_expr} as refund_rate_val
            FROM products p
            JOIN {table} d ON p.product_id = d.product_id AND d.{date_col} = ?
            WHERE p.status = 'active' AND {refund_filter} > 0
            ORDER BY d.payment_amount DESC
        ''', (period,)).fetchall()]
    return jsonify(rows)

@data_bp.route('/api/ad_performance', methods=['GET'])
def get_ad_performance():
    """推广效果数据"""
    dimension = request.args.get('dim', 'monthly')
    period = request.args.get('period', '')

    dim_cfg = DIMENSION_MAP.get(dimension)
    if not dim_cfg:
        return jsonify({'error': 'invalid dimension'}), 400
    table = dim_cfg['table']
    date_col = dim_cfg['date_col']

    with get_db() as conn:
        if dimension == 'monthly':
            ad_select = '''d.ad_spend, d.ad_roi, d.overall_roi, d.paid_ratio,
                   d.keyword_spend, d.keyword_roi, d.keyword_ppc,
                   d.crowd_spend, d.crowd_roi, d.crowd_ppc,
                   d.site_spend, d.site_roi, d.site_ppc,
                   d.payment_amount, d.refund_paid_ratio'''
        else:
            ad_select = '''d.ad_spend, d.ad_roi,
                   0 as overall_roi, 0 as paid_ratio,
                   0 as keyword_spend, 0 as keyword_roi, 0 as keyword_ppc,
                   0 as crowd_spend, 0 as crowd_roi, 0 as crowd_ppc,
                   0 as site_spend, 0 as site_roi, 0 as site_ppc,
                   d.payment_amount, 0 as refund_paid_ratio'''
        rows = [dict(r) for r in conn.execute(f'''
            SELECT p.product_id, p.title,
                   {ad_select}
            FROM products p
            JOIN {table} d ON p.product_id = d.product_id AND d.{date_col} = ?
            WHERE p.status = 'active' AND d.ad_spend > 0
            ORDER BY d.ad_spend DESC
        ''', (period,)).fetchall()]
    return jsonify(rows)

@data_bp.route('/api/ad_alerts', methods=['GET'])
def get_ad_alerts():
    """推广效果预警"""
    dim = request.args.get('dim', 'monthly')
    period = request.args.get('period', '')
    
    dim_cfg = DIMENSION_MAP.get(dim)
    if not dim_cfg:
        return jsonify([])
    table = dim_cfg['table']
    date_col = dim_cfg['date_col']
    
    with get_db() as conn:
        # Auto-detect latest period if not provided
        if not period:
            row = conn.execute(f'SELECT MAX({date_col}) as p FROM {table}').fetchone()
            period = row['p'] if row and row['p'] else ''
            if not period:
                return jsonify([])

        # Get current period ad data per product
        if dim == 'monthly':
            ad_select = 'd.ad_spend, d.ad_roi, d.overall_roi, d.payment_amount, d.keyword_spend, d.keyword_roi, d.crowd_spend, d.crowd_roi'
        else:
            # daily/weekly tables don't have overall_roi, keyword_*, crowd_* columns
            ad_select = 'd.ad_spend, d.ad_roi, d.payment_amount / NULLIF(d.ad_spend, 0) as overall_roi, d.payment_amount, 0 as keyword_spend, 0 as keyword_roi, 0 as crowd_spend, 0 as crowd_roi'
        
        rows = [dict(r) for r in conn.execute(f'''
            SELECT p.product_id, p.title, {ad_select}
            FROM products p
            JOIN {table} d ON p.product_id = d.product_id AND d.{date_col} = ?
            WHERE p.status = 'active' AND d.ad_spend > 0
        ''', (period,)).fetchall()]
        
        alerts = []
        for r in rows:
            roi = r.get('overall_roi') or r.get('ad_roi') or 0
            spend = r.get('ad_spend') or 0
            gmv = r.get('payment_amount') or 0
            
            # Alert 1: ROI < 3 (投产比过低)
            if roi > 0 and roi < 3:
                alerts.append({
                    'product_id': r['product_id'],
                    'title': r['title'],
                    'alert_type': 'low_roi',
                    'severity': 'danger' if roi < 1.5 else 'warning',
                    'message': f'投产比仅 {roi:.2f}，低于安全线3.0',
                    'metric': 'ROI',
                    'value': roi,
                    'threshold': 3.0,
                })
            
            # Alert 2: 高花费低产出 (花费>5000 but ROI<5)
            if spend > 5000 and roi > 0 and roi < 5:
                alerts.append({
                    'product_id': r['product_id'],
                    'title': r['title'],
                    'alert_type': 'high_cost_low_return',
                    'severity': 'warning',
                    'message': f'花费¥{spend:.0f}但投产比仅{roi:.2f}',
                    'metric': '花费/ROI',
                    'value': f'¥{spend:.0f}/{roi:.2f}',
                    'threshold': 'ROI≥5',
                })
            
            # Alert 3: 关键词推广ROI过低
            kw_roi = r.get('keyword_roi') or 0
            kw_spend = r.get('keyword_spend') or 0
            if kw_spend > 1000 and kw_roi > 0 and kw_roi < 2:
                alerts.append({
                    'product_id': r['product_id'],
                    'title': r['title'],
                    'alert_type': 'keyword_low_roi',
                    'severity': 'warning',
                    'message': f'直通车投产比仅{kw_roi:.2f}，花费¥{kw_spend:.0f}',
                    'metric': '直通车ROI',
                    'value': kw_roi,
                    'threshold': 2.0,
                })
            
            # Alert 4: 人群推广ROI过低
            cr_roi = r.get('crowd_roi') or 0
            cr_spend = r.get('crowd_spend') or 0
            if cr_spend > 1000 and cr_roi > 0 and cr_roi < 2:
                alerts.append({
                    'product_id': r['product_id'],
                    'title': r['title'],
                    'alert_type': 'crowd_low_roi',
                    'severity': 'warning',
                    'message': f'人群推广投产比仅{cr_roi:.2f}，花费¥{cr_spend:.0f}',
                    'metric': '人群ROI',
                    'value': cr_roi,
                    'threshold': 2.0,
                })
    
    # Sort by severity
    severity_order = {'danger': 0, 'warning': 1, 'info': 2}
    alerts.sort(key=lambda x: severity_order.get(x['severity'], 99))
    
    return jsonify(alerts)

@data_bp.route('/api/ad_trend', methods=['GET'])
def get_ad_trend():
    """推广趋势分析 — 最近N个周期的推广核心指标"""
    dim = request.args.get('dim', 'monthly')
    period = request.args.get('period', '')
    periods_count = int(request.args.get('count', 6))
    
    dim_cfg = DIMENSION_MAP.get(dim)
    if not dim_cfg:
        return jsonify([])
    table = dim_cfg['table']
    date_col = dim_cfg['date_col']
    
    with get_db() as conn:
        # Auto-detect latest period if not provided
        if not period:
            row = conn.execute(f'SELECT MAX({date_col}) as p FROM {table}').fetchone()
            period = row['p'] if row and row['p'] else ''
            if not period:
                return jsonify([])

        # Get recent periods
        if dim == 'monthly':
            rows = [dict(r) for r in conn.execute(f'''
                SELECT {date_col} as period,
                       SUM(ad_spend) as ad_spend,
                       SUM(payment_amount) as gmv,
                       SUM(ad_spend) / NULLIF(SUM(payment_amount), 0) as ad_ratio,
                       SUM(payment_amount) / NULLIF(SUM(ad_spend), 0) as overall_roi,
                       AVG(payment_conversion) as conversion,
                       COUNT(DISTINCT d.product_id) as product_count
                FROM {table} d
                JOIN products p ON p.product_id = d.product_id
                WHERE d.{date_col} <= ? AND p.status = 'active' AND d.ad_spend > 0
                GROUP BY d.{date_col}
                ORDER BY d.{date_col} DESC
                LIMIT ?
            ''', (period, periods_count)).fetchall()]
        elif dim == 'weekly':
            from datetime import timedelta
            try:
                base = datetime.strptime(period, '%Y-%m-%d')
                periods = [(base - timedelta(weeks=i)).strftime('%Y-%m-%d') for i in range(periods_count)]
                placeholders = ','.join(['?' for _ in periods])
                rows = [dict(r) for r in conn.execute(f'''
                    SELECT {date_col} as period,
                           SUM(ad_spend) as ad_spend,
                           SUM(payment_amount) as gmv,
                           SUM(ad_spend) / NULLIF(SUM(payment_amount), 0) as ad_ratio,
                           SUM(payment_amount) / NULLIF(SUM(ad_spend), 0) as overall_roi,
                           AVG(payment_conversion) as conversion,
                           COUNT(DISTINCT product_id) as product_count
                    FROM {table}
                    WHERE {date_col} IN ({placeholders})
                    GROUP BY {date_col}
                    ORDER BY {date_col} DESC
                ''', periods).fetchall()]
            except Exception:
                rows = []
        else:  # daily
            from datetime import timedelta
            try:
                base = datetime.strptime(period, '%Y-%m-%d')
                periods = [(base - timedelta(days=i)).strftime('%Y-%m-%d') for i in range(min(periods_count, 30))]
                placeholders = ','.join(['?' for _ in periods])
                rows = [dict(r) for r in conn.execute(f'''
                    SELECT {date_col} as period,
                           SUM(ad_spend) as ad_spend,
                           SUM(payment_amount) as gmv,
                           SUM(ad_spend) / NULLIF(SUM(payment_amount), 0) as ad_ratio,
                           SUM(payment_amount) / NULLIF(SUM(ad_spend), 0) as overall_roi,
                           AVG(payment_conversion) as conversion,
                           COUNT(DISTINCT product_id) as product_count
                    FROM {table}
                    WHERE {date_col} IN ({placeholders})
                    GROUP BY {date_col}
                    ORDER BY {date_col} DESC
                ''', periods).fetchall()]
            except Exception:
                rows = []
        
        # Reverse to chronological order
        rows.reverse()
        
        # Calculate MoM changes
        for i in range(1, len(rows)):
            prev = rows[i-1]
            curr = rows[i]
            for key in ['ad_spend', 'gmv', 'overall_roi', 'conversion']:
                prev_val = prev.get(key) or 0
                curr_val = curr.get(key) or 0
                if prev_val != 0:
                    curr[f'{key}_change'] = round((curr_val - prev_val) / abs(prev_val) * 100, 1)
                else:
                    curr[f'{key}_change'] = None
        
        return jsonify(rows)

@data_bp.route('/api/periods', methods=['GET'])
def get_periods():
    """获取可选的时间周期列表"""
    dimension = request.args.get('dim', 'weekly')
    unsupported = _reject_legacy_shop_scope(dimension)
    if unsupported:
        return unsupported
    dim_cfg = DIMENSION_MAP.get(dimension)
    if not dim_cfg:
        return jsonify({'error': 'invalid dimension'}), 400
    table = dim_cfg['table']
    date_col = dim_cfg['date_col']

    with get_db() as conn:
        if dimension == 'daily':
            rows = [dict(r) for r in conn.execute(
                f'SELECT DISTINCT {date_col} as period FROM {table} WHERE shop_id = ? ORDER BY {date_col} DESC LIMIT 90',
                (get_shop_id(),)).fetchall()]
        else:
            rows = [dict(r) for r in conn.execute(
                f'SELECT DISTINCT {date_col} as period FROM {table} ORDER BY {date_col} DESC').fetchall()]

    return jsonify(rows)

# 预留接口：数据备份（前端暂未调用）
@data_bp.route('/api/backup', methods=['POST'])
def trigger_backup():
    """手动触发数据库备份"""
    if current_app.config.get('TESTING'):
        return jsonify({'success': True, 'skipped': 'testing'})
    from scripts.import_data import backup_database
    success = backup_database()
    return jsonify({'success': success})

@data_bp.route('/api/legacy/actions', methods=['GET'])
def get_actions():
    """运营动作列表"""
    period = request.args.get('period', '')
    product_id = request.args.get('product_id', '')
    limit = request.args.get('limit', 100, type=int)
    limit = max(1, min(limit or 100, 500))

    with get_db() as conn:
        clauses = []
        params = []
        if period:
            clauses.append('a.action_date LIKE ?')
            params.append(f'{period}%')
        if product_id:
            clauses.append('a.product_id = ?')
            params.append(product_id)
        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ''
        params.append(limit)
        rows = [dict(r) for r in conn.execute(f'''
            SELECT a.id, a.product_id, a.action_date, a.action_type, a.action_detail,
                   a.effectiveness_score, p.title, p.image_url
            FROM operation_actions a
            JOIN products p ON a.product_id = p.product_id
            {where_sql}
            ORDER BY a.action_date DESC
            LIMIT ?
        ''', params).fetchall()]
    return jsonify(rows)

# ==================== 流量结构分析 API ====================

@data_bp.route('/api/traffic_structure', methods=['GET'])
def get_traffic_structure():
    """流量结构分析"""
    dim = request.args.get('dim', 'monthly')
    period = request.args.get('period', '')
    
    dim_cfg = DIMENSION_MAP.get(dim)
    if not dim_cfg:
        return jsonify({'error': 'Invalid dimension'}), 400
    table = dim_cfg['table']
    date_col = dim_cfg['date_col']
    
    with get_db() as conn:
        # Auto-detect latest period if not provided
        if not period:
            row = conn.execute(f'SELECT MAX({date_col}) as p FROM {table}').fetchone()
            period = row['p'] if row and row['p'] else ''
            if not period:
                return jsonify({'structure': {}, 'trend': []})

        # Current period traffic breakdown
        if dim == 'monthly':
            traffic_cols = 'SUM(search_ipv) as search, SUM(recommend_ipv) as recommend, SUM(paid_ipv) as paid, SUM(organic_ipv) as organic, SUM(visitors) as total'
        else:
            traffic_cols = 'SUM(search_ipv) as search, SUM(recommend_ipv) as recommend, SUM(paid_ipv) as paid, SUM(organic_ipv) as organic, SUM(ipv) as total'
        
        current = conn.execute(f'SELECT {traffic_cols} FROM {table} WHERE {date_col} = ?', (period,)).fetchone()
        current = dict(current) if current else {}
        
        total = current.get('total') or 0
        if total > 0:
            structure = {
                'search': round((current.get('search') or 0) / total * 100, 1),
                'recommend': round((current.get('recommend') or 0) / total * 100, 1),
                'paid': round((current.get('paid') or 0) / total * 100, 1),
                'organic': round((current.get('organic') or 0) / total * 100, 1),
                'free': round(((current.get('search') or 0) + (current.get('recommend') or 0)) / total * 100, 1),
            }
            structure['search_val'] = current.get('search') or 0
            structure['recommend_val'] = current.get('recommend') or 0
            structure['paid_val'] = current.get('paid') or 0
            structure['organic_val'] = current.get('organic') or 0
            structure['total_val'] = total
        else:
            structure = {}
        
        # Trend (last 6 periods)
        trend = []
        if dim == 'monthly':
            rows = conn.execute(f'''
                SELECT {date_col} as period,
                       SUM(search_ipv) as search, SUM(recommend_ipv) as recommend,
                       SUM(paid_ipv) as paid, SUM(organic_ipv) as organic, SUM(visitors) as total
                FROM {table}
                WHERE {date_col} <= ?
                GROUP BY {date_col} ORDER BY {date_col} DESC LIMIT 6
            ''', (period,)).fetchall()
        elif dim == 'weekly':
            try:
                base = datetime.strptime(period, '%Y-%m-%d')
                periods = [(base - timedelta(weeks=i)).strftime('%Y-%m-%d') for i in range(6)]
                placeholders = ','.join(['?' for _ in periods])
                rows = conn.execute(f'''
                    SELECT {date_col} as period,
                           SUM(search_ipv) as search, SUM(recommend_ipv) as recommend,
                           SUM(paid_ipv) as paid, SUM(organic_ipv) as organic, SUM(ipv) as total
                    FROM {table} WHERE {date_col} IN ({placeholders})
                    GROUP BY {date_col} ORDER BY {date_col} DESC
                ''', periods).fetchall()
            except Exception:
                rows = []
        else:
            rows = []
        
        for r in rows:
            r = dict(r)
            t = r.get('total') or 0
            if t > 0:
                r['search_pct'] = round((r.get('search') or 0) / t * 100, 1)
                r['recommend_pct'] = round((r.get('recommend') or 0) / t * 100, 1)
                r['paid_pct'] = round((r.get('paid') or 0) / t * 100, 1)
                r['organic_pct'] = round((r.get('organic') or 0) / t * 100, 1)
            trend.append(r)
        trend.reverse()
    
    return jsonify({'structure': structure, 'trend': trend, 'period': period, 'dim': dim})

# ==================== 任务看板 API ====================

@data_bp.route('/api/tasks', methods=['GET'])
def get_tasks():
    """获取任务列表"""
    status = request.args.get('status', '')
    priority = request.args.get('priority', '')
    with get_db() as conn:
        where = ['1=1']
        params = []
        if status:
            where.append('status = ?')
            params.append(status)
        if priority:
            where.append('priority = ?')
            params.append(priority)
        rows = [dict(r) for r in conn.execute(f'''
            SELECT * FROM task_items WHERE {' AND '.join(where)}
            ORDER BY CASE priority WHEN 'P0' THEN 0 WHEN 'P1' THEN 1 WHEN 'P2' THEN 2 WHEN 'P3' THEN 3 ELSE 4 END,
                     due_date IS NULL, due_date ASC, created_at DESC
        ''', params).fetchall()]
    return jsonify(rows)

@data_bp.route('/api/tasks', methods=['POST'])
def create_task():
    """创建任务"""
    data = request.get_json(force=True, silent=True) or {}
    with get_db() as conn:
        conn.execute('''INSERT INTO task_items (title, description, status, priority, assignee, due_date)
            VALUES (?, ?, ?, ?, ?, ?)''',
            (data.get('title', ''), data.get('description', ''), data.get('status', 'todo'),
             data.get('priority', 'P2'), data.get('assignee', ''), data.get('due_date', '')))
        conn.commit()
        return jsonify({'success': True})

@data_bp.route('/api/tasks/<int:task_id>', methods=['PUT'])
def update_task(task_id):
    """更新任务"""
    data = request.get_json(force=True, silent=True) or {}
    with get_db() as conn:
        sets = []
        params = []
        for field in ['title', 'description', 'status', 'priority', 'assignee', 'due_date']:
            if field in data:
                sets.append(f'{field} = ?')
                params.append(data[field])
        if not sets:
            return jsonify({'error': 'No fields to update'}), 400
        sets.append("updated_at = datetime('now')")
        params.append(task_id)
        cursor = conn.execute(f'UPDATE task_items SET {", ".join(sets)} WHERE id = ?', params)
        if cursor.rowcount == 0:
            return jsonify({'error': 'Task not found'}), 404
        conn.commit()
        return jsonify({'success': True})

@data_bp.route('/api/tasks/<int:task_id>', methods=['DELETE'])
def delete_task(task_id):
    """删除任务"""
    with get_db() as conn:
        cursor = conn.execute('DELETE FROM task_items WHERE id = ?', (task_id,))
        if cursor.rowcount == 0:
            return jsonify({'error': 'Task not found'}), 404
        conn.commit()
        return jsonify({'success': True})

# ==================== 用户KPI API ====================

@data_bp.route('/api/user_kpis', methods=['GET'])
def get_user_kpis():
    """获取用户KPI列表"""
    period = request.args.get('period', '')
    with get_db() as conn:
        where = '1=1'
        params = []
        if period:
            where = 'period = ?'
            params.append(period)
        rows = [dict(r) for r in conn.execute(f'''
            SELECT * FROM user_kpis WHERE {where} ORDER BY achievement_rate DESC
        ''', params).fetchall()]
    return jsonify(rows)

@data_bp.route('/api/user_kpis', methods=['POST'])
def create_user_kpi():
    """创建用户KPI"""
    data = request.get_json(force=True, silent=True) or {}
    with get_db() as conn:
        conn.execute('''INSERT INTO user_kpis (user_name, period, target_gmv, actual_gmv, achievement_rate, rating)
            VALUES (?, ?, ?, ?, ?, ?)''',
            (data.get('user_name', ''), data.get('period', ''), data.get('target_gmv', 0),
             data.get('actual_gmv', 0), data.get('achievement_rate', 0), data.get('rating', 'C')))
        conn.commit()
        return jsonify({'success': True})

@data_bp.route('/api/user_kpis/<int:kpi_id>', methods=['PUT'])
def update_user_kpi(kpi_id):
    """更新用户KPI"""
    data = request.get_json(force=True, silent=True) or {}
    with get_db() as conn:
        sets = []
        params = []
        for field in ['user_name', 'period', 'target_gmv', 'actual_gmv', 'achievement_rate', 'rating']:
            if field in data:
                sets.append(f'{field} = ?')
                params.append(data[field])
        if not sets:
            return jsonify({'error': 'No fields to update'}), 400
        sets.append("updated_at = datetime('now')")
        params.append(kpi_id)
        cursor = conn.execute(f'UPDATE user_kpis SET {", ".join(sets)} WHERE id = ?', params)
        if cursor.rowcount == 0:
            return jsonify({'error': 'KPI not found'}), 404
        conn.commit()
        return jsonify({'success': True})

@data_bp.route('/api/user_kpis/<int:kpi_id>', methods=['DELETE'])
def delete_user_kpi(kpi_id):
    """删除用户KPI"""
    with get_db() as conn:
        cursor = conn.execute('DELETE FROM user_kpis WHERE id = ?', (kpi_id,))
        if cursor.rowcount == 0:
            return jsonify({'error': 'KPI not found'}), 404
        conn.commit()
        return jsonify({'success': True})

# ==================== 搜索词效能 API ====================

@data_bp.route('/api/upload/keywords', methods=['POST'])
def upload_keywords():
    """上传搜索词数据Excel"""
    if 'file' not in request.files:
        return jsonify({'error': '未上传文件'}), 400
    file = request.files['file']
    if not file.filename.lower().endswith(('.xlsx', '.xls')):
        return jsonify({'error': '仅支持Excel文件'}), 400
    
    import pandas as pd
    from db import init_db, get_db
    
    init_db()
    
    try:
        df = pd.read_excel(file)
        df.columns = [str(c).strip().lower() for c in df.columns]
        
        # Column mapping (生意参谋 common column names)
        col_map = {
            '搜索词': 'keyword', '关键词': 'keyword', 'keyword': 'keyword',
            '搜索人气': 'popularity', '人气': 'popularity', 'popularity': 'popularity',
            '展现量': 'impressions', '展现': 'impressions', 'impressions': 'impressions',
            '点击量': 'clicks', '点击': 'clicks', 'clicks': 'clicks',
            '点击率': 'ctr', 'ctr': 'ctr',
            '花费': 'cost', '消耗': 'cost', 'cost': 'cost',
            '支付金额': 'gmv', '成交金额': 'gmv', 'gmv': 'gmv',
            '转化率': 'cvr', '支付转化率': 'cvr', 'cvr': 'cvr',
            '投入产出比': 'roi', 'roi': 'roi', '投产比': 'roi',
            '点击单价': 'cpc', 'cpc': 'cpc',
            '支付买家数': 'conversion', '成交笔数': 'conversion', 'conversion': 'conversion',
        }
        
        renamed = {}
        for cn, en in col_map.items():
            if cn in df.columns:
                renamed[cn] = en
        
        if 'keyword' not in renamed.values():
            # Try to find keyword column by common patterns
            for c in df.columns:
                if '词' in c or 'keyword' in c:
                    renamed[c] = 'keyword'
                    break
        
        if 'keyword' not in renamed.values():
            return jsonify({'error': '未找到搜索词列，请确认表头包含"搜索词"或"关键词"'}), 400
        
        df = df.rename(columns=renamed)
        
        # Extract date from filename or use today
        import re
        date_match = re.search(r'(\d{4}-\d{2}-\d{2})', file.filename)
        if date_match:
            date_str = date_match.group(1)
        else:
            date_match = re.search(r'(\d{4}\.\d{2}\.\d{2})', file.filename)
            if date_match:
                date_str = date_match.group(1).replace('.', '-')
            else:
                from datetime import datetime
                date_str = datetime.now().strftime('%Y-%m-%d')
        
        # Normalize numeric values before calculating derived metrics. Tmall
        # exports often use blank cells or "-" for unavailable values.
        numeric_columns = [
            'popularity', 'impressions', 'clicks', 'ctr', 'cost', 'gmv',
            'cvr', 'roi', 'cpc', 'conversion',
        ]
        for numeric_column in numeric_columns:
            if numeric_column in df.columns:
                df[numeric_column] = pd.to_numeric(df[numeric_column], errors='coerce').fillna(0)

        # Calculate derived metrics
        if 'ctr' not in df.columns and 'clicks' in df.columns and 'impressions' in df.columns:
            df['ctr'] = df.apply(lambda r: r['clicks'] / r['impressions'] if r.get('impressions', 0) > 0 else 0, axis=1)
        if 'cpc' not in df.columns and 'cost' in df.columns and 'clicks' in df.columns:
            df['cpc'] = df.apply(lambda r: r['cost'] / r['clicks'] if r.get('clicks', 0) > 0 else 0, axis=1)
        if 'roi' not in df.columns and 'gmv' in df.columns and 'cost' in df.columns:
            df['roi'] = df.apply(lambda r: r['gmv'] / r['cost'] if r.get('cost', 0) > 0 else 0, axis=1)
        if 'cvr' not in df.columns and 'conversion' in df.columns and 'clicks' in df.columns:
            df['cvr'] = df.apply(lambda r: r['conversion'] / r['clicks'] if r.get('clicks', 0) > 0 else 0, axis=1)

        # Calculate efficacy (词效能)
        with get_db() as conn:
            avg_ctr = df['ctr'].mean() if 'ctr' in df.columns else 0
            avg_cvr = df['cvr'].mean() if 'cvr' in df.columns else 0
            
            count = 0
            for _, row in df.iterrows():
                kw = str(row.get('keyword', '')).strip()
                if not kw or kw.lower() in {'nan', 'none', 'null', '--'}:
                    continue
                
                ctr_val = float(row.get('ctr', 0) or 0)
                cvr_val = float(row.get('cvr', 0) or 0)
                
                # Efficacy = (CTR / avg_CTR) * (CVR / avg_CVR)
                if avg_ctr > 0 and avg_cvr > 0:
                    efficacy = (ctr_val / avg_ctr) * (cvr_val / avg_cvr)
                else:
                    efficacy = 0
                
                # Category
                if efficacy >= 1.2:
                    category = '蓝海词'
                elif efficacy >= 0.8:
                    category = '流量词'
                else:
                    category = '废词'
                
                conn.execute('''
                    INSERT INTO keyword_metrics
                    (date, keyword, popularity, impressions, clicks, ctr, cost, gmv, cvr, roi, cpc, conversion, efficacy, category)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(date, keyword) DO UPDATE SET
                        popularity=excluded.popularity, impressions=excluded.impressions,
                        clicks=excluded.clicks, ctr=excluded.ctr, cost=excluded.cost,
                        gmv=excluded.gmv, cvr=excluded.cvr, roi=excluded.roi,
                        cpc=excluded.cpc, conversion=excluded.conversion,
                        efficacy=excluded.efficacy, category=excluded.category
                ''', (
                    date_str, kw,
                    int(row.get('popularity', 0) or 0),
                    int(row.get('impressions', 0) or 0),
                    int(row.get('clicks', 0) or 0),
                    float(ctr_val),
                    float(row.get('cost', 0) or 0),
                    float(row.get('gmv', 0) or 0),
                    float(cvr_val),
                    float(row.get('roi', 0) or 0),
                    float(row.get('cpc', 0) or 0),
                    int(row.get('conversion', 0) or 0),
                    float(efficacy),
                    category
                ))
                count += 1
            
            conn.commit()
        
        return jsonify({'success': True, 'rows_imported': count, 'date': date_str})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@data_bp.route('/api/keywords', methods=['GET'])
def get_keywords():
    """搜索词效能列表"""
    date = request.args.get('date', '')
    category = request.args.get('category', '')
    search = request.args.get('search', '')
    sort = request.args.get('sort', 'efficacy')
    order = request.args.get('order', 'desc')
    try:
        page = max(1, int(request.args.get('page', 1)))
        per_page = max(1, min(int(request.args.get('per_page', 50)), 200))
    except (TypeError, ValueError):
        return jsonify({'error': 'page and per_page must be positive integers'}), 400
    
    with get_db() as conn:
        # Get available dates
        dates = [r[0] for r in conn.execute('SELECT DISTINCT date FROM keyword_metrics ORDER BY date DESC').fetchall()]
        if not date and dates:
            date = dates[0]
        
        where_clauses = ['1=1']
        params = []
        if date:
            where_clauses.append('date = ?')
            params.append(date)
        if category:
            where_clauses.append('category = ?')
            params.append(category)
        if search:
            where_clauses.append('keyword LIKE ?')
            params.append(f'%{search}%')
        
        where_sql = ' AND '.join(where_clauses)
        
        # Count
        total = conn.execute(f'SELECT COUNT(*) FROM keyword_metrics WHERE {where_sql}', params).fetchone()[0]
        
        # Sort whitelist
        sort_whitelist = ['efficacy', 'popularity', 'impressions', 'clicks', 'ctr', 'cost', 'gmv', 'roi', 'cvr', 'cpc', 'keyword']
        if sort not in sort_whitelist:
            sort = 'efficacy'
        order_sql = 'DESC' if order.lower() == 'desc' else 'ASC'
        
        # Query
        offset = (page - 1) * per_page
        rows = [dict(r) for r in conn.execute(f'''
            SELECT * FROM keyword_metrics WHERE {where_sql}
            ORDER BY {sort} {order_sql}
            LIMIT ? OFFSET ?
        ''', params + [per_page, offset]).fetchall()]
        
        # Summary stats
        summary = {}
        if date:
            s = conn.execute('''
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN category='蓝海词' THEN 1 ELSE 0 END) as blue_ocean,
                    SUM(CASE WHEN category='流量词' THEN 1 ELSE 0 END) as traffic,
                    SUM(CASE WHEN category='废词' THEN 1 ELSE 0 END) as dead,
                    AVG(ctr) as avg_ctr,
                    AVG(cvr) as avg_cvr,
                    AVG(roi) as avg_roi,
                    SUM(cost) as total_cost,
                    SUM(gmv) as total_gmv
                FROM keyword_metrics WHERE date = ?
            ''', (date,)).fetchone()
            if s:
                summary = dict(s)
    
    return jsonify({
        'items': rows,
        'total': total,
        'page': page,
        'per_page': per_page,
        'dates': dates,
        'date': date,
        'summary': summary,
    })

# ==================== 市场分析 API ====================

@data_bp.route('/api/upload/market', methods=['POST'])
def upload_market():
    """上传市场分析数据文件"""
    files = request.files.getlist('files')
    if not files:
        return jsonify({'error': 'No files uploaded'}), 400

    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    saved_paths = []

    for file in files:
        if not file.filename:
            continue
        filename, filepath = _unique_upload_path(file.filename)
        file.save(filepath)
        saved_paths.append(filepath)

    if len(saved_paths) < 3:
        return jsonify({'error': '需要至少3个文件（30天搜索、7天搜索、趋势分析）'}), 400

    try:
        from scripts.import_market import identify_market_files, import_market_data
        identified = identify_market_files(saved_paths)

        if not identified['f30'] or not identified['f7'] or not identified['ft']:
            return jsonify({
                'success': False,
                'error': '无法识别文件类型，请确保文件名包含"搜索排行"和"趋势分析"',
                'identified': identified
            }), 400

        count = import_market_data(identified['f30'], identified['f7'], identified['ft'])
        return jsonify({
            'success': True,
            'count': count,
            'message': '市场分析数据导入成功，共处理 %d 个关键词' % count
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@data_bp.route('/api/market/summary', methods=['GET'])
def get_market_summary():
    """获取市场分析摘要"""
    category = request.args.get('category', '')
    report_id = request.args.get('report_id', '')

    with get_db() as conn:
        query = 'SELECT * FROM market_analysis WHERE 1=1'
        params = []
        if category:
            query += ' AND category_path = ?'
            params.append(category)
        if report_id:
            query += ' AND id = ?'
            params.append(report_id)
        query += ' ORDER BY analysis_date DESC LIMIT 1'

        row = conn.execute(query, params).fetchone()

    if not row:
        return jsonify({'meta': None, 'summary': {}, 'keywords_count': 0, 'empty': True})

    data = dict(row)
    return jsonify({
        'meta': {
            'category_path': data['category_path'],
            'category_short': data['category_short'],
            'period_30d': data['period_30d'],
            'period_7d': data['period_7d'],
            'period_trend': data['period_trend'],
            'total_keywords': data['total_keywords'],
            'avg_ctr_7d': data['avg_ctr_7d'],
            'avg_cvr_30d': data['avg_cvr_30d'],
            'top5_keywords': json.loads(data['top5_keywords']) if data['top5_keywords'] else [],
        },
        'summary': json.loads(data['summary_data']) if data['summary_data'] else {},
        'keywords_count': data['total_keywords'],
    })


@data_bp.route('/api/market/keywords', methods=['GET'])
def get_market_keywords():
    """获取关键词分析数据"""
    category = request.args.get('category', '')
    limit = max(1, min(request.args.get('limit', 50, type=int) or 50, 200))
    opportunity = request.args.get('opportunity', '')

    with get_db() as conn:
        query = 'SELECT * FROM market_analysis WHERE 1=1'
        params = []
        if category:
            query += ' AND category_path = ?'
            params.append(category)
        query += ' ORDER BY analysis_date DESC LIMIT 1'

        row = conn.execute(query, params).fetchone()

    if not row:
        return jsonify({'error': 'no data'}), 404

    data = dict(row)
    keywords = json.loads(data['keywords_data']) if data['keywords_data'] else []

    # 按机会类别过滤
    if opportunity:
        keywords = [kw for kw in keywords if kw.get('opportunity_category') == opportunity]

    total = len(keywords)
    keywords = keywords[:limit]

    return jsonify({
        'keywords': keywords,
        'total': total,
    })


@data_bp.route('/api/market/need_stats', methods=['GET'])
def get_market_need_stats():
    """获取8维度需求统计"""
    category = request.args.get('category', '')

    with get_db() as conn:
        query = 'SELECT * FROM market_analysis WHERE 1=1'
        params = []
        if category:
            query += ' AND category_path = ?'
            params.append(category)
        query += ' ORDER BY analysis_date DESC LIMIT 1'

        row = conn.execute(query, params).fetchone()

    if not row:
        return jsonify({'error': 'no data'}), 404

    data = dict(row)
    return jsonify({
        'need_stats': json.loads(data['need_stats_data']) if data['need_stats_data'] else {},
        'dimension_details': json.loads(data['dimension_details']) if data['dimension_details'] else {},
    })


@data_bp.route('/api/market/rankings', methods=['GET'])
def get_market_rankings():
    """获取商品排名数据"""
    category = request.args.get('category', '')
    ranking_type = request.args.get('ranking_type', '')

    with get_db() as conn:
        query = 'SELECT * FROM market_analysis WHERE 1=1'
        params = []
        if category:
            query += ' AND category_path = ?'
            params.append(category)
        query += ' ORDER BY analysis_date DESC LIMIT 1'

        row = conn.execute(query, params).fetchone()

    if not row:
        return jsonify({'error': 'no data'}), 404

    data = dict(row)
    rankings = json.loads(data['rankings_data']) if data['rankings_data'] else {}

    # 按排名类型过滤
    if ranking_type and ranking_type in rankings:
        rankings = {ranking_type: rankings[ranking_type]}

    return jsonify({
        'rankings': rankings,
    })


@data_bp.route('/api/market/histograms', methods=['GET'])
def get_market_histograms():
    """获取直方图数据"""
    category = request.args.get('category', '')

    with get_db() as conn:
        query = 'SELECT * FROM market_analysis WHERE 1=1'
        params = []
        if category:
            query += ' AND category_path = ?'
            params.append(category)
        query += ' ORDER BY analysis_date DESC LIMIT 1'

        row = conn.execute(query, params).fetchone()

    if not row:
        return jsonify({'error': 'no data'}), 404

    data = dict(row)
    return jsonify({
        'histograms': json.loads(data['histograms_data']) if data['histograms_data'] else {},
    })


@data_bp.route('/api/market/opportunities', methods=['GET'])
def get_market_opportunities():
    """获取关键词机会（跨Skill联动）"""
    analysis_date = request.args.get('analysis_date', '')

    with get_db() as conn:

        if analysis_date:
            query = '''
                SELECT * FROM market_keyword_opportunities
                WHERE analysis_date = ?
                  AND opportunity_category IN ('供给不足蓝海词', '小众高意向蓝海词')
                ORDER BY opportunity_score DESC
            '''
            params = [analysis_date]
        else:
            query = '''
                SELECT * FROM market_keyword_opportunities
                WHERE analysis_date = (
                    SELECT MAX(analysis_date) FROM market_keyword_opportunities
                )
                  AND opportunity_category IN ('供给不足蓝海词', '小众高意向蓝海词')
                ORDER BY opportunity_score DESC
            '''
            params = []

        rows = [dict(r) for r in conn.execute(query, params).fetchall()]

    # 解析 need_tags JSON
    for row in rows:
        if row.get('need_tags'):
            try:
                row['need_tags'] = json.loads(row['need_tags'])
            except (json.JSONDecodeError, TypeError):
                row['need_tags'] = []

    return jsonify({
        'opportunities': rows,
    })


@data_bp.route('/api/market/reports', methods=['GET'])
def get_market_reports():
    """获取所有市场分析报告列表"""
    with get_db() as conn:
        rows = [dict(r) for r in conn.execute('''
            SELECT id, analysis_date, category_path, total_keywords, created_at
            FROM market_analysis
            ORDER BY analysis_date DESC
        ''').fetchall()]
    return jsonify({
        'reports': rows,
    })

@data_bp.route('/api/legacy/actions', methods=['POST'])
def create_action():
    return failure(
        'LEGACY_READ_ONLY',
        'Legacy actions are read-only; use /api/actions.',
        details={'replacement': '/api/actions'},
        status=409,
    )

@data_bp.route('/api/legacy/actions/<int:action_id>', methods=['PUT'])
def update_action(action_id):
    return failure(
        'LEGACY_READ_ONLY',
        'Legacy actions are read-only; use /api/actions.',
        details={'replacement': '/api/actions'},
        status=409,
    )

@data_bp.route('/api/legacy/actions/<int:action_id>', methods=['DELETE'])
def delete_action(action_id):
    return failure(
        'LEGACY_READ_ONLY',
        'Legacy actions are read-only; use /api/actions.',
        details={'replacement': '/api/actions'},
        status=409,
    )

@data_bp.route('/api/action_stats', methods=['GET'])
def get_action_stats():
    """动作类型效果统计"""
    with get_db() as conn:
        rows = [dict(r) for r in conn.execute('''
            SELECT action_type,
                   COUNT(*) as count,
                   AVG(payment_change) as avg_payment_change,
                   AVG(conversion_change) as avg_conversion_change,
                   AVG(effectiveness_score) as avg_score
            FROM operation_actions
            WHERE effectiveness_score > 0
            GROUP BY action_type
            ORDER BY avg_score DESC
        ''').fetchall()]
    return jsonify(rows)

# 预留接口：异常检测（前端暂未调用）
@data_bp.route('/api/anomalies', methods=['GET'])
def get_anomalies():
    """获取当前周期的异常指标"""
    dimension = request.args.get('dim', 'weekly')
    period = request.args.get('period', '')
    prev_period = request.args.get('prev_period', '')

    dim_cfg = DIMENSION_MAP.get(dimension)
    if not dim_cfg:
        return jsonify({'error': 'invalid dimension'}), 400
    table = dim_cfg['table']
    date_col = dim_cfg['date_col']
    visitors_col = dim_cfg['visitors_col']

    with get_db() as conn:

        def query_period(p):
            if not p:
                return None
            row = conn.execute(f'''
                SELECT
                    COALESCE(SUM(payment_amount),0) as gmv,
                    COALESCE(SUM(refund_amount),0) as refund,
                    COALESCE(SUM(payment_amount),0) - COALESCE(SUM(refund_amount),0) as net_sales,
                    COALESCE(SUM({visitors_col}),0) as visitors,
                    CASE WHEN SUM({visitors_col}) > 0 THEN SUM(payment_amount) * 1.0 / SUM({visitors_col}) ELSE 0 END as aov,
                    CASE WHEN SUM(payment_amount) > 0 THEN SUM(refund_amount) * 1.0 / SUM(payment_amount) ELSE 0 END as refund_rate,
                    COALESCE(SUM(ad_spend),0) as ad_spend,
                    CASE WHEN SUM(ad_spend) > 0 THEN SUM(payment_amount) * 1.0 / SUM(ad_spend) ELSE 0 END as roi
                FROM {table} WHERE {date_col} = ?
            ''', (p,)).fetchone()
            return dict(row) if row else None

        current = query_period(period)
        previous = query_period(prev_period)

        anomalies = []
        config = load_config()
        anomaly_decline = config.get('thresholds', {}).get('anomaly_decline', 0.20)

        if current and previous:
            metric_labels = {
                'gmv': '支付金额',
                'net_sales': '净销售额',
                'visitors': '访客数',
                'aov': '客单价'
            }
            for key, label in metric_labels.items():
                prev_val = previous.get(key, 0)
                curr_val = current.get(key, 0)
                if prev_val > 0:
                    change = round((curr_val - prev_val) / prev_val * 100, 1)
                    if change < 0 and abs(change) > anomaly_decline * 100:
                        anomalies.append({
                            'metric': key,
                            'label': label,
                            'change': change,
                            'current': curr_val,
                            'previous': prev_val,
                            'direction': 'decline',
                            'severity': 'high' if abs(change) > anomaly_decline * 200 else 'warning'
                        })

    return jsonify({
        'period': period,
        'prev_period': prev_period,
        'anomaly_threshold': anomaly_decline,
        'anomalies': anomalies,
        'has_anomalies': len(anomalies) > 0
    })

# ==================== 目标管理 API ====================

def _get_prev_month(period):
    """获取上一个自然月"""
    try:
        parts = period.split('-')
        year, month = int(parts[0]), int(parts[1])
        month -= 1
        if month == 0:
            month = 12
            year -= 1
        return f"{year}-{month:02d}"
    except (ValueError, IndexError, TypeError):
        return None

def generate_alerts(conn, period):
    """生成预警"""

    # 获取目标
    target = conn.execute('SELECT * FROM shop_targets WHERE period = ?', (period,)).fetchone()
    if not target:
        return

    target = dict(target)
    actual = conn.execute('''
        SELECT SUM(payment_amount) as gsv, SUM(ad_spend) as ad_spend, AVG(payment_conversion) as conversion
        FROM monthly_data WHERE month = ?
    ''', (period,)).fetchone()
    actual = dict(actual) if actual else {}

    gsv_actual = actual.get('gsv', 0) or 0
    ad_actual = actual.get('ad_spend', 0) or 0
    gsv_target = target.get('target_gsv', 0) or 0
    ad_target = target.get('target_ad_spend', 0) or 0
    target_ad_ratio = target.get('target_ad_ratio', 0) or 0

    today = datetime.now()
    try:
        month_end = datetime.strptime(period + '-01', '%Y-%m-%d')
        _, days_in_month = calendar.monthrange(month_end.year, month_end.month)
        if today.year == month_end.year and today.month == month_end.month:
            time_progress = today.day / days_in_month
        else:
            time_progress = 1.0
    except (ValueError, IndexError, TypeError):
        time_progress = 1.0

    # 预警1：进度落后
    if gsv_target > 0 and time_progress > 0 and time_progress < 1:
        gsv_progress = gsv_actual / gsv_target
        if gsv_progress < time_progress * 0.7:
            severity = 'critical' if gsv_progress < time_progress * 0.5 else 'high'
            conn.execute('''
                INSERT INTO alerts (alert_date, alert_type, severity, title, detail, metric_name, current_value, target_value, period)
                VALUES (date('now'), 'progress_behind', ?, ?, ?, ?, ?, ?, ?)
            ''', (severity, 'GSV进度严重落后',
                  f'当前完成{gsv_progress*100:.1f}%，时间进度{time_progress*100:.1f}%，缺口¥{(gsv_target-gsv_actual)/10000:.1f}万',
                  'gsv', gsv_actual, gsv_target, period))

    # 预警2：费比超标
    if gsv_actual > 0 and target_ad_ratio > 0:
        actual_ad_ratio = ad_actual / gsv_actual
        if actual_ad_ratio > target_ad_ratio * 1.3:
            severity = 'critical' if actual_ad_ratio > target_ad_ratio * 1.5 else 'high'
            conn.execute('''
                INSERT INTO alerts (alert_date, alert_type, severity, title, detail, metric_name, current_value, target_value, period)
                VALUES (date('now'), 'ad_ratio_exceed', ?, ?, ?, ?, ?, ?, ?)
            ''', (severity, '费比超标',
                  f'实际费比{actual_ad_ratio*100:.1f}%，目标{target_ad_ratio*100:.1f}%，超{(actual_ad_ratio-target_ad_ratio)*100:.1f}个百分点',
                  'ad_ratio', actual_ad_ratio, target_ad_ratio, period))

    # 预警3：智能预测不达标
    if gsv_target > 0 and time_progress > 0.1 and time_progress < 0.9:
        forecast = gsv_actual / time_progress
        if forecast < gsv_target * 0.9:
            severity = 'high' if forecast < gsv_target * 0.7 else 'warning'
            conn.execute('''
                INSERT INTO alerts (alert_date, alert_type, severity, title, detail, metric_name, current_value, target_value, period)
                VALUES (date('now'), 'forecast_miss', ?, ?, ?, ?, ?, ?, ?)
            ''', (severity, '月底GSV可能不达标',
                  f'预测月底GSV ¥{forecast/10000:.1f}万，目标 ¥{gsv_target/10000:.1f}万，缺口 ¥{(gsv_target-forecast)/10000:.1f}万',
                  'gsv_forecast', forecast, gsv_target, period))

    # 预警4：同比异常
    prev_period = _get_prev_month(period)
    if prev_period:
        prev = conn.execute('SELECT SUM(payment_amount) as gsv FROM monthly_data WHERE month = ?', (prev_period,)).fetchone()
        prev = dict(prev) if prev else {}
        prev_gsv = prev.get('gsv', 0) or 0
        if prev_gsv > 0:
            yoy = (gsv_actual - prev_gsv) / prev_gsv
            if yoy < -0.3:
                severity = 'critical' if yoy < -0.5 else 'high'
                conn.execute('''
                    INSERT INTO alerts (alert_date, alert_type, severity, title, detail, metric_name, current_value, target_value, period)
                    VALUES (date('now'), 'yoy_anomaly', ?, ?, ?, ?, ?, ?, ?)
                ''', (severity, '同比大幅下降',
                      f'GSV同比{yoy*100:.1f}%，上月 ¥{prev_gsv/10000:.1f}万，本月 ¥{gsv_actual/10000:.1f}万',
                      'gsv_yoy', gsv_actual, prev_gsv, period))

    conn.commit()

@data_bp.route('/api/target_progress', methods=['GET'])
def get_target_progress():
    if request.args.get('dim', 'monthly') == 'daily' and (denied := reject_legacy_shop_scope('店铺目标')):
        return denied
    """目标完成进度 — 支持日/周/月维度"""
    period = request.args.get('period', '')
    dim = request.args.get('dim', 'monthly')
    unsupported = _reject_legacy_shop_scope(dim)
    if unsupported:
        return unsupported
    shop_id = get_shop_id()
    with get_db() as conn:

        # 获取店铺目标（period字段兼容月/周/日格式）
        target = conn.execute('SELECT * FROM shop_targets WHERE period = ?', (period,)).fetchone()
        target = dict(target) if target else None

        # 根据维度查询实际数据
        if dim == 'daily':
            actual = conn.execute('''
                SELECT
                    SUM(payment_amount) as gsv,
                    SUM(refund_amount) as refund,
                    SUM(payment_amount) - SUM(refund_amount) as net_sales,
                    SUM(ipv) as visitors,
                    AVG(payment_conversion) as conversion,
                    SUM(ad_spend) as ad_spend,
                    COUNT(DISTINCT product_id) as product_count
                FROM daily_data WHERE shop_id = ? AND date = ?
            ''', (shop_id, period)).fetchone()
        elif dim == 'weekly':
            actual = conn.execute('''
                SELECT
                    SUM(payment_amount) as gsv,
                    SUM(refund_amount) as refund,
                    SUM(payment_amount) - SUM(refund_amount) as net_sales,
                    SUM(ipv) as visitors,
                    AVG(payment_conversion) as conversion,
                    SUM(ad_spend) as ad_spend,
                    COUNT(DISTINCT product_id) as product_count
                FROM weekly_data WHERE week_start = ?
            ''', (period,)).fetchone()
        else:
            actual = conn.execute('''
                SELECT
                    SUM(payment_amount) as gsv,
                    SUM(refund_amount) as refund,
                    SUM(payment_amount) - SUM(refund_amount) as net_sales,
                    SUM(visitors) as visitors,
                    AVG(payment_conversion) as conversion,
                    SUM(ad_spend) as ad_spend,
                    COUNT(DISTINCT product_id) as product_count
                FROM monthly_data WHERE month = ?
            ''', (period,)).fetchone()
        actual = dict(actual) if actual else None

        result = {'target': target, 'actual': actual, 'period': period, 'dim': dim}

        if target and actual:
            gsv_target = target['target_gsv'] or 0
            gsv_actual = actual['gsv'] or 0
            ad_target = target['target_ad_spend'] or 0
            ad_actual = actual['ad_spend'] or 0

            result['gsv_progress'] = round(gsv_actual / gsv_target * 100, 1) if gsv_target > 0 else None
            result['gsv_gap'] = gsv_target - gsv_actual
            result['ad_progress'] = round(ad_actual / ad_target * 100, 1) if ad_target > 0 else None
            result['ad_gap'] = ad_target - ad_actual
            result['actual_ad_ratio'] = round(ad_actual / gsv_actual, 4) if gsv_actual > 0 else None
            result['target_ad_ratio'] = target['target_ad_ratio']

            # 时间进度估算
            try:
                today = datetime.now()
                if dim == 'daily':
                    # 日维度：当月已过天数 / 当月总天数
                    try:
                        month_str = period[:7]  # 从 "2026-04-25" 提取 "2026-04"
                        month_end = datetime.strptime(month_str + '-01', '%Y-%m-%d')
                        _, days_in_month = calendar.monthrange(month_end.year, month_end.month)
                    except (ValueError, IndexError):
                        month_end = today
                        _, days_in_month = calendar.monthrange(today.year, today.month)
                    if today.year == month_end.year and today.month == month_end.month:
                        time_progress = round(today.day / days_in_month * 100, 1)
                    elif (today.year > month_end.year) or (today.year == month_end.year and today.month > month_end.month):
                        time_progress = 100
                    else:
                        time_progress = 0
                elif dim == 'weekly':
                    # 周维度：当前周已过天数 / 7
                    try:
                        week_start = datetime.strptime(period, '%Y-%m-%d')
                        days_elapsed = (today - week_start).days + 1
                        time_progress = round(min(max(days_elapsed, 0) / 7 * 100, 100), 1)
                    except (ValueError, IndexError):
                        time_progress = round(today.weekday() / 7 * 100, 1) + 14.3  # 近似
                else:
                    # 月维度：自然月进度
                    month_end = datetime.strptime(period + '-01', '%Y-%m-%d')
                    _, days_in_month = calendar.monthrange(month_end.year, month_end.month)
                    if today.year == month_end.year and today.month == month_end.month:
                        time_progress = round(today.day / days_in_month * 100, 1)
                    elif (today.year > month_end.year) or (today.year == month_end.year and today.month > month_end.month):
                        time_progress = 100
                    else:
                        time_progress = 0
                result['time_progress'] = time_progress
            except (ValueError, IndexError, TypeError):
                result['time_progress'] = None

            # 智能预测
            if result.get('time_progress') and result.get('time_progress', 0) > 0 and result.get('time_progress', 0) < 100:
                speed = gsv_actual / (result['time_progress'] / 100)
                if dim == 'daily':
                    # 日维度：日均 × 当月总天数
                    try:
                        month_str = period[:7]
                        month_end = datetime.strptime(month_str + '-01', '%Y-%m-%d')
                        _, days_in_month = calendar.monthrange(month_end.year, month_end.month)
                    except (ValueError, IndexError):
                        days_in_month = 30
                    result['gsv_forecast'] = round(speed * days_in_month, 0)
                    result['forecast_label'] = f'预计本月GSV'
                elif dim == 'weekly':
                    # 周维度：日均 × 7
                    result['gsv_forecast'] = round(speed * 7, 0)
                    result['forecast_label'] = f'预计本周GSV'
                else:
                    result['gsv_forecast'] = round(speed, 0)
                    result['forecast_label'] = f'预计月底GSV'
                result['forecast_gap'] = round(gsv_target - result['gsv_forecast'], 0)

            # 同比数据
            if dim == 'monthly':
                prev_period = _get_prev_month(period)
                if prev_period:
                    prev = conn.execute('''
                        SELECT SUM(payment_amount) as gsv, SUM(ad_spend) as ad_spend
                        FROM monthly_data WHERE month = ?
                    ''', (prev_period,)).fetchone()
                    prev = dict(prev) if prev else None
                    if prev:
                        result['yoy_gsv'] = round((gsv_actual - (prev['gsv'] or 0)) / (prev['gsv'] or 1) * 100, 1)
                        result['yoy_ad'] = round((ad_actual - (prev['ad_spend'] or 0)) / (prev['ad_spend'] or 1) * 100, 1)
            elif dim == 'daily':
                # 日维度：取前一天对比
                try:
                    from datetime import timedelta
                    prev_date = (datetime.strptime(period, '%Y-%m-%d') - timedelta(days=1)).strftime('%Y-%m-%d')
                    prev = conn.execute('''
                        SELECT SUM(payment_amount) as gsv, SUM(ad_spend) as ad_spend
                        FROM daily_data WHERE shop_id = ? AND date = ?
                    ''', (shop_id, prev_date)).fetchone()
                    prev = dict(prev) if prev else None
                    if prev:
                        result['yoy_gsv'] = round((gsv_actual - (prev['gsv'] or 0)) / (prev['gsv'] or 1) * 100, 1)
                        result['yoy_ad'] = round((ad_actual - (prev['ad_spend'] or 0)) / (prev['ad_spend'] or 1) * 100, 1)
                except (ValueError, IndexError):
                    pass
            elif dim == 'weekly':
                # 周维度：取上一周对比
                try:
                    from datetime import timedelta
                    prev_week = (datetime.strptime(period, '%Y-%m-%d') - timedelta(days=7)).strftime('%Y-%m-%d')
                    prev = conn.execute('''
                        SELECT SUM(payment_amount) as gsv, SUM(ad_spend) as ad_spend
                        FROM weekly_data WHERE week_start = ?
                    ''', (prev_week,)).fetchone()
                    prev = dict(prev) if prev else None
                    if prev:
                        result['yoy_gsv'] = round((gsv_actual - (prev['gsv'] or 0)) / (prev['gsv'] or 1) * 100, 1)
                        result['yoy_ad'] = round((ad_actual - (prev['ad_spend'] or 0)) / (prev['ad_spend'] or 1) * 100, 1)
                except (ValueError, IndexError):
                    pass

    return jsonify(result)

# 预留接口：商品分层目标进度（前端暂未调用）
@data_bp.route('/api/product_target_progress', methods=['GET'])
def get_product_target_progress():
    """商品/分层目标进度"""
    if (denied := reject_legacy_shop_scope('商品目标')):
        return denied
    period = request.args.get('period', '')
    target_shop = (request.args.get('shop_id') or '').strip() or str(current_app.config.get('SHOP_ID') or os.environ.get('TMALL_SHOP_ID') or '').strip()
    if target_shop and target_shop != 'default':
        return failure('UNSUPPORTED_SCOPE', '商品目标当前不支持 shop_id；请先完成目标表店铺迁移', status=422)
    with get_db() as conn:

        rows = [dict(r) for r in conn.execute('''
            SELECT pt.*,
                   COALESCE(m.payment_amount, 0) as actual_gsv,
                   COALESCE(m.ad_spend, 0) as actual_ad_spend,
                   p.title, p.tier, p.image_url
            FROM product_targets pt
            LEFT JOIN monthly_data m ON pt.product_id = m.product_id AND m.month = pt.period
            LEFT JOIN products p ON pt.product_id = p.product_id
            WHERE pt.period = ?
            ORDER BY (pt.target_gsv - COALESCE(m.payment_amount, 0)) DESC
        ''', (period,)).fetchall()]

        # 计算进度
        for r in rows:
            if r['target_gsv'] and r['target_gsv'] > 0:
                r['gsv_progress'] = round(r['actual_gsv'] / r['target_gsv'] * 100, 1)
            if r['target_ad_spend'] and r['target_ad_spend'] > 0:
                r['ad_progress'] = round(r['actual_ad_spend'] / r['target_ad_spend'] * 100, 1)

    return jsonify(rows)

@data_bp.route('/api/alerts', methods=['GET'])
def get_alerts():
    """获取预警列表"""
    if (denied := reject_legacy_shop_scope('经营预警')):
        return denied
    period = request.args.get('period', '')
    with get_db() as conn:

        # 仅在无预警记录时生成（避免重复插入）
        existing = conn.execute('SELECT COUNT(*) FROM alerts WHERE period = ?', (period,)).fetchone()[0]
        if existing == 0:
            generate_alerts(conn, period)

        rows = [dict(r) for r in conn.execute('''
            SELECT * FROM alerts WHERE period = ? AND dismissed = 0 ORDER BY severity DESC, created_at DESC
        ''', (period,)).fetchall()]

    return jsonify(rows)

@data_bp.route('/api/alerts/<int:alert_id>/dismiss', methods=['POST'])
def dismiss_alert(alert_id):
    if (denied := reject_legacy_shop_scope('经营预警')):
        return denied
    with get_db() as conn:
        conn.execute('UPDATE alerts SET dismissed = 1 WHERE id = ?', (alert_id,))
        conn.commit()
    return jsonify({'success': True})

# 预留接口：手动设置店铺目标（前端暂未调用）
@data_bp.route('/api/targets/shop', methods=['POST'])
def set_shop_target():
    """手动设置店铺目标"""
    if (denied := reject_legacy_shop_scope('店铺目标')):
        return denied
    data = request.get_json(silent=True) or {}
    period = str(data.get('period') or '').strip()
    try:
        datetime.strptime(period, '%Y-%m')
    except (TypeError, ValueError):
        return failure('VALIDATION_ERROR', 'period must use YYYY-MM format', status=422)
    with get_db() as conn:
        conn.execute('''
            INSERT OR REPLACE INTO shop_targets (period, target_gsv, target_ad_spend, target_ad_ratio, target_conversion, target_refund_rate, remark)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (period, data.get('target_gsv'), data.get('target_ad_spend'),
              data.get('target_ad_ratio'), data.get('target_conversion'), data.get('target_refund_rate'),
              data.get('remark')))
        conn.commit()
    return jsonify({'success': True})

# ==================== 生命周期管理 API ====================

@data_bp.route('/api/lifecycle', methods=['GET'])
def get_lifecycle():
    """Get product lifecycle data - monthly GSV for each product"""
    if (denied := reject_legacy_shop_scope('生命周期')):
        return denied
    product_id = request.args.get('product_id', '')
    limit = request.args.get('limit', 500, type=int)
    limit = max(1, min(limit or 500, 2000))

    with get_db() as conn:
        if product_id:
            # Single product lifecycle
            rows = conn.execute('''
                SELECT p.product_id, p.title, p.image_url, p.tier, p.style,
                       d.month, d.payment_amount as gsv, d.payment_qty, d.refund_amount,
                       d.visitors, d.ad_spend, d.ad_roi, d.payment_conversion,
                       d.cart_rate, d.fav_rate, d.bounce_rate, d.avg_stay_duration,
                       d.uv_value, d.search_visitors, d.search_ratio, d.net_sales,
                       d.buyers, d.avg_order_value, d.repurchase_rate, d.cross_sell_rate
                FROM products p
                JOIN monthly_data d ON p.product_id = d.product_id
                WHERE p.product_id = ?
                ORDER BY d.month
            ''', (product_id,)).fetchall()
        else:
            # Top products lifecycle summary
            rows = conn.execute('''
                SELECT p.product_id, p.title, p.image_url, p.tier, p.style,
                       GROUP_CONCAT(d.month || ':' || COALESCE(d.payment_amount,0)) as gsv_series,
                       SUM(d.payment_amount) as total_gsv,
                       COUNT(DISTINCT d.month) as active_months,
                       MIN(d.month) as first_month,
                       MAX(d.month) as last_month
                FROM products p
                JOIN monthly_data d ON p.product_id = d.product_id
                GROUP BY p.product_id
                ORDER BY total_gsv DESC
                LIMIT ?
            ''', (limit,)).fetchall()

    return jsonify([dict(r) for r in rows])

# ==================== 商品健康度 API ====================

@data_bp.route('/api/health', methods=['GET'])
def get_health():
    """商品健康度（12维度）"""
    period = request.args.get('period', '')
    level = request.args.get('level', '')
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

    return jsonify({'products': rows, 'stats': stats})

# ==================== 评价数据 API ====================

@data_bp.route('/api/upload/reviews', methods=['POST'])
def upload_reviews():
    """上传评价数据文件"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file'}), 400

    file = request.files['file']
    if not file.filename.lower().endswith(('.xlsx', '.xls', '.csv')):
        return jsonify({'error': 'Unsupported file type'}), 400

    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    filename, filepath = _unique_upload_path(file.filename)
    file.save(filepath)

    # 解析并导入
    try:
        from scripts.import_data import import_reviews_from_file
        count = import_reviews_from_file(filepath)
        return jsonify({'success': True, 'count': count, 'filename': filename})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@data_bp.route('/api/upload/data', methods=['POST'])
def upload_business_data():
    """上传核心业务数据Excel文件"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    file = request.files['file']
    suffix = os.path.splitext(file.filename or '')[1].lower()
    if suffix not in {'.xlsx', '.xls', '.csv', '.zip'}:
        return jsonify({'error': 'Only .xlsx, .xls, .csv, and .zip files are supported'}), 400

    import tempfile
    from scripts.import_data import import_excel_file

    # 保存到临时文件
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        file.save(tmp.name)
        tmp_path = tmp.name

    # 生成任务ID，立即返回，后台线程执行导入
    task_id = str(uuid.uuid4())[:8]
    filename = file.filename

    def _do_import(task_id, file_path, filename):
        """后台线程执行导入，更新进度"""
        try:
            _import_progress[task_id] = {
                'status': 'processing', 'progress': 10,
                'message': '正在解析文件...', 'started_at': time.time()
            }

            result = import_excel_file(file_path)

            _import_progress[task_id] = {
                'status': 'completed', 'progress': 100,
                'message': f'导入完成，共 {result.get("total_rows", 0)} 行数据',
                'result': result
            }

            # 记录操作日志
            try:
                with get_db() as conn:
                    conn.execute(
                        'INSERT INTO operation_logs (action, detail, operator) VALUES (?, ?, ?)',
                        ('数据导入', f'导入文件: {filename}', 'admin')
                    )
                    conn.commit()
            except Exception:
                pass
        except Exception as e:
            _import_progress[task_id] = {
                'status': 'error', 'progress': 0,
                'message': str(e)
            }
        finally:
            try:
                os.unlink(file_path)
            except Exception:
                pass

    threading.Thread(target=_do_import, args=(task_id, tmp_path, filename), daemon=True).start()
    return jsonify({'success': True, 'task_id': task_id, 'message': '导入任务已提交'})


@data_bp.route('/api/import_progress/<task_id>', methods=['GET'])
def get_import_progress(task_id):
    """获取导入任务进度"""
    progress = _import_progress.get(task_id, {})
    return jsonify(progress)

@data_bp.route('/api/reviews/summary', methods=['GET'])
def get_reviews_summary():
    """评价总览"""
    product_id = request.args.get('product_id', '')
    with get_db() as conn:

        if product_id:
            where = ' WHERE product_id = ?'
            params = [product_id]
        else:
            where = ''
            params = []

        # 总体统计
        stats = dict(conn.execute(f'''
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN sentiment='positive' THEN 1 ELSE 0 END) as positive,
                SUM(CASE WHEN sentiment='negative' THEN 1 ELSE 0 END) as negative,
                SUM(CASE WHEN sentiment='neutral' THEN 1 ELSE 0 END) as neutral,
                SUM(is_effective) as effective,
                AVG(rating) as avg_rating,
                SUM(has_image) as with_image
            FROM reviews {where}
        ''', params).fetchone())

        # 正面维度分布
        pos_dims = conn.execute(f'''
            SELECT value, COUNT(*) as count FROM reviews, json_each(positive_dims)
            {where} GROUP BY value ORDER BY count DESC LIMIT 10
        ''', params).fetchall()

        # 负面维度分布
        neg_dims = conn.execute(f'''
            SELECT value, COUNT(*) as count FROM reviews, json_each(negative_dims)
            {where} GROUP BY value ORDER BY count DESC LIMIT 10
        ''', params).fetchall()

        # 场景分布
        scenes = conn.execute(f'''
            SELECT value, COUNT(*) as count FROM reviews, json_each(scenes)
            {where} GROUP BY value ORDER BY count DESC LIMIT 10
        ''', params).fetchall()

        # 高频词（从评价内容中提取，限制处理数量避免性能问题）
        top_words = []
        try:
            import jieba.analyse
            all_content = conn.execute(f'SELECT content FROM reviews {where} LIMIT 500', params).fetchall()
            word_freq = {}
            for row in all_content:
                for word, freq in jieba.analyse.extract_tags(row[0], topK=50):
                    if len(word) >= 2:
                        word_freq[word] = word_freq.get(word, 0) + freq
            top_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:30]
        except ImportError:
            top_words = []

        # 评分分布
        rating_dist = conn.execute(f'''
            SELECT rating, COUNT(*) as count FROM reviews {where} GROUP BY rating ORDER BY rating
        ''', params).fetchall()

    return jsonify({
        'stats': dict(stats),
        'positive_dims': [dict(r) for r in pos_dims],
        'negative_dims': [dict(r) for r in neg_dims],
        'scenes': [dict(r) for r in scenes],
        'top_words': top_words,
        'rating_dist': [dict(r) for r in rating_dist]
    })

@data_bp.route('/api/reviews/list', methods=['GET'])
def get_reviews_list():
    """评价列表"""
    product_id = request.args.get('product_id', '')
    sentiment = request.args.get('sentiment', '')
    limit = max(1, min(request.args.get('limit', 50, type=int) or 50, 200))
    offset = max(0, request.args.get('offset', 0, type=int) or 0)

    with get_db() as conn:
        query = 'SELECT * FROM reviews WHERE 1=1'
        params = []

        if product_id:
            query += ' AND product_id = ?'
            params.append(product_id)
        if sentiment:
            query += ' AND sentiment = ?'
            params.append(sentiment)

        query += ' ORDER BY imported_at DESC LIMIT ? OFFSET ?'
        params.extend([limit, offset])

        rows = [dict(r) for r in conn.execute(query, params).fetchall()]
    return jsonify(rows)

@data_bp.route('/api/alert_rules', methods=['GET'])
def get_alert_rules():
    """获取所有预警规则"""
    with get_db() as conn:
        rows = [dict(r) for r in conn.execute(
            'SELECT * FROM alert_rules ORDER BY created_at DESC'
        ).fetchall()]
    return jsonify(rows)

@data_bp.route('/api/alert_rules', methods=['POST'])
def create_alert_rule():
    """创建预警规则"""
    data = request.get_json(force=True) or {}
    metric = data.get('metric', '')
    operator = data.get('operator', '')
    threshold = data.get('threshold')
    level = data.get('level', 'warning')

    if not metric or operator not in ('gt', 'lt', 'gte', 'lte') or threshold is None:
        return jsonify({'error': '参数不完整'}), 400
    try:
        threshold = float(threshold)
    except (ValueError, TypeError):
        return jsonify({'error': '阈值必须为数字'}), 400
    if level not in ('info', 'warning', 'danger'):
        level = 'warning'

    with get_db() as conn:
        conn.execute(
            'INSERT INTO alert_rules (metric, operator, threshold, level) VALUES (?, ?, ?, ?)',
            (metric, operator, float(threshold), level)
        )
        conn.commit()
    return jsonify({'success': True})

@data_bp.route('/api/alert_rules/<int:rule_id>', methods=['DELETE'])
def delete_alert_rule(rule_id):
    """删除预警规则"""
    with get_db() as conn:
        conn.execute('DELETE FROM alert_rules WHERE id = ?', (rule_id,))
        conn.commit()
    return jsonify({'success': True})

@data_bp.route('/api/alert_checks', methods=['GET'])
def check_alerts():
    """检查当前周期数据是否触发预警规则"""
    dimension = request.args.get('dim', 'weekly')
    period = request.args.get('period', '')

    dim_cfg = DIMENSION_MAP.get(dimension)
    if not dim_cfg:
        return jsonify({'error': 'invalid dimension'}), 400
    table = dim_cfg['table']
    date_col = dim_cfg['date_col']
    visitors_col = dim_cfg['visitors_col']

    with get_db() as conn:
        # 获取当前周期KPI汇总数据
        row = conn.execute(f'''
            SELECT
                COALESCE(SUM(payment_amount),0) as gmv,
                COALESCE(SUM(payment_amount),0) - COALESCE(SUM(refund_amount),0) as net_sales,
                COALESCE(SUM({visitors_col}),0) as visitors,
                AVG(payment_conversion) as conversion,
                CASE WHEN SUM(payment_amount) > 0 THEN SUM(refund_amount) * 1.0 / SUM(payment_amount) ELSE 0 END as refund_rate,
                CASE WHEN SUM(ad_spend) > 0 THEN SUM(payment_amount) * 1.0 / SUM(ad_spend) ELSE 0 END as roi,
                COALESCE(SUM(ad_spend),0) as ad_spend
            FROM {table} WHERE {date_col} = ?
        ''', (period,)).fetchone()

        if not row:
            return jsonify([])

        current = dict(row)

        # 获取所有启用的规则
        rules = [dict(r) for r in conn.execute(
            "SELECT * FROM alert_rules WHERE enabled = 1 AND COALESCE(scope, 'store') = 'store'"
        ).fetchall()]

    # 逐条检查规则
    triggered = []
    op_map = {
        'gt': lambda a, b: a > b,
        'lt': lambda a, b: a < b,
        'gte': lambda a, b: a >= b,
        'lte': lambda a, b: a <= b,
    }

    metric_labels = {
        'gmv': '总销售额', 'net_sales': '净销售额', 'visitors': '总访客',
        'conversion': '转化率', 'refund_rate': '退款率', 'roi': 'ROI', 'ad_spend': '推广花费'
    }

    for rule in rules:
        val = current.get(rule['metric'])
        if val is None:
            continue
        op_func = op_map.get(rule['operator'])
        if op_func and op_func(val, rule['threshold']):
            triggered.append({
                'id': rule['id'],
                'metric': rule['metric'],
                'label': metric_labels.get(rule['metric'], rule['metric']),
                'operator': rule['operator'],
                'threshold': rule['threshold'],
                'level': rule['level'],
                'current_value': round(val, 4),
            })

    return jsonify(triggered)

@data_bp.route('/api/notes/<product_id>', methods=['GET'])
def get_notes(product_id):
    """获取商品备注列表"""
    with get_db() as conn:
        rows = [dict(r) for r in conn.execute(
            'SELECT * FROM product_notes WHERE product_id = ? ORDER BY created_at DESC',
            (product_id,)
        ).fetchall()]
    return jsonify(rows)

@data_bp.route('/api/notes', methods=['POST'])
def add_note():
    """添加商品备注"""
    data = request.get_json(force=True) or {}
    product_id = data.get('product_id', '')
    note = data.get('note', '').strip()
    if not product_id or not note:
        return jsonify({'error': '参数不完整'}), 400
    with get_db() as conn:
        conn.execute(
            'INSERT INTO product_notes (product_id, note) VALUES (?, ?)',
            (product_id, note)
        )
        conn.commit()
        # 记录操作日志
        conn.execute(
            'INSERT INTO operation_logs (action, detail, operator) VALUES (?, ?, ?)',
            ('添加备注', f'商品 {product_id}: {note[:50]}', 'admin')
        )
        conn.commit()
    return jsonify({'success': True})

@data_bp.route('/api/notes/<int:note_id>', methods=['DELETE'])
def delete_note(note_id):
    """删除商品备注"""
    with get_db() as conn:
        # 先查询备注内容用于日志
        row = conn.execute('SELECT product_id, note FROM product_notes WHERE id = ?', (note_id,)).fetchone()
        conn.execute('DELETE FROM product_notes WHERE id = ?', (note_id,))
        conn.commit()
        # 记录操作日志
        if row:
            conn.execute(
                'INSERT INTO operation_logs (action, detail, operator) VALUES (?, ?, ?)',
                ('删除备注', f'商品 {row[0]}: {row[1][:50]}', 'admin')
            )
            conn.commit()
    return jsonify({'success': True})

@data_bp.route('/api/reviews/products', methods=['GET'])
def get_reviewed_products():
    """有评价的商品列表"""
    with get_db() as conn:
        rows = [dict(r) for r in conn.execute('''
            SELECT r.product_id, p.title, p.image_url, p.tier, p.style,
                   COUNT(*) as review_count,
                   AVG(r.rating) as avg_rating,
                   SUM(CASE WHEN r.sentiment='positive' THEN 1 ELSE 0 END) as positive_count,
                   SUM(CASE WHEN r.sentiment='negative' THEN 1 ELSE 0 END) as negative_count
            FROM reviews r
            LEFT JOIN products p ON r.product_id = p.product_id
            GROUP BY r.product_id
            ORDER BY review_count DESC
        ''').fetchall()]
    return jsonify(rows)

# ==================== 操作日志 API ====================

@data_bp.route('/api/logs', methods=['GET'])
def get_logs():
    """获取最近操作日志"""
    limit = max(1, min(request.args.get('limit', 50, type=int) or 50, 200))
    with get_db() as conn:
        rows = [dict(r) for r in conn.execute(
            'SELECT * FROM operation_logs ORDER BY id DESC LIMIT ?', (limit,)
        ).fetchall()]
    return jsonify(rows)

@data_bp.route('/api/logs', methods=['POST'])
def create_log():
    """记录操作日志"""
    data = request.get_json(force=True) or {}
    action = data.get('action', '').strip()
    detail = data.get('detail', '').strip()
    operator = data.get('operator', 'admin').strip()
    if not action:
        return jsonify({'error': 'action is required'}), 400
    with get_db() as conn:
        conn.execute(
            'INSERT INTO operation_logs (action, detail, operator) VALUES (?, ?, ?)',
            (action, detail, operator)
        )
        conn.commit()
    return jsonify({'success': True})


@data_bp.route('/api/review', methods=['GET'])
def get_review_data():
    """复盘数据 — 核心指标环比+同比"""
    dim = request.args.get('dim', 'monthly')
    period = request.args.get('period', '')

    with get_db() as conn:
        # Define metrics to compute
        # Current period data
        if dim == 'weekly':
            table = 'weekly_data'
            period_col = 'week_start'
            visitors_col = 'ipv'
        elif dim == 'daily':
            table = 'daily_data'
            period_col = 'date'
            visitors_col = 'ipv'
        else:
            table = 'monthly_data'
            period_col = 'month'
            visitors_col = 'visitors'

        # Auto-detect latest period if not provided
        if not period:
            row = conn.execute(f'SELECT MAX({period_col}) as p FROM {table}').fetchone()
            period = row['p'] if row and row['p'] else ''
            if not period:
                return jsonify({'period': '', 'dim': dim, 'prev_period': '', 'yoy_period': '', 'metrics': [], 'trend': []})

        # Build field expressions based on table (some fields differ between tables)
        if dim == 'monthly':
            click_rate_expr = 'AVG(click_rate) as click_rate'
            buyers_expr = 'SUM(buyers) as buyers'
        elif dim == 'weekly':
            click_rate_expr = 'AVG(search_click_rate) as click_rate'
            buyers_expr = '0 as buyers'
        else:  # daily
            click_rate_expr = '0 as click_rate'
            buyers_expr = 'SUM(buyers) as buyers'

        # Current period
        current = conn.execute(f'''
            SELECT
                SUM(payment_amount) as gsv,
                SUM(refund_amount) as refund_amount,
                SUM(payment_amount) - SUM(refund_amount) as net_sales,
                SUM({visitors_col}) as visitors,
                AVG(payment_conversion) as conversion,
                SUM(ad_spend) as ad_spend,
                SUM(ad_spend) / NULLIF(SUM(payment_amount), 0) as ad_ratio,
                SUM(payment_amount) / NULLIF(SUM(ad_spend), 0) as overall_roi,
                {click_rate_expr},
                AVG(cart_rate) as cart_rate,
                AVG(fav_rate) as fav_rate,
                SUM(payment_amount) / NULLIF(SUM({visitors_col}), 0) as avg_order_value,
                COUNT(DISTINCT product_id) as product_count,
                {buyers_expr}
            FROM {table} WHERE {period_col} = ?
        ''', (period,)).fetchone()
        current = dict(current) if current else {}

        # Previous period (环比)
        if dim == 'monthly':
            prev_period = _get_prev_month(period)
        elif dim == 'weekly':
            from datetime import timedelta
            try:
                prev_period = (datetime.strptime(period, '%Y-%m-%d') - timedelta(days=7)).strftime('%Y-%m-%d')
            except Exception:
                prev_period = None
        else:  # daily
            from datetime import timedelta
            try:
                prev_period = (datetime.strptime(period, '%Y-%m-%d') - timedelta(days=1)).strftime('%Y-%m-%d')
            except Exception:
                prev_period = None

        prev = {}
        if prev_period:
            prev = conn.execute(f'''
                SELECT
                    SUM(payment_amount) as gsv,
                    SUM(refund_amount) as refund_amount,
                    SUM(payment_amount) - SUM(refund_amount) as net_sales,
                    SUM({visitors_col}) as visitors,
                    AVG(payment_conversion) as conversion,
                    SUM(ad_spend) as ad_spend,
                    SUM(ad_spend) / NULLIF(SUM(payment_amount), 0) as ad_ratio,
                    SUM(payment_amount) / NULLIF(SUM(ad_spend), 0) as overall_roi,
                    {click_rate_expr},
                    AVG(cart_rate) as cart_rate,
                    AVG(fav_rate) as fav_rate,
                    SUM(payment_amount) / NULLIF(SUM({visitors_col}), 0) as avg_order_value,
                    COUNT(DISTINCT product_id) as product_count,
                    {buyers_expr}
                FROM {table} WHERE {period_col} = ?
            ''', (prev_period,)).fetchone()
            prev = dict(prev) if prev else {}

        # Same period last year (同比)
        yoy_period = None
        if dim == 'monthly' and len(period) == 7:
            yoy_period = str(int(period[:4]) - 1) + period[4:]
        elif dim in ('weekly', 'daily') and len(period) == 10:
            yoy_period = str(int(period[:4]) - 1) + period[4:]

        yoy = {}
        if yoy_period:
            yoy = conn.execute(f'''
                SELECT
                    SUM(payment_amount) as gsv,
                    SUM(refund_amount) as refund_amount,
                    SUM(payment_amount) - SUM(refund_amount) as net_sales,
                    SUM({visitors_col}) as visitors,
                    AVG(payment_conversion) as conversion,
                    SUM(ad_spend) as ad_spend,
                    SUM(ad_spend) / NULLIF(SUM(payment_amount), 0) as ad_ratio,
                    SUM(payment_amount) / NULLIF(SUM(ad_spend), 0) as overall_roi,
                    {click_rate_expr},
                    AVG(cart_rate) as cart_rate,
                    AVG(fav_rate) as fav_rate,
                    SUM(payment_amount) / NULLIF(SUM({visitors_col}), 0) as avg_order_value,
                    COUNT(DISTINCT product_id) as product_count,
                    {buyers_expr}
                FROM {table} WHERE {period_col} = ?
            ''', (yoy_period,)).fetchone()
            yoy = dict(yoy) if yoy else {}

        # Build metrics list with changes
        metrics = [
            {'key': 'gsv', 'label': 'GSV', 'format': 'money', 'icon': '💰'},
            {'key': 'net_sales', 'label': '净销售额', 'format': 'money', 'icon': '💳'},
            {'key': 'visitors', 'label': '访客数', 'format': 'number', 'icon': '👁'},
            {'key': 'conversion', 'label': '转化率', 'format': 'percent', 'icon': '🎯'},
            {'key': 'ad_spend', 'label': '推广花费', 'format': 'money', 'icon': '📢'},
            {'key': 'ad_ratio', 'label': '费比', 'format': 'percent', 'icon': '📊'},
            {'key': 'overall_roi', 'label': '投产比', 'format': 'decimal', 'icon': '📈'},
            {'key': 'click_rate', 'label': '点击率', 'format': 'percent', 'icon': '🖱'},
            {'key': 'cart_rate', 'label': '加购率', 'format': 'percent', 'icon': '🛒'},
            {'key': 'avg_order_value', 'label': '客单价', 'format': 'money', 'icon': '🧾'},
            {'key': 'buyers', 'label': '买家数', 'format': 'number', 'icon': '👥'},
            {'key': 'refund_amount', 'label': '退款金额', 'format': 'money', 'icon': '↩️'},
        ]

        # Lower is better for these metrics
        lower_better = {'ad_ratio', 'refund_amount'}

        result_metrics = []
        for m in metrics:
            val = current.get(m['key'])
            prev_val = prev.get(m['key'])
            yoy_val = yoy.get(m['key'])

            item = {
                'key': m['key'],
                'label': m['label'],
                'format': m['format'],
                'icon': m['icon'],
                'value': val,
                'prev_value': prev_val,
                'yoy_value': yoy_val,
            }

            # MoM change
            if val is not None and prev_val is not None and prev_val != 0:
                change = (val - prev_val) / abs(prev_val) * 100
                item['mom_change'] = round(change, 1)
                item['mom_abs'] = round(val - prev_val, 2)

            # YoY change
            if val is not None and yoy_val is not None and yoy_val != 0:
                change = (val - yoy_val) / abs(yoy_val) * 100
                item['yoy_change'] = round(change, 1)
                item['yoy_abs'] = round(val - yoy_val, 2)

            # Direction: is increase good or bad?
            item['lower_better'] = m['key'] in lower_better

            result_metrics.append(item)

        # Historical trend (last 6 periods for sparkline)
        trend = []
        if dim == 'monthly':
            periods_list = []
            y, m = int(period[:4]), int(period[5:7])
            for i in range(5, -1, -1):
                mm = m - i
                yy = y
                while mm <= 0:
                    mm += 12
                    yy -= 1
                periods_list.append(f"{yy}-{mm:02d}")
            for p in periods_list:
                row = conn.execute(f'''
                    SELECT SUM(payment_amount) as gsv, SUM(ad_spend) as ad_spend,
                           AVG(payment_conversion) as conversion
                    FROM {table} WHERE {period_col} = ?
                ''', (p,)).fetchone()
                if row:
                    trend.append({'period': p, 'gsv': row['gsv'], 'ad_spend': row['ad_spend'], 'conversion': row['conversion']})
        elif dim == 'weekly':
            from datetime import timedelta
            try:
                base = datetime.strptime(period, '%Y-%m-%d')
                for i in range(5, -1, -1):
                    p = (base - timedelta(weeks=i)).strftime('%Y-%m-%d')
                    row = conn.execute(f'''
                        SELECT SUM(payment_amount) as gsv, SUM(ad_spend) as ad_spend,
                               AVG(payment_conversion) as conversion
                        FROM {table} WHERE {period_col} = ?
                    ''', (p,)).fetchone()
                    if row and row['gsv']:
                        trend.append({'period': p, 'gsv': row['gsv'], 'ad_spend': row['ad_spend'], 'conversion': row['conversion']})
            except Exception:
                pass

        return jsonify({
            'period': period,
            'dim': dim,
            'prev_period': prev_period,
            'yoy_period': yoy_period,
            'metrics': result_metrics,
            'trend': trend,
        })


# ==================== 数据报告 API ====================

@data_bp.route('/api/report', methods=['GET'])
def generate_report():
    """生成文本格式的数据摘要报告"""
    dim = request.args.get('dim', 'monthly')
    period = request.args.get('period', '')
    if not period:
        return jsonify({'error': 'period required'}), 400

    dim_cfg = DIMENSION_MAP.get(dim)
    if not dim_cfg:
        return jsonify({'error': 'invalid dimension'}), 400
    table = dim_cfg['table']
    date_col = dim_cfg['date_col']
    visitors_col = dim_cfg['visitors_col']

    with get_db() as conn:
        # 1. KPI汇总
        kpi_row = conn.execute(f'''
            SELECT
                COALESCE(SUM(payment_amount),0) as gmv,
                COALESCE(SUM(refund_amount),0) as refund_amount,
                COALESCE(SUM(payment_amount),0) - COALESCE(SUM(refund_amount),0) as net_sales,
                COALESCE(SUM({visitors_col}),0) as visitors,
                CASE WHEN SUM({visitors_col}) > 0 THEN SUM(payment_amount) * 1.0 / SUM({visitors_col}) ELSE 0 END as aov,
                CASE WHEN SUM(payment_amount) > 0 THEN SUM(refund_amount) * 1.0 / SUM(payment_amount) ELSE 0 END as refund_rate,
                COALESCE(SUM(ad_spend),0) as ad_spend,
                CASE WHEN SUM(ad_spend) > 0 THEN SUM(payment_amount) * 1.0 / SUM(ad_spend) ELSE 0 END as roi,
                AVG(payment_conversion) as conversion
            FROM {table} WHERE {date_col} = ?
        ''', (period,)).fetchone()

        if not kpi_row:
            return jsonify({'error': 'no data for period'}), 404

        kpi = dict(kpi_row)
        gmv = kpi['gmv']
        net_sales = kpi['net_sales']
        visitors = kpi['visitors']
        conv_rate = kpi['conversion'] * 100 if kpi['conversion'] else 0
        ad_cost = kpi['ad_spend']
        roi = kpi['roi']
        refund_rate = kpi['refund_rate'] * 100 if kpi['refund_rate'] else 0
        aov = kpi['aov']

        # 2. Top5商品（按销售额）
        top5_rows = conn.execute(f'''
            SELECT p.title, d.payment_amount, d.{visitors_col} as visitors, d.payment_conversion, d.ad_spend, d.ad_roi
            FROM products p
            JOIN {table} d ON p.product_id = d.product_id AND d.{date_col} = ?
            WHERE p.status = 'active'
            ORDER BY d.payment_amount DESC
            LIMIT 5
        ''', (period,)).fetchall()

        top5_text = ''
        for i, r in enumerate(top5_rows, 1):
            rd = dict(r)
            top5_text += f"  {i}. {rd['title'][:30]}\n"
            top5_text += f"     销售额: {_fmt_wan(rd['payment_amount'])}  访客: {rd.get('visitors', 0):,}  转化率: {rd.get('payment_conversion', 0) * 100:.1f}%\n"

        if not top5_text:
            top5_text = '  暂无商品数据\n'

        # 3. 异常指标
        alerts_text = ''
        config = load_config()
        anomaly_decline = config.get('thresholds', {}).get('anomaly_decline', 0.20)

        # 查询上期数据做环比
        prev_period = get_prev_period(period, dim)
        prev_row = None
        if prev_period != period:
            prev_row = conn.execute(f'''
                SELECT
                    COALESCE(SUM(payment_amount),0) as gmv,
                    COALESCE(SUM(refund_amount),0) as refund_amount,
                    COALESCE(SUM(payment_amount),0) - COALESCE(SUM(refund_amount),0) as net_sales,
                    COALESCE(SUM({visitors_col}),0) as visitors,
                    CASE WHEN SUM(ad_spend) > 0 THEN SUM(payment_amount) * 1.0 / SUM(ad_spend) ELSE 0 END as roi,
                    AVG(payment_conversion) as conversion
                FROM {table} WHERE {date_col} = ?
            ''', (prev_period,)).fetchone()

        if prev_row:
            prev = dict(prev_row)
            metric_labels = {
                'gmv': '总销售额', 'net_sales': '净销售额',
                'visitors': '总访客', 'conversion': '转化率', 'roi': 'ROI'
            }
            for key, label in metric_labels.items():
                curr_val = kpi.get(key, 0) or 0
                prev_val = prev.get(key, 0) or 0
                if prev_val > 0:
                    change_pct = (curr_val - prev_val) / prev_val * 100
                    if change_pct < 0 and abs(change_pct) > anomaly_decline * 100:
                        alerts_text += f"  - {label}: 环比下降 {abs(change_pct):.1f}% (上期: {_fmt_wan(prev_val)}, 本期: {_fmt_wan(curr_val)})\n"

        # 退款率异常
        if refund_rate > 15:
            alerts_text += f"  - 退款率偏高: {refund_rate:.1f}%\n"

        if not alerts_text:
            alerts_text = '  各项指标正常\n'

        # 4. 生成报告文本
        report = f"""📊 天猫数据报告
📅 报告周期：{period}（{dim}）
⏰ 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}

📈 核心指标
- 总销售额：{_fmt_wan(gmv)}
- 净销售额：{_fmt_wan(net_sales)}
- 总访客：{visitors:,}
- 整体转化率：{conv_rate:.1f}%
- 推广花费：{_fmt_wan(ad_cost)}
- 综合ROI：{roi:.2f}
- 退款率：{refund_rate:.1f}%
- 客单价：¥{aov:.1f}

🏆 销售TOP5
{top5_text}
⚠️ 异常指标
{alerts_text}"""

    return jsonify({'report': report})


# ==================== Feature 4: 多周期趋势叠加 ====================
@data_bp.route('/api/multi_trend', methods=['GET'])
def get_multi_trend():
    """多周期趋势叠加数据"""
    dim = request.args.get('dim', 'monthly')
    periods_str = request.args.get('periods', '')
    metric = request.args.get('metric', 'payment_amount')
    shop_id = get_shop_id()

    if not periods_str:
        return jsonify({'error': '请选择至少一个周期'}), 400

    periods = [p.strip() for p in periods_str.split(',') if p.strip()]
    if not periods:
        return jsonify({'error': '请选择至少一个周期'}), 400

    # 指标白名单
    metric_whitelist = {
        'payment_amount': 'payment_amount',
        'visitors': 'visitors',
        'conversion': 'payment_conversion',
        'refund_rate': None,  # 需要计算
    }
    if metric not in metric_whitelist:
        return jsonify({'error': '不支持的指标'}), 400

    dim_cfg = DIMENSION_MAP.get(dim)
    if not dim_cfg:
        return jsonify({'error': '不支持的维度'}), 400

    result = {'periods': []}

    with get_db() as conn:
        for period in periods:
            if dim == 'monthly':
                # 月度维度：查询该月每日数据，按周聚合
                year, month = period.split('-')
                month_start = f"{period}-01"
                # 计算月末
                last_day = calendar.monthrange(int(year), int(month))[1]
                month_end = f"{period}-{last_day:02d}"

                rows = conn.execute('''
                    SELECT date, SUM(payment_amount) as payment_amount,
                           SUM(ipv) as visitors,
                           AVG(payment_conversion) as payment_conversion,
                           CASE WHEN SUM(payment_amount) > 0 THEN SUM(refund_amount) * 1.0 / SUM(payment_amount) ELSE 0 END as refund_rate
                    FROM daily_data
                     WHERE shop_id = ? AND date >= ? AND date <= ?
                    GROUP BY date ORDER BY date
                ''', (shop_id, month_start, month_end)).fetchall()

                # 按周聚合
                weekly_data = {}
                for row in rows:
                    d = datetime.strptime(row['date'], '%Y-%m-%d')
                    # 计算周偏移（该月第几周）
                    week_num = (d.day - 1) // 7 + 1
                    week_key = f"W{week_num}"
                    if week_key not in weekly_data:
                        weekly_data[week_key] = {'date': week_key, 'payment_amount': 0, 'visitors': 0, 'conversion': [], 'refund_rate': []}
                    weekly_data[week_key]['payment_amount'] += row['payment_amount'] or 0
                    weekly_data[week_key]['visitors'] += row['visitors'] or 0
                    if row['payment_conversion'] is not None:
                        weekly_data[week_key]['conversion'].append(row['payment_conversion'])
                    if row['refund_rate'] is not None:
                        weekly_data[week_key]['refund_rate'].append(row['refund_rate'])

                data = []
                for wk in sorted(weekly_data.keys()):
                    wd = weekly_data[wk]
                    if metric == 'conversion':
                        val = sum(wd['conversion']) / len(wd['conversion']) if wd['conversion'] else 0
                    elif metric == 'refund_rate':
                        val = sum(wd['refund_rate']) / len(wd['refund_rate']) if wd['refund_rate'] else 0
                    else:
                        val = wd[metric] or 0
                    data.append({'date': wd['date'], 'value': round(val, 4)})

            elif dim == 'weekly':
                # 周度维度：查询该周每日数据
                try:
                    week_start = period
                    week_end_dt = datetime.strptime(period, '%Y-%m-%d') + timedelta(days=6)
                    week_end = week_end_dt.strftime('%Y-%m-%d')
                except Exception:
                    data = []
                else:
                    rows = conn.execute('''
                        SELECT date, SUM(payment_amount) as payment_amount,
                               SUM(ipv) as visitors,
                               AVG(payment_conversion) as payment_conversion,
                               CASE WHEN SUM(payment_amount) > 0 THEN SUM(refund_amount) * 1.0 / SUM(payment_amount) ELSE 0 END as refund_rate
                        FROM daily_data
                         WHERE shop_id = ? AND date >= ? AND date <= ?
                        GROUP BY date ORDER BY date
                    ''', (shop_id, week_start, week_end)).fetchall()

                    data = []
                    for row in rows:
                        val = row[metric] if metric != 'refund_rate' else row['refund_rate']
                        data.append({'date': row['date'], 'value': round(val or 0, 4)})

            else:
                # 日度维度：直接查询当天数据
                rows = conn.execute('''
                    SELECT date, SUM(payment_amount) as payment_amount,
                           SUM(ipv) as visitors,
                           AVG(payment_conversion) as payment_conversion,
                           CASE WHEN SUM(payment_amount) > 0 THEN SUM(refund_amount) * 1.0 / SUM(payment_amount) ELSE 0 END as refund_rate
                    FROM daily_data
                     WHERE shop_id = ? AND date = ?
                    GROUP BY date
                ''', (shop_id, period)).fetchall()
                data = []
                for row in rows:
                    val = row[metric] if metric != 'refund_rate' else row['refund_rate']
                    data.append({'date': row['date'], 'value': round(val or 0, 4)})

            result['periods'].append({'period': period, 'data': data})

    return jsonify(result)


# ==================== Feature 7: 数据异常事件标注 ====================
@data_bp.route('/api/chart_events', methods=['GET'])
def get_chart_events():
    """获取图表事件标注"""
    chart_type = request.args.get('chart_type', 'sales')
    with get_db() as conn:
        rows = conn.execute(
            'SELECT id, event_date, title, description, color, chart_type, created_at FROM chart_events WHERE chart_type = ? ORDER BY event_date',
            (chart_type,)
        ).fetchall()
        events = [dict(r) for r in rows]
    return jsonify(events)


@data_bp.route('/api/chart_events', methods=['POST'])
def create_chart_event():
    """创建图表事件标注"""
    data = request.get_json(force=True) or {}
    event_date = data.get('event_date', '')
    title = data.get('title', '')
    description = data.get('description', '')
    color = data.get('color', '#EF4444')
    chart_type = data.get('chart_type', 'sales')

    if not event_date or not title:
        return jsonify({'error': '日期和标题不能为空'}), 400

    with get_db() as conn:
        conn.execute(
            'INSERT INTO chart_events (event_date, title, description, color, chart_type) VALUES (?, ?, ?, ?, ?)',
            (event_date, title, description, color, chart_type)
        )
        conn.commit()
    return jsonify({'success': True, 'message': '标注已添加'})


@data_bp.route('/api/chart_events/<int:event_id>', methods=['DELETE'])
def delete_chart_event(event_id):
    """删除图表事件标注"""
    with get_db() as conn:
        conn.execute('DELETE FROM chart_events WHERE id = ?', (event_id,))
        conn.commit()
    return jsonify({'success': True, 'message': '标注已删除'})


# ==================== Feature 8: 智能数据导入调度 ====================
# 内存中的调度器状态
_scheduler_lock = threading.Lock()
_scheduler_running = False


def _parse_cron_expr(cron_expr):
    """解析简单 cron 表达式，返回下次运行时间"""
    try:
        parts = cron_expr.strip().lower().split()
        if not parts:
            return None
        now = datetime.now()

        if parts[0] == 'daily':
            # daily HH:MM
            time_str = parts[1] if len(parts) > 1 else '08:00'
            h, m = map(int, time_str.split(':'))
            next_run = now.replace(hour=h, minute=m, second=0, microsecond=0)
            if next_run <= now:
                next_run += timedelta(days=1)
            return next_run

        elif parts[0] == 'weekly':
            # weekly day HH:MM
            day_map = {'mon': 0, 'tue': 1, 'wed': 2, 'thu': 3, 'fri': 4, 'sat': 5, 'sun': 6}
            day_name = parts[1] if len(parts) > 1 else 'mon'
            time_str = parts[2] if len(parts) > 2 else '08:00'
            h, m = map(int, time_str.split(':'))
            target_day = day_map.get(day_name, 0)
            next_run = now.replace(hour=h, minute=m, second=0, microsecond=0)
            days_ahead = (target_day - now.weekday()) % 7
            if days_ahead == 0 and next_run <= now:
                days_ahead = 7
            next_run += timedelta(days=days_ahead)
            return next_run

        elif parts[0] == 'monthly':
            # monthly DD HH:MM
            dom = int(parts[1]) if len(parts) > 1 else 1
            time_str = parts[2] if len(parts) > 2 else '08:00'
            h, m = map(int, time_str.split(':'))
            try:
                next_run = now.replace(day=dom, hour=h, minute=m, second=0, microsecond=0)
            except ValueError:
                # 处理月末日期（如31号在某些月份不存在）
                last_day = _calendar.monthrange(now.year, now.month)[1]
                dom = min(dom, last_day)
                next_run = now.replace(day=dom, hour=h, minute=m, second=0, microsecond=0)
            if next_run <= now:
                if now.month == 12:
                    next_run = next_run.replace(year=now.year + 1, month=1)
                else:
                    next_run = next_run.replace(month=now.month + 1)
            return next_run

    except Exception:
        pass
    return None


def _cron_to_label(cron_expr):
    """将 cron 表达式转为可读中文标签"""
    try:
        parts = cron_expr.strip().lower().split()
        if parts[0] == 'daily':
            time_str = parts[1] if len(parts) > 1 else '08:00'
            return f"每天 {time_str}"
        elif parts[0] == 'weekly':
            day_names = {'mon': '周一', 'tue': '周二', 'wed': '周三', 'thu': '周四', 'fri': '周五', 'sat': '周六', 'sun': '周日'}
            day_name = day_names.get(parts[1] if len(parts) > 1 else 'mon', '周一')
            time_str = parts[2] if len(parts) > 2 else '08:00'
            return f"每{day_name} {time_str}"
        elif parts[0] == 'monthly':
            dom = parts[1] if len(parts) > 1 else '1'
            time_str = parts[2] if len(parts) > 2 else '08:00'
            return f"每月{dom}号 {time_str}"
    except Exception:
        pass
    return cron_expr


def _check_and_run_scheduled_tasks():
    # Deprecated: the standalone scanner owns all scheduled imports.
    return []
    """检查并执行到期的定时任务"""
    with _scheduler_lock:
        with get_db() as conn:
            tasks = conn.execute(
                'SELECT id, task_name, cron_expr, file_pattern, last_run, next_run FROM scheduled_tasks WHERE enabled = 1 AND status = ?',
                ('active',)
            ).fetchall()

            now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            now = datetime.now()

            for task in tasks:
                next_run_str = task['next_run']
                if not next_run_str:
                    # 计算下次运行时间
                    next_run = _parse_cron_expr(task['cron_expr'])
                    if next_run:
                        conn.execute(
                            'UPDATE scheduled_tasks SET next_run = ? WHERE id = ?',
                            (next_run.strftime('%Y-%m-%d %H:%M:%S'), task['id'])
                        )
                    continue

                try:
                    next_run_dt = datetime.strptime(next_run_str, '%Y-%m-%d %H:%M:%S')
                except Exception:
                    continue

                if now >= next_run_dt:
                    # 执行任务
                    conn.execute(
                        'UPDATE scheduled_tasks SET last_run = ?, status = ? WHERE id = ?',
                        (now_str, 'running', task['id'])
                    )
                    conn.commit()

                    # 模拟执行导入（实际环境中会读取文件）
                    try:
                        # 这里可以调用实际的导入逻辑
                        pattern = task['file_pattern'] or '*.xlsx'
                        matched_files = _scheduled_matches(pattern)

                        if matched_files:
                            # 执行导入
                            from scripts.import_data import import_excel_file
                            for fpath in matched_files[:1]:  # 每次最多导入一个文件
                                import_excel_file(fpath)

                        status = 'active'
                    except Exception:
                        status = 'error'

                    # 计算下次运行时间
                    next_run = _parse_cron_expr(task['cron_expr'])
                    next_run_str = next_run.strftime('%Y-%m-%d %H:%M:%S') if next_run else None

                    conn.execute(
                        'UPDATE scheduled_tasks SET status = ?, next_run = ? WHERE id = ?',
                        (status, next_run_str, task['id'])
                    )
                    conn.commit()


# 在每个请求前检查定时任务
@data_bp.before_request
def _scheduler_check():
    if request.path == '/api/scheduled_tasks' or request.path.startswith('/api/scheduled_tasks/'):
        return failure(
            'LEGACY_SCHEDULE_REMOVED',
            '旧定时任务已下线，请使用 /api/import-scans',
            status=410,
        )
    # Scheduling is intentionally performed by scripts/run_import_scanner.py.
    # Flask requests must never execute imports as a side effect.
    return None


@data_bp.route('/api/scheduled_tasks', methods=['GET'])
def get_scheduled_tasks():
    """获取所有定时任务"""
    with get_db() as conn:
        rows = conn.execute(
            'SELECT id, task_name, task_type, cron_expr, file_pattern, enabled, last_run, next_run, status, created_at FROM scheduled_tasks ORDER BY id DESC'
        ).fetchall()
        tasks = []
        for r in rows:
            t = dict(r)
            t['cron_label'] = _cron_to_label(t['cron_expr'])
            tasks.append(t)
    return jsonify(tasks)


@data_bp.route('/api/scheduled_tasks', methods=['POST'])
def create_scheduled_task():
    """创建定时任务"""
    data = request.get_json(force=True) or {}
    task_name = data.get('task_name', '')
    cron_expr = data.get('cron_expr', '')
    try:
        file_pattern = _validate_file_pattern(data.get('file_pattern', '*.xlsx'))
    except ValueError as error:
        return jsonify({'success': False, 'error': str(error)}), 422

    if not task_name or not cron_expr:
        return jsonify({'error': '任务名称和调度表达式不能为空'}), 400

    next_run = _parse_cron_expr(cron_expr)
    next_run_str = next_run.strftime('%Y-%m-%d %H:%M:%S') if next_run else None

    with get_db() as conn:
        conn.execute(
            'INSERT INTO scheduled_tasks (task_name, cron_expr, file_pattern, next_run) VALUES (?, ?, ?, ?)',
            (task_name, cron_expr, file_pattern, next_run_str)
        )
        conn.commit()
    return jsonify({'success': True, 'message': '任务已创建'})


@data_bp.route('/api/scheduled_tasks/<int:task_id>', methods=['PUT'])
def update_scheduled_task(task_id):
    """更新定时任务"""
    data = request.get_json(force=True) or {}

    with get_db() as conn:
        row = conn.execute('SELECT id FROM scheduled_tasks WHERE id = ?', (task_id,)).fetchone()
        if not row:
            return jsonify({'error': '任务不存在'}), 404

        if 'enabled' in data:
            conn.execute('UPDATE scheduled_tasks SET enabled = ? WHERE id = ?', (1 if data['enabled'] else 0, task_id))
            if data['enabled']:
                conn.execute("UPDATE scheduled_tasks SET status = 'active' WHERE id = ? AND status = 'error'", (task_id,))
        if 'cron_expr' in data and data['cron_expr']:
            cron_expr = data['cron_expr']
            next_run = _parse_cron_expr(cron_expr)
            next_run_str = next_run.strftime('%Y-%m-%d %H:%M:%S') if next_run else None
            conn.execute('UPDATE scheduled_tasks SET cron_expr = ?, next_run = ? WHERE id = ?', (cron_expr, next_run_str, task_id))
        if 'task_name' in data:
            conn.execute('UPDATE scheduled_tasks SET task_name = ? WHERE id = ?', (data['task_name'], task_id))
        if 'file_pattern' in data:
            try:
                file_pattern = _validate_file_pattern(data['file_pattern'])
            except ValueError as error:
                return jsonify({'success': False, 'error': str(error)}), 422
            conn.execute('UPDATE scheduled_tasks SET file_pattern = ? WHERE id = ?', (file_pattern, task_id))

        conn.commit()
    return jsonify({'success': True, 'message': '任务已更新'})


@data_bp.route('/api/scheduled_tasks/<int:task_id>', methods=['DELETE'])
def delete_scheduled_task(task_id):
    """删除定时任务"""
    with get_db() as conn:
        conn.execute('DELETE FROM scheduled_tasks WHERE id = ?', (task_id,))
        conn.commit()
    return jsonify({'success': True, 'message': '任务已删除'})


@data_bp.route('/api/scheduled_tasks/<int:task_id>/run', methods=['POST'])
def run_scheduled_task(task_id):
    """手动触发定时任务"""
    with get_db() as conn:
        row = conn.execute('SELECT id, task_name, cron_expr, file_pattern FROM scheduled_tasks WHERE id = ?', (task_id,)).fetchone()
        if not row:
            return jsonify({'error': '任务不存在'}), 404

        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        conn.execute('UPDATE scheduled_tasks SET last_run = ?, status = ? WHERE id = ?', (now_str, 'running', task_id))
        conn.commit()

        # 模拟执行
        try:
            pattern = row['file_pattern'] or '*.xlsx'
            matched_files = _scheduled_matches(pattern)
            if matched_files:
                from scripts.import_data import import_excel_file
                import_excel_file(matched_files[0])
            status = 'active'
            message = f'任务 "{row["task_name"]}" 执行完成'
        except Exception as e:
            status = 'error'
            message = f'任务执行失败: {str(e)}'

        next_run = _parse_cron_expr(row['cron_expr'])
        next_run_str = next_run.strftime('%Y-%m-%d %H:%M:%S') if next_run else None
        conn.execute('UPDATE scheduled_tasks SET status = ?, next_run = ? WHERE id = ?', (status, next_run_str, task_id))
        conn.commit()

    return jsonify({'success': True, 'message': message})


# ==================== Feature 9: 商品批量打标签 ====================
@data_bp.route('/api/batch_tags', methods=['POST'])
def batch_add_tags():
    """批量添加商品标签"""
    data = request.get_json(force=True) or {}
    product_ids = data.get('product_ids', [])
    tag = data.get('tag', '').strip()

    if not product_ids or not tag:
        return jsonify({'error': '商品ID列表和标签不能为空'}), 400

    count = 0
    failed = 0
    with get_db() as conn:
        for pid in product_ids:
            try:
                conn.execute('INSERT OR IGNORE INTO product_tags (product_id, tag) VALUES (?, ?)', (pid, tag))
                count += 1
            except Exception:
                failed += 1
        conn.commit()
    msg = f'已为 {count} 件商品添加标签 "{tag}"'
    if failed:
        msg += f'，{failed} 件失败'
    return jsonify({'success': True, 'message': msg})


@data_bp.route('/api/batch_tags', methods=['DELETE'])
def batch_remove_tags():
    """批量移除商品标签"""
    data = request.get_json(force=True) or {}
    product_ids = data.get('product_ids', [])
    tag = data.get('tag', '').strip()

    if not product_ids or not tag:
        return jsonify({'error': '商品ID列表和标签不能为空'}), 400

    with get_db() as conn:
        placeholders = ','.join(['?'] * len(product_ids))
        cursor = conn.execute(
            f'DELETE FROM product_tags WHERE product_id IN ({placeholders}) AND tag = ?',
            product_ids + [tag]
        )
        deleted_count = cursor.rowcount
        conn.commit()
    return jsonify({'success': True, 'message': f'已移除标签 "{tag}"', 'deleted': deleted_count})



# ==================== 新老客分析 API ====================

@data_bp.route('/api/customer_analysis', methods=['GET'])
def get_customer_analysis():
    """新老客分析：新客数、老客数、占比及趋势"""
    dim = request.args.get('dim', 'monthly')
    period = request.args.get('period', '')

    dim_cfg = DIMENSION_MAP.get(dim)
    if not dim_cfg:
        return jsonify({'error': 'invalid dimension'}), 400
    table = dim_cfg['table']
    date_col = dim_cfg['date_col']
    visitors_col = dim_cfg['visitors_col']

    with get_db() as conn:
        # new_buyers 列只在 monthly_data 中存在
        new_buyers_col = 'new_buyers' if dim == 'monthly' else '0'
        buyers_col = 'buyers' if dim == 'monthly' else ('buyers' if dim == 'daily' else '0')

        # 当期数据
        row = conn.execute(f'''
            SELECT
                COALESCE(SUM({new_buyers_col}), 0) as new_buyers,
                COALESCE(SUM({visitors_col}), 0) as visitors,
                COALESCE(SUM({buyers_col}), 0) as buyers
            FROM {table} WHERE {date_col} = ?
        ''', (period,)).fetchone()

        new_buyers = row['new_buyers'] if row else 0
        total_visitors = row['visitors'] if row else 0
        # 日/周维度没有 new_buyers，用 buyers 作为近似
        if dim != 'monthly':
            new_buyers = row['buyers'] if row else 0
        returning_buyers = max(0, total_visitors - new_buyers)
        new_ratio = new_buyers / total_visitors if total_visitors > 0 else 0
        returning_ratio = returning_buyers / total_visitors if total_visitors > 0 else 0

        # 上期数据（环比）
        prev_period = get_prev_period(period, dim)
        prev_new_ratio = None
        prev_returning_ratio = None
        if prev_period:
            prev_row = conn.execute(f'''
                SELECT
                    COALESCE(SUM({new_buyers_col}), 0) as new_buyers,
                    COALESCE(SUM({visitors_col}), 0) as visitors,
                    COALESCE(SUM({buyers_col}), 0) as buyers
                FROM {table} WHERE {date_col} = ?
            ''', (prev_period,)).fetchone()
            if prev_row:
                prev_visitors = prev_row['visitors'] or 0
                prev_new = prev_row['new_buyers'] if dim == 'monthly' else (prev_row['buyers'] or 0)
                prev_ret = max(0, prev_visitors - prev_new)
                prev_new_ratio = prev_new / prev_visitors if prev_visitors > 0 else 0
                prev_returning_ratio = prev_ret / prev_visitors if prev_visitors > 0 else 0

        # 趋势：最近6个周期
        trend_rows = conn.execute(f'''
            SELECT {date_col} as period,
                   COALESCE(SUM({new_buyers_col}), 0) as new_buyers,
                   COALESCE(SUM({visitors_col}), 0) as visitors,
                   COALESCE(SUM({buyers_col}), 0) as buyers
            FROM {table}
            WHERE {date_col} <= ?
            GROUP BY {date_col}
            ORDER BY {date_col} DESC
            LIMIT 6
        ''', (period,)).fetchall()
        trend = []
        for r in reversed(list(trend_rows)):
            rd = dict(r)
            nb = rd['new_buyers'] if dim == 'monthly' else (rd['buyers'] or 0)
            vis = rd['visitors'] or 0
            trend.append({
                'period': rd['period'],
                'new_buyers': nb,
                'returning_buyers': max(0, vis - nb),
            })

    return jsonify({
        'new_buyers': new_buyers,
        'returning_buyers': returning_buyers,
        'total_visitors': total_visitors,
        'new_ratio': round(new_ratio, 4),
        'returning_ratio': round(returning_ratio, 4),
        'prev_new_ratio': round(prev_new_ratio, 4) if prev_new_ratio is not None else None,
        'prev_returning_ratio': round(prev_returning_ratio, 4) if prev_returning_ratio is not None else None,
        'trend': trend,
    })


# ==================== 加购→支付漏斗分析 API ====================

@data_bp.route('/api/funnel', methods=['GET'])
def get_funnel_analysis():
    """漏斗分析：曝光→浏览→加购→收藏→支付"""
    dim = request.args.get('dim', 'monthly')
    period = request.args.get('period', '')

    dim_cfg = DIMENSION_MAP.get(dim)
    if not dim_cfg:
        return jsonify({'error': 'invalid dimension'}), 400
    table = dim_cfg['table']
    date_col = dim_cfg['date_col']
    visitors_col = dim_cfg['visitors_col']

    def query_funnel(p, conn):
        if not p:
            return None
        page_views_col = 'page_views' if dim == 'monthly' else ('pv' if dim == 'daily' else '0')
        cart_qty_col = 'cart_qty' if dim == 'monthly' else '0'
        fav_users_col = 'fav_users' if dim == 'monthly' else '0'
        payment_qty_col = 'payment_qty' if dim == 'monthly' else '0'
        row = conn.execute(f'''
            SELECT
                COALESCE(SUM({visitors_col}), 0) as visitors,
                COALESCE(SUM({page_views_col}), 0) as page_views,
                COALESCE(SUM({cart_qty_col}), 0) as cart_qty,
                COALESCE(SUM({fav_users_col}), 0) as fav_users,
                COALESCE(SUM({payment_qty_col}), 0) as payment_qty
            FROM {table} WHERE {date_col} = ?
        ''', (p,)).fetchone()
        if not row:
            return None
        rd = dict(row)
        steps = [
            {'name': '曝光', 'value': rd['visitors'] or 0},
            {'name': '浏览', 'value': rd['page_views'] or 0},
            {'name': '加购', 'value': rd['cart_qty'] or 0},
            {'name': '收藏', 'value': rd['fav_users'] or 0},
            {'name': '支付', 'value': rd['payment_qty'] or 0},
        ]
        # 计算各步骤转化率（相对于上一步）
        for i in range(len(steps)):
            if i == 0:
                steps[i]['rate'] = 1.0
            else:
                prev_val = steps[i - 1]['value']
                steps[i]['rate'] = steps[i]['value'] / prev_val if prev_val > 0 else 0
        return steps

    with get_db() as conn:
        steps = query_funnel(period, conn)
        prev_period = get_prev_period(period, dim)
        prev_steps = query_funnel(prev_period, conn)

    return jsonify({
        'steps': steps or [],
        'prev_steps': prev_steps or [],
    })


# ==================== 行业基准对比 API ====================

@data_bp.route('/api/industry_benchmark', methods=['GET'])
def get_industry_benchmark():
    """Return conditional benchmark evidence without inventing zero values."""
    dim = request.args.get('dim', 'monthly')
    period = request.args.get('period', '')
    dim_cfg = DIMENSION_MAP.get(dim)
    if not dim_cfg:
        return failure('VALIDATION_ERROR', 'invalid dimension', {'dim': dim}, status=422)
    table = dim_cfg['table']
    date_col = dim_cfg['date_col']
    shop_ctr_expr = 'click_rate' if dim == 'monthly' else 'search_click_rate'
    industry_ctr_expr = 'industry_ctr'

    with get_db() as conn:
        table_columns = {row['name'] for row in conn.execute(f'PRAGMA table_info("{table}")')}
        shop_available = shop_ctr_expr in table_columns
        industry_available = industry_ctr_expr in table_columns
        shop_sql = f'NULLIF({shop_ctr_expr}, 0)' if shop_available else 'NULL'
        industry_sql = f'NULLIF({industry_ctr_expr}, 0)' if industry_available else 'NULL'
        row = conn.execute(f'''
            SELECT COUNT(*) AS row_count,
                   AVG({industry_sql}) AS industry_ctr,
                   AVG({shop_sql}) AS shop_ctr
            FROM {table} WHERE {date_col} = ?
        ''', (period,)).fetchone()
        row_count = int(row['row_count'] or 0) if row else 0
        shop_ctr = row['shop_ctr'] if row else None
        industry_ctr = row['industry_ctr'] if row else None
        missing_inputs = ['industry_benchmark'] if row_count == 0 else []
        if row_count and (not shop_available or shop_ctr is None):
            missing_inputs.append('shop_ctr')
        if row_count and (not industry_available or industry_ctr is None):
            missing_inputs.append('industry_ctr')
        gap = shop_ctr - industry_ctr if not missing_inputs else None
        gap_pct = gap / industry_ctr * 100 if gap is not None and industry_ctr else None
        trend_rows = conn.execute(f'''
            SELECT {date_col} AS period,
                   AVG({shop_sql}) AS shop_ctr,
                   AVG({industry_sql}) AS industry_ctr
            FROM {table} WHERE {date_col} <= ?
            GROUP BY {date_col} ORDER BY {date_col} DESC LIMIT 6
        ''', (period,)).fetchall()
        trend = [
            {'period': item['period'], 'shop_ctr': item['shop_ctr'], 'industry_ctr': item['industry_ctr']}
            for item in reversed(trend_rows)
            if item['shop_ctr'] is not None and item['industry_ctr'] is not None
        ]

    availability = 'no-data' if row_count == 0 else 'available' if not missing_inputs else 'missing-fields'
    return success(
        {
            'shop_ctr': round(shop_ctr, 6) if shop_ctr is not None else None,
            'industry_ctr': round(industry_ctr, 6) if industry_ctr is not None else None,
            'gap': round(gap, 6) if gap is not None else None,
            'gap_pct': round(gap_pct, 2) if gap_pct is not None else None,
            'trend': trend,
        },
        availability=availability,
        capabilities={'can_view': availability == 'available'},
        filters={'dim': dim, 'period': period},
        missing_inputs=missing_inputs,
        limitations=limitations_for(availability, missing_inputs=missing_inputs),
        freshness={'period': period, 'latest_period': trend[-1]['period'] if trend else None},
        evidence=[{'source': table, 'row_count': row_count}],
        evidence_level=evidence_level_for(availability, missing_inputs=missing_inputs),
    )


# ==================== 商品画像标签 API ====================

@data_bp.route('/api/product_tags', methods=['GET'])
def get_product_tags():
    """商品自动画像标签 + 自定义标签"""
    dim = request.args.get('dim', 'monthly')
    period = request.args.get('period', '')

    dim_cfg = DIMENSION_MAP.get(dim)
    if not dim_cfg:
        return jsonify({'error': 'invalid dimension'}), 400
    table = dim_cfg['table']
    date_col = dim_cfg['date_col']

    with get_db() as conn:
        # 获取当期所有活跃商品数据
        payment_qty_col = 'd.payment_qty' if dim == 'monthly' else '0'
        refund_rate_expr = 'd.refund_rate' if dim == 'monthly' else 'CASE WHEN d.payment_amount > 0 THEN d.refund_amount * 1.0 / d.payment_amount ELSE 0 END'
        overall_roi_expr = 'd.overall_roi' if dim == 'monthly' else '0'
        rows = conn.execute(f'''
            SELECT d.product_id, d.payment_amount, d.payment_conversion,
                   {refund_rate_expr} as refund_rate, d.ad_roi, {overall_roi_expr} as overall_roi, {payment_qty_col} as payment_qty
            FROM {table} d
            JOIN products p ON d.product_id = p.product_id
            WHERE d.{date_col} = ? AND p.status = 'active'
        ''', (period,)).fetchall()

        if not rows:
            return jsonify([])

        data_list = [dict(r) for r in rows]

        # 获取上期数据用于环比计算
        prev_period = get_prev_period(period, dim)
        prev_map = {}
        if prev_period:
            prev_rows = conn.execute(f'''
                SELECT product_id, payment_amount
                FROM {table}
                WHERE {date_col} = ?
            ''', (prev_period,)).fetchall()
            for r in prev_rows:
                prev_map[r['product_id']] = r['payment_amount'] or 0

        # 计算百分位
        amounts = sorted([d['payment_amount'] or 0 for d in data_list])
        n = len(amounts)
        p90 = amounts[int(n * 0.9)] if n > 0 else 0
        p10 = amounts[int(n * 0.1)] if n > 0 else 0

        # 批量查询所有自定义标签（避免N+1查询）
        all_pids = [d['product_id'] for d in data_list]
        if all_pids:
            placeholders = ','.join(['?'] * len(all_pids))
            custom_all = conn.execute(
                f'SELECT product_id, tag FROM product_tags WHERE product_id IN ({placeholders}) AND is_auto = 0',
                all_pids
            ).fetchall()
            custom_map = {}
            for cr in custom_all:
                custom_map.setdefault(cr['product_id'], []).append(cr['tag'])
        else:
            custom_map = {}

        # 自动标签规则
        results = []
        for d in data_list:
            pid = d['product_id']
            tags = []
            amt = d['payment_amount'] or 0
            conv = d['payment_conversion'] or 0
            refund = d['refund_rate'] or 0
            roi = d['overall_roi'] or d['ad_roi'] or 0
            prev_amt = prev_map.get(pid, 0)

            # 爆款：支付金额 >= 90th 百分位 AND 转化率 >= 3%
            if amt >= p90 and conv >= 0.03:
                tags.append('爆款')
            # 潜力款：转化率 >= 5% AND 支付金额环比增长 > 20%
            if conv >= 0.05 and prev_amt > 0 and (amt - prev_amt) / prev_amt > 0.20:
                tags.append('潜力款')
            # 衰退款：支付金额环比下降 > 30%
            if prev_amt > 0 and (amt - prev_amt) / prev_amt < -0.30:
                tags.append('衰退款')
            # 滞销款：支付金额 < 10th 百分位
            if amt <= p10:
                tags.append('滞销款')
            # 高退款：退款率 > 20%
            if refund > 0.20:
                tags.append('高退款')
            # 高ROI：综合ROI > 15
            if roi > 15:
                tags.append('高ROI')

            # 从预查询的map中获取自定义标签
            for ct in custom_map.get(pid, []):
                if ct not in tags:
                    tags.append(ct)

            results.append({
                'product_id': pid,
                'tags': tags,
            })

    return jsonify(results)


@data_bp.route('/api/product_tags', methods=['POST'])
def add_product_tag():
    """添加自定义标签"""
    data = request.get_json(force=True) or {}
    product_id = data.get('product_id', '')
    tag = data.get('tag', '').strip()
    if not product_id or not tag:
        return jsonify({'error': '缺少参数'}), 400

    with get_db() as conn:
        try:
            conn.execute(
                'INSERT OR IGNORE INTO product_tags (product_id, tag, is_auto) VALUES (?, ?, 0)',
                (product_id, tag)
            )
            conn.commit()
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    return jsonify({'success': True})


@data_bp.route('/api/product_tags/<int:tag_id>', methods=['DELETE'])
def delete_product_tag(tag_id):
    """删除标签"""
    with get_db() as conn:
        conn.execute('DELETE FROM product_tags WHERE id = ?', (tag_id,))
        conn.commit()
    return jsonify({'success': True})
