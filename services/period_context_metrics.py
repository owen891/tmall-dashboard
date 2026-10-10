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

def _empty_totals():
    return {
        'gsv': 0.0, 'refund_amount': 0.0, 'net_sales': 0.0, 'ad_spend': 0.0,
        'profit': 0.0, 'visitors': 0.0, 'buyers': 0.0, 'payment_qty': 0.0, 'pv': 0.0,
        'paid_ipv': 0.0,
        'product_count': 0, 'day_count': 0,
        'first_date': None, 'last_date': None,
        'cart_rate': None, 'fav_rate': None, 'bounce_rate': None,
    }

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

def _baseline_grain_comparable(baseline_grain, current_full_month=False):
    """对比基线若来自月度兜底（data_grain='monthly'），只有当前周期本身是完整月
    时量纲才一致。

    daily_data 只覆盖部分日期（实测 2025-09-01~2026-10-02 但仅 93 天，2025-10
    整月缺失），去年同周/同日、以及进行中的本月，都会整月回退到 monthly_data。
    此时直接算变化率会把「数天 vs 整月」当成真实变化 —— 实测：
      - week/2026-10-W1（4 天）同比 gsv -98.0%
      - month/2026-10（进行中，仅过 3 天）同比 gsv -98.0%
    必须拦截，而不是把极端百分比当事实展示。已完成的月（如 2026-09）即便基线
    走月表兜底，双方都是整月，量纲一致，仍应正常对比。
    """
    if baseline_grain != 'monthly':
        return True
    return bool(current_full_month)

def _comparability(baseline_totals, baseline_grain, baseline_available, current_full_month=False):
    """对比基线可比性判定，供前端决定是否展示变化率（不臆造百分比）。"""
    baseline_days = int((baseline_totals or {}).get('day_count') or 0)
    if not baseline_available or not baseline_days:
        return {'comparable': False, 'reason': 'baseline_no_data',
                'baseline_grain': baseline_grain, 'baseline_days': baseline_days}
    if not _baseline_grain_comparable(baseline_grain, current_full_month):
        return {'comparable': False, 'reason': 'baseline_grain_mismatch',
                'baseline_grain': baseline_grain, 'baseline_days': baseline_days}
    return {'comparable': True, 'reason': None,
            'baseline_grain': baseline_grain, 'baseline_days': baseline_days}

def _metric_items(current, prev, yoy, prev_grain=None, yoy_grain=None, current_full_month=False):
    """逐指标产出当前值 + 环比/同比。

    变化率只在「基线可比」时输出；基线不可比（月度兜底量纲错配）时改为
    输出 mom_unavailable / yoy_unavailable 原因，绝不输出极端百分比。
    """
    mom_comparable = _baseline_grain_comparable(prev_grain, current_full_month)
    yoy_comparable = _baseline_grain_comparable(yoy_grain, current_full_month)
    items = []
    for key, label, fmt, lower_better in METRIC_DEFS:
        value = current.get(key)
        prev_value = prev.get(key)
        yoy_value = yoy.get(key)
        item = {
            'key': key, 'label': label, 'format': fmt, 'lower_better': lower_better,
            'value': value, 'prev_value': prev_value, 'yoy_value': yoy_value,
            'mom_comparable': mom_comparable, 'yoy_comparable': yoy_comparable,
        }
        if value is not None and prev_value:
            if mom_comparable:
                item['mom_change'] = round((value - prev_value) / abs(prev_value) * 100, 1)
                item['mom_abs'] = round(value - prev_value, 4)
            else:
                item['mom_unavailable'] = 'baseline_grain_mismatch'
        if value is not None and yoy_value:
            if yoy_comparable:
                item['yoy_change'] = round((value - yoy_value) / abs(yoy_value) * 100, 1)
                item['yoy_abs'] = round(value - yoy_value, 4)
            else:
                item['yoy_unavailable'] = 'baseline_grain_mismatch'
        items.append(item)
    return items

def _totals_for_range(conn, start, end, category_label=None, allow_monthly_fallback=True):
    """周期指标聚合：daily_data 为主口径。

    对比期月份数据可能只有 monthly_data（BI 日度补采窗口外），此时按同品类
    过滤回退月表；分周/分日拆解必须保持原粒度，不允许用整月值填充。
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
    if allow_monthly_fallback and not totals.get('day_count'):
        monthly = _monthly_fallback_totals(conn, start, end, category_label)
        if monthly:
            return monthly
    return totals

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
        totals = _totals_for_range(
            conn, span['start'], span['end'], category_label,
            allow_monthly_fallback=False,
        )
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

METRIC_DEFS = [
    ('gsv', '销售额（支付金额）', 'money', False),
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

BREAKDOWN_METRIC_KEYS = (
    'gsv', 'net_sales', 'profit', 'visitors', 'conversion', 'aov',
    'cart_rate', 'ad_spend', 'ad_ratio', 'roi', 'paid_cpc',
)
