# -*- coding: utf-8 -*-
"""复盘素材聚合：业绩全景、目标路径、货品/市场/动作/告警等素材块。

设计约束：
- 只读、幂等，不写入任何业务表。
- 缺失数据一律显式标记（None / 空列表），绝不把缺失当零值。
- 周/月复盘都以 daily_data 为主口径。
"""

from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta

from db import get_db
from services.category_mode_service import mode_to_label
from services import category_analysis_service as category_service
from services.period_parsing import (
    PERIOD_TYPES, resolve_period, resolve_compare, recent_periods,
    available_periods, _key_for, _period_label, _month_bounded_weeks,
)
from services.period_templates import TEMPLATES, WEEK_TEMPLATE, MONTH_TEMPLATE, DAY_TEMPLATE

# ---------------------------------------------------------------------------


def _daily_scope(category_label):
    """返回 (from_sql, where_sql, extra_params)。

    品类过滤沿用全站口径：命中 products.shop_label，支持多标签值（如
    '标品袜子,平销商品'）按 token 匹配。category_label 为空表示不限品类。
    """
    if category_label:
        return (
            'FROM daily_data d JOIN products p ON p.product_id = d.product_id',
            "(d.date BETWEEN ? AND ?) AND (p.shop_label = ? OR instr(',' || p.shop_label || ',', ',' || ? || ',') > 0)",
            [category_label, category_label],
        )
    return 'FROM daily_data d', '(d.date BETWEEN ? AND ?)', []
# ---------------------------------------------------------------------------
# 指标聚合
# ---------------------------------------------------------------------------


def _empty_totals():
    return {
        'gsv': 0.0, 'refund_amount': 0.0, 'net_sales': 0.0, 'ad_spend': 0.0,
        'profit': 0.0, 'visitors': 0.0, 'buyers': 0.0, 'payment_qty': 0.0, 'pv': 0.0,
        'paid_ipv': 0.0,
        'product_count': 0, 'day_count': 0,
        'first_date': None, 'last_date': None,
        'cart_rate': None, 'fav_rate': None, 'bounce_rate': None,
    }


def _totals_for_range(conn, start, end, category_label=None):
    """周期指标聚合：daily_data 为主口径。

    对比期月份数据可能只有 monthly_data（BI 日度补采窗口外），此时按同品类
    过滤回退月表（方案原定不做，实测 2025-08/2026-07 同比环比全空后决定加）：
    - 仅当 daily 在该区间 day_count=0 时回退，daily 有值绝不覆盖；
    - 月表 operating_profit 在部分月份为 0（未回填），profit=0 视为缺失不采信；
    - 回退后 day_count 记 1，让上游有数据判断成立，比率类字段（转化率等）
      月表已有列直接取，不重算。
    """
    from_sql, where_sql, extra = _daily_scope(category_label)
    row = conn.execute(
        f'''
        SELECT
            COALESCE(SUM(d.payment_amount), 0) AS gsv,
            COALESCE(SUM(d.refund_amount), 0) AS refund_amount,
            COALESCE(SUM(d.net_sales), 0) AS net_sales,
            COALESCE(SUM(d.ad_spend), 0) AS ad_spend,
            COALESCE(SUM(d.operating_profit), 0) AS profit,
            COALESCE(SUM(d.ipv), 0) AS visitors,
            COALESCE(SUM(d.paid_ipv), 0) AS paid_ipv,
            COALESCE(SUM(d.buyers), 0) AS buyers,
            COALESCE(SUM(d.payment_qty), 0) AS payment_qty,
            COALESCE(SUM(d.pv), 0) AS pv,
            COUNT(DISTINCT d.product_id) AS product_count,
            COUNT(DISTINCT d.date) AS day_count,
            MIN(d.date) AS first_date,
            MAX(d.date) AS last_date,
            AVG(NULLIF(d.cart_rate, 0)) AS cart_rate,
            AVG(NULLIF(d.fav_rate, 0)) AS fav_rate,
            AVG(NULLIF(d.bounce_rate, 0)) AS bounce_rate
        {from_sql}
        WHERE {where_sql}
        ''',
        (start, end, *extra),
    ).fetchone()
    if row is None:
        return _empty_totals()
    totals = {key: row[key] for key in row.keys()}
    for key, value in totals.items():
        if value is None:
            totals[key] = None if key.endswith('_rate') or key.endswith('_date') else 0.0
    totals['gsv'] = float(totals.get('gsv') or 0.0)
    # 日粒度完全缺失时回退 monthly_data（仅对比期场景；见函数 docstring）。
    if not totals.get('day_count'):
        monthly = _monthly_fallback_totals(conn, start, end, category_label)
        if monthly:
            return monthly
    return totals


def _monthly_fallback_totals(conn, start, end, category_label=None):
    """对比期日数据缺失时的 monthly_data 回退；无可回退数据返回 None。

    品类过滤沿用 _daily_scope 的 shop_label 口径；比率列（转化率/加购率）取月表
    现成列。profit=0 是月表未回填的哨兵值，按缺失处理（None），不当作真 0。
    """
    month = start[:7]
    if not end.startswith(month):
        return None
    where_month = 'm.month = ?'
    params = [month]
    if category_label:
        where_month = ("m.month = ? AND (p.shop_label = ? OR instr(',' || p.shop_label || ',', ',' || ? || ',') > 0)")
        params = [month, category_label, category_label]
        from_month = 'FROM monthly_data m JOIN products p ON p.product_id = m.product_id'
    else:
        from_month = 'FROM monthly_data m'
    row = conn.execute(
        f'''SELECT COUNT(*) AS row_count,
                   COALESCE(SUM(m.payment_amount), 0) AS gsv,
                   COALESCE(SUM(m.refund_amount), 0) AS refund_amount,
                   COALESCE(SUM(m.net_sales), 0) AS net_sales,
                   COALESCE(SUM(m.ad_spend), 0) AS ad_spend,
                   SUM(m.operating_profit) AS profit,
                   COALESCE(SUM(m.visitors), 0) AS visitors,
                   0 AS paid_ipv,
                   COALESCE(SUM(m.buyers), 0) AS buyers,
                   COALESCE(SUM(m.payment_qty), 0) AS payment_qty,
                   0 AS pv,
                   COUNT(DISTINCT m.product_id) AS product_count,
                   COUNT(DISTINCT m.month) AS day_count,
                   MIN(m.month) || '-01' AS first_date,
                   MAX(m.month) || '-28' AS last_date,
                   AVG(NULLIF(m.payment_conversion, 0)) AS conversion,
                   AVG(NULLIF(m.cart_rate, 0)) AS cart_rate,
                   AVG(NULLIF(m.fav_rate, 0)) AS fav_rate,
                   AVG(NULLIF(m.bounce_rate, 0)) AS bounce_rate
            {from_month}
            WHERE {where_month}''',
        params,
    ).fetchone()
    if not row or not row['row_count'] or not row['day_count']:
        return None
    totals = {key: row[key] for key in row.keys()}
    totals.pop('row_count', None)
    for key, value in totals.items():
        if value is None:
            totals[key] = None if key.endswith('_rate') or key.endswith('_date') else 0.0
    # 月表 profit 未回填的月份整列 0，与「真 0 利润」无法区分，按缺失处理。
    if totals.get('profit') == 0:
        totals['profit'] = None
    totals['gsv'] = float(totals.get('gsv') or 0.0)
    totals['data_grain'] = 'monthly'
    return totals


def _derive(totals):
    """由总量推导比率类指标；分母为 0 时返回 None（不臆造 0）。

    这里只产出概览级比率。注意「费比」与「净费比」是两个口径，不要混：
    - 费比（ad_ratio）= 推广花费 ÷ GSV
    - 净费比（expense_ratio，见 category_analysis_service）= 推广花费 ÷ 净销售额
    """
    gsv = totals['gsv']
    net_sales = totals['net_sales']
    visitors = totals['visitors']
    buyers = totals['buyers']
    ad_spend = totals['ad_spend']
    paid_ipv = totals.get('paid_ipv') or 0.0
    return {
        'gsv': gsv,
        'net_sales': net_sales,
        'refund_amount': totals['refund_amount'],
        'ad_spend': ad_spend,
        'profit': totals['profit'],
        'visitors': visitors,
        'paid_ipv': paid_ipv,
        'buyers': buyers,
        'payment_qty': totals['payment_qty'],
        'product_count': totals['product_count'],
        'day_count': totals['day_count'],
        'conversion': (buyers / visitors) if visitors else None,
        'ad_ratio': (ad_spend / gsv) if gsv else None,
        'net_expense_ratio': (ad_spend / net_sales) if net_sales else None,
        'roi': (gsv / ad_spend) if ad_spend else None,
        'aov': (gsv / buyers) if buyers else None,
        'refund_ratio': (totals['refund_amount'] / gsv) if gsv else None,
        'cart_rate': totals.get('cart_rate'),
        'fav_rate': totals.get('fav_rate'),
        'bounce_rate': totals.get('bounce_rate'),
        # 单次付费访客成本 = 推广花费 ÷ 付费访客数（paid_ipv）。
        'paid_cpc': (ad_spend / paid_ipv) if paid_ipv else None,
    }


METRIC_DEFS = [
    ('gsv', 'GSV（支付金额）', 'money', False),
    ('net_sales', '净销售额', 'money', False),
    ('visitors', '访客数', 'number', False),
    ('conversion', '支付转化率', 'percent', False),
    ('buyers', '支付买家数', 'number', False),
    ('aov', '客单价', 'money', False),
    ('ad_spend', '推广花费', 'money', False),
    ('ad_ratio', '费比', 'percent', True),
    ('roi', '投产比', 'decimal', False),
    ('refund_amount', '退款金额', 'money', True),
    ('refund_ratio', '退款率', 'percent', True),
    ('cart_rate', '加购率', 'percent', False),
    ('paid_cpc', '单次付费访客成本', 'money', True),
]


