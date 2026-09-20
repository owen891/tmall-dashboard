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
        WHERE level = 0
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

# 参与聚合/合成的指标列（渠道行与合成分组行共用）
_CHANNEL_METRIC_KEYS = (
    'uv', 'pv', 'pay_amount', 'pay_buyer_count', 'cart_buyer_count',
    'collect_item_count', 'new_uv', 'deal_buyer_count', 'pay_item_count',
)


def _load_shop_tree_group_map(cursor):
    """构造「渠道名 -> 根层分组名」的映射，取自店铺流量来源树。

    背景：生意参谋单品「第一次访问来源」接口只返回一层平铺渠道，不带父子关系
    （实测 level 恒为 2、pageId 前缀不可靠），所以单品侧一直只有一层。
    但同一个店铺的「店铺流量来源」采的是 tree 接口，含完整层级
    （平台流量 → 手淘搜索 → 手淘搜索-商品及其他）。两张表的渠道命名一致，
    因此可以用店铺树把单品渠道上溯到根层分组，给单品也补出稳定的两级结构。

    返回 name -> 顶层分组名；顶层分组自身映射到自己。
    """
    parent_of = {}
    for name, parent in cursor.execute(
            'SELECT channel_name, IFNULL(parent_channel, "") FROM sycm_flow_source_daily'):
        if name and name not in parent_of:
            parent_of[name] = parent or ''

    cache = {}

    def root_of(name):
        if name in cache:
            return cache[name]
        seen, cur = set(), name
        while True:
            parent = parent_of.get(cur, '')
            if not parent or parent == cur or parent in seen:
                break
            seen.add(parent)
            cur = parent
        cache[name] = cur
        return cur

    return {name: root_of(name) for name in parent_of}


def _empty_channel(name, parent, level):
    channel = {'channel_name': name, 'parent_channel': parent, 'level': level,
               'channel_type': None, 'pay_rate': 0, 'parent_derived': False,
               'synthetic': False}
    for key in _CHANNEL_METRIC_KEYS:
        channel[key] = 0
    return channel


