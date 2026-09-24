# -*- coding: utf-8 -*-
"""生意参谋（SYCM）市场与竞店竞品的共享数据访问。

从 api/sycm_api.py 下沉的数据访问层：
- latest_date：各 sycm 表的最新统计日
- rival_trend / rival_entity_trend / rival_entities：竞店/竞品按表名
  参数化的通用查询（shop 表与 item 表共用一套口径，is_self=0
  且排除本店商品）。
- flow_source_*：店铺/单品流量来源聚合。
- item_flow_*：单品流量来源渠道聚合与商品口径合计。
- market_*：市场排行/搜索榜/外部店铺与单品实体。
- snapshot_*：浏览器插件导出的周期榜单。

设计约束：
- 只读，不写业务表。
- 缺失数据显式返回（None / 空列表 / coverage 字段），不把缺失当零值。
- 表名/列名来自调用方硬编码白名单（非用户输入），值一律参数化。
"""

from datetime import date

from db import get_connection


def latest_date(table, date_col='stat_date'):
    conn = get_connection()
    try:
        row = conn.execute(
            f'SELECT MAX({date_col}) as latest FROM {table}'
        ).fetchone()
        return row[0] if row and row[0] else None
    finally:
        conn.close()


def expected_days(start_date, end_date):
    try:
        return max(1, (date.fromisoformat(end_date) - date.fromisoformat(start_date)).days + 1)
    except (TypeError, ValueError):
        return None


def rival_trend(table, key, start_date, end_date):
    """Return daily market observations without filling missing dates as zero."""
    is_rank_items = table == 'sycm_market_item_rank'
    item_source = (
        f'''(SELECT stat_date, item_id, MAX(uv) AS uv, MAX(pay_buyer_count) AS pay_buyer_count
             FROM {table} WHERE is_self = 0
               AND NOT EXISTS (SELECT 1 FROM products p WHERE p.product_id = {table}.item_id)
             GROUP BY stat_date, item_id)'''
        if is_rank_items else table
    )
    own_item_filter = (
        'AND NOT EXISTS (SELECT 1 FROM products p WHERE p.product_id = sycm_market_rival_item.item_id)'
        if table == 'sycm_market_rival_item' else ''
    )
    conn = get_connection()
    try:
        sql = (
            f'''SELECT stat_date, COUNT(DISTINCT {key}) AS entity_count,
                       SUM(uv) AS uv, SUM(pay_buyer_count) AS pay_buyer_count,
                       CASE WHEN SUM(uv) IS NULL OR SUM(uv) = 0 THEN NULL
                            ELSE SUM(pay_buyer_count) * 1.0 / SUM(uv) END AS pay_rate
                FROM {item_source}
                WHERE stat_date BETWEEN ? AND ? {own_item_filter}
                GROUP BY stat_date ORDER BY stat_date'''
        )
        params = (start_date, end_date)
        rows = conn.execute(sql, params).fetchall()
    except Exception:
        conn.close()
        return None
    conn.close()
    expected = expected_days(start_date, end_date)
    observed_days = len(rows)
    trend = [dict(row) for row in rows]
    totals = {
        'uv': sum(float(row['uv'] or 0) for row in rows),
        'pay_buyer_count': sum(float(row['pay_buyer_count'] or 0) for row in rows),
    }
    totals['pay_rate'] = (totals['pay_buyer_count'] / totals['uv']) if totals['uv'] else None
    totals['avg_uv_per_day'] = totals['uv'] / observed_days if observed_days else None
    totals['avg_pay_buyers_per_day'] = totals['pay_buyer_count'] / observed_days if observed_days else None
    coverage_rate = (observed_days / expected) if expected else None
    return {
        'start_date': start_date,
        'end_date': end_date,
        'expected_days': expected,
        'observed_days': observed_days,
        'coverage_rate': coverage_rate,
        'coverage_status': 'complete' if coverage_rate == 1 else ('partial' if observed_days else 'no_data'),
        'trend_comparable': bool(expected and coverage_rate >= 0.8),
        'totals': totals,
        'daily': trend,
    }


