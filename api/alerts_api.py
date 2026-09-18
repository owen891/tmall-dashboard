import math
from services.shop_scope_service import reject_legacy_shop_scope, require_admin_write
from datetime import datetime
"""Alerts API - 智能预警相关接口

从 data_api.py 拆分出来的独立模块，包含：
- 退款预警
- 告警列表/已读
- 告警规则 CRUD
- 告警检查触发
"""

from flask import Blueprint, jsonify, request
from api.data_api import DIMENSION_MAP, _validate_period_arg

from db import get_db
from api.api_response import failure, json_object, success
from services.alert_rules_service import AlertRuleValidationError, alert_rules_service


alerts_bp = Blueprint('alerts', __name__)


@alerts_bp.route('/api/refund_alert', methods=['GET'])
def get_refund_alert():
    """退款预警商品列表"""
    try:
        threshold = float(request.args.get('threshold', 0.20))
    except (ValueError, TypeError):
        return failure('VALIDATION_ERROR', 'threshold 必须是数字', status=422)
    if not math.isfinite(threshold) or threshold < 0 or threshold > 1:
        return failure('VALIDATION_ERROR', 'threshold 必须在 0 到 1 之间', {'threshold': threshold}, status=422)
    dimension = request.args.get('dim', 'monthly')
    period = request.args.get('period', '')

    dim_cfg = DIMENSION_MAP.get(dimension)
    if not dim_cfg:
        return failure('VALIDATION_ERROR', 'invalid dimension', {'dim': dimension}, status=422)
    table = dim_cfg['table']
    date_col = dim_cfg['date_col']

    if period:
        period_format = '%Y-%m' if dimension == 'monthly' else '%Y-%m-%d'
        try:
            parsed_period = datetime.strptime(period, period_format)
        except (TypeError, ValueError):
            return failure(
                'VALIDATION_ERROR',
                f'period must use {period_format.replace("%Y", "YYYY").replace("%m", "MM").replace("%d", "DD")}',
                {'dim': dimension, 'period': period},
                status=422,
            )
        if parsed_period.strftime(period_format) != period:
            return failure(
                'VALIDATION_ERROR',
                f'period must use {period_format.replace("%Y", "YYYY").replace("%m", "MM").replace("%d", "DD")}',
                {'dim': dimension, 'period': period},
                status=422,
            )

    if (denied := reject_legacy_shop_scope('退款预警')):
        return denied
    with get_db() as conn:
        refund_rate_expr = 'd.refund_rate' if dimension == 'monthly' else 'CASE WHEN d.payment_amount > 0 THEN d.refund_amount * 1.0 / d.payment_amount ELSE 0 END'
        rows = [dict(r) for r in conn.execute(f'''
            SELECT p.product_id, p.title, p.image_url,
                   d.payment_amount, d.refund_amount,
                   {refund_rate_expr} as refund_rate,
                   {refund_rate_expr} as refund_rate_val
            FROM products p
            JOIN {table} d ON p.product_id = d.product_id AND d.{date_col} = ?
            WHERE p.status = 'active' AND ({refund_rate_expr}) >= ?
            ORDER BY d.payment_amount DESC
        ''', (period, threshold)).fetchall()]
    return jsonify(rows)

@alerts_bp.route('/api/alerts', methods=['GET'])
def get_alerts():
    """获取预警列表"""
    if (denied := reject_legacy_shop_scope('经营预警')):
        return denied
    period = request.args.get('period', '')
    invalid = _validate_period_arg('monthly', period)
    if invalid:
        return invalid
    with get_db() as conn:

        # GET 只读；预警由导入/定时任务生成，避免读请求产生副作用。
        rows = [dict(r) for r in conn.execute('''
            SELECT * FROM alerts
            WHERE period = ? AND dismissed = 0
            ORDER BY CASE severity
                       WHEN 'critical' THEN 0
                       WHEN 'high' THEN 1
                       WHEN 'warning' THEN 2
                       WHEN 'info' THEN 3
                       ELSE 4
                     END,
                     created_at DESC
        ''', (period,)).fetchall()]

    return jsonify(rows)

@alerts_bp.route('/api/alerts/<int:alert_id>/dismiss', methods=['POST'])
def dismiss_alert(alert_id):
    if (denied := reject_legacy_shop_scope('经营预警')):
        return denied
    if (denied := reject_legacy_shop_scope('经营预警')):
        return denied
    if (denied := require_admin_write()):
        return denied
    with get_db() as conn:
        conn.execute('UPDATE alerts SET dismissed = 1 WHERE id = ?', (alert_id,))
        conn.commit()
    return jsonify({'success': True})

# 预留接口：手动设置店铺目标（前端暂未调用）

@alerts_bp.route('/api/alert_rules', methods=['GET'])
def get_alert_rules():
    """获取所有预警规则"""
    with get_db() as conn:
        rows = [dict(r) for r in conn.execute(
            'SELECT * FROM alert_rules ORDER BY created_at DESC'
        ).fetchall()]
    return jsonify(rows)


@alerts_bp.route('/api/alert_rules', methods=['POST'])
def create_legacy_alert_rule():
    """兼容旧版下划线路径，委托到统一规则服务。"""
    try:
        result = alert_rules_service.create(json_object(request))
    except AlertRuleValidationError as error:
        return failure('VALIDATION_ERROR', str(error), status=422)
    return jsonify({'success': True, 'data': result})


@alerts_bp.route('/api/alert_rules/<int:rule_id>', methods=['DELETE'])
def delete_alert_rule(rule_id):
    """删除预警规则"""
    with get_db() as conn:
        conn.execute('DELETE FROM alert_rules WHERE id = ?', (rule_id,))
        conn.commit()
    return jsonify({'success': True})

@alerts_bp.route('/api/alert_checks', methods=['GET'])
def check_alerts():
    """检查当前周期数据是否触发预警规则"""
    dimension = request.args.get('dim', 'weekly')
    period = request.args.get('period', '')

    dim_cfg = DIMENSION_MAP.get(dimension)
    if not dim_cfg:
        return failure('VALIDATION_ERROR', 'invalid dimension', {'dim': dimension}, status=422)
    invalid = _validate_period_arg(dimension, period)
    if invalid:
        return invalid
    table = dim_cfg['table']
    date_col = dim_cfg['date_col']
    visitors_col = dim_cfg['visitors_col']

    with get_db() as conn:
        # 获取当前周期KPI汇总数据
        row = conn.execute(f'''
            SELECT
                COUNT(*) as row_count,
                COALESCE(SUM(payment_amount),0) as gmv,
                COALESCE(SUM(payment_amount),0) - COALESCE(SUM(refund_amount),0) as net_sales,
                COALESCE(SUM({visitors_col}),0) as visitors,
                AVG(payment_conversion) as conversion,
                CASE WHEN SUM(payment_amount) > 0 THEN SUM(refund_amount) * 1.0 / SUM(payment_amount) ELSE 0 END as refund_rate,
                CASE WHEN SUM(ad_spend) > 0 THEN SUM(payment_amount) * 1.0 / SUM(ad_spend) ELSE 0 END as roi,
                COALESCE(SUM(ad_spend),0) as ad_spend
            FROM {table} WHERE {date_col} = ?
        ''', (period,)).fetchone()

        if not row or not row['row_count']:
            return jsonify([])

        current = dict(row)
        current.pop('row_count', None)

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

