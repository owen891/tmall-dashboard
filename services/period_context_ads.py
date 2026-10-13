"""复盘素材聚合子模块（自 services/period_context.py 拆分，2026-10-10）。

只读、幂等，不写入任何业务表。缺失数据一律显式标记（None / 空列表），
绝不把缺失当零值。周/月复盘以 daily_data 为主口径。
"""

from __future__ import annotations

import calendar
import logging
from datetime import date, datetime, timedelta

from db import get_db
from services.category_mode_service import mode_to_label
from services import category_analysis_service as category_service
# 市场分级算法（8大归类 / 词根需求 / 蓝海机会 / 趋势节点 / 竞店爆品）已投产于市场排行页，
# 月复盘页此前未复用 → 这里直接引用同一实现，避免两套口径漂移。
from services import market_monitor_service as market_monitor
from services.period_parsing import (
    PERIOD_TYPES, resolve_period, resolve_compare, recent_periods,
    available_periods, _key_for, _period_label, _month_bounded_weeks,
)
from services.period_templates import TEMPLATES, WEEK_TEMPLATE, MONTH_TEMPLATE, DAY_TEMPLATE


_log = logging.getLogger(__name__)

from services.period_context_metrics import _daily_scope

# ---------------------------------------------------------------------------

def _rate_change(value, baseline):
    if value is None or baseline in (None, 0):
        return None
    return round((float(value) - float(baseline)) / abs(float(baseline)), 4)

def _channel_derived_metrics(spend, payment, direct, carts, new_buyers, clicks, buyers):
    """渠道聚合行的派生指标（与商品×渠道明细 derived() 同口径）。

    任一分子/分母缺失或为 0 一律返回 None，前端显示 '--'，不补 0。
    """
    def div(numerator, denominator):
        if numerator is None or denominator in (None, 0):
            return None
        return float(numerator) / float(denominator)

    return {
        'direct_roi': (round(div(direct, spend), 4) if div(direct, spend) is not None else None),
        'cart_rate': (round(div(carts, clicks), 6) if div(carts, clicks) is not None else None),
        'cart_cost': (round(div(spend, carts), 2) if div(spend, carts) is not None else None),
        'new_cost': (round(div(spend, new_buyers), 2) if div(spend, new_buyers) is not None else None),
        'new_buyer_share': (round(div(new_buyers, buyers), 6) if div(new_buyers, buyers) is not None else None),
    }

def _campaign_attribution(conn, period, category_label=None, limit=20, include_product_rows=False):
    """计划 → 商品归因。返回 None 表示相关表缺失。

    返回 {available, items, exact_share, first_fact_date, attribution_note,
          missing_inputs}；`include_product_rows=True` 时额外带 `product_rows`
    —— 它的 key 是 `(channel, product_id)` **元组**，不可 JSON 序列化，
    所以**默认不返回**，只有内部消费方（商品×渠道补全）才显式索取。
    - items：计划级列表（按花费降序，最多 limit 条），每条含
      campaign_id / name / channel / ad_spend / attributed_payment / roi /
      product_count / attribution('exact'|'shared') / product_id / product_title /
      image_url / partial
    - product_rows：{(channel, product_id): {ad_spend, attributed_payment, ...}}
      **只含 exact（1:1）计划**，供商品级渠道补全（尤其全站推广）使用。
    """
    try:
        for table in ('promotion_campaign_items', 'promotion_daily_facts'):
            if not conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
            ).fetchone():
                return None

        # ① 计划 → 商品映射（当前快照）
        mapping = {}
        for row in conn.execute(
            '''SELECT campaign_id, channel, product_id, product_name, campaign_name, image_url
               FROM promotion_campaign_items'''
        ).fetchall():
            entry = mapping.setdefault(row['campaign_id'], {
                'channel': row['channel'] or '',
                'name': row['campaign_name'] or '',
                'products': [],
                'titles': {},
                'images': {},
            })
            pid = row['product_id'] or ''
            if pid and pid not in entry['products']:
                entry['products'].append(pid)
            if row['campaign_name']:
                entry['name'] = row['campaign_name']
            if row['product_name']:
                entry['titles'].setdefault(pid, row['product_name'])
            if row['image_url']:
                entry['images'].setdefault(pid, row['image_url'])

        # ② 品类归属（用于品类模式过滤；exact 计划可精确过滤，shared 只能近似）
        category_products = None
        if category_label:
            category_products = {
                row['product_id'] for row in conn.execute(
                    '''SELECT product_id FROM products
                       WHERE shop_label = ? OR instr(',' || shop_label || ',', ',' || ? || ',') > 0''',
                    (category_label, category_label),
                ).fetchall()
            }

        # ③ 计划级事实（campaign 粒度）
        facts = conn.execute(
            '''SELECT campaign_id,
                      MAX(channel) AS channel,
                      MAX(NULLIF(campaign_name, '')) AS campaign_name,
                      SUM(ad_spend) AS ad_spend,
                      SUM(attributed_payment_amount) AS attributed_payment,
                      SUM(direct_payment_amount) AS direct_payment,
                      SUM(cart_adds) AS cart_adds,
                      SUM(new_buyers) AS new_buyers,
                      SUM(COALESCE(payment_buyers, 0)) AS payment_buyers,
                      SUM(clicks) AS clicks,
                      SUM(impressions) AS impressions,
                      COUNT(DISTINCT date) AS sample_days,
                      MIN(date) AS first_date,
                      MAX(date) AS last_date
               FROM promotion_daily_facts
               WHERE grain = 'campaign' AND date BETWEEN ? AND ?
               GROUP BY campaign_id''',
            (period['start'], period['end']),
        ).fetchall()
        if not facts:
            empty = {
                'available': False, 'items': [],
                'exact_share': None, 'first_fact_date': None,
                'attribution_note': CAMPAIGN_ATTRIBUTION_NOTE,
                'missing_inputs': ['promotion_daily_facts.campaign'],
            }
            if include_product_rows:
                empty['product_rows'] = {}
            return empty

        items = []
        product_rows = {}
        total_spend = 0.0
        exact_spend = 0.0
        first_fact_date = None
        for row in facts:
            cid = row['campaign_id']
            info = mapping.get(cid, {'channel': '', 'name': '', 'products': [], 'titles': {}, 'images': {}})
            channel = info['channel'] or row['channel'] or ''
            products = info['products']
            spend = float(row['ad_spend'] or 0)
            exact = len(products) == 1
            pid = products[0] if exact else None
            if category_products is not None:
                # exact：按唯一商品的品类精确判定；shared：只要计划下有本品类商品就保留，
                # 但花费含品类外商品，必须标 partial（见下面 item['partial']）。
                if not (set(products) & category_products):
                    continue
            # ⚠️ 分母必须与分子同口径：只累加**通过品类过滤**的计划，否则品类模式下
            # exact_share 会变成「品类内精确花费 ÷ 全店总花费」，比率无意义。
            total_spend += spend
            if exact:
                exact_spend += spend
            if first_fact_date is None or (row['first_date'] and row['first_date'] < first_fact_date):
                first_fact_date = row['first_date']
            item = {
                'campaign_id': cid,
                'name': info['name'] or row['campaign_name'] or cid,
                'channel': channel,
                'ad_spend': round(spend, 2),
                'attributed_payment': round(float(row['attributed_payment'] or 0), 2),
                'direct_payment': round(float(row['direct_payment'] or 0), 2),
                'cart_adds': int(row['cart_adds'] or 0),
                'new_buyers': int(row['new_buyers'] or 0),
                'payment_buyers': int(row['payment_buyers'] or 0),
                'clicks': row['clicks'],
                'impressions': row['impressions'],
                'sample_days': int(row['sample_days'] or 0),
                'roi': (float(row['attributed_payment'] or 0) / spend if spend else None),
                'product_count': len(products),
                'attribution': 'exact' if exact else 'shared',
                'product_id': pid,
                'product_title': (info['titles'].get(pid) or pid) if pid else None,
                'image_url': (info['images'].get(pid) or '') if pid else '',
                'partial': (category_products is not None and not exact),
            }
            items.append(item)
            if exact and pid:
                # 商品级渠道补全：只登记 1:1 计划（精确），多商品计划不摊。
                key = (channel, pid)
                bucket = product_rows.get(key)
                if bucket is None:
                    bucket = {'ad_spend': 0.0, 'attributed_payment': 0.0,
                              'direct_payment': 0.0, 'cart_adds': 0, 'new_buyers': 0,
                              'payment_buyers': 0, 'clicks': 0, 'impressions': 0}
                    product_rows[key] = bucket
                bucket['ad_spend'] += spend
                bucket['attributed_payment'] += float(row['attributed_payment'] or 0)
                bucket['direct_payment'] += float(row['direct_payment'] or 0)
                bucket['cart_adds'] += int(row['cart_adds'] or 0)
                bucket['new_buyers'] += int(row['new_buyers'] or 0)
                bucket['payment_buyers'] += int(row['payment_buyers'] or 0)
                bucket['clicks'] += int(row['clicks'] or 0)
                bucket['impressions'] += int(row['impressions'] or 0)

        items.sort(key=lambda item: float(item.get('ad_spend') or 0), reverse=True)
        exact_share = round(exact_spend / total_spend, 4) if total_spend else None
        result = {
            'available': bool(items),
            'items': items[:limit] if limit else items,
            'exact_share': exact_share,
            'first_fact_date': first_fact_date,
            'attribution_note': CAMPAIGN_ATTRIBUTION_NOTE,
            'missing_inputs': [],
        }
        if include_product_rows:
            result['product_rows'] = product_rows
        return result
    except Exception:
        return None

