# -*- coding: utf-8 -*-
"""生意参谋数据API
流量来源、竞店竞品、市场排行等数据查询接口
"""
from flask import Blueprint, request, jsonify
from db import get_connection
from api.api_response import success, failure

sycm_bp = Blueprint('sycm', __name__, url_prefix='/api/sycm')


def get_latest_date(table, date_col='stat_date'):
    """获取最新数据日期"""
    conn = get_connection()
    c = conn.cursor()
    c.execute(f'SELECT MAX({date_col}) FROM {table}')
    row = c.fetchone()
    conn.close()
    return row[0] if row and row[0] else None


# ==================== 流量来源 ====================

@sycm_bp.route('/flow-source/summary', methods=['GET'])
def flow_source_summary():
    """流量来源汇总：一级渠道数据"""
    stat_date = request.args.get('date') or get_latest_date('sycm_flow_source_daily')
    if not stat_date:
        return failure('NO_DATA', '暂无流量来源数据')

    conn = get_connection()
    c = conn.cursor()

    # 一级渠道
    c.execute('''
        SELECT channel_name, uv, pay_amount, pay_buyer_count, pay_rate,
               cart_buyer_count, new_uv, uv_value, ad_click_count, ad_pay_amount,
               direct_pay_buyer_count, collect_item_count, fans_pay_buyer_count
        FROM sycm_flow_source_daily
        WHERE stat_date = ? AND level = 0
        ORDER BY uv DESC
    ''', (stat_date,))
    level1 = []
    total_uv = 0
    total_pay = 0
    for row in c.fetchall():
        level1.append({
            'channel_name': row[0],
            'uv': row[1],
            'pay_amount': row[2],
            'pay_buyer_count': row[3],
            'pay_rate': row[4],
            'cart_buyer_count': row[5],
            'new_uv': row[6],
            'uv_value': row[7],
            'ad_click_count': row[8],
            'ad_pay_amount': row[9],
            'direct_pay_buyer_count': row[10],
            'collect_item_count': row[11],
            'fans_pay_buyer_count': row[12],
        })
        total_uv += row[1] or 0
        total_pay += row[3] or 0

    conn.close()

    return success({
        'stat_date': stat_date,
        'belong': 'farthest',
        'belong_name': '第一次访问来源',
        'total_uv': total_uv,
        'total_pay_amount': total_pay,
        'level1_channels': level1,
    })


@sycm_bp.route('/flow-source/detail', methods=['GET'])
def flow_source_detail():
    """流量来源详情：二级渠道数据"""
    stat_date = request.args.get('date') or get_latest_date('sycm_flow_source_daily')
    parent = request.args.get('parent', '')
    if not stat_date:
        return failure('NO_DATA', '暂无流量来源数据')

    conn = get_connection()
    c = conn.cursor()

    query = '''
        SELECT channel_name, parent_channel, uv, pay_amount, pay_buyer_count,
               pay_rate, cart_buyer_count, new_uv, uv_value, level,
               ad_click_count, ad_pay_amount, direct_pay_buyer_count, collect_item_count
        FROM sycm_flow_source_daily
        WHERE stat_date = ?
    '''
    params = [stat_date]

    if parent:
        query += ' AND parent_channel = ?'
        params.append(parent)
    else:
        query += ' AND level = 1'

    query += ' ORDER BY uv DESC'

    c.execute(query, params)
    channels = []
    for row in c.fetchall():
        channels.append({
            'channel_name': row[0],
            'parent_channel': row[1],
            'uv': row[2],
            'pay_amount': row[3],
            'pay_buyer_count': row[4],
            'pay_rate': row[5],
            'cart_buyer_count': row[6],
            'new_uv': row[7],
            'uv_value': row[8],
            'level': row[9],
            'ad_click_count': row[10],
            'ad_pay_amount': row[11],
            'direct_pay_buyer_count': row[12],
            'collect_item_count': row[13],
        })

    conn.close()
    return success({'stat_date': stat_date, 'channels': channels})