def rival_entities(table, key, label, start_date, end_date):
    if table == 'sycm_market_item_rank':
        conn = get_connection()
        try:
            rows = conn.execute(
                '''SELECT item_id AS entity_id, MAX(title) AS entity_name,
                          COUNT(DISTINCT stat_date) AS observed_days, MAX(stat_date) AS last_seen
                   FROM sycm_market_item_rank
                   WHERE stat_date BETWEEN ? AND ? AND is_self = 0
                     AND NOT EXISTS (SELECT 1 FROM products p WHERE p.product_id = sycm_market_item_rank.item_id)
                   GROUP BY item_id ORDER BY observed_days DESC, last_seen DESC, entity_name''',
                (start_date, end_date),
            ).fetchall()
        except Exception:
            conn.close()
            return []
        conn.close()
        return [dict(row) for row in rows]
    own_item_filter = (
        'AND NOT EXISTS (SELECT 1 FROM products p WHERE p.product_id = sycm_market_rival_item.item_id)'
        if table == 'sycm_market_rival_item' else ''
    )
    conn = get_connection()
    try:
        rows = conn.execute(
            f'''SELECT {key} AS entity_id, MAX({label}) AS entity_name,
                       COUNT(DISTINCT stat_date) AS observed_days,
                       MAX(stat_date) AS last_seen
                FROM {table} WHERE stat_date BETWEEN ? AND ? {own_item_filter}
                GROUP BY {key} ORDER BY observed_days DESC, last_seen DESC, entity_name''',
            (start_date, end_date),
        ).fetchall()
    except Exception:
        conn.close()
        return []
    conn.close()
    return [dict(row) for row in rows]


def rival_entity_trend(table, key, entity_id, start_date, end_date):
    """Return one shop/item's daily facts and explicit coverage."""
    if table == 'sycm_market_item_rank':
        conn = get_connection()
        try:
            rows = conn.execute(
                '''SELECT stat_date, MAX(title) AS title, MAX(pic_url) AS pic_url,
                          MAX(uv) AS uv, MAX(pay_buyer_count) AS pay_buyer_count
                   FROM sycm_market_item_rank
                   WHERE item_id = ? AND stat_date BETWEEN ? AND ? AND is_self = 0
                     AND NOT EXISTS (SELECT 1 FROM products p WHERE p.product_id = sycm_market_item_rank.item_id)
                   GROUP BY stat_date ORDER BY stat_date''',
                (entity_id, start_date, end_date),
            ).fetchall()
        except Exception:
            conn.close()
            return None
        conn.close()
        expected = expected_days(start_date, end_date)
        daily = [dict(row) for row in rows]
        for row in daily:
            uv = row.get('uv')
            row['pay_rate'] = (float(row.get('pay_buyer_count') or 0) / float(uv)) if uv else None
        observed_days = len(daily)
        coverage_rate = observed_days / expected if expected else None
        identity = daily[-1] if daily else {}
        return {
            'entity_id': entity_id, 'entity_name': identity.get('title'),
            'start_date': start_date, 'end_date': end_date,
            'expected_days': expected, 'observed_days': observed_days,
            'coverage_rate': coverage_rate,
            'coverage_status': 'complete' if coverage_rate == 1 else ('partial' if observed_days else 'no_data'),
            'trend_comparable': bool(expected and coverage_rate >= 0.8), 'daily': daily,
        }

    columns = (
        'stat_date, shop_name, uv, pay_buyer_count, pay_rate, cart_buyer_count, collect_buyer_count'
        if table == 'sycm_market_rival_shop' else
        'stat_date, title, uv, pay_buyer_count, pic_url, detail_url'
    )
    own_item_filter = (
        'AND NOT EXISTS (SELECT 1 FROM products p WHERE p.product_id = sycm_market_rival_item.item_id)'
        if table == 'sycm_market_rival_item' else ''
    )
    conn = get_connection()
    try:
        rows = conn.execute(
            f'SELECT {columns} FROM {table} WHERE {key} = ? AND stat_date BETWEEN ? AND ? {own_item_filter} ORDER BY stat_date',
            (entity_id, start_date, end_date),
        ).fetchall()
    except Exception:
        conn.close()
        return None
    conn.close()
    expected = expected_days(start_date, end_date)
    daily = [dict(row) for row in rows]
    for row in daily:
        if table == 'sycm_market_rival_item':
            uv = row.get('uv')
            row['pay_rate'] = (float(row.get('pay_buyer_count') or 0) / float(uv)) if uv else None
    observed_days = len(daily)
    coverage_rate = observed_days / expected if expected else None
    identity = daily[-1] if daily else {}
    return {
        'entity_id': entity_id,
        'entity_name': identity.get('shop_name') or identity.get('title'),
        'start_date': start_date,
        'end_date': end_date,
        'expected_days': expected,
        'observed_days': observed_days,
        'coverage_rate': coverage_rate,
        'coverage_status': 'complete' if coverage_rate == 1 else ('partial' if observed_days else 'no_data'),
        'trend_comparable': bool(expected and coverage_rate >= 0.8),
        'daily': daily,
    }