def _attribution_channel_rows(conn, start, end, category_label, covered):
    """计划→商品 1:1 精确归因行聚合成「渠道 → 合计」，供品类渠道视图补全站推广。

    promotion_creative_daily 不含全站推广场景，品类口径下全站的唯一商品级来源是
    计划归因的 exact 行（品类过滤在归因内完成）。`covered` 是已有渠道集合——
    只补 creative 覆盖不到的渠道，两边相加就是重复计数。
    """
    attribution = _campaign_attribution(
        conn, {'start': start, 'end': end}, category_label, include_product_rows=True,
    )
    merged = {}
    for (channel, _pid), bucket in ((attribution or {}).get('product_rows') or {}).items():
        if channel in covered:
            continue
        if not (bucket.get('ad_spend') or 0) and not (bucket.get('attributed_payment') or 0):
            continue
        agg = merged.setdefault(channel, {key: 0.0 for key in (
            'ad_spend', 'attributed_payment', 'direct_payment',
            'cart_adds', 'new_buyers', 'clicks', 'impressions', 'payment_buyers',
        )})
        for key in agg:
            agg[key] += float(bucket.get(key) or 0)
    return [
        {'channel': channel, 'sample_days': None, **agg}
        for channel, agg in merged.items()
    ]

def _ads_direct_totals(conn, start, end, category_label=None):
    """直接成交/花费合计（推广事实表 product+'全部' 行，内部自洽口径）。

    不拿 daily_data.ad_spend 当分母：两表覆盖天数有出入，混用会把缺口
    变成虚高/虚低的 ROI。这里分子分母同源，缺口只影响覆盖，不扭曲比值。
    """
    try:
        table_exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='promotion_daily_facts'"
        ).fetchone()
        if not table_exists:
            return None
        category_sql = ''
        category_params = []
        if category_label:
            category_sql = " AND (p.shop_label = ? OR instr(',' || p.shop_label || ',', ',' || ? || ',') > 0)"
            category_params = [category_label, category_label]
        row = conn.execute(
            f'''SELECT SUM(f.ad_spend) AS ad_spend,
                       SUM(f.direct_payment_amount) AS direct_payment,
                       COUNT(DISTINCT f.date) AS sample_days
                FROM promotion_daily_facts f
                LEFT JOIN products p ON p.product_id = f.product_id
                WHERE f.date BETWEEN ? AND ? AND f.grain = 'product' AND f.channel = '全部'
                  {category_sql}''',
            [start, end, *category_params],
        ).fetchone()
        if row and row['ad_spend']:
            return {
                'ad_spend': float(row['ad_spend']),
                'direct_payment': float(row['direct_payment'] or 0),
                'sample_days': int(row['sample_days'] or 0),
            }
    except Exception:
        return None
    return None

