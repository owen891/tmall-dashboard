"""把万相台「引导访问潜客」单品日粒度数据回填到商品列表接口。

数据源
------
`promotion_lead_daily`（采集器 `scripts/fetch_wanxiangtai_lead.py`，万相台
`item_promotion` 报表，商品×日粒度）。原始平台字段：
`inshopUv` → `inshop_uv`（入店访客数）、`inshopPotentialUv` → `potential_uv`
（引导访问潜客数）、`inshopPotentialUvRate` → `potential_uv_rate`。

口径（照抄 `scripts/promo_review/build_data.py:735-739`，勿改）
--------------------------------------------------------------
1. **引导潜客占比 = potential_uv / inshop_uv**，即「引导访问潜客数 ÷ 入店访客数」。
   平台字段 `inshopPotentialUvRate` 与该式逐行一致（品类 714 行样本，0 例外）。
   区间聚合时比率必须用 **SUM(分子)/SUM(分母)** 重算，不能对日比率取平均。
2. **单品口径不可相加**：同一用户逛多个商品会被重复计数，所以 SUM 只代表
   「各单品之和」，必然大于店铺账户口径，不能当店铺整体看 —— 必须在
   `limitations` 里标注。
3. 商品列表字段映射：`guide_visitors` ← `inshop_uv`、`guide_potential` ←
   `potential_uv`、`guide_potential_ratio` ← 上式。`guide_visits`（引导访问）
   没有对应源（报表只给访客数，不给访问次数），保持 NULL。

窗口纪律
--------
该表是滚动窗口（当前 2026-10-04~2026-10-20），请求区间可能只被部分覆盖。
做法与 `build_data.py` 一致：取**交集**聚合，并显式披露实际覆盖的子区间与
天数；完全没有交集时不回填。绝不把部分窗口的结果冒充整段。
"""

from services.dmp_item_metrics import _prepare_connection

SOURCE_TABLE = 'promotion_lead_daily'

# 允许回填的字段（只填 NULL）。
FILLABLE_FIELDS = ('guide_visitors', 'guide_potential', 'guide_potential_ratio')

_DERIVED = 'guide_potential_ratio'


def _has_source_table(conn):
    try:
        return bool(conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (SOURCE_TABLE,),
        ).fetchone())
    except Exception:
        return False


def _day_span(start, end):
    from datetime import datetime
    try:
        a = datetime.strptime(str(start)[:10], '%Y-%m-%d').date()
        b = datetime.strptime(str(end)[:10], '%Y-%m-%d').date()
    except (TypeError, ValueError):
        return None
    return (b - a).days + 1


def resolve_window(conn, start, end):
    """求请求区间与表内实际覆盖区间的交集。

    返回 `{'start','end','covered_days','requested_days','full'}`，
    无交集返回 None。
    """
    if not _has_source_table(conn):
        return None
    _prepare_connection(conn)
    try:
        span = conn.execute(
            f'SELECT MIN(date) a, MAX(date) b FROM {SOURCE_TABLE}'
        ).fetchone()
    except Exception:
        return None
    if not span or not span['a'] or not span['b']:
        return None
    table_start = str(span['a'])[:10]
    table_end = str(span['b'])[:10]
    req_start = str(start)[:10]
    req_end = str(end)[:10]
    covered_start = max(req_start, table_start)
    covered_end = min(req_end, table_end)
    if covered_start > covered_end:
        return None
    covered_days = _day_span(covered_start, covered_end) or 0
    requested_days = _day_span(req_start, req_end) or 0
    return {
        'start': covered_start,
        'end': covered_end,
        'covered_days': covered_days,
        'requested_days': requested_days,
        'full': covered_start == req_start and covered_end == req_end,
        'table_start': table_start,
        'table_end': table_end,
    }


def fetch_lead_metrics(conn, product_ids, window):
    """按商品聚合潜客指标。返回 {product_id: {'guide_visitors','guide_potential','guide_potential_ratio'}}。

    只返回在窗口内**真实有行**的商品；没有推广的商品不出现，字段保持 NULL。
    """
    if not product_ids or not window:
        return {}
    placeholders = ','.join(['?'] * len(product_ids))
    sql = f'''
        SELECT product_id,
               SUM(COALESCE(inshop_uv, 0)) AS guide_visitors,
               SUM(COALESCE(potential_uv, 0)) AS guide_potential,
               COUNT(*) AS fact_rows
        FROM {SOURCE_TABLE}
        WHERE date BETWEEN ? AND ?
          AND product_id IN ({placeholders})
        GROUP BY product_id
    '''
    params = [window['start'], window['end']] + [str(p) for p in product_ids]
    try:
        records = conn.execute(sql, params).fetchall()
    except Exception:
        return {}

    metrics = {}
    for fact in records:
        record = dict(fact)
        product_id = str(record.get('product_id'))
        visitors = record.get('guide_visitors')
        potential = record.get('guide_potential')
        # 区间比率用 SUM(分子)/SUM(分母) 重算，不对日比率取平均。
        record[_DERIVED] = (
            float(potential) / float(visitors)
            if visitors and potential is not None else None
        )
        metrics[product_id] = record
    return metrics


def enrich_rows(conn, rows, start, end):
    """用潜客指标补齐 rows 里缺失的字段（原地修改并返回元信息）。"""
    if not rows or not start or not end:
        return {'applied': False, 'reason': 'no rows or window'}
    window = resolve_window(conn, start, end)
    if not window:
        return {'applied': False, 'reason': 'no overlapping window'}
    product_ids = [str(row.get('product_id')) for row in rows if row.get('product_id')]
    if not product_ids:
        return {'applied': False, 'reason': 'no product ids'}
    metrics = fetch_lead_metrics(conn, product_ids, window)
    if not metrics:
        return {'applied': False, 'reason': 'no lead facts'}

    filled = {}
    for row in rows:
        product_id = str(row.get('product_id') or '')
        record = metrics.get(product_id)
        if not record:
            continue
        count = 0
        for field in FILLABLE_FIELDS:
            if field not in row or field not in record:
                continue
            incoming = record[field]
            if incoming is None:
                continue
            # 只在行里本来就有这一列时才回填（导出可能只挑几列）。
            if row.get(field) is not None:
                continue
            row[field] = incoming
            count += 1
        if count:
            filled[product_id] = count

    return {
        'applied': bool(filled),
        'window': window,
        'filled': filled,
        'matched_items': len(metrics),
    }


def source_metadata(result):
    """接口层披露用。"""
    if not result or not result.get('applied'):
        return None
    window = result.get('window') or {}
    return {
        'source': SOURCE_TABLE,
        'grain': 'product_day',
        'fields': list(FILLABLE_FIELDS),
        'matched_items': result.get('matched_items') or 0,
        'covered_start': window.get('start'),
        'covered_end': window.get('end'),
        'covered_days': window.get('covered_days'),
        'requested_days': window.get('requested_days'),
        'full_window': bool(window.get('full')),
        'table_start': window.get('table_start'),
        'table_end': window.get('table_end'),
    }