@sycm_bp.route('/flow-source/trend', methods=['GET'])
def flow_source_trend():
    """流量来源趋势：最近N天的一级渠道数据"""
    days = int(request.args.get('days', 14))
    conn = get_connection()
    c = conn.cursor()

    c.execute('''
        SELECT stat_date, channel_name, uv, pay_amount, pay_buyer_count
        FROM sycm_flow_source_daily
        WHERE level = 0 AND belong = 'farthest'
        ORDER BY stat_date DESC
        LIMIT ?
    ''', (days * 5,))  # 假设最多5个一级渠道

    trend = {}
    for row in c.fetchall():
        date = row[0]
        channel = row[1]
        if date not in trend:
            trend[date] = {}
        trend[date][channel] = {
            'uv': row[2],
            'pay_amount': row[3],
            'pay_buyer_count': row[4],
        }

    conn.close()

    dates = sorted(trend.keys())
    return success({
        'dates': dates,
        'trend': {d: trend[d] for d in dates},
    })


# ==================== 单品流量来源 ====================

@sycm_bp.route('/item-flow/summary', methods=['GET'])
def item_flow_summary():
    """单品流量来源汇总"""
    stat_date = request.args.get('date') or get_latest_date('sycm_item_flow_source_daily')
    item_id = request.args.get('item_id')
    if not stat_date:
        return failure('NO_DATA', '暂无单品流量来源数据')

    conn = get_connection()
    c = conn.cursor()

    if item_id:
        c.execute('''
            SELECT channel_name, uv, pv, pay_amount, pay_buyer_count, pay_rate,
                   cart_buyer_count, collect_item_count, new_uv, deal_buyer_count, pay_item_count
            FROM sycm_item_flow_source_daily
            WHERE stat_date = ? AND item_id = ? AND belong = 'farthest'
            ORDER BY uv DESC
        ''', (stat_date, item_id))
    else:
        c.execute('''
            SELECT channel_name, SUM(uv) as uv, SUM(pv) as pv, SUM(pay_amount) as pay_amount,
                   SUM(pay_buyer_count) as pay_buyer_count,
                   AVG(pay_rate) as pay_rate, SUM(cart_buyer_count) as cart_buyer_count,
                   SUM(collect_item_count) as collect_item_count, SUM(new_uv) as new_uv,
                   SUM(deal_buyer_count) as deal_buyer_count, SUM(pay_item_count) as pay_item_count
            FROM sycm_item_flow_source_daily
            WHERE stat_date = ? AND belong = 'farthest'
            GROUP BY channel_name
            ORDER BY uv DESC
        ''', (stat_date,))

    channels = []
    total_uv = 0
    total_pay = 0
    for row in c.fetchall():
        channels.append({
            'channel_name': row[0],
            'uv': row[1],
            'pv': row[2],
            'pay_amount': row[3],
            'pay_buyer_count': row[4],
            'pay_rate': row[5],
            'cart_buyer_count': row[6],
            'collect_item_count': row[7],
            'new_uv': row[8],
            'deal_buyer_count': row[9],
            'pay_item_count': row[10],
        })
        total_uv += row[1] or 0
        total_pay += row[3] or 0

    conn.close()
    return success({
        'stat_date': stat_date,
        'item_id': item_id,
        'total_uv': total_uv,
        'total_pay_amount': total_pay,
        'channels': channels,
    })


@sycm_bp.route('/item-flow/top-items', methods=['GET'])
def item_flow_top_items():
    """流量来源TOP商品"""
    stat_date = request.args.get('date') or get_latest_date('sycm_item_flow_source_daily')
    channel = request.args.get('channel', '')
    limit = int(request.args.get('limit', 20))

    conn = get_connection()
    c = conn.cursor()

    query = '''
        SELECT item_id, SUM(uv) as uv, SUM(pay_amount) as pay_amount,
               SUM(pay_buyer_count) as pay_buyer_count
        FROM sycm_item_flow_source_daily
        WHERE stat_date = ? AND belong = 'farthest'
    '''
    params = [stat_date]
    if channel:
        query += ' AND channel_name = ?'
        params.append(channel)
    query += ' GROUP BY item_id ORDER BY uv DESC LIMIT ?'
    params.append(limit)

    c.execute(query, params)
    items = []
    for row in c.fetchall():
        items.append({
            'item_id': row[0],
            'uv': row[1],
            'pay_amount': row[2],
            'pay_buyer_count': row[3],
        })

    conn.close()
    return success({'stat_date': stat_date, 'channel': channel, 'items': items})