# ==================== 店铺流量来源 ====================

def flow_source_level1(start_date, end_date):
    """一级渠道（level=0）聚合，按 uv 降序。"""
    conn = get_connection()
    try:
        rows = conn.execute(
            '''SELECT channel_name, SUM(uv), SUM(pay_amount), SUM(pay_buyer_count),
                      SUM(cart_buyer_count), SUM(new_uv), SUM(ad_click_count),
                      SUM(ad_pay_amount), SUM(direct_pay_buyer_count),
                      SUM(collect_item_count), SUM(fans_pay_buyer_count)
               FROM sycm_flow_source_daily
               WHERE stat_date BETWEEN ? AND ? AND level = 0
               GROUP BY channel_name ORDER BY uv DESC''',
            (start_date, end_date)).fetchall()
    finally:
        conn.close()
    level1 = []
    for row in rows:
        uv, pay, buyers = row[1], row[2], row[3]
        level1.append({
            'channel_name': row[0],
            'uv': uv,
            'pay_amount': pay,
            'pay_buyer_count': buyers,
            'pay_rate': round((buyers or 0) / (uv or 1), 6) if uv else 0,
            'cart_buyer_count': row[4],
            'new_uv': row[5],
            'uv_value': round((pay or 0) / (uv or 1), 2) if uv else 0,
            'ad_click_count': row[6],
            'ad_pay_amount': row[7],
            'direct_pay_buyer_count': row[8],
            'collect_item_count': row[9],
            'fans_pay_buyer_count': row[10],
        })
    return level1


def flow_source_level2(start_date, end_date, parent):
    """二级渠道（level=1 或指定父渠道）聚合，按 uv 降序。"""
    query = '''
        SELECT channel_name, parent_channel, MAX(channel_type), SUM(uv),
               SUM(pay_amount), SUM(pay_buyer_count), SUM(cart_buyer_count),
               SUM(new_uv), MAX(level), SUM(ad_click_count), SUM(ad_pay_amount),
               SUM(direct_pay_buyer_count), SUM(collect_item_count)
        FROM sycm_flow_source_daily
        WHERE stat_date BETWEEN ? AND ?
    '''
    params = [start_date, end_date]
    if parent:
        query += ' AND parent_channel = ?'
        params.append(parent)
    else:
        query += ' AND level = 1'
    query += ' GROUP BY channel_name, parent_channel ORDER BY SUM(uv) DESC'
    conn = get_connection()
    try:
        rows = conn.execute(query, params).fetchall()
    finally:
        conn.close()
    channels = []
    for row in rows:
        uv, pay, buyers = row[3], row[4], row[5]
        channels.append({
            'channel_name': row[0],
            'parent_channel': row[1],
            'channel_type': row[2],
            'uv': uv,
            'pay_amount': pay,
            'pay_buyer_count': buyers,
            'pay_rate': round((buyers or 0) / (uv or 1), 6) if uv else 0,
            'cart_buyer_count': row[6],
            'new_uv': row[7],
            'uv_value': round((pay or 0) / (uv or 1), 2) if uv else 0,
            'level': row[8],
            'ad_click_count': row[9],
            'ad_pay_amount': row[10],
            'direct_pay_buyer_count': row[11],
            'collect_item_count': row[12],
        })
    return channels


def flow_source_recent_trend(days):
    """最近 N 天的一级渠道日序列，返回 {stat_date: {channel: {uv, pay_amount, pay_buyer_count}}}。"""
    conn = get_connection()
    try:
        rows = conn.execute(
            '''SELECT stat_date, channel_name, uv, pay_amount, pay_buyer_count
               FROM sycm_flow_source_daily
               WHERE level = 0
               ORDER BY stat_date DESC
               LIMIT ?''',
            (days * 5,)).fetchall()  # 假设最多5个一级渠道
    finally:
        conn.close()
    trend = {}
    for row in rows:
        date, channel = row[0], row[1]
        trend.setdefault(date, {})[channel] = {
            'uv': row[2],
            'pay_amount': row[3],
            'pay_buyer_count': row[4],
        }
    return trend


# ==================== 单品流量来源 ====================