def _metric_items(current, prev, yoy):
    items = []
    for key, label, fmt, lower_better in METRIC_DEFS:
        value = current.get(key)
        prev_value = prev.get(key)
        yoy_value = yoy.get(key)
        item = {
            'key': key, 'label': label, 'format': fmt, 'lower_better': lower_better,
            'value': value, 'prev_value': prev_value, 'yoy_value': yoy_value,
        }
        if value is not None and prev_value:
            item['mom_change'] = round((value - prev_value) / abs(prev_value) * 100, 1)
            item['mom_abs'] = round(value - prev_value, 4)
        if value is not None and yoy_value:
            item['yoy_change'] = round((value - yoy_value) / abs(yoy_value) * 100, 1)
            item['yoy_abs'] = round(value - yoy_value, 4)
        items.append(item)
    return items


# ---------------------------------------------------------------------------
# 单次付费访客成本（口径兜底）
# daily_data.paid_ipv 当前采集为空（实测整列 0），无法算「花费 ÷ 付费访客」；
# 退回万相台事实表口径：花费 ÷ 推广点击（付费访客 = 点击进店的付费流量）。
# 指标来源会标注在 metrics.paid_cpc_source，两套口径不静默混用。
# ---------------------------------------------------------------------------


def _promotion_paid_cpc(conn, start, end, category_label=None):
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
            f'''SELECT SUM(f.ad_spend) AS spend, SUM(f.clicks) AS clicks
                FROM promotion_daily_facts f
                LEFT JOIN products p ON p.product_id = f.product_id
                WHERE f.date BETWEEN ? AND ? AND f.grain = 'product' AND f.channel = '全部'
                  {category_sql}''',
            [start, end, *category_params],
        ).fetchone()
        if row and row['spend'] and row['clicks']:
            return float(row['spend']) / float(row['clicks'])
    except Exception:
        return None
    return None


# ---------------------------------------------------------------------------
# 周期内分解（月复盘 = 月内分周；周复盘 = 期内按日）
# 来自用户的月复盘框架：品类汇总的销售/利润指标要有「周维度」表格方便对比。
# ---------------------------------------------------------------------------

BREAKDOWN_METRIC_KEYS = (
    'gsv', 'net_sales', 'profit', 'visitors', 'conversion', 'aov',
    'cart_rate', 'ad_spend', 'ad_ratio', 'roi', 'paid_cpc',
)


def _breakdown_block(conn, period, category_label=None):
    """返回周期内更细粒度的指标行。

    月复盘拆成月内周（与 _month_bounded_weeks 同口径：W1 从 1 号到第一个周日），
    周复盘拆成逐日，日复盘只有一行。每行独立聚合并推导比率，
    缺天不补 0 行，只返回有数据的天/周。
    """
    if period['type'] == 'month':
        year, month = int(period['key'][:4]), int(period['key'][5:7])
        spans = [
            {'label': f'第{num}周（{start.isoformat()} ~ {end.isoformat()}）',
             'start': start.isoformat(), 'end': end.isoformat()}
            for num, start, end in _month_bounded_weeks(year, month)
        ]
        grain = 'week'
    elif period['type'] == 'week':
        start = date.fromisoformat(period['start'])
        end = date.fromisoformat(period['end'])
        spans = [
            {'label': f'{(start + timedelta(days=offset)).isoformat()}', 
             'start': (start + timedelta(days=offset)).isoformat(),
             'end': (start + timedelta(days=offset)).isoformat()}
            for offset in range((end - start).days + 1)
        ]
        grain = 'day'
    else:
        spans = [{'label': period['key'], 'start': period['start'], 'end': period['end']}]
        grain = 'day'

    rows = []
    for span in spans:
        totals = _totals_for_range(conn, span['start'], span['end'], category_label)
        if not totals['day_count']:
            continue
        derived = _derive(totals)
        if derived.get('paid_cpc') is None:
            derived['paid_cpc'] = _promotion_paid_cpc(conn, span['start'], span['end'], category_label)
        rows.append({
            'label': span['label'],
            'start': span['start'],
            'end': span['end'],
            'day_count': totals['day_count'],
            'metrics': {key: (round(derived[key], 4) if isinstance(derived.get(key), float) else derived.get(key))
                        for key in BREAKDOWN_METRIC_KEYS},
        })
    return {'grain': grain, 'rows': rows}


# ---------------------------------------------------------------------------
# 目标 / 达成路径
# ---------------------------------------------------------------------------


def _goal_target(conn, period_type, period_key, period):
    target = conn.execute(
        'SELECT SUM(target_amount) AS total FROM daily_goals WHERE goal_date BETWEEN ? AND ?',
        (period['start'], period['end']),
    ).fetchone()
    if target and target['total']:
        return float(target['total']), 'daily_goals'

    adjustment = conn.execute(
        '''SELECT target_amount FROM goal_adjustments
           WHERE period_type = ? AND period_key = ?
           ORDER BY created_at DESC, id DESC LIMIT 1''',
        (period_type, period_key),
    ).fetchone()
    if adjustment and adjustment['target_amount']:
        return float(adjustment['target_amount']), 'goal_adjustments'
    return None, 'none'


def _target_path(period, target, target_source, net_sales, category_label=None,
                 targets=None):
    """目标达成路径。

    口径与经营目标表一致：目标是「销售额（净销售额）」目标，达成率 = 净销售额 / 目标。
    早期版本用 GSV 作分子，会把含退款的支付金额算进达成率，导致达成率系统性偏高。

    targets 为可选的多指标目标（销售额/净利润额/推广费/推广费比），
    用于复盘页的「目标 vs 实际」四行表。
    """
    gap = None
    achieved_rate = None
    required_daily = None
    remaining_days = period['remaining_days']
    if target:
        achieved_rate = net_sales / target
        gap = target - net_sales
        if period['is_ongoing'] and remaining_days > 0:
            required_daily = gap / remaining_days if gap > 0 else 0.0
    # 经营目标表没有品类维度，目标始终是店铺级；按品类复盘时口径可能不一致，必须显式提示。
    store_level_target = target_source in ('daily_goals', 'goal_adjustments')
    return {
        'target': target,
        'source': target_source,
        'metric': 'net_sales',
        'metric_label': '销售额',
        'actual': net_sales,
        'scope': 'store',
        'scope_mismatch': bool(store_level_target and category_label),
        'gap': gap,
        'achieved_rate': achieved_rate,
        'remaining_days': remaining_days,
        'required_daily': required_daily,
        'is_ongoing': period['is_ongoing'],
        'targets': list(targets or []),
    }


# 复盘设置里可录目标的多项指标。顺序即前端展示顺序。
#
# 口径对齐用户「经营目标」Excel（已逐周核对）：
#   key / label / format
#   reverse_rate：达成率是否取倒数（True = 目标 ÷ 实际）
#   rate_better ：达成率高好还是低好，仅用于前端配色
#
# **推广费在用户表里是「实际 ÷ 目标」（预算使用率），不是倒数**：
#   9 月 W1 2.5/4.8=52.23%、W2 4.3/7.7=56%、W3 5.1/7.5=68%、合计 11.9/33.2=36%。
#   但「花得少」仍然是好事，所以配色单独用 rate_better='low' 表达，
#   不能靠 reverse_rate 兼顾——两件事必须分开。
# 净费比则确实是倒数：W1 23.70/23.01=103.01%、W2 23.70/21.55=110%、W3 23.70/26.04=91%。
TARGET_METRICS = (
    ('net_sales', '销售额', 'money', False, 'high'),
    ('profit', '净利润额', 'money', False, 'high'),
    ('ad_spend', '推广费', 'money', False, 'low'),
    ('net_expense_ratio', '净费比', 'percent', True, 'high'),
)

#: period_reviews 表字段 -> TARGET_METRICS 的 key
TARGET_FORM_FIELDS = {
    'target_amount': 'net_sales',
    'target_profit': 'profit',
    'target_ad_spend': 'ad_spend',
    'target_net_expense_ratio': 'net_expense_ratio',
}


def _target_rows(current, saved_review):
    """把复盘设置里录入的四项目标与本期实际配对，供复盘页目标表渲染。

    达成率：默认 = 实际 ÷ 目标；`reverse_rate` 的指标（净费比）= 目标 ÷ 实际。
    未录入目标的项 target 为 None，前端显示「未设置」而不是 0。
    """
    saved = saved_review or {}
    rows = []
    for key, label, fmt, reverse_rate, rate_better in TARGET_METRICS:
        field = next((f for f, k in TARGET_FORM_FIELDS.items() if k == key), None)
        raw = saved.get(field) if field else None
        target_value = None
        if raw not in (None, ''):
            try:
                target_value = float(raw)
            except (TypeError, ValueError):
                target_value = None
        actual = current.get(key)
        gap = None
        achieved_rate = None
        if target_value:
            gap = target_value - (actual or 0.0)
            if reverse_rate:
                achieved_rate = (target_value / actual) if actual else None
            else:
                achieved_rate = (actual or 0.0) / target_value
        rows.append({
            'key': key,
            'field': field,
            'label': label,
            'format': fmt,
            'reverse_rate': reverse_rate,
            'rate_better': rate_better,
            'target': target_value,
            'actual': actual,
            'gap': gap,
            'achieved_rate': achieved_rate,
        })
    return rows
# ---------------------------------------------------------------------------
# 货品
# ---------------------------------------------------------------------------


def _product_meta(conn, product_ids):
    if not product_ids:
        return {}
    placeholders = ','.join('?' for _ in product_ids)
    rows = conn.execute(
        f'SELECT product_id, title, image_url, product_tags, category FROM products '
        f'WHERE product_id IN ({placeholders})',
        list(product_ids),
    ).fetchall()
    return {row['product_id']: dict(row) for row in rows}


def _ads_block(current, prev):
    def pick(source):
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
    return {'current': cur, 'prev': pre, 'delta': delta}


