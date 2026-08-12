"""
KPI API 路由 — 从 data_api.py 拆分。

原始代码在 data_api.py 中，包含 /api/status、/api/kpi、/api/trend、
/api/anomalies 等路由，业务逻辑内联。

重构后：路由只做参数提取和响应，逻辑在 KpiService 中。
"""
from flask import Blueprint, jsonify, request

from services.kpi_service import KpiService
from utils.cache import cache

kpi_bp = Blueprint('kpi', __name__)


@kpi_bp.route('/api/status', methods=['GET'])
def status():
    """系统状态检查"""
    return jsonify({
        'status': 'ok',
        'version': '2.0',
    })


@kpi_bp.route('/api/kpi', methods=['GET'])
def get_kpi():
    """
    KPI 概览 — 替代原 /api/kpi 路由（约 80 行）。

    原始代码：
        dim = request.args.get('dim', 'monthly')
        period = request.args.get('period', ...)
        sql = "SELECT SUM(payment_amount), ... FROM monthly_data WHERE month = ?"
        # + 手动计算环比 + 格式化

    重构后：调用 service，5 行搞定。
    """
    dim = request.args.get('dim', 'monthly')
    period = request.args.get('period')

    if not period:
        from repos.product_repo import ProductRepo
        periods = ProductRepo.get_periods(dim)
        period = periods[0] if periods else None

    if not period:
        return jsonify({'error': 'No data available'}), 404

    # 使用缓存（5 分钟 TTL）
    cache_key = f'kpi_{dim}_{period}'
    result = cache.get(cache_key)
    if result is None:
        result = KpiService.get_kpi_summary(dim, period)
        cache.set(cache_key, result, ttl=300)

    return jsonify(result)


@kpi_bp.route('/api/trend', methods=['GET'])
def get_trend():
    """趋势数据 — 替代原 /api/trend 路由"""
    dim = request.args.get('dim', 'monthly')
    period = request.args.get('period')
    metric = request.args.get('metric', 'payment_amount')
    limit = int(request.args.get('limit', 30))

    if not period:
        from repos.product_repo import ProductRepo
        periods = ProductRepo.get_periods(dim)
        period = periods[0] if periods else None

    data = KpiService.get_trend_data(dim, period, metric, limit)
    return jsonify({'data': data})


@kpi_bp.route('/api/anomalies', methods=['GET'])
def get_anomalies():
    """异常检测 — 替代原 /api/anomalies 路由（约 170 行）"""
    dim = request.args.get('dim', 'monthly')
    period = request.args.get('period')

    if not period:
        from repos.product_repo import ProductRepo
        periods = ProductRepo.get_periods(dim)
        period = periods[0] if periods else None

    anomalies = KpiService.detect_anomalies(dim, period)
    return jsonify({'anomalies': anomalies})