def _ads_channel_totals(conn, start, end, category_label=None):
    """三渠道（全站/关键词/人群）推广成交金额合计（XMind「广告-汇总」）。

    两条口径，量纲不同不能混：
    - **全店**（无品类过滤）：`promotion_daily_facts` 的 campaign 粒度行自带渠道名，
      覆盖 全站/关键词/人群（campaign 日粒度 2026-08-20 起，更早月份回退
      campaign_month 并标注来源）。
    - **按品类**：campaign 行不带商品映射、无法过滤；改从商品×渠道明细
      （`promotion_creative_daily`，带 product_id 可 JOIN products）聚合。它覆盖
      关键词/人群/其他，**缺 全站推广**（creative 表不含该场景）→ 再用计划→商品
      1:1 精确归因把全站补进来（只补 creative 没有的渠道，相加即重复计数）。
      多商品全站计划仍无商品级明细 → 仍标 partial，不计算成交占比。
    """
    try:
        table_exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='promotion_daily_facts'"
        ).fetchone()
        if not table_exists:
            return None

        rows = []
        source = 'campaign'
        partial = False
        if category_label:
            source = 'promotion_creative_daily'
            partial = True
            creative_exists = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='promotion_creative_daily'"
            ).fetchone()
            if creative_exists:
                rows = [dict(row) for row in conn.execute(
                    f'''SELECT f.channel AS channel,
                              SUM(f.ad_spend) AS ad_spend,
                              SUM(f.attributed_payment_amount) AS attributed_payment,
                              COUNT(DISTINCT f.date) AS sample_days,
                              {CHANNEL_SUM_COLUMNS}
                       FROM promotion_creative_daily f
                       LEFT JOIN products p ON p.product_id = f.product_id
                       WHERE f.date BETWEEN ? AND ?
                         AND (p.shop_label = ? OR instr(',' || p.shop_label || ',', ',' || ? || ',') > 0)
                       GROUP BY f.channel''',
                    [start, end, category_label, category_label],
                ).fetchall()]
            # 全站推广补全：品类过滤在归因内完成（exact=唯一商品品类精确判定）。
            rows.extend(_attribution_channel_rows(conn, start, end, category_label,
                                                  {row['channel'] for row in rows}))
        else:
            rows = [dict(row) for row in conn.execute(
                f'''SELECT f.channel AS channel,
                           SUM(f.ad_spend) AS ad_spend,
                           SUM(f.attributed_payment_amount) AS attributed_payment,
                           COUNT(DISTINCT f.date) AS sample_days,
                           {CHANNEL_SUM_COLUMNS}
                    FROM promotion_daily_facts f
                    WHERE f.date BETWEEN ? AND ? AND f.grain = 'campaign'
                    GROUP BY f.channel''',
                [start, end],
            ).fetchall()]
            if not rows:
                month = str(start)[:7]
                if str(end)[:7] != month:
                    return None
                rows = [dict(row) for row in conn.execute(
                    f'''SELECT f.channel, SUM(f.ad_spend) AS ad_spend,
                              SUM(f.attributed_payment_amount) AS attributed_payment,
                              COUNT(*) AS sample_days,
                              {CHANNEL_SUM_COLUMNS}
                       FROM promotion_daily_facts f
                       WHERE f.grain = 'campaign_month' AND substr(f.date, 1, 7) = ?
                       GROUP BY f.channel''',
                    (month,),
                ).fetchall()]
                source = 'campaign_month'
        if not rows:
            return {'groups': [], 'source': source, 'sample_days': 0,
                    'missing_inputs': ['promotion_category_scope' if category_label else 'promotion_channel_scope']}
        # 花费占比分母：全店 = campaign 渠道总和（覆盖完整）；按品类 = 该品类商品级
        # 花费合计（grain='product' channel='全部'，与货品榜同源）——渠道分子不含
        # 多商品全站计划，占比是下界，partial 文案里已说明。
        total_spend = sum(float(row.get('ad_spend') or 0) for row in rows)
        if category_label:
            row = conn.execute(
                '''SELECT SUM(f.ad_spend) FROM promotion_daily_facts f
                   LEFT JOIN products p ON p.product_id = f.product_id
                   WHERE f.date BETWEEN ? AND ? AND f.grain = 'product' AND f.channel = '全部'
                     AND (p.shop_label = ? OR instr(',' || p.shop_label || ',', ',' || ? || ',') > 0)''',
                [start, end, category_label, category_label],
            ).fetchone()
            if row and row[0]:
                total_spend = float(row[0])
        by_channel = {row['channel']: dict(row) for row in rows}
        groups = []
        total_payment = sum(float(row.get('attributed_payment') or 0) for row in rows)

        def col(key):
            return sum(float(by_channel[c].get(key) or 0) for c in channels if c in by_channel)

        for group_name, channels in PROMOTION_CHANNEL_GROUPS:
            spend = col('ad_spend')
            payment = sum(float(by_channel[c].get('attributed_payment') or 0) for c in channels if c in by_channel)
            if spend <= 0 and payment <= 0:
                continue
            groups.append({
                'name': group_name,
                'ad_spend': round(spend, 2),
                'attributed_payment': round(payment, 2),
                'direct_payment': round(col('direct_payment'), 2),
                'cart_adds': int(col('cart_adds')),
                'new_buyers': int(col('new_buyers')),
                'clicks': int(col('clicks')),
                'impressions': int(col('impressions')),
                'payment_buyers': int(col('payment_buyers')),
                'roi': (round(payment / spend, 4) if spend else None),
                'spend_share': (round(spend / total_spend, 6) if total_spend else None),
                # 按品类时只覆盖部分渠道（多商品全站计划无明细），成交占比分母不全
                # → 不给占比，避免误导。
                'payment_share': (None if partial
                                  else (round(payment / total_payment, 6) if total_payment else None)),
                **_channel_derived_metrics(spend, payment, col('direct_payment'), col('cart_adds'),
                                           col('new_buyers'), col('clicks'), col('payment_buyers')),
            })
        sample_days = max((int(row.get('sample_days') or 0) for row in rows), default=0)
        result = {'groups': groups, 'source': source, 'sample_days': sample_days}
        if partial:
            result['partial'] = True
            result['missing_inputs'] = ['promotion_channel_all_site_scope']
        return result
    except Exception:
        return None