def _rate_change(value, baseline):
    if value is None or baseline in (None, 0):
        return None
    return round((float(value) - float(baseline)) / abs(float(baseline)), 4)


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

    has_source_facts = any(item['value'] not in (None, 0) for item in items)
    return {
        'available': bool(current.get('sample_days')) and has_source_facts,
        'sample_days': int(current.get('sample_days') or 0),
        'compare_sample_days': int(baseline.get('sample_days') or 0),
        'period_days': period.get('total_days'),
        'items': items,
        'totals': {
            'visitors': current.get('visitors'),
            'buyers': current.get('buyers'),
            'payment_amount': current.get('payment_amount'),
        },
        'missing_inputs': [] if has_source_facts else ['daily_data.traffic_source'],
        'source': 'daily_data',
    }


def _promotion_dimension(conn, period, compare, category_label=None):
    """Build separate channel and campaign views from their respective grains."""
    try:
        table_exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='promotion_daily_facts'"
        ).fetchone()
        if not table_exists:
            return {'available': False, 'grain': None, 'items': [], 'missing_inputs': ['promotion_daily_facts']}

        def aggregate(span, grain, dimension):
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
                           SUM(f.impressions) AS impressions,
                           SUM(f.clicks) AS clicks,
                           SUM(f.payment_buyers) AS payment_buyers,
                           SUM(f.new_buyers) AS new_buyers
                    FROM promotion_daily_facts f
                    LEFT JOIN products p ON p.product_id = f.product_id
                    WHERE f.date BETWEEN ? AND ? AND f.grain = ?{category_sql}
                    GROUP BY dimension_key ORDER BY ad_spend DESC''',
                params,
            ).fetchall()
            return {row['dimension_key'] or 'unknown': dict(row) for row in rows}

        def build_view(grain, dimension):
            if category_label and grain != 'product':
                return {'available': False, 'grain': grain, 'items': [],
                        'missing_inputs': ['promotion_category_scope']}
            current = aggregate(period, grain, dimension)
            baseline = aggregate(compare, grain, dimension) if compare.get('available') else {}
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
                    'impressions': row.get('impressions'),
                    'clicks': row.get('clicks'),
                    'payment_buyers': row.get('payment_buyers'),
                    'new_buyers': row.get('new_buyers'),
                    'roi': (float(payment) / float(spend) if payment is not None and spend not in (None, 0) else None),
                    'ctr': (float(row['clicks']) / float(row['impressions'])
                            if row.get('clicks') is not None and row.get('impressions') not in (None, 0) else None),
                    'payment_rate': (float(row['payment_buyers']) / float(row['clicks'])
                                     if row.get('payment_buyers') is not None and row.get('clicks') not in (None, 0) else None),
                    'ad_spend_change_rate': _rate_change(spend, old_spend),
                    'payment_change_rate': _rate_change(payment, old_payment),
                    'previous_roi': (float(old_payment) / float(old_spend)
                                     if old_payment is not None and old_spend not in (None, 0) else None),
                })
            items.sort(key=lambda item: float(item.get('ad_spend') or 0), reverse=True)
            return {'available': bool(items), 'grain': grain, 'items': items[:20],
                    'comparison_available': bool(baseline),
                    'missing_inputs': [] if items else [f'promotion_daily_facts.{grain}']}

        channels = build_view('channel', 'channel')
        campaigns = build_view('campaign', 'campaign')
        return {'available': channels['available'] or campaigns['available'],
                'channels': channels, 'campaigns': campaigns,
                'source': 'promotion_daily_facts'}
    except Exception:
        return {'available': False, 'grain': None, 'items': [], 'missing_inputs': ['promotion_daily_facts']}


# ---------------------------------------------------------------------------
# 广告单品 TOP 消耗（对齐用户的月复盘框架「广告-单品-TOP20消耗商品」）
#
# 数据边界（已实测，勿改）：
# - 商品级指标来自 channel='全部' AND grain='product' 的行：这是唯一带
#   product_id 的完整商品级汇总（花费/归因成交/直接成交/加购/拉新/点击齐全）。
# - 具名渠道（关键词/人群/货品全站…）的行 product_id 全为空；campaign→商品
#   是一对多映射，join 会把花费重复计量，不能用来拆「商品×渠道」。
#   因此渠道分组列只在采集端写出带商品映射的渠道行（历史上全站推广/product
#   粒度存在过）时才有值，否则保持 None 并在 missing_inputs 里说明。
# ---------------------------------------------------------------------------

PROMOTION_CHANNEL_GROUPS = (
    ('全站', ('全站推广', '货品全站推广')),
    ('关键词', ('关键词推广',)),
    ('人群', ('人群推广',)),
    ('其他', ('店铺直达', '超级短视频')),
)


def _product_trend(conn, product_id, weeks=8, category_label=None):
    """单商品近 N 个完整月内周的趋势序列（GSV/访客/买家/净销售/转化）。

    用于货品榜「点击字段 → 周维度折线预览」。周期口径与复盘一致
    （_month_bounded_weeks：W1 从 1 号到第一个周日）；当前不完整周不纳入。
    """
    try:
        today = date.today()
        # 从当月往前找 weeks 个周跨度：先算当月已有完整周数，不足再往前月补。
        spans = []
        year, month = today.year, today.month
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
        for label, start, end in spans:
            row = conn.execute(
                '''SELECT COALESCE(SUM(d.payment_amount), 0) AS gsv,
                          COALESCE(SUM(d.ipv), 0) AS visitors,
                          COALESCE(SUM(d.buyers), 0) AS buyers,
                          COALESCE(SUM(d.net_sales), 0) AS net_sales
                   FROM daily_data d WHERE d.product_id = ? AND d.date BETWEEN ? AND ?''',
                (product_id, start.isoformat(), end.isoformat()),
            ).fetchone()
            if row is None:
                continue
            gsv = float(row['gsv'] or 0)
            visitors = float(row['visitors'] or 0)
            buyers = float(row['buyers'] or 0)
            rows.append({
                'label': label,
                'start': start.isoformat(),
                'end': end.isoformat(),
                'gsv': round(gsv, 2),
                'net_sales': round(float(row['net_sales'] or 0), 2),
                'visitors': round(visitors, 0),
                'buyers': round(buyers, 0),
                'conversion': round(buyers / visitors, 6) if visitors else None,
            })
        return {'available': bool(rows), 'weeks': rows}
    except Exception:
        return {'available': False, 'weeks': []}


def _promotion_items_block(conn, period, category_label=None, limit=20):
    try:
        table_exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='promotion_daily_facts'"
        ).fetchone()
        if not table_exists:
            return {'available': False, 'items': [], 'missing_inputs': ['promotion_daily_facts']}

        category_sql = ''
        category_params = []
        if category_label:
            category_sql = " AND (p.shop_label = ? OR instr(',' || p.shop_label || ',', ',' || ? || ',') > 0)"
            category_params = [category_label, category_label]

        def aggregate(start, end, channels):
            placeholders = ','.join('?' for _ in channels)
            rows = conn.execute(
                f'''SELECT f.product_id,
                           SUM(f.ad_spend) AS ad_spend,
                           SUM(f.attributed_payment_amount) AS attributed_payment,
                           SUM(f.direct_payment_amount) AS direct_payment,
                           SUM(f.cart_adds) AS cart_adds,
                           SUM(f.new_buyers) AS new_buyers,
                           SUM(f.clicks) AS clicks
                    FROM promotion_daily_facts f
                    LEFT JOIN products p ON p.product_id = f.product_id
                    WHERE f.date BETWEEN ? AND ? AND f.grain = 'product'
                      AND f.product_id IS NOT NULL AND f.product_id != ''
                      AND f.channel IN ({placeholders}){category_sql}
                    GROUP BY f.product_id''',
                [start, end, *channels, *category_params],
            ).fetchall()
            return {row['product_id']: dict(row) for row in rows}

        # 总计口径：channel='全部' 的商品级行。
        totals_map = aggregate(period['start'], period['end'], channels=['全部'])
        # 渠道口径：具名渠道且带商品映射的商品级行（当前采集大多没有）。
        channel_maps = {}
        for group_name, channels in PROMOTION_CHANNEL_GROUPS:
            channel_maps[group_name] = aggregate(period['start'], period['end'], channels=list(channels))

        def derived(row):
            spend = row.get('ad_spend')
            pay = row.get('attributed_payment')
            direct = row.get('direct_payment')
            carts = row.get('cart_adds')
            new_buyers = row.get('new_buyers')
            clicks = row.get('clicks')
            def div(numerator, denominator):
                if numerator is None or denominator is None or denominator == 0:
                    return None
                return float(numerator) / float(denominator)
            return {
                'ad_spend': float(spend) if spend is not None else None,
                'attributed_payment': float(pay) if pay is not None else None,
                'direct_payment': float(direct) if direct is not None else None,
                'cart_adds': carts, 'new_buyers': new_buyers, 'clicks': clicks,
                'roi': div(pay, spend),
                'direct_roi': div(direct, spend),
                'ad_ratio': div(spend, pay),       # 费比 = 花费 ÷ 归因成交
                'cart_cost': div(spend, carts),    # 加购成本
                'new_cost': div(spend, new_buyers),  # 拉新成本 = 花费 ÷ 成交新客
                'cart_rate': div(carts, clicks),   # 加购率 = 加购 ÷ 点击
            }

        top_ids = sorted(
            totals_map, key=lambda pid: float(totals_map[pid].get('ad_spend') or 0), reverse=True
        )[:limit]
        meta = _product_meta(conn, set(top_ids))
        items = []
        has_channel_data = False
        for pid in top_ids:
            info = meta.get(pid, {})
            channels_data = {}
            has_channel_data = False
            for group_name, _ in PROMOTION_CHANNEL_GROUPS:
                row = channel_maps[group_name].get(pid)
                if row is not None and (row.get('ad_spend') or 0) > 0:
                    channels_data[group_name] = derived(row)
                    has_channel_data = True
            items.append({
                'product_id': pid,
                'title': info.get('title') or pid,
                'image_url': info.get('image_url') or '',
                'totals': derived(totals_map[pid]),
                'channels': channels_data,
            })

        missing_inputs = []
        if not items:
            missing_inputs.append('promotion_daily_facts.product')
        elif not has_channel_data:
            missing_inputs.append('promotion_product_channel_scope')
        return {'available': bool(items), 'items': items,
                'channel_groups': [name for name, _ in PROMOTION_CHANNEL_GROUPS],
                'missing_inputs': missing_inputs}
    except Exception:
        return {'available': False, 'items': [], 'missing_inputs': ['promotion_daily_facts']}


# ---------------------------------------------------------------------------
# 动作 / 告警 / 异常
# ---------------------------------------------------------------------------


def _market_block(conn, period):
    start, end = period['start'], period['end']
    previous = period.get('prev') or {}

    def rate(current, baseline):
        if current is None or baseline in (None, 0):
            return None
        return round((float(current) - float(baseline)) / abs(float(baseline)), 4)

    # The legacy ranking import is optional.  The daily SYCM snapshots are the
    # primary source for period review because they carry an explicit date and
    # can be aligned with the selected review period.
    try:
        run = conn.execute(
            '''SELECT id, analysis_date, period_start, period_end, source
               FROM market_analysis_runs
               WHERE COALESCE(period_end, analysis_date) <= ?
               ORDER BY COALESCE(period_end, analysis_date) DESC, id DESC LIMIT 1''',
            (end,),
        ).fetchone()
    except Exception:
        run = None
    run = dict(run) if run else None
    try:
        previous_run = conn.execute(
            '''SELECT id, analysis_date, period_start, period_end, source
               FROM market_analysis_runs
               WHERE COALESCE(period_end, analysis_date) < ?
               ORDER BY COALESCE(period_end, analysis_date) DESC, id DESC LIMIT 1''',
            ((run.get('period_start') or run.get('analysis_date')) if run else '',),
        ).fetchone()
    except Exception:
        previous_run = None

    categories = []
    try:
        rows = conn.execute(
            '''SELECT category, trend_up, trend_down, trend_new, concentration_top10,
                      concentration_top50, total_buyers
               FROM market_category_stats WHERE run_id = ?
               ORDER BY total_buyers DESC LIMIT 8''',
            (run['id'],) if run else (None,),
        ).fetchall()
        old = {}
        if previous_run and run:
            old = {row['category']: dict(row) for row in conn.execute(
                'SELECT category, concentration_top10, total_buyers FROM market_category_stats WHERE run_id = ?',
                (previous_run['id'],),
            ).fetchall()}
        for row in rows:
            item = dict(row)
            base = old.get(item['category'], {})
            item['previous_total_buyers'] = base.get('total_buyers')
            item['buyers_change_rate'] = rate(item.get('total_buyers'), base.get('total_buyers'))
            item['previous_concentration_top10'] = base.get('concentration_top10')
            item['concentration_top10_delta'] = None if item.get('concentration_top10') is None or base.get('concentration_top10') is None else round(float(item['concentration_top10']) - float(base['concentration_top10']), 4)
            categories.append(item)
    except Exception:
        categories = []

    def snapshot_aggregate(table, key, fields):
        """Aggregate a dated source snapshot without treating missing rows as 0."""
        if table == 'sycm_market_item_rank':
            select_cols = (
                'COUNT(DISTINCT stat_date) AS sample_days, COUNT(*) AS row_count, '
                'AVG(uv) AS avg_uv, AVG(pay_buyer_count) AS avg_pay_buyer_count, '
                'SUM(CASE WHEN is_self = 1 THEN 1 ELSE 0 END) AS self_rows'
            )
        else:
            select_cols = (
                'COUNT(DISTINCT stat_date) AS sample_days, COUNT(*) AS row_count, '
                'AVG(search_heat) AS avg_search_heat, AVG(pay_rate) AS avg_pay_rate, '
                'AVG(click_rate) AS avg_click_rate'
            )
        rows = conn.execute(
            f'SELECT {key}, {select_cols} FROM {table} WHERE stat_date BETWEEN ? AND ? GROUP BY {key}',
            fields,
        ).fetchall()
        return {row[key]: dict(row) for row in rows if row[key] is not None}

    def classify_market(current, baseline):
        heat_change = rate(current.get('avg_search_heat'), baseline.get('avg_search_heat')) if baseline else None
        pay_change = rate(current.get('avg_pay_rate'), baseline.get('avg_pay_rate')) if baseline else None
        if heat_change is not None and heat_change >= 0.15:
            status = 'demand_up'
        elif heat_change is not None and heat_change <= -0.15:
            status = 'demand_down'
        elif pay_change is not None and pay_change >= 0.10:
            status = 'efficiency_up'
        elif pay_change is not None and pay_change <= -0.10:
            status = 'efficiency_down'
        else:
            status = 'stable'
        return status, heat_change, pay_change

    source_dates = {}
    market_signals = []
    keyword_signals = []
    try:
        current_categories = snapshot_aggregate('sycm_market_item_rank', 'cate_name', (start, end))
        previous_categories = snapshot_aggregate('sycm_market_item_rank', 'cate_name', (previous.get('start'), previous.get('end'))) if previous.get('start') and previous.get('end') else {}
        current_keywords = snapshot_aggregate('sycm_market_search_rank', 'keyword', (start, end))
        previous_keywords = snapshot_aggregate('sycm_market_search_rank', 'keyword', (previous.get('start'), previous.get('end'))) if previous.get('start') and previous.get('end') else {}
        for table in ('sycm_market_item_rank', 'sycm_market_search_rank'):
            try:
                row = conn.execute(f'SELECT MIN(stat_date) AS first_date, MAX(stat_date) AS last_date, COUNT(DISTINCT stat_date) AS sample_days FROM {table} WHERE stat_date BETWEEN ? AND ?', (start, end)).fetchone()
                source_dates[table] = dict(row) if row else {'first_date': None, 'last_date': None, 'sample_days': 0}
            except Exception:
                source_dates[table] = {'first_date': None, 'last_date': None, 'sample_days': 0}

        # Category-level facts: these are monitoring signals, not market GMV.
        for category, current in current_categories.items():
            baseline = previous_categories.get(category, {})
            market_signals.append({
                'category': category,
                'sample_days': current.get('sample_days', 0),
                'row_count': current.get('row_count', 0),
                'avg_uv': current.get('avg_uv'),
                'avg_pay_buyer_count': current.get('avg_pay_buyer_count'),
                'self_rows': current.get('self_rows', 0),
                'avg_uv_change_rate': rate(current.get('avg_uv'), baseline.get('avg_uv')) if baseline else None,
                'avg_pay_buyer_change_rate': rate(current.get('avg_pay_buyer_count'), baseline.get('avg_pay_buyer_count')) if baseline else None,
                'status': 'market_rank_observed',
            })
        # Keyword facts keep the strongest current terms and their observed
        # trend.  Search heat is a platform signal, not a sales amount.
        for keyword, current in sorted(current_keywords.items(), key=lambda pair: float(pair[1].get('avg_search_heat') or 0), reverse=True)[:20]:
            baseline = previous_keywords.get(keyword, {})
            status, heat_change, pay_change = classify_market(current, baseline)
            keyword_signals.append({
                'keyword': keyword,
                'sample_days': current.get('sample_days', 0),
                'avg_search_heat': current.get('avg_search_heat'),
                'avg_pay_rate': current.get('avg_pay_rate'),
                'avg_click_rate': current.get('avg_click_rate'),
                'search_heat_change_rate': heat_change,
                'pay_rate_change_rate': pay_change,
                'status': status,
            })
    except Exception:
        market_signals, keyword_signals = [], []

    def aggregate(table, key, fields, where_sql=''):
        if table == 'sycm_market_rival_shop':
            cols = ('COUNT(DISTINCT stat_date) AS sample_days, MAX(shop_name) AS shop_name, MAX(shop_url) AS shop_url, MAX(is_tmall) AS is_tmall,'
                    'SUM(uv) AS uv, SUM(pay_buyer_count) AS pay_buyer_count,'
                    'SUM(cart_buyer_count) AS cart_buyer_count, SUM(collect_buyer_count) AS collect_buyer_count')
        else:
            cols = ('COUNT(DISTINCT stat_date) AS sample_days, MAX(title) AS title, MAX(pic_url) AS pic_url, MAX(detail_url) AS detail_url,'
                    'SUM(uv) AS uv, SUM(pay_buyer_count) AS pay_buyer_count')
        rows = conn.execute(f'SELECT {key}, {cols} FROM {table} WHERE stat_date BETWEEN ? AND ? {where_sql} GROUP BY {key}', fields).fetchall()
        result = {}
        for row in rows:
            item = dict(row)
            sample_days = int(item.get('sample_days') or 0)
            item['avg_uv_per_day'] = round(float(item.get('uv') or 0) / sample_days, 2) if sample_days else None
            item['avg_pay_buyers_per_day'] = round(float(item.get('pay_buyer_count') or 0) / sample_days, 2) if sample_days else None
            item['pay_rate'] = None if item.get('uv') in (None, 0) else round(float(item.get('pay_buyer_count') or 0) / float(item['uv']), 6)
            result[item.get(key)] = item
        return result

    def comparable_coverage(current_item, baseline_item, current_period, baseline_period):
        """Require comparable observation coverage before assigning a trend label."""
        current_days = int(current_item.get('sample_days') or 0)
        baseline_days = int(baseline_item.get('sample_days') or 0)
        current_expected = max(1, (date.fromisoformat(current_period['end']) - date.fromisoformat(current_period['start'])).days + 1)
        baseline_expected = max(1, (date.fromisoformat(baseline_period['end']) - date.fromisoformat(baseline_period['start'])).days + 1)
        if current_days < current_expected * 0.8 or baseline_days < baseline_expected * 0.8:
            return False
        return abs((current_days / current_expected) - (baseline_days / baseline_expected)) <= 0.2

    missing, rivals, competitor_items = [], [], []
    try:
        current = aggregate('sycm_market_rival_shop', 'shop_id', (start, end))
        baseline = aggregate('sycm_market_rival_shop', 'shop_id', (previous.get('start'), previous.get('end'))) if previous else {}
        for key, item in sorted(current.items(), key=lambda pair: float(pair[1].get('avg_pay_buyers_per_day') or 0), reverse=True)[:10]:
            old = baseline.get(key, {})
            enough_coverage = bool(previous and old and comparable_coverage(item, old, {'start': start, 'end': end}, previous))
            uv_change = rate(item.get('avg_uv_per_day'), old.get('avg_uv_per_day')) if enough_coverage else None
            buyer_change = rate(item.get('avg_pay_buyers_per_day'), old.get('avg_pay_buyers_per_day')) if enough_coverage else None
            item.update(previous_uv=old.get('uv'), previous_pay_buyer_count=old.get('pay_buyer_count'), previous_avg_uv_per_day=old.get('avg_uv_per_day'), previous_avg_pay_buyers_per_day=old.get('avg_pay_buyers_per_day'), uv_change_rate=uv_change, pay_buyer_change_rate=buyer_change, pay_rate_delta=None if not enough_coverage or item.get('pay_rate') is None or old.get('pay_rate') is None else round(item['pay_rate'] - old['pay_rate'], 6), status=('rising' if buyer_change >= 0.2 else ('falling' if buyer_change <= -0.2 else 'stable')) if buyer_change is not None else 'insufficient_coverage', sample_days=item.get('sample_days', 0), trend_comparable=enough_coverage)
            # 按店日级趋势（XMind 竞店三件事中当前数据源可支撑的一项）：
            # 该店本期逐日 UV/支付买家，前端行展开渲染迷你趋势。
            try:
                daily_rows = conn.execute(
                    '''SELECT stat_date, uv, pay_buyer_count FROM sycm_market_rival_shop
                       WHERE shop_id = ? AND stat_date BETWEEN ? AND ? ORDER BY stat_date ASC''',
                    (key, start, end),
                ).fetchall()
                item['daily_trend'] = [
                    {'date': row['stat_date'], 'uv': row['uv'], 'buyers': row['pay_buyer_count']}
                    for row in daily_rows
                ]
            except Exception:
                item['daily_trend'] = []
            rivals.append(item)
    except Exception:
        missing.append('sycm_market_rival_shop')
    try:
        competitor_table = 'sycm_market_item_rank'
        competitor_filter = "AND is_self = 0 AND NOT EXISTS (SELECT 1 FROM products p WHERE p.product_id = sycm_market_item_rank.item_id)"
        current = aggregate(competitor_table, 'item_id', (start, end), where_sql=competitor_filter)
        baseline = aggregate(competitor_table, 'item_id', (previous.get('start'), previous.get('end')), where_sql=competitor_filter) if previous else {}
        for key, item in sorted(current.items(), key=lambda pair: float(pair[1].get('avg_pay_buyers_per_day') or 0), reverse=True)[:10]:
            old = baseline.get(key, {})
            enough_coverage = bool(previous and old and comparable_coverage(item, old, {'start': start, 'end': end}, previous))
            uv_change = rate(item.get('avg_uv_per_day'), old.get('avg_uv_per_day')) if enough_coverage else None
            buyer_change = rate(item.get('avg_pay_buyers_per_day'), old.get('avg_pay_buyers_per_day')) if enough_coverage else None
            item.update(previous_uv=old.get('uv'), previous_pay_buyer_count=old.get('pay_buyer_count'), previous_avg_uv_per_day=old.get('avg_uv_per_day'), previous_avg_pay_buyers_per_day=old.get('avg_pay_buyers_per_day'), uv_change_rate=uv_change, pay_buyer_change_rate=buyer_change, pay_rate_delta=None if not enough_coverage or item.get('pay_rate') is None or old.get('pay_rate') is None else round(item['pay_rate'] - old['pay_rate'], 6), status=('rising' if buyer_change >= 0.2 else ('falling' if buyer_change <= -0.2 else 'stable')) if buyer_change is not None else 'insufficient_coverage', sample_days=item.get('sample_days', 0), trend_comparable=enough_coverage)
            competitor_items.append(item)
    except Exception:
        missing.append('sycm_market_item_rank')
    # Use the same-period self rows when available to turn the competitor list
    # into an actionable gap list.  Missing self rows remain unknown instead of
    # being interpreted as zero performance.
    self_benchmark = {}
    try:
        self_rows = conn.execute(
            '''SELECT COUNT(DISTINCT stat_date) AS sample_days, SUM(uv) AS uv, SUM(pay_buyer_count) AS pay_buyer_count,
                      CASE WHEN SUM(uv) IS NULL OR SUM(uv) = 0 THEN NULL ELSE SUM(pay_buyer_count) / SUM(uv) END AS pay_rate
               FROM sycm_market_item_rank
               WHERE stat_date BETWEEN ? AND ? AND is_self = 1''',
            (start, end),
        ).fetchone()
        self_benchmark = dict(self_rows) if self_rows else {}
    except Exception:
        self_benchmark = {}

    period_days = max(1, (date.fromisoformat(end) - date.fromisoformat(start)).days + 1)
    for table, facts in source_dates.items():
        if facts.get('sample_days') and int(facts.get('sample_days') or 0) < period_days:
            missing.append(f'{table}_period_coverage')
    benchmark_days = int(self_benchmark.get('sample_days') or 0)
    benchmark_complete = benchmark_days >= period_days
    gap_threshold = 0.20
    # Enrich tracked competitor items with rank snapshots when the same item
    # is present in the market ranking source.  Missing matches stay unknown.
    try:
        rank_rows = conn.execute(
            '''SELECT item_id, MIN(rank) AS market_rank, MAX(title) AS market_title,
                      MAX(shop_name) AS market_shop
               FROM sycm_market_item_rank
               WHERE stat_date BETWEEN ? AND ? GROUP BY item_id''',
            (start, end),
        ).fetchall()
        rank_map = {row['item_id']: dict(row) for row in rank_rows}
        previous_rank_rows = conn.execute(
            '''SELECT item_id, MIN(rank) AS market_rank
               FROM sycm_market_item_rank
               WHERE stat_date BETWEEN ? AND ? GROUP BY item_id''',
            (previous.get('start'), previous.get('end')),
        ).fetchall() if previous.get('start') and previous.get('end') else []
        previous_rank_map = {row['item_id']: dict(row) for row in previous_rank_rows}
    except Exception:
        rank_map, previous_rank_map = {}, {}

    for item in competitor_items:
        rank_fact = rank_map.get(item.get('item_id')) or {}
        item['market_rank'] = rank_fact.get('market_rank')
        previous_rank = (previous_rank_map.get(item.get('item_id')) or {}).get('market_rank')
        item['previous_market_rank'] = previous_rank
        item['market_rank_change'] = None if item.get('market_rank') is None or previous_rank is None else previous_rank - item['market_rank']
        item['market_title'] = rank_fact.get('market_title')
        item['market_shop'] = rank_fact.get('market_shop')
        gaps = []
        if benchmark_complete:
            for metric, label in (('uv', 'UV'), ('pay_buyer_count', '支付买家'), ('pay_rate', '支付率')):
                own_value = self_benchmark.get(metric)
                rival_value = item.get(metric)
                if own_value in (None, 0) or rival_value is None:
                    continue
                # Positive gap means the rival is ahead of our benchmark.
                gap = (float(rival_value) - float(own_value)) / abs(float(own_value))
                if gap > gap_threshold:
                    gaps.append({'metric': metric, 'label': label, 'gap_rate': round(gap, 4)})
        item['comparison_basis'] = 'sycm_market_item_rank:is_self=1' if benchmark_complete else None
        item['benchmark_sample_days'] = benchmark_days
        item['benchmark_period_days'] = period_days
        item['gap_dimensions'] = gaps
        item['priority'] = 'P0' if any(gap['gap_rate'] >= 0.40 for gap in gaps) else ('P1' if gaps else 'P2' if item['comparison_basis'] else None)
    if competitor_items and not benchmark_complete:
        missing.append('sycm_market_item_rank_period_alignment')
    run_start = run.get('period_start') or run.get('analysis_date') if run else None
    run_end = run.get('period_end') or run.get('analysis_date') if run else None
    source_last_dates = [facts.get('last_date') for facts in source_dates.values() if facts.get('last_date')]
    source_first_dates = [facts.get('first_date') for facts in source_dates.values() if facts.get('first_date')]
    source_latest = max(source_last_dates) if source_last_dates else None
    source_earliest = min(source_first_dates) if source_first_dates else None
    if source_latest and source_earliest and source_latest >= start:
        run_alignment = 'aligned' if source_earliest <= start and source_latest >= end else 'partial'
    else:
        run_alignment = 'aligned' if run_start and run_end and run_start <= start and run_end >= end else ('stale' if run else 'source_facts')
    if run and not source_latest and run_alignment != 'aligned':
        missing.append('market_analysis_runs_period_alignment')
    if not categories:
        missing.append('market_category_stats')
    if not run and not (market_signals or keyword_signals or rivals or competitor_items):
        return {'available': False, 'run': None, 'categories': [], 'rivals': [], 'competitor_items': [], 'missing_inputs': ['market_source_facts']}

    decision_hints = []
    rising_keywords = [row for row in keyword_signals if row.get('status') == 'demand_up'][:3]
    rising_shops = [row for row in rivals if row.get('status') == 'rising'][:3]
    rising_items = [row for row in competitor_items if row.get('status') == 'rising'][:3]
    if rising_keywords:
        decision_hints.append({'kind': 'market', 'status': 'observe', 'title': '需求信号上升', 'detail': '、'.join(row['keyword'] for row in rising_keywords), 'confidence': '观察'})
    if rising_shops:
        decision_hints.append({'kind': 'shop', 'status': 'alert', 'title': '竞店增长预警', 'detail': '、'.join(row.get('shop_name') or '--' for row in rising_shops), 'confidence': '观察'})
    if rising_items:
        decision_hints.append({'kind': 'item', 'status': 'alert', 'title': '竞品上升预警', 'detail': '、'.join(row.get('title') or row.get('item_id') or '--' for row in rising_items), 'confidence': '观察'})

    if not market_signals:
        missing.append('sycm_market_item_rank')
    if not keyword_signals:
        missing.append('sycm_market_search_rank')
    missing.extend(['market_price', 'market_margin', 'market_reviews'])
    return {'available': True, 'run': run, 'run_alignment': run_alignment,
            'comparison_run': dict(previous_run) if previous_run else None,
            'period': {'start': start, 'end': end},
            'comparison_period': {'start': previous.get('start'), 'end': previous.get('end')} if previous else None,
            'categories': categories, 'rivals': rivals,
            'competitor_items': competitor_items,
            'market_signals': market_signals,
            'keyword_signals': keyword_signals,
            'source_dates': source_dates,
            'decision_hints': decision_hints,
            'missing_inputs': sorted(set(missing))}


def _actions_block(conn, period, category_label=None):
    start, end = period['start'], period['end']

    # 动作挂在商品上；选定品类时只保留该品类商品的动作。
    scope = ''
    scope_params = []
    if category_label:
        scope = (" AND (p.shop_label = ? OR instr(',' || p.shop_label || ',', ',' || ? || ',') > 0)")
        scope_params = [category_label, category_label]

    # 动作必须绑定当前复盘上下文：优先使用创建时记录的来源周期；
    # 兼容早期没有来源周期的动作时，退回到计划/执行日期范围，避免把未来动作带入本期复盘。
    period_scope = (
        " AND ((a.source_period_type = ? AND a.source_period_key = ?) "
        "OR (a.source_period_type IS NULL AND a.planned_at BETWEEN ? AND ?))"
    )
    period_params = [period['type'], period['key'], start, end]
    verification_scope = " AND a.verification_period_type = ? AND a.verification_period_key = ?"
    verification_params = [period['type'], period['key']]

    def rows(sql, params):
        try:
            return [dict(row) for row in conn.execute(sql, params).fetchall()]
        except Exception:
            return []

    base = ('SELECT a.id, a.product_id, p.title AS product_title, p.image_url AS product_image, '
            'a.action_type, a.action_detail, a.purpose_note, a.target_metric, a.expected_change, '
            'a.target_value, a.acceptance_criteria, a.status, a.version, a.planned_at, a.executed_at, '
            'a.observer_window_days, a.assigned_to, a.before_metric_value, a.after_metric_value, a.result_change, '
            'a.calculation_note, a.review_effective, a.review_reason, a.review_conclusion, a.review_next_action, '
            'a.blocked_reason, a.expected_recovery_at, a.source_period_type, a.source_period_key, '
            'a.source_compare_mode, a.source_compare_period_key, a.source_product_id, a.source_problem_key, '
            'a.source_diagnosis_snapshot, a.verification_period_type, a.verification_period_key '
            'FROM product_actions a JOIN products p ON p.product_id = a.product_id ')

    done = rows(
        base + "WHERE a.status = 'completed' AND COALESCE(a.executed_at, substr(a.updated_at,1,10)) BETWEEN ? AND ?"
               + scope +
               ' ORDER BY COALESCE(a.executed_at, substr(a.updated_at,1,10)) DESC LIMIT 30',
        [start, end, *scope_params],
    )
    planned = rows(
        base + "WHERE a.status IN ('draft','pending_execution','executing','observing')"
               + period_scope + scope +
       ' ORDER BY a.planned_at ASC LIMIT 30',
        [*period_params, *scope_params],
    )
    review = rows(
        base + "WHERE a.status = 'pending_review'"
               + " AND ((a.verification_period_type = ? AND a.verification_period_key = ?) "
               "OR (a.source_period_type = ? AND a.source_period_key = ?))" + scope +
               ' ORDER BY COALESCE(a.executed_at, a.planned_at) ASC LIMIT 30',
        [*verification_params, period['type'], period['key'], *scope_params],
    )
    verify = rows(
        base + "WHERE a.verification_period_type = ? AND a.verification_period_key = ? "
               "AND a.status IN ('observing', 'pending_review', 'completed')"
               + scope +
               ' ORDER BY COALESCE(a.executed_at, a.planned_at) ASC LIMIT 30',
        [period['type'], period['key'], *scope_params],
    )
    blocked = rows(
        base + "WHERE a.status = 'blocked'" + period_scope + scope + ' ORDER BY a.updated_at DESC LIMIT 30',
        [*period_params, *scope_params],
    )
    return {'done': done, 'planned': planned, 'review': review, 'verify': verify, 'blocked': blocked}


def _alerts_block(conn):
    try:
        rows = conn.execute(
            '''SELECT alert_date, alert_type, severity, title, detail, metric_name,
                      current_value, target_value, period
               FROM alerts WHERE COALESCE(dismissed, 0) = 0
               ORDER BY alert_date DESC, id DESC LIMIT 20''',
        ).fetchall()
        return [dict(row) for row in rows]
    except Exception:
        return []


def _anomalies_block(conn, period, current, prev, category_label=None):
    """由周期内日序列推导事实型异常，不做因果推断。"""
    from_sql, where_sql, extra = _daily_scope(category_label)
    rows = conn.execute(
        f'''SELECT d.date AS date, SUM(d.payment_amount) AS gsv, SUM(d.ad_spend) AS ad_spend,
                  SUM(d.buyers) AS buyers, SUM(d.ipv) AS visitors
           {from_sql} WHERE {where_sql}
           GROUP BY d.date ORDER BY d.date''',
        (period['start'], period['end'], *extra),
    ).fetchall()
    series = [dict(row) for row in rows if row['gsv'] is not None]
    items = []
    active = [row for row in series if (row['gsv'] or 0) > 0]
    if len(active) >= 2:
        best = max(active, key=lambda row: row['gsv'])
        worst = min(active, key=lambda row: row['gsv'])
        items.append({'level': 'info', 'label': '最高单日 GSV', 'detail': f"{best['date']} · {best['gsv']:.0f}"})
        items.append({'level': 'warning', 'label': '最低单日 GSV', 'detail': f"{worst['date']} · {worst['gsv']:.0f}"})

        avg_gsv = sum(row['gsv'] for row in active) / len(active)
        outliers = [row for row in active if row['gsv'] < avg_gsv * 0.5]
        if outliers:
            worst_outlier = min(outliers, key=lambda row: row['gsv'])
            items.append({
                'level': 'danger', 'label': '低于均值 50% 的异常日',
                'detail': f"{len(outliers)} 天，最低 {worst_outlier['date']} · {worst_outlier['gsv']:.0f}",
            })

    cur_ratio = current.get('refund_ratio')
    prev_ratio = prev.get('refund_ratio')
    if cur_ratio is not None and prev_ratio is not None and cur_ratio - prev_ratio > 0.01:
        items.append({
            'level': 'danger', 'label': '退款率上升',
            'detail': f'本期 {cur_ratio:.1%}，上期 {prev_ratio:.1%}（+{(cur_ratio - prev_ratio) * 100:.1f}pt）',
        })

    cur_ratio_ad = current.get('ad_ratio')
    prev_ratio_ad = prev.get('ad_ratio')
    if cur_ratio_ad is not None and prev_ratio_ad is not None and cur_ratio_ad - prev_ratio_ad > 0.03:
        items.append({
            'level': 'warning', 'label': '费比上升',
            'detail': f'本期 {cur_ratio_ad:.1%}，上期 {prev_ratio_ad:.1%}（+{(cur_ratio_ad - prev_ratio_ad) * 100:.1f}pt）',
        })

    return items

# 对外入口
# ---------------------------------------------------------------------------


def template_for(period_type):
    return TEMPLATES.get(period_type)


def build_context(period_type, period_key, saved_target=None, category_mode=None,
                  compare_mode=None, compare_period_key=None, today=None,
                  saved_review=None):
    """聚合某一周期的复盘素材。

    saved_target 为复盘里人工填写的销售额目标，优先级最高。
    saved_review 为该期已保存的整行复盘记录（含利润/推广费/净费比目标），
    用于渲染复盘设置里的多指标目标表；不传则只有销售额一项有目标。
    category_mode 决定品类口径（沿用全站 category_mode：sock=标品袜子，all=不限品类）。
    compare_mode / compare_period_key 决定对比基线（环比上一期 / 同比 / 自选周期 / 不对比）。
    """
    period = resolve_period(period_type, period_key, today=today)
    category_label = mode_to_label(category_mode)
    compare = resolve_compare(period, compare_mode, compare_period_key)
    with get_db() as conn:
        totals_cur = _totals_for_range(conn, period['start'], period['end'], category_label)
        totals_prev = (
            _totals_for_range(conn, compare['start'], compare['end'], category_label)
            if compare['available'] else _empty_totals()
        )
        totals_yoy = _totals_for_range(conn, period['yoy']['start'], period['yoy']['end'], category_label)

        current = _derive(totals_cur)
        prev = _derive(totals_prev) if totals_prev['day_count'] else {}
        yoy = _derive(totals_yoy) if totals_yoy['day_count'] else {}

        # 单次付费访客成本：daily_data.paid_ipv 为空时退回万相台点击口径。
        paid_cpc_source = 'daily_paid_ipv'
        if current.get('paid_cpc') is None:
            promo_cpc = _promotion_paid_cpc(conn, period['start'], period['end'], category_label)
            if promo_cpc is not None:
                current['paid_cpc'] = promo_cpc
                paid_cpc_source = 'promotion_clicks'
        if prev and prev.get('paid_cpc') is None and compare['available']:
            promo_cpc_prev = _promotion_paid_cpc(conn, compare['start'], compare['end'], category_label)
            if promo_cpc_prev is not None:
                prev['paid_cpc'] = promo_cpc_prev

        target, target_source = _goal_target(conn, period_type, period_key, period)
        if saved_target not in (None, ''):
            try:
                saved_target = float(saved_target)
            except (TypeError, ValueError):
                saved_target = None
            if saved_target and saved_target > 0:
                target, target_source = saved_target, 'review'

        products = _products_block(conn, period, category_label,
                                   {'start': compare['start'], 'end': compare['end']} if compare['available'] else None)
        market = _market_block(conn, {**period, 'prev': compare})
        traffic = _traffic_dimension(conn, period, compare, category_label)
        promotion = _promotion_dimension(conn, period, compare, category_label)
        promotion_items = _promotion_items_block(conn, period, category_label)
        breakdown = _breakdown_block(conn, period, category_label)
        actions = _actions_block(conn, period, category_label)
        alerts = _alerts_block(conn)
        anomalies = _anomalies_block(conn, period, current, prev, category_label)
        # 周月互汇（XMind：月复盘的周维度结论由本月各周复盘汇入）。
        # 月复盘读本月各周；周复盘读上月月复盘根因作参考——写月报从
        # 「从零分析」变成「检查各周结论找规律」。
        linked_summaries = _linked_period_summaries(conn, period)

    has_data = bool(totals_cur['day_count'])
    missing_inputs = [] if has_data else ['daily_data']
    expected_days = period['elapsed_days'] if period['is_ongoing'] else period['total_days']
    observed_days = int(totals_cur.get('day_count') or 0)
    coverage_status = 'no-data' if observed_days == 0 else ('complete' if observed_days >= expected_days else 'partial')
    coverage = {
        'status': coverage_status,
        'expected_days': expected_days,
        'observed_days': observed_days,
        'missing_days': max(expected_days - observed_days, 0),
        'observed_start': totals_cur.get('first_date'),
        'observed_end': totals_cur.get('last_date'),
    }
    # 对比周期自身没数据时，环比列不能当成 0 变化展示。
    compare = {**compare, 'has_data': bool(totals_prev['day_count'])}

    return {
        'period': period,
        'category': {
            'mode': category_mode or 'all',
            'label': category_label,
            'filtered': bool(category_label),
        },
        'compare': compare,
        'compare_options': recent_periods(period_type, period_key),
        'metrics': {
            'current': current,
            'prev': prev if prev else None,
            'yoy': yoy if yoy else None,
            'items': _metric_items(current, prev, yoy),
            'has_data': has_data,
            'coverage': coverage,
            'paid_cpc_source': paid_cpc_source,
        },
        # 达成率口径 = 净销售额 ÷ 目标（与经营目标表一致）。
        # 早期误用 GSV 作分子，会把含退款的支付金额算进达成率，系统性偏高约 20%。
        'target_path': _target_path(period, target, target_source, current['net_sales'], category_label,
                                    targets=_target_rows(current, saved_review)),
        'products': products,
        'ads': _ads_block(current, prev),
        'breakdown': breakdown,
        'promotion_items': promotion_items,
        'dimensions': {
            'traffic': traffic,
            'promotion': promotion,
        },
        'market': market,
        'actions_done': actions['done'],
        'actions_planned': actions['planned'],
        'actions_review': actions.get('review', []),
        'actions_to_verify': actions.get('verify', []),
        'actions_blocked': actions['blocked'],
        'linked_summaries': linked_summaries,
        'alerts': alerts,
        'anomalies': anomalies,
        'missing_inputs': missing_inputs,
    }
def legacy_fields_from_sections(period_type, sections):
    """把结构化段落映射回 period_reviews 的历史字段，保持旧接口/旧查询可用。"""
    sections = sections or {}
    template = template_for(period_type) or []
    ordered = [section['key'] for section in template]

    def text_of(key):
        entry = sections.get(key)
        if isinstance(entry, dict):
            return str(entry.get('text') or '').strip()
        return str(entry or '').strip()

    joined = []
    for key in ordered:
        value = text_of(key)
        if value:
            joined.append(value)

    # v2 模板周/月同构；别名链兼容 v1（周 performance/done/plan/highlights，
    # 月 campaign 等），保证旧复盘行映射出的三个 legacy 字段不丢内容。
    summary = (text_of('category_summary') or text_of('performance')
               or (joined[0] if joined else ''))
    conclusions = (text_of('summary') or text_of('highlights') or text_of('done')
                   or text_of('campaign') or (joined[1] if len(joined) > 1 else ''))
    next_actions = (text_of('next_plan') or text_of('plan') or (joined[-1] if joined else ''))

    fallback = '（未填写）'
    return {
        'summary': summary or fallback,
        'conclusions': conclusions or fallback,
        'next_actions': next_actions or fallback,
    }


# Keep the product diagnosis payload close to the period-review service contract.
# This definition intentionally lives after the legacy implementation so old
# callers keep their public shape while build_context() gets the richer data.
def _linked_period_summaries(conn, period):
    """周月互汇：跨周期读取已保存复盘的结论摘要。

    - 月复盘：读本月各周（period_key LIKE 'YYYY-MM-W%'）的周复盘，
      每期取 category_summary 的分析/根因子段 + 三大指标摘要；
    - 周复盘：读上月月复盘的根因，作为「对照月度根因」参考素材；
    - 只读，不写；未保存/缺子段时该期为空，不臆造内容。

    返回 {'kind': 'weekly'|'monthly', 'items': [...], 'missing_hint': str}。
    """
    def _section_text(sections, key):
        # SQL 直读的 sections 是 JSON 字符串（repo 层解析只在 get 单期时发生）。
        if isinstance(sections, str):
            try:
                import json as _json
                sections = _json.loads(sections) if sections.strip() else {}
            except Exception:
                sections = {}
        try:
            entry = (sections or {}).get(key) or {}
        except Exception:
            return None
        if isinstance(entry, dict):
            subs = entry.get('subsections')
            if isinstance(subs, dict) and any(str(v or '').strip() for v in subs.values()):
                return '\n'.join(
                    f"{k}: {str(v).strip()}" for k, v in subs.items() if str(v).strip()
                )
            text = str(entry.get('text') or '').strip()
            return text or None
        text = str(entry or '').strip()
        return text or None

    if period['type'] == 'month':
        prefix = f"{period['key']}-W"
        rows = conn.execute(
            '''SELECT period_key, status, reviewer, updated_at, sections
               FROM period_reviews
               WHERE period_type = 'week' AND period_key LIKE ?
               ORDER BY period_key ASC''',
            (f"{prefix}%",),
        ).fetchall()
        items = [{
            'period_key': row['period_key'],
            'status': row['status'],
            'reviewer': row['reviewer'],
            'updated_at': (row['updated_at'] or '')[:16],
            'analysis': _section_text(row['sections'], 'category_summary'),
        } for row in rows]
        return {
            'kind': 'weekly',
            'items': items,
            'missing_hint': '本月还没有已保存的周复盘；各周写完后这里会自动汇入结论。' if not items else '',
        }
    if period['type'] == 'week':
        # 周的所属月从 period.start 推（周键有 YYYY-MM-WN 与老式 YYYY-WNN 两种格式，
        # 不能靠切 key 推月份）。周可能跨月，取 start 所在月的上一个自然月。
        start_date = date.fromisoformat(period['start'])
        prev_month_date = date(start_date.year, start_date.month, 1) - timedelta(days=1)
        prev_month_key = prev_month_date.isoformat()[:7]
        row = conn.execute(
            '''SELECT period_key, status, reviewer, updated_at, sections
               FROM period_reviews
               WHERE period_type = 'month' AND period_key = ?
               ORDER BY updated_at DESC LIMIT 1''',
            (prev_month_key,),
        ).fetchone()
        items = []
        if row:
            items.append({
                'period_key': row['period_key'],
                'status': row['status'],
                'reviewer': row['reviewer'],
                'updated_at': (row['updated_at'] or '')[:16],
                'analysis': _section_text(row['sections'], 'category_summary'),
            })
        return {
            'kind': 'monthly',
            'items': items,
            'missing_hint': f'{prev_month_key} 还没有已保存的月复盘；定稿后周复盘会显示上月根因参考。' if not items else '',
        }
    return {'kind': 'none', 'items': [], 'missing_hint': ''}


def _products_block(conn, period, category_label=None, compare_range=None):
    from_sql, where_sql, extra = _daily_scope(category_label)
    baseline = compare_range or period.get('prev')

    def aggregate(start, end):
        rows = conn.execute(
            f'''SELECT d.product_id,
                       SUM(d.payment_amount) AS gsv,
                       SUM(d.net_sales) AS net_sales,
                       SUM(d.refund_amount) AS refund_amount,
                       SUM(d.buyers) AS buyers,
                       SUM(d.ipv) AS visitors,
                       SUM(d.ad_spend) AS ad_spend,
                       SUM(d.product_cost) AS product_cost,
                       SUM(d.operating_profit) AS operating_profit
                {from_sql}
                WHERE {where_sql}
                GROUP BY d.product_id''',
            (start, end, *extra),
        ).fetchall()
        return {row['product_id']: dict(row) for row in rows}

    current = aggregate(period['start'], period['end'])
    previous = aggregate(baseline['start'], baseline['end']) if baseline else {}
    total_gsv = sum(float(row.get('gsv') or 0) for row in current.values())

    def number(row, key):
        value = row.get(key) if row else None
        return None if value is None else float(value)

    def rounded(value, digits=2):
        return None if value is None else round(value, digits)

    def rate(numerator, denominator):
        if numerator is None or denominator is None or denominator == 0:
            return None
        return numerator / denominator

    def change_rate(current_value, previous_value):
        if current_value is None or previous_value in (None, 0):
            return None
        return (current_value - previous_value) / abs(previous_value)

    def decorate(product_id):
        cur = current.get(product_id)
        prev = previous.get(product_id)
        cur_row = cur or {}
        prev_row = prev or {}
        current_record_exists = cur is not None
        previous_record_exists = prev is not None
        gsv = number(cur_row, 'gsv')
        prev_gsv = number(prev_row, 'gsv')
        delta = (-prev_gsv if not current_record_exists and prev_gsv is not None
                 else None if gsv is None or prev_gsv is None else gsv - prev_gsv)
        current_net_sales = number(cur_row, 'net_sales')
        previous_net_sales = number(prev_row, 'net_sales')
        buyers = number(cur_row, 'buyers')
        prev_buyers = number(prev_row, 'buyers')
        visitors = number(cur_row, 'visitors')
        prev_visitors = number(prev_row, 'visitors')
        ad_spend = number(cur_row, 'ad_spend')
        prev_ad_spend = number(prev_row, 'ad_spend')
        product_cost = number(cur_row, 'product_cost')
        prev_product_cost = number(prev_row, 'product_cost')
        operating_profit = number(cur_row, 'operating_profit')
        prev_operating_profit = number(prev_row, 'operating_profit')
        gross_profit = (current_net_sales - product_cost
                        if current_net_sales is not None and product_cost is not None else None)
        prev_gross_profit = (previous_net_sales - prev_product_cost
                             if previous_net_sales is not None and prev_product_cost is not None else None)
        profit_rate = rate(operating_profit, current_net_sales)
        prev_profit_rate = rate(prev_operating_profit, previous_net_sales)
        refund_amount = number(cur_row, 'refund_amount')
        prev_refund_amount = number(prev_row, 'refund_amount')
        conversion = rate(buyers, visitors)
        prev_conversion = rate(prev_buyers, prev_visitors)
        aov = rate(gsv, buyers)
        prev_aov = rate(prev_gsv, prev_buyers)
        refund_rate = rate(refund_amount, gsv)
        prev_refund_rate = rate(prev_refund_amount, prev_gsv)

        anomaly_tags = []
        system_facts = []
        unknowns = []
        tag_flow = '\u6d41\u91cf\u4e0b\u964d'
        tag_conversion = '\u8f6c\u5316\u4e0b\u964d'
        tag_aov = '\u5ba2\u5355\u4ef7\u4e0b\u964d'
        tag_ad = '\u6295\u653e\u6548\u7387\u4e0b\u964d'
        tag_refund = '\u9000\u6b3e\u7387\u4e0a\u5347'
        if visitors is not None and prev_visitors not in (None, 0) and visitors < prev_visitors:
            anomaly_tags.append(tag_flow)
        if conversion is not None and prev_conversion is not None and conversion < prev_conversion:
            anomaly_tags.append(tag_conversion)
        if aov is not None and prev_aov not in (None, 0) and aov < prev_aov:
            anomaly_tags.append(tag_aov)
        current_roi = rate(gsv, ad_spend)
        previous_roi = rate(prev_gsv, prev_ad_spend)
        if current_roi is not None and previous_roi is not None and current_roi < previous_roi:
            anomaly_tags.append(tag_ad)
        if refund_rate is not None and prev_refund_rate is not None and refund_rate > prev_refund_rate:
            anomaly_tags.append(tag_refund)

        if gsv is not None:
            system_facts.append(f"GSV={gsv:.2f}")
        if delta is not None:
            system_facts.append(f"delta={delta:.2f}")
        if not current_record_exists:
            anomaly_tags.append('\u672c\u671f\u65e0\u8bb0\u5f55')
            unknowns.append('\u672c\u671f\u65e0\u5546\u54c1\u8bb0\u5f55\uff0c\u6309\u9500\u552e\u6d88\u5931\u5904\u7406')
        if visitors is None or prev_visitors is None:
            unknowns.append('\u8bbf\u5ba2\u5bf9\u6bd4\u6570\u636e\u4e0d\u5b8c\u6574')
        if buyers is None or prev_buyers is None:
            unknowns.append('\u652f\u4ed8\u4e70\u5bb6\u5bf9\u6bd4\u6570\u636e\u4e0d\u5b8c\u6574')
        if ad_spend is None or prev_ad_spend is None:
            unknowns.append('\u6295\u653e\u6570\u636e\u4e0d\u5b8c\u6574')
        if refund_amount is None or prev_refund_amount is None:
            unknowns.append('\u9000\u6b3e\u6570\u636e\u4e0d\u5b8c\u6574')

        return {
            'product_id': product_id,
            'title': '',
            'image_url': '',
            'tags': '',
            'gsv': rounded(gsv),
            'current_record_exists': current_record_exists,
            'previous_record_exists': previous_record_exists,
            'current_data_status': 'no-record' if not current_record_exists else 'recorded',
            'net_sales': rounded(current_net_sales),
            'prev_gsv': rounded(prev_gsv),
            'delta': rounded(delta),
            'change_rate': rounded(-1.0 if not current_record_exists and prev_gsv not in (None, 0) else change_rate(gsv, prev_gsv), 6),
            'share_of_gsv': rounded(rate(gsv, total_gsv), 6),
            'buyers': rounded(buyers),
            'prev_buyers': rounded(prev_buyers),
            'visitors': rounded(visitors),
            'prev_visitors': rounded(prev_visitors),
            'conversion': rounded(conversion, 6),
            'prev_conversion': rounded(prev_conversion, 6),
            'aov': rounded(aov),
            'prev_aov': rounded(prev_aov),
            'ad_spend': rounded(ad_spend),
            'prev_ad_spend': rounded(prev_ad_spend),
            'product_cost': rounded(product_cost),
            'prev_product_cost': rounded(prev_product_cost),
            'gross_profit': rounded(gross_profit),
            'prev_gross_profit': rounded(prev_gross_profit),
            'operating_profit': rounded(operating_profit),
            'prev_operating_profit': rounded(prev_operating_profit),
            'profit_rate': rounded(profit_rate, 6),
            'prev_profit_rate': rounded(prev_profit_rate, 6),
            'refund_rate': rounded(refund_rate, 6),
            'prev_refund_rate': rounded(prev_refund_rate, 6),
            'anomaly_tags': anomaly_tags,
            'system_facts': system_facts,
            'unknowns': unknowns,
        }

    top_ids = [
        product_id for product_id, row in sorted(
            current.items(), key=lambda item: float(item[1].get('gsv') or 0), reverse=True
        )
        if (row.get('gsv') or 0) > 0
    ][:10]
    decline_ids = [
        product_id for product_id in sorted(
            set(current) | set(previous),
            key=lambda item: (
                float(current.get(item, {}).get('gsv') or 0) - float(previous.get(item, {}).get('gsv') or 0)
            ),
        )
        if previous.get(product_id, {}).get('gsv') not in (None, 0)
        and (
            product_id not in current
            or (
                current[product_id].get('gsv') is not None
                and current[product_id].get('gsv') < previous[product_id].get('gsv')
            )
        )
    ][:10]

    # ---- 新增榜单（对齐用户的月复盘框架）----
    # 付费 TOP：按本期推广花费排序，广告复盘里看钱花在哪些商品上。
    paid_ids = [
        product_id for product_id, row in sorted(
            current.items(), key=lambda item: float(item[1].get('ad_spend') or 0), reverse=True
        )
        if (row.get('ad_spend') or 0) > 0
    ][:10]
    # 盈利 TOP / 亏损 TOP：按经营利润（支付预估）排。
    profit_ids = [
        product_id for product_id, row in sorted(
            current.items(), key=lambda item: float(item[1].get('operating_profit') or 0), reverse=True
        )
        if (row.get('operating_profit') or 0) > 0
    ][:10]
    loss_ids = [
        product_id for product_id, row in sorted(
            current.items(), key=lambda item: float(item[1].get('operating_profit') or 0)
        )
        if (row.get('operating_profit') or 0) < 0
    ][:10]

    # 新品：最近 60 天上架（以周期结束日为参照，上架不能晚于周期末）。
    new_ids = []
    try:
        period_end = date.fromisoformat(str(period['end']))
        new_cutoff = (period_end - timedelta(days=60)).isoformat()
        new_rows = conn.execute(
            '''SELECT product_id FROM products
               WHERE list_date IS NOT NULL AND list_date != ''
                 AND list_date <= ? AND list_date >= ?''',
            (period['end'], new_cutoff),
        ).fetchall()
        new_ids = [row['product_id'] for row in new_rows]
    except Exception:
        new_ids = []
    new_ids = [pid for pid in new_ids if pid in current]
    new_top_ids = [
        pid for pid in sorted(
            new_ids, key=lambda pid: float(current[pid].get('net_sales') or 0), reverse=True
        )
        if (current[pid].get('net_sales') or 0) > 0
    ][:10]
    new_paid_ids = [
        pid for pid in sorted(
            new_ids, key=lambda pid: float(current[pid].get('ad_spend') or 0), reverse=True
        )
        if (current[pid].get('ad_spend') or 0) > 0
    ][:10]

    ids = set(top_ids + decline_ids + paid_ids + profit_ids + loss_ids + new_top_ids + new_paid_ids)
    meta = _product_meta(conn, ids)

    def with_meta(product_id):
        item = decorate(product_id)
        info = meta.get(product_id, {})
        item['title'] = info.get('title') or product_id
        item['image_url'] = info.get('image_url') or ''
        item['tags'] = info.get('product_tags') or ''
        return item

    # 问题单品聚合（对齐 XMind「问题单品分析」）：跨榜合并去重，
    # 出现在下滑榜或亏损榜，或费比超阈值且 GSV 占比 >1% 的商品。
    # 每项标注来源榜单，作为「从看数到生成运营动作」的最短路径入口。
    AD_RATIO_PROBLEM_THRESHOLD = 0.30
    problem_sources = {}
    for product_id in decline_ids:
        problem_sources.setdefault(product_id, []).append('下滑榜')
    for product_id in loss_ids:
        problem_sources.setdefault(product_id, []).append('亏损榜')
    for product_id, row in current.items():
        ad_spend_value = float(row.get('ad_spend') or 0)
        gsv_value = float(row.get('gsv') or 0)
        if (gsv_value > 0 and ad_spend_value > 0
                and ad_spend_value / gsv_value > AD_RATIO_PROBLEM_THRESHOLD
                and total_gsv > 0 and gsv_value / total_gsv > 0.01):
            problem_sources.setdefault(product_id, []).append('高费比')
    problem_items = []
    for product_id in sorted(problem_sources, key=lambda pid: -abs(float((current.get(pid) or {}).get('gsv') or 0))):
        item = with_meta(product_id)
        item['problem_sources'] = problem_sources[product_id]
        problem_items.append(item)
    problem_items = problem_items[:20]

    return {
        'top': [with_meta(product_id) for product_id in top_ids],
        'decline': [with_meta(product_id) for product_id in decline_ids],
        'paid': [with_meta(product_id) for product_id in paid_ids],
        'profit': [with_meta(product_id) for product_id in profit_ids],
        'loss': [with_meta(product_id) for product_id in loss_ids],
        'new': [with_meta(product_id) for product_id in new_top_ids],
        'new_paid': [with_meta(product_id) for product_id in new_paid_ids],
        'problem_items': problem_items,
    }