# ==================== 竞店分析 ====================

@sycm_bp.route('/rival-shops/list', methods=['GET'])
def rival_shops_list():
    """竞店列表"""
    stat_date = request.args.get('date') or get_latest_date('sycm_market_rival_shop')
    if not stat_date:
        return failure('NO_DATA', '暂无竞店数据')

    conn = get_connection()
    c = conn.cursor()

    c.execute('''
        SELECT shop_id, user_id, shop_name, shop_url, is_tmall,
               uv, pay_buyer_count, cart_buyer_count, pay_rate, collect_buyer_count
        FROM sycm_market_rival_shop
        WHERE stat_date = ?
        ORDER BY uv DESC
    ''', (stat_date,))

    shops = []
    for row in c.fetchall():
        shops.append({
            'shop_id': row[0],
            'user_id': row[1],
            'shop_name': row[2],
            'shop_url': row[3],
            'is_tmall': bool(row[4]),
            'uv': row[5],
            'pay_buyer_count': row[6],
            'cart_buyer_count': row[7],
            'pay_rate': row[8],
            'collect_buyer_count': row[9],
        })

    conn.close()
    return success({'stat_date': stat_date, 'shops': shops})


@sycm_bp.route('/rival-shops/summary', methods=['GET'])
def rival_shops_summary():
    """竞店分析汇总"""
    stat_date = request.args.get('date') or get_latest_date('sycm_market_rival_shop')
    if not stat_date:
        return failure('NO_DATA', '暂无竞店数据')

    conn = get_connection()
    c = conn.cursor()

    # 竞店统计
    c.execute('''
        SELECT COUNT(*), AVG(uv), AVG(pay_buyer_count), AVG(pay_rate),
               SUM(CASE WHEN is_tmall = 1 THEN 1 ELSE 0 END),
               SUM(CASE WHEN is_tmall = 0 THEN 1 ELSE 0 END)
        FROM sycm_market_rival_shop
        WHERE stat_date = ?
    ''', (stat_date,))
    row = c.fetchone()

    # TOP竞店
    c.execute('''
        SELECT shop_name, uv, pay_buyer_count, pay_rate, is_tmall
        FROM sycm_market_rival_shop
        WHERE stat_date = ?
        ORDER BY uv DESC LIMIT 10
    ''', (stat_date,))
    top_shops = []
    for r in c.fetchall():
        top_shops.append({
            'shop_name': r[0],
            'uv': r[1],
            'pay_buyer_count': r[2],
            'pay_rate': r[3],
            'is_tmall': bool(r[4]),
        })

    conn.close()

    return success({
        'stat_date': stat_date,
        'total_shops': row[0],
        'avg_uv': row[1],
        'avg_pay_buyers': row[2],
        'avg_pay_rate': row[3],
        'tmall_count': row[4],
        'taobao_count': row[5],
        'top_shops': top_shops,
    })


# ==================== 竞品分析 ====================

@sycm_bp.route('/rival-items/list', methods=['GET'])
def rival_items_list():
    """竞品列表"""
    stat_date = request.args.get('date') or get_latest_date('sycm_market_rival_item')
    if not stat_date:
        return failure('NO_DATA', '暂无竞品数据')

    conn = get_connection()
    c = conn.cursor()

    c.execute('''
        SELECT item_id, title, uv, pay_buyer_count, pic_url, detail_url
        FROM sycm_market_rival_item
        WHERE stat_date = ?
        ORDER BY uv DESC
    ''', (stat_date,))

    items = []
    for row in c.fetchall():
        items.append({
            'item_id': row[0],
            'title': row[1],
            'uv': row[2],
            'pay_buyer_count': row[3],
            'pic_url': row[4],
            'detail_url': row[5],
        })

    conn.close()
    return success({'stat_date': stat_date, 'items': items})