def _ads_block(conn, current, prev, period, compare_range, category_label=None):
    def pick(source):
        source = source or {}
        return {
            'ad_spend': source.get('ad_spend'),
            'roi': source.get('roi'),
            'ad_ratio': source.get('ad_ratio'),
        }
    cur = pick(current)
    pre = pick(prev)
    delta = {}
    if cur['ad_spend'] is not None and pre['ad_spend']:
        delta['ad_spend_change'] = round((cur['ad_spend'] - pre['ad_spend']) / abs(pre['ad_spend']) * 100, 1)
    if cur['ad_ratio'] is not None and pre['ad_ratio'] is not None:
        delta['ad_ratio_delta_pt'] = round((cur['ad_ratio'] - pre['ad_ratio']) * 100, 2)
    if cur['roi'] is not None and pre['roi'] is not None:
        delta['roi_delta'] = round(cur['roi'] - pre['roi'], 2)
    # 汇总层直接 ROI（XMind「广告-汇总：增加直接 ROI 字段」）：
    # 直接成交 ÷ 推广花费，分子分母同源（见 _ads_direct_totals）。
    direct = _ads_direct_totals(conn, period['start'], period['end'], category_label)
    direct_roi = None
    if direct and direct['ad_spend']:
        direct_roi = direct['direct_payment'] / direct['ad_spend']
    direct_prev = None
    if compare_range and compare_range.get('available'):
        direct_prev = _ads_direct_totals(conn, compare_range['start'], compare_range['end'], category_label)
        if direct_prev and not direct_prev['ad_spend']:
            direct_prev = None
    prev_direct_roi = None
    if direct_prev and direct_prev['ad_spend']:
        prev_direct_roi = direct_prev['direct_payment'] / direct_prev['ad_spend']
    if direct_roi is not None and prev_direct_roi is not None:
        delta['direct_roi_delta'] = round(direct_roi - prev_direct_roi, 2)
    channel_totals = _ads_channel_totals(conn, period['start'], period['end'], category_label)
    return {
        'current': cur,
        'prev': pre,
        'delta': delta,
        'direct_roi': direct_roi,
        'prev_direct_roi': prev_direct_roi,
        'direct_sample_days': (direct or {}).get('sample_days'),
        'channel_totals': channel_totals,
    }

def _traffic_dimension(conn, period, compare, category_label=None):
    """Aggregate traffic-source facts without turning missing values into zero."""
    from_sql, where_sql, extra = _daily_scope(category_label)

    source_columns = (
        ('search', 'search'),
        ('recommend', 'recommend'),
        ('paid', 'paid'),
        ('organic', 'organic'),
    )

    def aggregate(span):
        row = conn.execute(
            f'''SELECT COUNT(DISTINCT d.date) AS sample_days,
                       SUM(d.ipv) AS visitors, SUM(d.buyers) AS buyers,
                       SUM(d.payment_amount) AS payment_amount,
                       SUM(d.search_ipv) AS search,
                       SUM(d.recommend_ipv) AS recommend,
                       SUM(d.paid_ipv) AS paid,
                       SUM(d.organic_ipv) AS organic
                {from_sql} WHERE {where_sql}''',
            (span['start'], span['end'], *extra),
        ).fetchone()
        return dict(row) if row else {}

    current = aggregate(period)
    baseline = aggregate(compare) if compare.get('available') else {}
    visitors = current.get('visitors')
    items = []
    for key, column in source_columns:
        value = current.get(column)
        previous = baseline.get(column)
        items.append({
            'key': key,
            'value': value,
            'previous_value': previous,
            'change_rate': _rate_change(value, previous),
            'share_of_visitors': (float(value) / float(visitors)
                                  if value is not None and visitors not in (None, 0) else None),
        })

    # 占比口径修正：share_of_visitors 的分子是单个来源访客、分母是全店访客
    # （SUM(ipv)），四个来源只是全店访客的一部分。BI 日快照不提供
    # recommend/paid/organic（source_resolution_service 对 business_advisor
    # 快照显式置 NULL），若只列四行、表头写「占比」，读者会误以为四行合计 100%。
    # 因此回传残差行「未归类来源」= 全店访客 − 已归类来源之和，让占比可校验到 100%；
    # 并回传缺失来源清单，供前端解释这几行为什么是空的。
    missing_keys = [item['key'] for item in items if item['value'] is None]
    unclassified = None
    if visitors not in (None, 0):
        known = sum(float(item['value']) for item in items if item['value'] is not None)
        residual = float(visitors) - known
        # 四来源齐备且与全店访客恒等时残差≈0，不渲染该行（避免造一个 0 行）。
        if residual > max(1.0, 0.005 * float(visitors)):
            unclassified = {
                'value': residual,
                'share_of_visitors': residual / float(visitors),
            }

    has_source_facts = any(item['value'] not in (None, 0) for item in items)
    return {
        'available': bool(current.get('sample_days')) and has_source_facts,
        'sample_days': int(current.get('sample_days') or 0),
        'compare_sample_days': int(baseline.get('sample_days') or 0),
        'period_days': period.get('total_days'),
        'items': items,
        'unclassified': unclassified,
        'missing_sources': missing_keys,
        'totals': {
            'visitors': current.get('visitors'),
            'buyers': current.get('buyers'),
            'payment_amount': current.get('payment_amount'),
        },
        'missing_inputs': [] if has_source_facts else ['daily_data.traffic_source'],
        'source': 'daily_data',
    }

