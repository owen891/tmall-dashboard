"""把达摩盘单品指标回填到商品列表接口。

设计要点
--------
1. **不改写 daily_data**：达摩盘快照是滚动窗口（7/30 天），把它写进日粒度事实表
   会污染单日口径，也会让 `trend_change` 之类的环比计算失真。所以这里只做
   查询期回填（query-time enrichment），原始事实表保持原样。
2. **只填 NULL**：BI/生意参谋主源已有的值优先。达摩盘只补 `daily_data` 里
   从未有非零值的那些列，避免两个源打架。
3. **必须披露窗口**：快照末日与请求末日可能错位几天，返回值里带
   `aligned_days` / `snapshot_end_date` / `period`，接口把它放进
   `source_batches` + `limitations`，前端和导出都能看到这批数字的真实窗口。
4. **天数对不上就放弃**：用 7 天快照冒充 30 天区间会让复购率、连带率全部失真，
   这种情况下宁可继续显示 `--`。
"""

from datetime import datetime

from services.dmp_item_metrics import resolve_dmp_snapshot

# 这些列 daily_data 里从来没采到过，允许达摩盘覆盖（含 NULL → 值）。
FILLABLE_FIELDS = (
    'search_click_rate',
    'category_width',
    'repurchase_rate',
    'repurchase_users',
    'cross_sell_qty',
    'cross_sell_rate',
    'industry_ctr',
    'presale_amount',
    'presale_qty',
)

# 这些列是比率：达摩盘给的已经是小数（0.0484 = 4.84%），不需要再除 100。
_RATIO_FIELDS = {'search_click_rate', 'repurchase_rate', 'cross_sell_rate', 'industry_ctr'}

# 流量来源拆分（paid_ipv / organic_ipv / recommend_ipv）**暂不接线**。
# 达摩盘 `row_json` 里有真实值（run5/p7：paidIpv 1257/1593、freeIpv 1581、
# recommendFreeIpv 1460），但实测口径与生意参谋差 2.26 倍：
#   单品 832824503023、2026-10-12~18：
#     生意参谋 daily_data  ipv 合计 9478（search_ipv 3101）
#     达摩盘 dmp_shop_items ipv 21440（paidIpv 733 + freeIpv 20661，
#                                  searchFreeIpv 8548、recommendFreeIpv 3589）
# 达摩盘内部自洽（733+20661=21394≈21440），但把它填在「商品访客数 9478」
# 旁边会渲染成「自然访客 20661 > 商品访客数 9478」这种自相矛盾的一屏。
# 要么整屏访客口径一起切到达摩盘，要么就不填——这是产品口径决策，
# 不是实现细节，所以这里保持 NULL，等口径确认后再接线。
TRAFFIC_FIELDS = ()


def _is_missing(value):
    return value is None


def enrich_rows(conn, rows, start, end):
    """用达摩盘快照补齐 rows 里缺失的字段（原地修改并返回元信息）。

    返回 dict：`{'applied': bool, 'snapshot': {...}, 'filled': {product_id: n}}`。
    没有可用快照时返回 `{'applied': False, 'reason': '...'}`。
    """
    if not rows:
        return {'applied': False, 'reason': 'no rows'}
    snapshot = resolve_dmp_snapshot(conn, start, end)
    if not snapshot:
        return {'applied': False, 'reason': 'no aligned snapshot'}

    product_ids = [str(row.get('product_id')) for row in rows if row.get('product_id')]
    if not product_ids:
        return {'applied': False, 'reason': 'no product ids'}

    placeholders = ','.join(['?'] * len(product_ids))
    try:
        facts = conn.execute(
            f"SELECT * FROM {snapshot['sql']} WHERE item_id IN ({placeholders})",
            product_ids,
        ).fetchall()
    except Exception:
        return {'applied': False, 'reason': 'snapshot query failed'}
    if not facts:
        return {'applied': False, 'reason': 'no matching items'}

    by_item = {}
    for fact in facts:
        record = dict(fact)
        item_id = str(record.pop('item_id'))
        by_item[item_id] = record

    # 流量来源拆分来自另一张表（dmp_shop_items.row_json），同一 run/period。
    # 目前 TRAFFIC_FIELDS 为空（口径未确认，见文件头），这段保留以便接线。
    traffic_sql = snapshot.get('traffic_sql')
    if traffic_sql and TRAFFIC_FIELDS:
        try:
            traffic_rows = conn.execute(
                f"SELECT * FROM {traffic_sql} WHERE item_id IN ({placeholders})",
                product_ids,
            ).fetchall()
        except Exception:
            traffic_rows = []
        for fact in traffic_rows:
            record = dict(fact)
            item_id = str(record.pop('item_id'))
            by_item.setdefault(item_id, {}).update(
                {k: v for k, v in record.items() if k in TRAFFIC_FIELDS}
            )

    filled = {}
    for row in rows:
        item_id = str(row.get('product_id') or '')
        record = by_item.get(item_id)
        if not record:
            continue
        count = 0
        for field in FILLABLE_FIELDS + TRAFFIC_FIELDS:
            if field not in record:
                continue
            incoming = record[field]
            if incoming is None:
                continue
            # 只在行里**本来就有这一列**时才回填：导出接口允许调用方只挑几列，
            # 凭空新增键会把表头和数据列数撑错位。
            if field not in row:
                continue
            if not _is_missing(row.get(field)):
                # 主源已有值，保持不动。
                continue
            row[field] = incoming
            count += 1
        # 付费占比 = 付费访客 / 总访客。分子分母必须同源：paid_ipv 目前不填
        # （达摩盘访客口径与生意参谋差 2.26 倍，见文件头），所以这里不会生效，
        # 保留结构以便口径统一后一次接通。
        if 'paid_ratio' in row and _is_missing(row.get('paid_ratio')):
            paid = row.get('paid_ipv')
            visitors = row.get('visitors')
            try:
                if paid is not None and visitors:
                    row['paid_ratio'] = float(paid) / float(visitors)
                    count += 1
            except (TypeError, ValueError):
                pass
        if count:
            filled[item_id] = count

    return {
        'applied': bool(filled),
        'snapshot': snapshot,
        'filled': filled,
        'matched_items': len(by_item),
    }


def snapshot_metadata(snapshot):
    """把快照信息整理成接口层可用的披露字段。"""
    if not snapshot:
        return None
    end = snapshot.get('end_date')
    gap = snapshot.get('aligned_days') or 0
    window_start = None
    try:
        end_date = datetime.strptime(str(end)[:10], '%Y-%m-%d').date()
        from datetime import timedelta
        window_start = (end_date - timedelta(days=int(snapshot['period']) - 1)).isoformat()
    except Exception:
        window_start = None
    return {
        'source': 'dmp_shop_item_indicators',
        'run_id': snapshot.get('run_id'),
        'period_days': snapshot.get('period'),
        'snapshot_end_date': end,
        'snapshot_start_date': window_start,
        'aligned_days': gap,
        'exact_window': bool(snapshot.get('exact')),
        'fields': list(FILLABLE_FIELDS) + list(TRAFFIC_FIELDS),
    }
