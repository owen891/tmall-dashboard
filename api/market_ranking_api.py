# -*- coding: utf-8 -*-
"""市场排行分析API
店透视市场排行数据查询接口
"""
from flask import Blueprint, request, jsonify
from db import get_connection
from api.api_response import success, failure

market_ranking_bp = Blueprint('market_ranking', __name__, url_prefix='/api/market-ranking')


def get_latest_run_id(analysis_date=None):
    """获取最新分析批次ID"""
    conn = get_connection()
    try:
        c = conn.cursor()
        if analysis_date:
            c.execute('''SELECT id FROM market_analysis_runs
                         WHERE analysis_date <= ? ORDER BY analysis_date DESC LIMIT 1''', (analysis_date,))
        else:
            c.execute('SELECT id FROM market_analysis_runs ORDER BY analysis_date DESC LIMIT 1')
        row = c.fetchone()
    finally:
        conn.close()
    return row[0] if row else None



# --- 新采集链路适配 -------------------------------------------------------
# 店透视 XLSX 导入（market_analysis_*）与生意参谋采集（sycm_market_*）是两条
# 独立链路。旧链路已停更（最后批次 2026-09-27），新链路仍在每日写入。
# 这里让接口优先读新链路，并把它折算成旧响应结构，前端无需改动。
SYCM_ITEM = 'sycm_market_item_rank'
SYCM_SEARCH = 'sycm_market_search_rank'


def _sycm_latest_date(conn, analysis_date=None):
    """新链路可用的最新 stat_date（不晚于请求日期）。"""
    sql = f'SELECT MAX(stat_date) FROM {SYCM_ITEM}'
    params = ()
    if analysis_date:
        sql += ' WHERE stat_date <= ?'
        params = (analysis_date,)
    try:
        row = conn.execute(sql, params).fetchone()
    except Exception:
        return None
    return row[0] if row else None


def _sycm_summary(conn, stat_date):
    """按新链路聚合出旧 summary 结构（类目统计 + 总览指标）。"""
    rows = conn.execute(f"""
        SELECT cate_name,
               COUNT(*) AS item_rows,
               SUM(uv) AS total_uv,
               SUM(CASE WHEN rank <= 10 THEN uv ELSE 0 END) AS top10_uv,
               SUM(CASE WHEN rank <= 50 THEN uv ELSE 0 END) AS top50_uv,
               SUM(pay_buyer_count) AS buyers,
               COUNT(DISTINCT shop_id) AS shops
          FROM {SYCM_ITEM}
         WHERE stat_date = ?
      GROUP BY cate_name
      ORDER BY total_uv DESC
    """, (stat_date,)).fetchall()

    categories = []
    for name, item_rows, total_uv, top10_uv, top50_uv, buyers, shops in rows:
        total_uv = total_uv or 0
        categories.append({
            'category': name,
            # 旧字段语义：在榜店铺数。新链路只有排名样本，用去重店铺数近似。
            'shop_tmall': int(shops or 0),
            'shop_taobao': 0,
            'trend_flat': 0, 'trend_up': 0, 'trend_down': 0,
            'trend_out': 0, 'trend_new': 0,
            'concentration_top10': round(100.0 * (top10_uv or 0) / total_uv, 2) if total_uv else 0,
            'concentration_top50': round(100.0 * (top50_uv or 0) / total_uv, 2) if total_uv else 0,
            'total_buyers': float(buyers or 0),
        })

    product_count = conn.execute(
        f'SELECT COUNT(*) FROM {SYCM_ITEM} WHERE stat_date = ?', (stat_date,)).fetchone()[0]
    keyword_count = conn.execute(
        f'SELECT COUNT(*) FROM {SYCM_SEARCH} WHERE stat_date = ?', (stat_date,)).fetchone()[0]
    shop_count = conn.execute(
        f'SELECT COUNT(DISTINCT shop_id) FROM {SYCM_ITEM} WHERE stat_date = ?', (stat_date,)).fetchone()[0]

    return {
        'run_id': f'sycm:{stat_date}',
        'analysis_date': stat_date,
        'period_start': stat_date,
        'period_end': stat_date,
        'source': '店透视市场排行（生意参谋采集）',
        'category_count': len(categories),
        'product_count': product_count,
        'keyword_count': keyword_count,
        'overlap_shop_count': shop_count,
        'categories': categories,
    }