def _dmp_traffic_dimension(conn, period, compare, category_label=None):
    """达摩盘单品快照的流量来源（商品级，可按品类过滤）。

    为什么用它：BI 日快照不提供 recommend/paid/organic（见 _traffic_dimension
    注释），复盘页那三行长期为空。达摩盘「货品洞察」的单品快照带商品级访客
    拆分，且 item_id 可 JOIN products 按品类过滤——正是标品口径所需。

    窗口匹配（关键，不能放松）：达摩盘快照是 period 天滚动窗口，end_date 为
    窗口末日。只有 period 等于复盘周期天数、且 end_date 落在复盘区间内时口径
    才对得上；否则返回 None 交 daily_data 兜底，绝不拿错窗口的数据冒充本期。

    行语义：达摩盘 freeIpv(自然) **包含** searchFreeIpv/recommendFreeIpv，
    paidIpv 与 freeIpv 互斥。四行若直接取 搜索/推荐/付费/自然 会重复计数，
    故第四行取「其他自然」= 自然 − 搜索 − 推荐，四行才是互斥分区、可合计 100%。
    """
    try:
        if not conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='dmp_shop_items'"
        ).fetchone():
            return None
        days = period.get('total_days')
        if not days:
            return None

        def snapshot(span):
            # 必须精确对齐窗口末日：达摩盘是「period 天滚动窗口、end_date 为末日」，
            # 只有 period == 复盘天数 且 end_date == 本期末日时，窗口才恰好等于本期。
            # 放宽到「区间内任意末日」会取到错位窗口（如 7 天窗口落在 10-03~10-09
            # 却当成 10-05~10-11），宁可返回 None 退回 daily_data。
            return conn.execute(
                '''SELECT end_date, period FROM dmp_shop_items
                   WHERE period = ? AND end_date = ?
                   LIMIT 1''',
                (days, span['end']),
            ).fetchone()

        def aggregate(span):
            snap = snapshot(span)
            if not snap:
                return None
            extra_sql, extra_params = '', []
            if category_label:
                extra_sql = (" AND (p.shop_label = ?"
                             " OR instr(',' || p.shop_label || ',', ',' || ? || ',') > 0)")
                extra_params = [category_label, category_label]
            row = conn.execute(
                f'''SELECT
                        SUM(json_extract(i.row_json, '$.ipv')) AS visitors,
                        SUM(json_extract(i.row_json, '$.searchFreeIpv')) AS search,
                        SUM(json_extract(i.row_json, '$.recommendFreeIpv')) AS recommend,
                        SUM(json_extract(i.row_json, '$.paidIpv')) AS paid,
                        SUM(json_extract(i.row_json, '$.freeIpv')) AS organic,
                        COUNT(*) AS item_count
                    FROM dmp_shop_items i
                    LEFT JOIN products p ON p.product_id = i.item_id
                    WHERE i.end_date = ? AND i.period = ?{extra_sql}''',
                [snap['end_date'], snap['period'], *extra_params],
            ).fetchone()
            if not row or not row['item_count']:
                return None
            result = dict(row)
            result['end_date'] = snap['end_date']
            return result

        current = aggregate(period)
        if not current:
            return None
        baseline = aggregate(compare) if compare.get('available') else None

        def other_organic(snapshot_row):
            """第四行「其他自然」= 总访客 − 搜索 − 推荐 − 付费。

            达摩盘自身 paidIpv+freeIpv 与 ipv 不严格恒等（实测差约 0.9%），
            若按「自然 − 搜索 − 推荐」取，四行会合计到 100.9%，读者一眼看出
            占比不平。改用总访客作锚点取残差，四行才是严格互斥分区、恒等 100%；
            语义上仍等于「其他自然」，只是把达摩盘自身的口径差并进这一行。
            """
            if not snapshot_row or snapshot_row.get('visitors') is None:
                return None
            return max(0.0, float(snapshot_row['visitors'])
                       - float(snapshot_row.get('search') or 0)
                       - float(snapshot_row.get('recommend') or 0)
                       - float(snapshot_row.get('paid') or 0))

        visitors = current.get('visitors')
        items = []
        for key, column in (('search', 'search'), ('recommend', 'recommend'), ('paid', 'paid')):
            value = current.get(column)
            previous = (baseline or {}).get(column)
            items.append({
                'key': key,
                'value': value,
                'previous_value': previous,
                'change_rate': _rate_change(value, previous),
                'share_of_visitors': (float(value) / float(visitors)
                                      if value is not None and visitors not in (None, 0) else None),
            })
        other = other_organic(current)
        other_prev = other_organic(baseline)
        items.append({
            'key': 'organic_other',
            'value': other,
            'previous_value': other_prev,
            'change_rate': _rate_change(other, other_prev),
            'share_of_visitors': (other / float(visitors)
                                  if other is not None and visitors not in (None, 0) else None),
        })

        return {
            'available': True,
            'sample_days': days,
            'compare_sample_days': days if baseline else 0,
            'period_days': days,
            'items': items,
            'unclassified': None,
            'missing_sources': [],
            'totals': {'visitors': visitors},
            'missing_inputs': [],
            'source': 'dmp_shop_items',
            'snapshot_end_date': current.get('end_date'),
            'item_count': int(current.get('item_count') or 0),
        }
    except Exception:
        return None