def shop_tree_group_map():
    """构造「渠道名 -> 根层分组名」的映射，取自店铺流量来源树。

    背景：生意参谋单品「第一次访问来源」接口只返回一层平铺渠道，不带父子关系
    （实测 level 恒为 2、pageId 前缀不可靠），所以单品侧一直只有一层。
    但同一个店铺的「店铺流量来源」采的是 tree 接口，含完整层级
    （平台流量 → 手淘搜索 → 手淘搜索-商品及其他）。两张表的渠道命名一致，
    因此可以用店铺树把单品渠道上溯到根层分组，给单品也补出稳定的两级结构。

    返回 name -> 顶层分组名；顶层分组自身映射到自己。
    """
    conn = get_connection()
    try:
        parent_of = {}
        for name, parent in conn.execute(
                'SELECT channel_name, IFNULL(parent_channel, "") FROM sycm_flow_source_daily'):
            if name and name not in parent_of:
                parent_of[name] = parent or ''
    finally:
        conn.close()

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


def item_flow_source_dates(start_date, end_date, belong):
    """单品流量来源表在范围内实际有数据的日期（按 belong 过滤）。"""
    conn = get_connection()
    try:
        rows = conn.execute(
            '''SELECT DISTINCT stat_date FROM sycm_item_flow_source_daily
               WHERE stat_date BETWEEN ? AND ? AND belong = ? ORDER BY stat_date''',
            (start_date, end_date, belong)).fetchall()
    finally:
        conn.close()
    return [row[0] for row in rows]


def item_flow_channel_rollup(start_date, end_date, belong, item_id=''):
    """单品流量来源按渠道聚合（可选单品过滤），按层级与 uv 排序。"""
    conditions = ['stat_date BETWEEN ? AND ?', 'belong = ?']
    params = [start_date, end_date, belong]
    if item_id:
        conditions.append('CAST(item_id AS TEXT) = ?')
        params.append(item_id)
    conn = get_connection()
    try:
        rows = conn.execute(f'''
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
        ''', params).fetchall()
    finally:
        conn.close()
    channels = []
    for row in rows:
        uv = row['uv'] or 0
        buyers = row['pay_buyer_count'] or 0
        channels.append({
            'channel_name': row['channel_name'],
            'parent_channel': row['parent_channel'],
            'level': row['level'],
            'channel_type': row['channel_type'],
            'uv': uv,
            'pv': row['pv'],
            'pay_amount': round(row['pay_amount'] or 0, 2),
            'pay_buyer_count': buyers,
            # 按聚合后的买家/访客重算，避免 AVG(每日转化率) 带来的偏差
            'pay_rate': round(buyers / uv, 6) if uv else 0,
            'cart_buyer_count': row['cart_buyer_count'],
            'collect_item_count': row['collect_item_count'],
            'new_uv': row['new_uv'],
            'deal_buyer_count': row['deal_buyer_count'],
            'pay_item_count': row['pay_item_count'],
            'parent_derived': False,
            'synthetic': False,
        })
    return channels


def item_flow_product_totals(item_id, dates):
    """商品经营口径合计（daily_data），只统计流量表实际有数据的日期。"""
    if not dates:
        return None
    placeholders = ','.join('?' for _ in dates)
    conn = get_connection()
    try:
        row = conn.execute(f'''
            SELECT SUM(ipv), SUM(pv), SUM(payment_amount), SUM(buyers), COUNT(DISTINCT date)
            FROM daily_data
            WHERE CAST(product_id AS TEXT) = ? AND date IN ({placeholders})
        ''', [item_id] + dates).fetchone()
    finally:
        conn.close()
    if not row or not row[4]:
        return None
    return {
        'visitors': row[0] or 0,
        'pv': row[1] or 0,
        'payment_amount': round(row[2] or 0, 2),
        'buyers': row[3] or 0,
        'days': row[4],
    }


def item_flow_top_items(stat_date, channel='', limit=20):
    """单品流量来源 TOP 商品（farthest 口径）。"""
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
    conn = get_connection()
    try:
        rows = conn.execute(query, params).fetchall()
    finally:
        conn.close()
    return [
        {'item_id': row[0], 'uv': row[1], 'pay_amount': row[2], 'pay_buyer_count': row[3]}
        for row in rows
    ]


# ==================== 竞店/竞品单日列表 ====================

