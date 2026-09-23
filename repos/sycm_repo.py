# -*- coding: utf-8 -*-
"""生意参谋（SYCM）市场与竞店竞品的共享数据访问。

从 api/sycm_api.py 下沉的四个跨路由复用查询：
- latest_date：各 sycm 表的最新统计日
- rival_trend / rival_entity_trend / rival_entities：竞店/竞品按表名
  参数化的通用查询（shop 表与 item 表共用一套口径，is_self=0
  且排除本店商品）。

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