def _promotion_dimension(conn, period, compare, category_label=None):
    """Build separate channel and campaign views from their respective grains."""
    try:
        table_exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='promotion_daily_facts'"
        ).fetchone()
        if not table_exists:
            return {'available': False, 'grain': None, 'items': [], 'missing_inputs': ['promotion_daily_facts']}

        def aggregate(span, grain, dimension):
            # 按品类 + 渠道维度：promotion_daily_facts 的渠道行不带商品映射、无法过滤，
            # 改从商品×渠道明细（promotion_creative_daily）聚合，可 JOIN products 过滤。
            # 它只覆盖 关键词/人群/其他，缺 全站推广（creative 表不含该场景）
            # → 再用计划→商品 1:1 精确归因补（只补 creative 没有的渠道，相加即重复计数）。
            if category_label and dimension == 'channel':
                rows = []
                if conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='promotion_creative_daily'"
                ).fetchone():
                    rows = [dict(row) for row in conn.execute(
                        f'''SELECT f.channel AS dimension_key,
                                  COUNT(DISTINCT f.date) AS sample_days,
                                  SUM(f.ad_spend) AS ad_spend,
                                  SUM(f.attributed_payment_amount) AS attributed_payment,
                                  {CHANNEL_SUM_COLUMNS}
                           FROM promotion_creative_daily f
                           LEFT JOIN products p ON p.product_id = f.product_id
                           WHERE f.date BETWEEN ? AND ?
                             AND (p.shop_label = ? OR instr(',' || p.shop_label || ',', ',' || ? || ',') > 0)
                           GROUP BY dimension_key ORDER BY ad_spend DESC''',
                        [span['start'], span['end'], category_label, category_label],
                    ).fetchall()]
                covered = {row['dimension_key'] for row in rows}
                for extra in _attribution_channel_rows(conn, span['start'], span['end'],
                                                       category_label, covered):
                    rows.append({**extra, 'dimension_key': extra['channel']})
                return {row['dimension_key'] or 'unknown': dict(row) for row in rows}
            # 按品类 + 计划维度：campaign 粒度行不带商品映射，无法直接过滤。
            # 改走「计划→商品归因」（promotion_campaign_items × campaign 事实）：
            # 计划下有本品类商品即保留。1:1 计划是**精确**过滤；多商品计划的花费
            # 含品类外商品，标 partial（不拆、不摊）。
            # 这是既有缺口「品类模式下推广计划拆解为空」的正解。
            if category_label and dimension == 'campaign':
                attr = _campaign_attribution(conn, span, category_label, limit=None)
                if not attr or not attr.get('available'):
                    return {}
                out = {}
                for item in attr['items']:
                    key = item['name'] or item['campaign_id']
                    out[key] = {
                        'dimension_key': key,
                        'sample_days': item.get('sample_days'),
                        'ad_spend': item.get('ad_spend'),
                        'attributed_payment': item.get('attributed_payment'),
                        'direct_payment': item.get('direct_payment'),
                        'cart_adds': item.get('cart_adds'),
                        'new_buyers': item.get('new_buyers'),
                        'payment_buyers': item.get('payment_buyers'),
                        'impressions': item.get('impressions'),
                        'clicks': item.get('clicks'),
                        'partial': item.get('partial'),
                    }
                return out

            # 渠道维度（全店）：实测 promotion_daily_facts **没有 grain='channel' 行**
            # （只有 campaign / campaign_month / product / unit_month），渠道名挂在
            # campaign 粒度行上 —— 所以渠道视图查 campaign 粒度再按 channel 分组。
            # 这是既有 bug：原先查 grain='channel' 恒空，导致「推广渠道拆解」两种
            # 口径下都永远没数据。
            if dimension == 'channel':
                grain = 'campaign'
            params = [span['start'], span['end'], grain]
            category_sql = ''
            if category_label and grain == 'product':
                category_sql = " AND (p.shop_label = ? OR instr(',' || p.shop_label || ',', ',' || ? || ',') > 0)"
                params.extend([category_label, category_label])
            key_sql = 'f.channel' if dimension == 'channel' else "COALESCE(NULLIF(f.campaign_name, ''), f.campaign_id, 'unknown')"
            rows = conn.execute(
                f'''SELECT {key_sql} AS dimension_key,
                           COUNT(DISTINCT f.date) AS sample_days,
                           SUM(f.ad_spend) AS ad_spend,
                           SUM(f.attributed_payment_amount) AS attributed_payment,
                           {CHANNEL_SUM_COLUMNS}
                    FROM promotion_daily_facts f
                    LEFT JOIN products p ON p.product_id = f.product_id
                    WHERE f.date BETWEEN ? AND ? AND f.grain = ?{category_sql}
                    GROUP BY dimension_key ORDER BY ad_spend DESC''',
                params,
            ).fetchall()
            return {row['dimension_key'] or 'unknown': dict(row) for row in rows}

        def build_view(grain, dimension):
            # 渠道维度在品类模式下走商品×渠道明细（见 aggregate）；
            # 计划维度在品类模式下走「计划→商品归因」（见 aggregate）；
            # 其余非商品粒度在品类模式下仍不可用。
            creative_channel = bool(category_label) and dimension == 'channel'
            campaign_by_category = bool(category_label) and dimension == 'campaign'
            if category_label and grain != 'product' and not creative_channel and not campaign_by_category:
                return {'available': False, 'grain': grain, 'items': [],
                        'missing_inputs': ['promotion_category_scope']}
            current = aggregate(period, grain, dimension)
            baseline = aggregate(compare, grain, dimension) if compare.get('available') else {}
            # 花费占比分母（只给渠道维度）：品类口径 = 该品类商品级花费合计
            # （grain='product' channel='全部'，与货品榜同源）；全店口径 = 渠道总和
            # （campaign 粒度覆盖完整）。渠道分子缺多商品全站计划 → 占比是下界。
            scope_total = None
            if dimension == 'channel':
                if category_label:
                    total_row = conn.execute(
                        '''SELECT SUM(f.ad_spend) FROM promotion_daily_facts f
                           LEFT JOIN products p ON p.product_id = f.product_id
                           WHERE f.date BETWEEN ? AND ? AND f.grain = 'product' AND f.channel = '全部'
                             AND (p.shop_label = ? OR instr(',' || p.shop_label || ',', ',' || ? || ',') > 0)''',
                        [period['start'], period['end'], category_label, category_label],
                    ).fetchone()
                    scope_total = (float(total_row[0]) if total_row and total_row[0] else None)
                else:
                    scope_total = (sum(float(r.get('ad_spend') or 0) for r in current.values()) or None)
            items = []
            for name, row in current.items():
                old = baseline.get(name, {})
                spend, payment = row.get('ad_spend'), row.get('attributed_payment')
                old_spend, old_payment = old.get('ad_spend'), old.get('attributed_payment')
                items.append({
                    'name': name,
                    'sample_days': int(row.get('sample_days') or 0),
                    'ad_spend': spend,
                    'attributed_payment': payment,
                    'direct_payment': row.get('direct_payment'),
                    'cart_adds': row.get('cart_adds'),
                    'new_buyers': row.get('new_buyers'),
                    'payment_buyers': row.get('payment_buyers'),
                    'impressions': row.get('impressions'),
                    'clicks': row.get('clicks'),
                    'roi': (float(payment) / float(spend) if payment is not None and spend not in (None, 0) else None),
                    'spend_share': (round(float(spend) / scope_total, 6)
                                    if scope_total and spend is not None else None),
                    'ctr': (float(row['clicks']) / float(row['impressions'])
                            if row.get('clicks') is not None and row.get('impressions') not in (None, 0) else None),
                    'payment_rate': (float(row['payment_buyers']) / float(row['clicks'])
                                     if row.get('payment_buyers') is not None and row.get('clicks') not in (None, 0) else None),
                    'ad_spend_change_rate': _rate_change(spend, old_spend),
                    'payment_change_rate': _rate_change(payment, old_payment),
                    'previous_roi': (float(old_payment) / float(old_spend)
                                     if old_payment is not None and old_spend not in (None, 0) else None),
                    **_channel_derived_metrics(spend, payment, row.get('direct_payment'),
                                               row.get('cart_adds'), row.get('new_buyers'),
                                               row.get('clicks'), row.get('payment_buyers')),
                })
            items.sort(key=lambda item: float(item.get('ad_spend') or 0), reverse=True)
            if creative_channel:
                # 按品类口径只覆盖部分渠道（缺全站推广），标注清楚，别让读者以为这就是全部。
                return {'available': bool(items), 'grain': grain, 'items': items[:20],
                        'comparison_available': bool(baseline),
                        'partial': True,
                        'missing_inputs': [] if items else ['promotion_channel_all_site_scope']}
            if campaign_by_category:
                # 计划维度按品类：1:1 计划精确过滤；多商品计划花费含品类外商品 → partial。
                # 映射表是当前快照，只对 2026-08-20 之后成立（见 _campaign_attribution）。
                partial = any(row.get('partial') for row in current.values())
                return {'available': bool(items), 'grain': grain, 'items': items[:20],
                        'comparison_available': bool(baseline),
                        'partial': partial,
                        'attribution_note': CAMPAIGN_ATTRIBUTION_NOTE,
                        'missing_inputs': [] if items else ['promotion_campaign_items']}
            return {'available': bool(items), 'grain': grain, 'items': items[:20],
                    'comparison_available': bool(baseline),
                    'missing_inputs': [] if items else [f'promotion_daily_facts.{grain}']}

        channels = build_view('channel', 'channel')
        campaigns = build_view('campaign', 'campaign')
        return {'available': channels['available'] or campaigns['available'],
                'channels': channels, 'campaigns': campaigns,
                'source': 'promotion_daily_facts'}
    except Exception:
        # 整块推广维度消失会让复盘页静默少一大块素材；留痕以便定位是
        # 表缺失（预期）还是 SQL/数据异常（缺陷）。
        _log.warning('_promotion_dimension failed; returning unavailable block', exc_info=True)
        return {'available': False, 'grain': None, 'items': [], 'missing_inputs': ['promotion_daily_facts']}