def competitor_item_table():
    """Use the external market-item sample when it has the self/competitor flag."""
    conn = get_connection()
    try:
        exists = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='sycm_market_item_rank'").fetchone()
        columns = {row[1] for row in conn.execute('PRAGMA table_info(sycm_market_item_rank)').fetchall()} if exists else set()
        return 'sycm_market_item_rank' if exists and 'is_self' in columns else 'sycm_market_rival_item'
    finally:
        conn.close()


def rival_shop_day_list(stat_date):
    conn = get_connection()
    try:
        rows = conn.execute(
            '''SELECT shop_id, user_id, shop_name, shop_url, is_tmall,
                      uv, pay_buyer_count, cart_buyer_count, pay_rate, collect_buyer_count
               FROM sycm_market_rival_shop
               WHERE stat_date = ?
               ORDER BY uv DESC''',
            (stat_date,)).fetchall()
    finally:
        conn.close()
    return [
        {
            'shop_id': row[0], 'user_id': row[1], 'shop_name': row[2], 'shop_url': row[3],
            'is_tmall': bool(row[4]), 'uv': row[5], 'pay_buyer_count': row[6],
            'cart_buyer_count': row[7], 'pay_rate': row[8], 'collect_buyer_count': row[9],
        }
        for row in rows
    ]


def rival_shop_day_summary(stat_date):
    """返回（汇总行, TOP10 竞店列表）。"""
    conn = get_connection()
    try:
        summary = conn.execute(
            '''SELECT COUNT(*), AVG(uv), AVG(pay_buyer_count), AVG(pay_rate),
                      SUM(CASE WHEN is_tmall = 1 THEN 1 ELSE 0 END),
                      SUM(CASE WHEN is_tmall = 0 THEN 1 ELSE 0 END)
               FROM sycm_market_rival_shop
               WHERE stat_date = ?''',
            (stat_date,)).fetchone()
        top_shops = [
            {
                'shop_name': row[0], 'uv': row[1], 'pay_buyer_count': row[2],
                'pay_rate': row[3], 'is_tmall': bool(row[4]),
            }
            for row in conn.execute(
                '''SELECT shop_name, uv, pay_buyer_count, pay_rate, is_tmall
                   FROM sycm_market_rival_shop
                   WHERE stat_date = ?
                   ORDER BY uv DESC LIMIT 10''',
                (stat_date,)).fetchall()
        ]
    finally:
        conn.close()
    return summary, top_shops


def rival_items_day_list(source_table, stat_date):
    """竞品单日列表，返回（items, excluded_own_count）。"""
    conn = get_connection()
    try:
        if source_table == 'sycm_market_rival_item':
            rows = conn.execute(
                '''SELECT item_id, title, uv, pay_buyer_count, pic_url, detail_url, NULL AS shop_name
                   FROM sycm_market_rival_item r
                   WHERE stat_date = ?
                     AND NOT EXISTS (SELECT 1 FROM products p WHERE p.product_id = r.item_id)
                   ORDER BY uv DESC''',
                (stat_date,)).fetchall()
            excluded_own_count = int(conn.execute(
                '''SELECT COUNT(*)
                   FROM sycm_market_rival_item r
                   WHERE r.stat_date = ?
                     AND EXISTS (SELECT 1 FROM products p WHERE p.product_id = r.item_id)''',
                (stat_date,)).fetchone()[0] or 0)
        else:
            rows = conn.execute(
                '''SELECT item_id, MAX(title), MAX(uv), MAX(pay_buyer_count), MAX(pic_url), NULL, MAX(shop_name)
                   FROM sycm_market_item_rank
                   WHERE stat_date = ? AND is_self = 0
                     AND NOT EXISTS (SELECT 1 FROM products p WHERE p.product_id = sycm_market_item_rank.item_id)
                   GROUP BY item_id ORDER BY MAX(uv) DESC LIMIT 50''',
                (stat_date,)).fetchall()
            excluded_own_count = int(conn.execute(
                '''SELECT COUNT(DISTINCT item_id) FROM sycm_market_item_rank r WHERE stat_date = ?
                   AND (is_self = 1 OR EXISTS (SELECT 1 FROM products p WHERE p.product_id = r.item_id))''',
                (stat_date,)).fetchone()[0] or 0)
    finally:
        conn.close()
    is_item_rank = source_table == 'sycm_market_item_rank'
    items = [
        {
            'item_id': row[0], 'title': row[1], 'uv': row[2], 'pay_buyer_count': row[3],
            'pic_url': row[4],
            'detail_url': row[5] or f"https://item.taobao.com/item.htm?id={row[0]}" if is_item_rank else row[5],
            'shop_name': row[6],
        }
        for row in rows
    ]
    return items, excluded_own_count


