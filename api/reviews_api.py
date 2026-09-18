from datetime import datetime
"""Reviews API - 经营复盘相关接口

从 data_api.py 拆分出来的独立模块，包含：
- 复盘汇总/列表
- 商品备注 CRUD
- 复盘数据生成
- 已复盘商品列表
"""

from flask import Blueprint, jsonify, request
from utils.cache import cache as _ttl_cache
from api.data_api import _aov_expression, _get_prev_month

from db import get_db
from api.api_response import failure, json_object, success


reviews_bp = Blueprint('reviews', __name__)


def _request_cache_key(prefix):
    """生成基于请求路径和查询参数的缓存 key"""
    params = sorted(request.args.items())
    param_str = "&".join(f"{k}={v}" for k, v in params)
    from flask import g
    shop_id = getattr(getattr(g, 'shop_id', None), '__str__', lambda: 'default')()
    return f"{prefix}:{request.path}:{shop_id}:{param_str}"


def cached_api(prefix, ttl=60):
    """API 缓存装饰器"""
    def decorator(f):
        def wrapped(*args, **kwargs):
            key = _request_cache_key(prefix)
            cached = _ttl_cache.get(key)
            if cached is not None:
                return jsonify(cached)
            result = f(*args, **kwargs)
            try:
                if hasattr(result, 'status_code') and result.status_code == 200 and hasattr(result, 'get_json'):
                    data = result.get_json()
                    if data is not None:
                        _ttl_cache.set(key, data, ttl)
            except Exception:
                pass
            return result
        wrapped.__name__ = getattr(f, '__name__', 'wrapped')
        wrapped.__doc__ = getattr(f, '__doc__', '')
        return wrapped
    return decorator


@reviews_bp.route('/api/reviews/summary', methods=['GET'])
@cached_api('get_reviews_summary', ttl=60)
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

    stats_payload = dict(stats)
    return jsonify({
        'availability': 'available' if (stats_payload.get('total') or 0) else 'no-data',
        'stats': stats_payload,
        'positive_dims': [dict(r) for r in pos_dims],
        'negative_dims': [dict(r) for r in neg_dims],
        'scenes': [dict(r) for r in scenes],
        'top_words': top_words,
        'rating_dist': [dict(r) for r in rating_dist]
    })

@reviews_bp.route('/api/reviews/list', methods=['GET'])
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

#

@reviews_bp.route('/api/notes/<product_id>', methods=['GET'])
def get_notes(product_id):
    """获取商品备注列表"""
    with get_db() as conn:
        rows = [dict(r) for r in conn.execute(
            'SELECT * FROM product_notes WHERE product_id = ? ORDER BY created_at DESC',
            (product_id,)
        ).fetchall()]
    return jsonify(rows)

@reviews_bp.route('/api/notes', methods=['POST'])
def add_note():
    """添加商品备注"""
    data = json_object(request)
    product_id = str(data.get('product_id') or '').strip()
    note = str(data.get('note') or '').strip()
    if not product_id or not note:
        return failure('VALIDATION_ERROR', '参数不完整', status=422)
    with get_db() as conn:
        if not conn.execute(
            'SELECT 1 FROM products WHERE product_id = ? LIMIT 1',
            (product_id,),
        ).fetchone():
            return failure('NOT_FOUND', '商品不存在', status=404)
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

@reviews_bp.route('/api/notes/<int:note_id>', methods=['DELETE'])
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

@reviews_bp.route('/api/review', methods=['GET'])
def get_review_data():
    """复盘数据 — 核心指标环比+同比"""
    dim = request.args.get('dim', 'monthly')
    period = request.args.get('period', '')

    period_format = {'monthly': '%Y-%m', 'weekly': '%Y-%m-%d', 'daily': '%Y-%m-%d'}.get(dim)
    if not period_format:
        return failure('VALIDATION_ERROR', 'dim must be monthly, weekly, or daily', {'dim': dim}, status=422)
    if period:
        try:
            parsed_period = datetime.strptime(period, period_format)
        except (TypeError, ValueError):
            return failure(
                'VALIDATION_ERROR',
                f'period must use {period_format.replace("%Y", "YYYY").replace("%m", "MM").replace("%d", "DD")}',
                {'dim': dim, 'period': period},
                status=422,
            )
        if parsed_period.strftime(period_format) != period:
            return failure(
                'VALIDATION_ERROR',
                f'period must use {period_format.replace("%Y", "YYYY").replace("%m", "MM").replace("%d", "DD")}',
                {'dim': dim, 'period': period},
                status=422,
            )

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
                COUNT(*) as row_count,
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
                {_aov_expression(dim)} as avg_order_value,
                COUNT(DISTINCT product_id) as product_count,
                {buyers_expr}
            FROM {table} WHERE {period_col} = ?
        ''', (period,)).fetchone()
        current = dict(current) if current else {}
        current_has_rows = bool(current.pop('row_count', 0))
        if not current_has_rows:
            current = {}

        # Previous period (环比)
        if dim == 'monthly':
            prev_period = _get_prev_month(period)
        elif dim == 'weekly':
            from datetime import timedelta
            try:
                prev_period = (datetime.strptime(period, '%Y-%m-%d') - timedelta(days=7)).strftime('%Y-%m-%d')
            except ValueError:
                prev_period = None
        else:  # daily
            from datetime import timedelta
            try:
                prev_period = (datetime.strptime(period, '%Y-%m-%d') - timedelta(days=1)).strftime('%Y-%m-%d')
            except ValueError:
                prev_period = None

        prev = {}
        if prev_period:
            prev = conn.execute(f'''
                SELECT
                    COUNT(*) as row_count,
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
                    {_aov_expression(dim)} as avg_order_value,
                    COUNT(DISTINCT product_id) as product_count,
                    {buyers_expr}
                FROM {table} WHERE {period_col} = ?
            ''', (prev_period,)).fetchone()
            prev = dict(prev) if prev else {}
            if not prev.pop('row_count', 0):
                prev = {}

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
                    COUNT(*) as row_count,
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
                    {_aov_expression(dim)} as avg_order_value,
                    COUNT(DISTINCT product_id) as product_count,
                    {buyers_expr}
                FROM {table} WHERE {period_col} = ?
            ''', (yoy_period,)).fetchone()
            yoy = dict(yoy) if yoy else {}
            if not yoy.pop('row_count', 0):
                yoy = {}

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
            except ValueError:
                # 趋势周期解析失败时跳过该周期
                pass

        return jsonify({
            'period': period,
            'dim': dim,
            'availability': 'available' if current_has_rows else 'no-data',
            'prev_period': prev_period,
            'yoy_period': yoy_period,
            'metrics': result_metrics,
            'trend': trend,
        })


# ==================== 数据报告 API ====================

@reviews_bp.route('/api/reviews/products', methods=['GET'])
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