def _product_trend(conn, product_id, weeks=8, category_label=None, grain='week'):
    """单商品近 N 个完整周期（周复盘=月内分周，月复盘=自然月）的趋势序列。

    grain='week'：月内分周口径（W1 从 1 号到第一个周日），聚合 daily_data；
    grain='month'：自然月口径，直接读 BI 月度快照 monthly_data（与生命周期分析
    同源）——日导入可能只有最近几个月，商品的完整历史在快照里。
    只统计已结束的周期，进行中的周/月不纳入；比率列与货品榜口径一致。
    返回 {available, grain, points}——points 即序列行。
    """
    try:
        today = date.today()
        rows = []
        if grain == 'month':
            # 月度复盘联动：直接读 BI 月度快照 monthly_data（与生命周期分析同源）。
            # 它的历史远长于日导入（日导入可能只有最近几个月），商品的季节性历史
            # 都在快照里；只取已结束的自然月（month < 当月），进行中月份不纳入。
            current_month = f'{today.year:04d}-{today.month:02d}'
            snapshot_rows = conn.execute(
                '''SELECT * FROM monthly_data
                   WHERE product_id = ? AND month < ?
                   ORDER BY month DESC LIMIT ?''',
                (product_id, current_month, weeks),
            ).fetchall()
            for snapshot in reversed(snapshot_rows):
                month_str = str(snapshot['month'])[:7]
                year, mon = int(month_str[:4]), int(month_str[5:7])
                start = date(year, mon, 1)
                end = date(year, 12, 31) if mon == 12 else date(year, mon + 1, 1) - timedelta(days=1)
                gsv = float(snapshot['payment_amount'] or 0)
                ad_spend = float(snapshot['ad_spend'] or 0)
                rows.append({
                    'label': month_str,
                    'start': start.isoformat(),
                    'end': end.isoformat(),
                    'gsv': round(gsv, 2),
                    'net_sales': round(float(snapshot['net_sales'] or 0), 2),
                    'visitors': round(float(snapshot['visitors'] or 0), 0),
                    'buyers': round(float(snapshot['buyers'] or 0), 0),
                    'conversion': (round(float(snapshot['payment_conversion']), 6) if snapshot['payment_conversion'] is not None else None),
                    'refund_rate': (round(float(snapshot['refund_rate']), 6) if snapshot['refund_rate'] is not None else None),
                    'payment_qty': round(float(snapshot['payment_qty'] or 0), 0),
                    'aov': (round(float(snapshot['avg_order_value']), 2) if snapshot['avg_order_value'] is not None else None),
                    'ad_spend': round(ad_spend, 2),
                    # 快照没有 ad_ratio 列，与榜单口径一致：花费 ÷ 销售额。
                    'ad_ratio': (round(ad_spend / gsv, 6) if gsv else None),
                    'operating_profit': (round(float(snapshot['operating_profit']), 2) if snapshot['operating_profit'] is not None else None),
                    'profit_rate': (round(float(snapshot['profit_rate']), 6) if snapshot['profit_rate'] is not None else None),
                })
        else:
            year, month = today.year, today.month
            # 从当月往前找 weeks 个周跨度：先算当月已有完整周数，不足再往前月补。
            spans = []
            while len(spans) < weeks:
                month_weeks = _month_bounded_weeks(year, month)
                # 当月只取已结束（end < 今天）的周
                usable = [
                    (num, start, end) for num, start, end in month_weeks
                    if end < today
                ]
                for num, start, end in reversed(usable):
                    spans.append((f'{start.isoformat()[:7]} 第{num}周', start, end))
                    if len(spans) >= weeks:
                        break
                month -= 1
                if month == 0:
                    year, month = year - 1, 12
            spans = list(reversed(spans[:weeks]))
            rows = []
            # 周序列带上货品榜全字段（XMind「点击字段指标看周折线」）：
            # 比率列由周总量重推，而不是均值，保证与榜单口径一致。
            for label, start, end in spans:
                row = conn.execute(
                '''SELECT COALESCE(SUM(d.payment_amount), 0) AS gsv,
                          COALESCE(SUM(d.ipv), 0) AS visitors,
                          COALESCE(SUM(d.buyers), 0) AS buyers,
                          COALESCE(SUM(d.net_sales), 0) AS net_sales,
                          COALESCE(SUM(d.refund_amount), 0) AS refund_amount,
                          COALESCE(SUM(d.payment_qty), 0) AS payment_qty,
                          COALESCE(SUM(d.ad_spend), 0) AS ad_spend,
                          COALESCE(SUM(d.operating_profit), 0) AS operating_profit
                   FROM daily_data d WHERE d.product_id = ? AND d.date BETWEEN ? AND ?''',
                (product_id, start.isoformat(), end.isoformat()),
            ).fetchone()
                if row is None:
                    continue
                gsv = float(row['gsv'] or 0)
                visitors = float(row['visitors'] or 0)
                buyers = float(row['buyers'] or 0)
                net_sales = float(row['net_sales'] or 0)
                ad_spend = float(row['ad_spend'] or 0)
                rows.append({
                    'label': label,
                    'start': start.isoformat(),
                    'end': end.isoformat(),
                    'gsv': round(gsv, 2),
                    'net_sales': round(net_sales, 2),
                    'visitors': round(visitors, 0),
                    'buyers': round(buyers, 0),
                    'conversion': round(buyers / visitors, 6) if visitors else None,
                    'refund_rate': (round(float(row['refund_amount'] or 0) / gsv, 6) if gsv else None),
                    'payment_qty': round(float(row['payment_qty'] or 0), 0),
                    'aov': round(gsv / buyers, 2) if buyers else None,
                    'ad_spend': round(ad_spend, 2),
                    'ad_ratio': round(ad_spend / gsv, 6) if gsv else None,
                    'operating_profit': round(float(row['operating_profit'] or 0), 2),
                    'profit_rate': (round(float(row['operating_profit'] or 0) / net_sales, 6) if net_sales else None),
                })
        return {'available': bool(rows), 'grain': grain, 'points': rows}
    except Exception:
        _log.warning('_product_trend failed; returning empty points', exc_info=True)
        return {'available': False, 'grain': grain, 'points': []}