# ==================== 市场排行 ====================

def market_external_filter(alias='r'):
    """市场实体趋势只使用外部商品榜样本，排除自家标记和商品主档。"""
    return f"{alias}.is_self = 0 AND NOT EXISTS (SELECT 1 FROM products p WHERE p.product_id = {alias}.item_id)"


def market_item_rank_rows(stat_date, cate_id='', cate_name='', limit=50):
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
    conn = get_connection()
    try:
        rows = conn.execute(query, params).fetchall()
    finally:
        conn.close()
    return [
        {
            'cate_id': row[0], 'cate_name': row[1], 'item_id': row[2], 'title': row[3],
            'pic_url': row[4], 'shop_name': row[5], 'shop_id': row[6], 'uv': row[7],
            'pay_buyer_count': row[8], 'core_keyword': row[9], 'rank': row[10],
            'is_self': bool(row[11]),
        }
        for row in rows
    ]


def market_search_rank_rows(stat_date, cate_id='', cate_name='', limit=50):
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
    conn = get_connection()
    try:
        rows = conn.execute(query, params).fetchall()
    finally:
        conn.close()
    return [
        {
            'cate_id': row[0], 'cate_name': row[1], 'keyword': row[2], 'search_heat': row[3],
            'pay_rate': row[4], 'free_click_rate': row[5], 'click_rate': row[6], 'rank': row[7],
        }
        for row in rows
    ]


def market_category_list(stat_date):
    conn = get_connection()
    try:
        rows = conn.execute(
            '''SELECT DISTINCT cate_id, cate_name,
                      COUNT(*) as item_count, AVG(uv) as avg_uv
               FROM sycm_market_item_rank
               WHERE stat_date = ?
               GROUP BY cate_id, cate_name
               ORDER BY avg_uv DESC''',
            (stat_date,)).fetchall()
    finally:
        conn.close()
    return [
        {'cate_id': row[0], 'cate_name': row[1], 'item_count': row[2], 'avg_uv': row[3]}
        for row in rows
    ]


def market_item_sample_daily(start_date, end_date):
    """外部商品榜样本的逐日聚合（去重后的 uv/买家均值）。"""
    conn = get_connection()
    try:
        return conn.execute(f'''
            SELECT stat_date, COUNT(*) AS item_count,
                   AVG(uv) AS avg_item_uv, AVG(pay_buyer_count) AS avg_item_buyers
            FROM (
              SELECT r.stat_date, r.item_id, MAX(r.uv) AS uv, MAX(r.pay_buyer_count) AS pay_buyer_count
              FROM sycm_market_item_rank r
              WHERE r.stat_date BETWEEN ? AND ? AND {market_external_filter('r')}
              GROUP BY r.stat_date, r.item_id
            ) sampled
            GROUP BY stat_date ORDER BY stat_date
        ''', (start_date, end_date)).fetchall()
    finally:
        conn.close()


def market_search_daily(start_date, end_date):
    """搜索榜逐日聚合。"""
    conn = get_connection()
    try:
        return conn.execute(
            '''SELECT stat_date, COUNT(*) AS keyword_count, AVG(search_heat) AS avg_search_heat,
                      AVG(pay_rate) AS avg_pay_rate, AVG(click_rate) AS avg_click_rate
               FROM sycm_market_search_rank WHERE stat_date BETWEEN ? AND ?
               GROUP BY stat_date ORDER BY stat_date''',
            (start_date, end_date)).fetchall()
    finally:
        conn.close()