@sycm_bp.route('/item-flow/summary', methods=['GET'])
def item_flow_summary():
    """单品流量来源汇总

    查询参数：
        item_id   商品 ID，可选；不传则按渠道汇总全部单品
        date      单日，可选（默认取表内最新日期）
        start/end 日期范围，优先级高于 date
        belong    farthest=第一次访问来源（默认）
                  all=全程来源（接口自带多级渠道树）

    层级说明：
        all 口径自带多级父子关系（付费推广 → 无界 → 关键词推广）。
        farthest 口径接口只返回平铺一层，早前父级全空，前端因此无法下钻；
        现在会按「店铺渠道树上溯」补出根层分组（平台流量 / 广告流量…），
        并合成分组行，使两种口径都能正常逐级下钻/回退。

    刻意返回两套口径，避免把「渠道相加」误当成「商品总计」：
        channel_totals —— 渠道明细合计，只统计**叶子渠道**（不再把父级和子级重复相加）。
        product_totals —— 商品维度真实值，取自 daily_data
                          （ipv / pv / 支付金额 / 买家数），与商品经营口径一致。
    两者都用「流量来源表在所选范围内实际有数据的日期」计算，保证时间窗一致。
    """
    item_id = (request.args.get('item_id') or '').strip()
    belong = (request.args.get('belong') or 'farthest').strip() or 'farthest'
    start_arg = (request.args.get('start') or '').strip()
    end_arg = (request.args.get('end') or '').strip()
    date_arg = (request.args.get('date') or '').strip()

    if start_arg and end_arg:
        bound_start, bound_end = sorted((start_arg, end_arg))
    elif date_arg:
        bound_start = bound_end = date_arg
    else:
        latest = get_latest_date('sycm_item_flow_source_daily')
        if not latest:
            return failure('NO_DATA', '暂无单品流量来源数据')
        bound_start = bound_end = latest

    conn = get_connection()
    c = conn.cursor()
    # 日期口径必须跟着 belong 走：全程来源(all)目前只有个别日期有数据，
    # 若这里不过滤 belong，就会出现「渠道侧 1 天、商品侧 10 天」的时间窗错配。
    c.execute(
        '''SELECT DISTINCT stat_date FROM sycm_item_flow_source_daily
           WHERE stat_date BETWEEN ? AND ? AND belong = ? ORDER BY stat_date''',
        (bound_start, bound_end, belong))
    dates = [row[0] for row in c.fetchall()]
    if not dates:
        conn.close()
        return failure('NO_DATA', '所选范围内暂无单品流量来源数据')

    conditions = ['stat_date BETWEEN ? AND ?', 'belong = ?']
    params = [bound_start, bound_end, belong]
    if item_id:
        conditions.append('CAST(item_id AS TEXT) = ?')
        params.append(item_id)

    c.execute(f'''
        SELECT channel_name,
               IFNULL(parent_channel, '') AS parent_channel,
               IFNULL(level, -1) AS level,
               MAX(channel_type) AS channel_type,
               SUM(COALESCE(uv, 0)) AS uv,
               SUM(COALESCE(pv, 0)) AS pv,
               SUM(COALESCE(pay_amount, 0)) AS pay_amount,
               SUM(COALESCE(pay_buyer_count, 0)) AS pay_buyer_count,
               SUM(COALESCE(cart_buyer_count, 0)) AS cart_buyer_count,
               SUM(COALESCE(collect_item_count, 0)) AS collect_item_count,
               SUM(COALESCE(new_uv, 0)) AS new_uv,
               SUM(COALESCE(deal_buyer_count, 0)) AS deal_buyer_count,
               SUM(COALESCE(pay_item_count, 0)) AS pay_item_count
        FROM sycm_item_flow_source_daily
        WHERE {' AND '.join(conditions)}
        GROUP BY channel_name, IFNULL(parent_channel, ''), IFNULL(level, -1)
        ORDER BY level ASC, uv DESC
    ''', params)

    channels = []
    for row in c.fetchall():
        uv = row[4] or 0
        pay = row[6] or 0
        buyers = row[7] or 0
        channels.append({
            'channel_name': row[0],
            'parent_channel': row[1],
            'level': row[2],
            'channel_type': row[3],
            'uv': uv,
            'pv': row[5],
            'pay_amount': round(pay, 2),
            'pay_buyer_count': buyers,
            # 按聚合后的买家/访客重算，避免 AVG(每日转化率) 带来的偏差
            'pay_rate': round(buyers / uv, 6) if uv else 0,
            'cart_buyer_count': row[8],
            'collect_item_count': row[9],
            'new_uv': row[10],
            'deal_buyer_count': row[11],
            'pay_item_count': row[12],
            'parent_derived': False,
            'synthetic': False,
        })

    # ---- 补层级：只有「全程来源」自带父子关系，其余口径用店铺渠道树上溯 ----
    derived_count = 0
    if channels:
        group_map = _load_shop_tree_group_map(c)
        present = {ch['channel_name'] for ch in channels}
        for ch in channels:
            if ch['parent_channel']:
                continue
            group = group_map.get(ch['channel_name'])
            if group and group != ch['channel_name'] and group not in present:
                ch['parent_channel'] = group
                ch['parent_derived'] = True
                ch['level'] = 1
                derived_count += 1

    # ---- 合成分组行（父级没有自己的数据行时补一行，否则前端下钻会落空）----
    groups = {}
    present = {ch['channel_name'] for ch in channels}
    for ch in channels:
        parent = ch['parent_channel']
        if not parent or parent in present:
            continue
        bucket = groups.setdefault(parent, _empty_channel(parent, '', 0))
        for key in _CHANNEL_METRIC_KEYS:
            bucket[key] = (bucket[key] or 0) + (ch.get(key) or 0)
    for name in sorted(groups, key=lambda n: -(groups[n]['uv'] or 0)):
        bucket = groups[name]
        uv = bucket['uv'] or 0
        bucket['pay_amount'] = round(bucket['pay_amount'] or 0, 2)
        bucket['pay_rate'] = round((bucket['pay_buyer_count'] or 0) / uv, 6) if uv else 0
        bucket['synthetic'] = True
        channels.insert(0, bucket)

    # ---- 合计只算叶子渠道：父子同表时直接相加会重复计数 ----
    parent_names = {ch['parent_channel'] for ch in channels if ch['parent_channel']}
    leaves = [ch for ch in channels if ch['channel_name'] not in parent_names]
    total_uv = sum(ch['uv'] or 0 for ch in leaves)
    total_pv = sum(ch['pv'] or 0 for ch in leaves)
    total_pay = sum(ch['pay_amount'] or 0 for ch in leaves)
    total_buyers = sum(ch['pay_buyer_count'] or 0 for ch in leaves)
    levels = sorted({ch['level'] for ch in channels
                     if isinstance(ch['level'], int) and ch['level'] >= 0})

    product_totals = None
    if item_id:
        placeholders = ','.join('?' for _ in dates)
        row = c.execute(f'''
            SELECT SUM(ipv), SUM(pv), SUM(payment_amount), SUM(buyers), COUNT(DISTINCT date)
            FROM daily_data
            WHERE CAST(product_id AS TEXT) = ? AND date IN ({placeholders})
        ''', [item_id] + dates).fetchone()
        if row and row[4]:
            product_totals = {
                'visitors': row[0] or 0,
                'pv': row[1] or 0,
                'payment_amount': round(row[2] or 0, 2),
                'buyers': row[3] or 0,
                'days': row[4],
            }
    conn.close()

    return success({
        'item_id': item_id or None,
        'belong': belong,
        # 兼容旧字段：只在单日查询时有值
        'stat_date': dates[0] if len(dates) == 1 else None,
        'start_date': dates[0],
        'end_date': dates[-1],
        'requested_start': bound_start,
        'requested_end': bound_end,
        'data_dates': dates,
        'data_days': len(dates),
        'is_range': len(dates) > 1,
        'total_uv': total_uv,
        'total_pay_amount': round(total_pay, 2),
        'channel_totals': {
            'uv': total_uv,
            'pv': total_pv,
            'pay_amount': round(total_pay, 2),
            'pay_buyer_count': total_buyers,
            'leaf_channels': len(leaves),
        },
        'product_totals': product_totals,
        'derived_parent_count': derived_count,
        'hierarchy_source': 'api' if belong == 'all' else 'shop_tree',
        'levels': levels,
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
        SELECT cate_id, cate_name, item_id, title, pic_url, shop_name, shop_id,
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
            'pic_url': row[4],
            'shop_name': row[5],
            'shop_id': row[6],
            'uv': row[7],
            'pay_buyer_count': row[8],
            'core_keyword': row[9],
            'rank': row[10],
            'is_self': bool(row[11]),
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