def _product_meta(conn, product_ids):
    """读取榜单商品元数据，并用广告明细图片补齐商品主档缺图。"""
    if not product_ids:
        return {}
    ids = list(product_ids)
    placeholders = ','.join('?' for _ in ids)
    rows = conn.execute(
        f'SELECT product_id, title, image_url, product_tags, category FROM products '
        f'WHERE product_id IN ({placeholders})',
        ids,
    ).fetchall()
    meta = {row['product_id']: dict(row) for row in rows}
    missing_ids = [
        product_id for product_id in ids
        if not str(meta.get(product_id, {}).get('image_url') or '').strip()
    ]
    if not missing_ids:
        return meta

    missing_placeholders = ','.join('?' for _ in missing_ids)
    # 历史广告导入可能只把图片写入推广商品/创意明细，按最新记录兜底。
    fallback_queries = (
        "SELECT product_id, image_url, product_name AS title, updated_at"
        " FROM promotion_campaign_items"
        " WHERE product_id IN ({placeholders}) AND TRIM(COALESCE(image_url, '')) <> ''"
        " ORDER BY updated_at DESC",
        "SELECT product_id, image_url, product_name AS title, updated_at"
        " FROM promotion_creatives"
        " WHERE product_id IN ({placeholders}) AND TRIM(COALESCE(image_url, '')) <> ''"
        " ORDER BY updated_at DESC",
    )
    for query in fallback_queries:
        try:
            fallback_rows = conn.execute(query.format(placeholders=missing_placeholders), missing_ids).fetchall()
        except Exception:
            # 兼容未初始化推广明细表的旧数据库/测试库。
            continue
        for row in fallback_rows:
            product_id = row['product_id']
            item = meta.setdefault(product_id, {'product_id': product_id})
            if not str(item.get('image_url') or '').strip():
                item['image_url'] = row['image_url'] or ''
            if not item.get('title') and row['title']:
                item['title'] = row['title']

    return meta

PROMOTION_CHANNEL_GROUPS = (
    ('全站', ('全站推广', '货品全站推广')),
    ('关键词', ('关键词推广',)),
    ('人群', ('人群推广',)),
    ('其他', ('店铺直达', '超级短视频')),
)

CHANNEL_SUM_COLUMNS = (
    'SUM(COALESCE(f.direct_payment_amount, 0)) AS direct_payment, '
    'SUM(COALESCE(f.cart_adds, 0)) AS cart_adds, '
    'SUM(COALESCE(f.new_buyers, 0)) AS new_buyers, '
    'SUM(COALESCE(f.clicks, 0)) AS clicks, '
    'SUM(COALESCE(f.impressions, 0)) AS impressions, '
    'SUM(COALESCE(f.payment_buyers, 0)) AS payment_buyers'
)

CAMPAIGN_ATTRIBUTION_NOTE = (
    '计划→商品归因：仅对「计划只绑 1 个商品」的计划做商品级归因（精确，非均摊）；'
    '多商品计划只在计划级展示。映射表为当前快照，仅 2026-08-20 之后有效。'
)