def market_shop_entities(start_date, end_date):
    """市场商品榜覆盖到的店铺实体列表（含逐日序列与最新值）。"""
    conn = get_connection()
    try:
        rows = conn.execute(f'''
            SELECT COALESCE(NULLIF(r.shop_id, ''), r.shop_name) AS entity_id,
                   MAX(r.shop_name) AS entity_name,
                   COUNT(DISTINCT r.stat_date) AS observed_days,
                   MAX(r.stat_date) AS last_seen,
                   COUNT(DISTINCT r.item_id) AS item_count
            FROM sycm_market_item_rank r
            WHERE r.stat_date BETWEEN ? AND ? AND {market_external_filter('r')}
              AND COALESCE(NULLIF(r.shop_id, ''), r.shop_name) IS NOT NULL
            GROUP BY COALESCE(NULLIF(r.shop_id, ''), r.shop_name)
            ORDER BY observed_days DESC, item_count DESC, last_seen DESC, entity_name
        ''', (start_date, end_date)).fetchall()
        daily_rows = conn.execute(f'''
            SELECT entity_id, stat_date, SUM(uv) AS uv,
                   SUM(pay_buyer_count) AS pay_buyer_count,
                   COUNT(*) AS item_count
            FROM (
              SELECT COALESCE(NULLIF(r.shop_id, ''), r.shop_name) AS entity_id,
                     r.stat_date, r.item_id,
                     MAX(r.uv) AS uv, MAX(r.pay_buyer_count) AS pay_buyer_count
              FROM sycm_market_item_rank r
              WHERE r.stat_date BETWEEN ? AND ? AND {market_external_filter('r')}
                AND COALESCE(NULLIF(r.shop_id, ''), r.shop_name) IS NOT NULL
              GROUP BY COALESCE(NULLIF(r.shop_id, ''), r.shop_name), r.stat_date, r.item_id
            ) deduped
            GROUP BY entity_id, stat_date
            ORDER BY stat_date
        ''', (start_date, end_date)).fetchall()
    finally:
        conn.close()
    daily_by_entity = {}
    for row in daily_rows:
        item = dict(row)
        uv = item.get('uv')
        buyers = item.get('pay_buyer_count')
        item['pay_rate'] = (buyers / uv) if uv else None
        daily_by_entity.setdefault(str(item['entity_id']), []).append(item)
    entities = []
    for row in rows:
        item = dict(row)
        item['daily'] = daily_by_entity.get(str(item['entity_id']), [])
        latest = item['daily'][-1] if item['daily'] else {}
        item['latest_uv'] = latest.get('uv')
        item['latest_pay_buyer_count'] = latest.get('pay_buyer_count')
        entities.append(item)
    return entities


def market_shop_entity_trend(start_date, end_date, entity_id):
    """单个市场店铺逐日趋势，返回（daily 行, TOP50 商品行）。"""
    conn = get_connection()
    try:
        market_item_columns = {
            column['name'] for column in conn.execute('PRAGMA table_info(sycm_market_item_rank)').fetchall()
        }
        detail_url_expr = 'r.detail_url' if 'detail_url' in market_item_columns else 'NULL'
        rows = conn.execute(f'''
            SELECT daily.stat_date, MAX(daily.shop_name) AS shop_name,
                   COUNT(*) AS item_count, SUM(daily.uv) AS uv,
                   SUM(daily.pay_buyer_count) AS pay_buyer_count,
                   CASE WHEN SUM(daily.uv) IS NULL OR SUM(daily.uv) = 0 THEN NULL
                        ELSE SUM(daily.pay_buyer_count) * 1.0 / SUM(daily.uv) END AS pay_rate
            FROM (
              SELECT r.stat_date, r.item_id, MAX(r.shop_name) AS shop_name,
                     MAX(r.uv) AS uv, MAX(r.pay_buyer_count) AS pay_buyer_count
              FROM sycm_market_item_rank r
              WHERE r.stat_date BETWEEN ? AND ?
                AND COALESCE(NULLIF(r.shop_id, ''), r.shop_name) = ?
                AND {market_external_filter('r')}
              GROUP BY r.stat_date, r.item_id
            ) daily
            GROUP BY daily.stat_date ORDER BY daily.stat_date
        ''', (start_date, end_date, entity_id)).fetchall()
        product_rows = conn.execute(f'''
            WITH ranked AS (
              SELECT r.item_id, r.title, r.pic_url, {detail_url_expr} AS detail_url, r.shop_name,
                     r.uv, r.pay_buyer_count, r.rank, r.stat_date,
                     ROW_NUMBER() OVER (
                       PARTITION BY r.item_id
                       ORDER BY r.stat_date DESC, r.rank ASC
                     ) AS row_num
              FROM sycm_market_item_rank r
              WHERE r.stat_date BETWEEN ? AND ?
                AND COALESCE(NULLIF(r.shop_id, ''), r.shop_name) = ?
                AND {market_external_filter('r')}
            )
            SELECT item_id, title, pic_url, detail_url, shop_name,
                   uv, pay_buyer_count, rank, stat_date
            FROM ranked WHERE row_num = 1
            ORDER BY uv DESC, pay_buyer_count DESC, title
            LIMIT 50
        ''', (start_date, end_date, entity_id)).fetchall()
    finally:
        conn.close()
    return rows, product_rows