@market_ranking_bp.route('/summary', methods=['GET'])
def summary():
    """汇总数据：类目统计+总览指标（优先新采集链路）"""
    requested = request.args.get('analysis_date')
    conn = get_connection()
    try:
        stat_date = _sycm_latest_date(conn, requested)
        if stat_date:
            return success(_sycm_summary(conn, stat_date))
    except Exception:
        pass
    finally:
        conn.close()

    run_id = get_latest_run_id(requested)
    if not run_id:
        return failure('NO_DATA', '暂无市场分析数据')

    conn = get_connection()
    try:
        c = conn.cursor()

        # 类目统计
        c.execute('''SELECT category, shop_tmall, shop_taobao, trend_flat, trend_up,
                     trend_down, trend_out, trend_new, concentration_top10,
                     concentration_top50, total_buyers
                     FROM market_category_stats WHERE run_id=?''', (run_id,))
        categories = []
        for row in c.fetchall():
            categories.append({
                'category': row[0],
                'shop_tmall': row[1],
                'shop_taobao': row[2],
                'trend_flat': row[3],
                'trend_up': row[4],
                'trend_down': row[5],
                'trend_out': row[6],
                'trend_new': row[7],
                'concentration_top10': row[8],
                'concentration_top50': row[9],
                'total_buyers': row[10],
            })

        # 商品总数
        c.execute('SELECT COUNT(DISTINCT category), COUNT(*) FROM market_products WHERE run_id=?', (run_id,))
        cat_count, product_count = c.fetchone()

        # 关键词总数
        c.execute('SELECT COUNT(*) FROM market_keywords WHERE run_id=?', (run_id,))
        keyword_count = c.fetchone()[0]

        # 重叠店铺
        c.execute('SELECT COUNT(*) FROM market_overlap_shops WHERE run_id=?', (run_id,))
        overlap_count = c.fetchone()[0]

        # 批次信息
        c.execute('SELECT analysis_date, period_start, period_end, source FROM market_analysis_runs WHERE id=?', (run_id,))
        run_info = c.fetchone()

    finally:
        conn.close()

    return success({
        'run_id': run_id,
        'analysis_date': run_info[0],
        'period_start': run_info[1],
        'period_end': run_info[2],
        'source': run_info[3],
        'category_count': cat_count,
        'product_count': product_count,
        'keyword_count': keyword_count,
        'overlap_shop_count': overlap_count,
        'categories': categories,
    })


@market_ranking_bp.route('/category-stats', methods=['GET'])
def category_stats():
    """类目统计详情"""
    run_id = get_latest_run_id(request.args.get('analysis_date'))
    if not run_id:
        return failure('NO_DATA', '暂无市场分析数据')

    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute('''SELECT category, shop_tmall, shop_taobao, trend_flat, trend_up,
                     trend_down, trend_out, trend_new, concentration_top10,
                     concentration_top50, total_buyers
                     FROM market_category_stats WHERE run_id=? ORDER BY total_buyers DESC''', (run_id,))
        rows = c.fetchall()
    finally:
        conn.close()

    return success([{
        'category': r[0], 'shop_tmall': r[1], 'shop_taobao': r[2],
        'trend_flat': r[3], 'trend_up': r[4], 'trend_down': r[5],
        'trend_out': r[6], 'trend_new': r[7],
        'concentration_top10': r[8], 'concentration_top50': r[9],
        'total_buyers': r[10],
    } for r in rows])


