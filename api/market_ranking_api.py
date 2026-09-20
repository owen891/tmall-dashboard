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
    c = conn.cursor()
    if analysis_date:
        c.execute('''SELECT id FROM market_analysis_runs
                     WHERE analysis_date <= ? ORDER BY analysis_date DESC LIMIT 1''', (analysis_date,))
    else:
        c.execute('SELECT id FROM market_analysis_runs ORDER BY analysis_date DESC LIMIT 1')
    row = c.fetchone()
    conn.close()
    return row[0] if row else None


@market_ranking_bp.route('/summary', methods=['GET'])
def summary():
    """汇总数据：类目统计+总览指标"""
    run_id = get_latest_run_id(request.args.get('analysis_date'))
    if not run_id:
        return failure('NO_DATA', '暂无市场分析数据')

    conn = get_connection()
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
    c = conn.cursor()
    c.execute('''SELECT category, shop_tmall, shop_taobao, trend_flat, trend_up,
                 trend_down, trend_out, trend_new, concentration_top10,
                 concentration_top50, total_buyers
                 FROM market_category_stats WHERE run_id=? ORDER BY total_buyers DESC''', (run_id,))
    rows = c.fetchall()
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
    """商品榜单，支持category和list_type筛选"""
    run_id = get_latest_run_id(request.args.get('analysis_date'))
    if not run_id:
        return failure('NO_DATA', '暂无市场分析数据')

    category = request.args.get('category', '')
    list_type = request.args.get('list_type', '')

    conn = get_connection()
    c = conn.cursor()

    sql = '''SELECT category, list_type, rank, title, shop, buyers, visitors
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
    conn.close()

    return success([{
        'category': r[0], 'list_type': r[1], 'rank': r[2],
        'title': r[3], 'shop': r[4], 'buyers': r[5], 'visitors': r[6],
    } for r in rows])


@market_ranking_bp.route('/keywords', methods=['GET'])
def keywords():
    """关键词，支持category和keyword_type筛选"""
    run_id = get_latest_run_id(request.args.get('analysis_date'))
    if not run_id:
        return failure('NO_DATA', '暂无市场分析数据')

    category = request.args.get('category', '')
    keyword_type = request.args.get('keyword_type', '')

    conn = get_connection()
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
    c = conn.cursor()
    c.execute('SELECT shop_name FROM market_overlap_shops WHERE run_id=? ORDER BY shop_name', (run_id,))
    rows = c.fetchall()
    conn.close()

    return success([r[0] for r in rows])


@market_ranking_bp.route('/filters', methods=['GET'])
def filters():
    """筛选选项"""
    run_id = get_latest_run_id(request.args.get('analysis_date'))
    if not run_id:
        return failure('NO_DATA', '暂无市场分析数据')

    conn = get_connection()
    c = conn.cursor()

    c.execute('SELECT DISTINCT category FROM market_products WHERE run_id=? ORDER BY category', (run_id,))
    categories = [r[0] for r in c.fetchall()]

    c.execute('SELECT DISTINCT list_type FROM market_products WHERE run_id=? ORDER BY list_type', (run_id,))
    list_types = [r[0] for r in c.fetchall()]

    c.execute('SELECT DISTINCT keyword_type FROM market_keywords WHERE run_id=? ORDER BY keyword_type', (run_id,))
    keyword_types = [r[0] for r in c.fetchall()]

    conn.close()

    return success({
        'categories': categories,
        'list_types': list_types,
        'keyword_types': keyword_types,
    })