def market_item_entities(start_date, end_date):
    """市场外部单品实体列表（含逐日序列、最新值与链接补全）。"""
    conn = get_connection()
    try:
        link_join = '''LEFT JOIN market_item_links l ON l.item_id = r.item_id'''
        rows = conn.execute(f'''
            SELECT r.item_id AS entity_id, MAX(r.title) AS entity_name,
                   MAX(r.shop_name) AS shop_name, MAX(r.shop_id) AS shop_id,
                   COALESCE(MAX(l.pic_url), MAX(r.pic_url)) AS pic_url,
                   MAX(l.detail_url) AS detail_url,
                   COUNT(DISTINCT r.stat_date) AS observed_days,
                   MAX(r.stat_date) AS last_seen,
                   MAX(r.uv) AS latest_uv, MAX(r.pay_buyer_count) AS latest_pay_buyer_count
            FROM sycm_market_item_rank r {link_join}
            WHERE r.stat_date BETWEEN ? AND ? AND {market_external_filter('r')}
            GROUP BY r.item_id
            ORDER BY observed_days DESC, latest_uv DESC, last_seen DESC, entity_name
        ''', (start_date, end_date)).fetchall()
        daily_rows = conn.execute(f'''
            SELECT r.item_id AS entity_id, r.stat_date, MAX(r.uv) AS uv,
                   MAX(r.pay_buyer_count) AS pay_buyer_count, MIN(r.rank) AS rank
            FROM sycm_market_item_rank r
            WHERE r.stat_date BETWEEN ? AND ? AND {market_external_filter('r')}
            GROUP BY r.item_id, r.stat_date ORDER BY r.stat_date
        ''', (start_date, end_date)).fetchall()
    finally:
        conn.close()
    daily_by_entity = {}
    for row in daily_rows:
        item = dict(row)
        uv = item.get('uv')
        buyers = item.get('pay_buyer_count')
        item['pay_rate'] = (buyers / uv) if uv else None
        daily_by_entity.setdefault(str(item['entity_id']), []).append(item)
    entities = []
    for row in rows:
        item = dict(row)
        item['daily'] = daily_by_entity.get(str(item['entity_id']), [])
        latest = item['daily'][-1] if item['daily'] else {}
        item['latest_uv'] = latest.get('uv')
        item['latest_pay_buyer_count'] = latest.get('pay_buyer_count')
        item['detail_url'] = item.get('detail_url') or f"https://item.taobao.com/item.htm?id={item['entity_id']}"
        entities.append(item)
    return entities


def market_item_entity_trend(start_date, end_date, entity_id):
    """单个市场外部单品逐日趋势行。"""
    conn = get_connection()
    try:
        return conn.execute(f'''
            SELECT r.stat_date, MAX(r.title) AS title, MAX(r.shop_name) AS shop_name,
                   MAX(r.shop_id) AS shop_id, MAX(r.cate_name) AS cate_name,
                   MAX(r.uv) AS uv, MAX(r.pay_buyer_count) AS pay_buyer_count,
                   MAX(r.rank) AS rank
            FROM sycm_market_item_rank r
            WHERE r.item_id = ? AND r.stat_date BETWEEN ? AND ?
              AND {market_external_filter('r')}
            GROUP BY r.stat_date ORDER BY r.stat_date
        ''', (entity_id, start_date, end_date)).fetchall()
    finally:
        conn.close()


# ==================== 周期榜单快照 ====================

def snapshot_batches():
    conn = get_connection()
    try:
        return [dict(row) for row in conn.execute(
            '''SELECT id, snapshot_type, source_filename, period_start, period_end,
                      row_count, created_at
               FROM market_snapshot_batches
               ORDER BY period_end DESC, period_start DESC, id DESC'''
        ).fetchall()]
    finally:
        conn.close()


def snapshot_batch_rows(table, entity, label_column, value, batch_id):
    """按批次读取榜单行；表/列名来自硬编码白名单，批次 id 参数化。"""
    conn = get_connection()
    try:
        return conn.execute(
            f'SELECT {entity} AS entity_id, MAX(COALESCE({label_column}, {entity})) AS entity_name, MAX({value}) AS metric FROM {table} WHERE batch_id=? GROUP BY {entity}',
            (batch_id,),
        ).fetchall()
    finally:
        conn.close()