@market_ranking_bp.route('/products', methods=['GET'])
def products():
    """商品榜单，支持category和list_type筛选（优先新采集链路）"""
    category = request.args.get('category', '')
    list_type = request.args.get('list_type', '')
    requested = request.args.get('analysis_date')

    conn = get_connection()
    try:
        stat_date = _sycm_latest_date(conn, requested)
        if stat_date:
            sql = (f'SELECT cate_name, rank, title, shop_name, pay_buyer_count, uv, pic_url, item_id '
                   f'FROM {SYCM_ITEM} WHERE stat_date = ?')
            params = [stat_date]
            if category:
                sql += ' AND cate_name = ?'
                params.append(category)
            sql += ' ORDER BY cate_name, rank'
            rows = conn.execute(sql, params).fetchall()
            return success([{
                'category': r[0], 'list_type': '支付买家数TOP', 'rank': r[1],
                'rank_change': None, 'title': r[2], 'shop': r[3],
                'buyers': r[4], 'visitors': r[5],
                'image_url': r[6], 'item_id': r[7],
            } for r in rows])
    except Exception:
        pass

    run_id = get_latest_run_id(requested)
    if not run_id:
        conn.close()
        return failure('NO_DATA', '暂无市场分析数据')

    try:
        c = conn.cursor()

        sql = '''SELECT category, list_type, rank, rank_change, title, shop, buyers, visitors
                 FROM market_products WHERE run_id=?'''
        params = [run_id]

        if category:
            sql += ' AND category=?'
            params.append(category)
        if list_type:
            sql += ' AND list_type=?'
            params.append(list_type)

        sql += ' ORDER BY category, list_type, rank'
        c.execute(sql, params)
        rows = c.fetchall()
    finally:
        conn.close()

    return success([{
        'category': r[0], 'list_type': r[1], 'rank': r[2], 'rank_change': r[3],
        'title': r[4], 'shop': r[5], 'buyers': r[6], 'visitors': r[7],
    } for r in rows])


@market_ranking_bp.route('/keywords', methods=['GET'])
def keywords():
    """关键词，支持category和keyword_type筛选（优先新采集链路）"""
    category = request.args.get('category', '')
    keyword_type = request.args.get('keyword_type', '')
    requested = request.args.get('analysis_date')

    conn = get_connection()
    try:
        stat_date = _sycm_latest_date(conn, requested)
        if stat_date:
            sql = (f'SELECT cate_name, keyword, search_heat, rank FROM {SYCM_SEARCH} '
                   f'WHERE stat_date = ?')
            params = [stat_date]
            if category:
                sql += ' AND cate_name = ?'
                params.append(category)
            sql += ' ORDER BY cate_name, rank LIMIT 2000'
            rows = conn.execute(sql, params).fetchall()
            return success([{
                'category': r[0], 'keyword_type': '搜索人气', 'keyword': r[1],
                'count': r[2], 'rank': r[3],
            } for r in rows])
    except Exception:
        pass

    run_id = get_latest_run_id(requested)
    if not run_id:
        conn.close()
        return failure('NO_DATA', '暂无市场分析数据')

    try:
        c = conn.cursor()

        sql = 'SELECT category, keyword_type, keyword, count, rank FROM market_keywords WHERE run_id=?'
        params = [run_id]

        if category:
            sql += ' AND category=?'
            params.append(category)
        if keyword_type:
            sql += ' AND keyword_type=?'
            params.append(keyword_type)

        sql += ' ORDER BY category, keyword_type, rank'
        c.execute(sql, params)
        rows = c.fetchall()
    finally:
        conn.close()

    return success([{
        'category': r[0], 'keyword_type': r[1],
        'keyword': r[2], 'count': r[3], 'rank': r[4],
    } for r in rows])


@market_ranking_bp.route('/overlap-shops', methods=['GET'])
def overlap_shops():
    """重叠店铺（同时在两个类目在榜的店铺）"""
    run_id = get_latest_run_id(request.args.get('analysis_date'))
    if not run_id:
        return failure('NO_DATA', '暂无市场分析数据')

    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute('SELECT shop_name FROM market_overlap_shops WHERE run_id=? ORDER BY shop_name', (run_id,))
        rows = c.fetchall()
    finally:
        conn.close()

    return success([r[0] for r in rows])


@market_ranking_bp.route('/filters', methods=['GET'])
def filters():
    """筛选选项"""
    run_id = get_latest_run_id(request.args.get('analysis_date'))
    if not run_id:
        return failure('NO_DATA', '暂无市场分析数据')

    conn = get_connection()
    try:
        c = conn.cursor()

        c.execute('SELECT DISTINCT category FROM market_products WHERE run_id=? ORDER BY category', (run_id,))
        categories = [r[0] for r in c.fetchall()]

        c.execute('SELECT DISTINCT list_type FROM market_products WHERE run_id=? ORDER BY list_type', (run_id,))
        list_types = [r[0] for r in c.fetchall()]

        c.execute('SELECT DISTINCT keyword_type FROM market_keywords WHERE run_id=? ORDER BY keyword_type', (run_id,))
        keyword_types = [r[0] for r in c.fetchall()]

    finally:
        conn.close()

    return success({
        'categories': categories,
        'list_types': list_types,
        'keyword_types': keyword_types,
    })