# ==================== 市场排行（生意参谋新数据） ====================

@sycm_bp.route('/market/item-rank', methods=['GET'])
def market_item_rank():
    """商品排行榜"""
    stat_date = request.args.get('date') or get_latest_date('sycm_market_item_rank')
    cate_id = request.args.get('cate_id', '')
    cate_name = request.args.get('cate_name', '')
    limit = int(request.args.get('limit', 50))

    conn = get_connection()
    c = conn.cursor()

    query = '''
        SELECT cate_id, cate_name, item_id, title, shop_name, shop_id,
               uv, pay_buyer_count, core_keyword, rank, is_self
        FROM sycm_market_item_rank
        WHERE stat_date = ?
    '''
    params = [stat_date]
    if cate_id:
        query += ' AND cate_id = ?'
        params.append(cate_id)
    if cate_name:
        query += ' AND cate_name = ?'
        params.append(cate_name)
    query += ' ORDER BY uv DESC LIMIT ?'
    params.append(limit)

    c.execute(query, params)
    items = []
    for row in c.fetchall():
        items.append({
            'cate_id': row[0],
            'cate_name': row[1],
            'item_id': row[2],
            'title': row[3],
            'shop_name': row[4],
            'shop_id': row[5],
            'uv': row[6],
            'pay_buyer_count': row[7],
            'core_keyword': row[8],
            'rank': row[9],
            'is_self': bool(row[10]),
        })

    conn.close()
    return success({'stat_date': stat_date, 'items': items})


@sycm_bp.route('/market/search-rank', methods=['GET'])
def market_search_rank():
    """搜索排行榜"""
    stat_date = request.args.get('date') or get_latest_date('sycm_market_search_rank')
    cate_id = request.args.get('cate_id', '')
    cate_name = request.args.get('cate_name', '')
    limit = int(request.args.get('limit', 50))

    conn = get_connection()
    c = conn.cursor()

    query = '''
        SELECT cate_id, cate_name, keyword, search_heat, pay_rate,
               free_click_rate, click_rate, rank
        FROM sycm_market_search_rank
        WHERE stat_date = ?
    '''
    params = [stat_date]
    if cate_id:
        query += ' AND cate_id = ?'
        params.append(cate_id)
    if cate_name:
        query += ' AND cate_name = ?'
        params.append(cate_name)
    query += ' ORDER BY search_heat DESC LIMIT ?'
    params.append(limit)

    c.execute(query, params)
    keywords = []
    for row in c.fetchall():
        keywords.append({
            'cate_id': row[0],
            'cate_name': row[1],
            'keyword': row[2],
            'search_heat': row[3],
            'pay_rate': row[4],
            'free_click_rate': row[5],
            'click_rate': row[6],
            'rank': row[7],
        })

    conn.close()
    return success({'stat_date': stat_date, 'keywords': keywords})


@sycm_bp.route('/market/categories', methods=['GET'])
def market_categories():
    """市场类目列表"""
    stat_date = request.args.get('date') or get_latest_date('sycm_market_item_rank')
    if not stat_date:
        return failure('NO_DATA', '暂无市场数据')

    conn = get_connection()
    c = conn.cursor()

    c.execute('''
        SELECT DISTINCT cate_id, cate_name,
               COUNT(*) as item_count, AVG(uv) as avg_uv
        FROM sycm_market_item_rank
        WHERE stat_date = ?
        GROUP BY cate_id, cate_name
        ORDER BY avg_uv DESC
    ''', (stat_date,))

    categories = []
    for row in c.fetchall():
        categories.append({
            'cate_id': row[0],
            'cate_name': row[1],
            'item_count': row[2],
            'avg_uv': row[3],
        })

    conn.close()
    return success({'stat_date': stat_date, 'categories': categories})
