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
# 市场分级算法（8大归类 / 词根需求 / 蓝海机会 / 趋势节点 / 竞店爆品）已投产于市场排行页，
# 月复盘页此前未复用 → 这里直接引用同一实现，避免两套口径漂移。
from services import market_monitor_service as market_monitor
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
#
# ⚠️ 这里的 rate_better='low' 与「涨跌配色」是**两套语义**，2026-10-01 业务已确认：
#   涨跌配色（assets/metric-polarity.js）：推广花费涨 = 投放规模扩大 = 好（绿），
#     ad_spend 归 HIGHER_IS_BETTER，与 MATRIX_METRICS 的 lower_better=False 一致；
#   目标达成率（本表）：推广费是「预算使用率」，花超预算算超标，所以越低越好。
#   两者刻意不统一，别顺手改。若将来要统一，需要业务重新定义「推广费预算」是不是硬上限。
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


def _target_rows(current, saved_review, preset_targets=None):
    """把复盘设置里录入的四项目标与本期实际配对，供复盘页目标表渲染。

    达成率：默认 = 实际 ÷ 目标；`reverse_rate` 的指标（净费比）= 目标 ÷ 实际。
    未录入目标的项 target 为 None，前端显示「未设置」而不是 0。

    preset_targets 为经营目标页按周期预置的辅助目标（goal_metric_targets 表，
    净利润/推广费/净费比）；复盘里手填的值优先，未填时回退预置值并标注来源。
    """
    saved = saved_review or {}
    preset = preset_targets or {}
    rows = []
    for key, label, fmt, reverse_rate, rate_better in TARGET_METRICS:
        field = next((f for f, k in TARGET_FORM_FIELDS.items() if k == key), None)
        raw = saved.get(field) if field else None
        target_value = None
        target_source = None
        if raw not in (None, ''):
            try:
                target_value = float(raw)
                target_source = 'review'
            except (TypeError, ValueError):
                target_value = None
        if target_value is None and preset.get(key) is not None:
            target_value = float(preset[key])
            target_source = 'goals_page'
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
            'target_source': target_source,
            'actual': actual,
            'gap': gap,
            'achieved_rate': achieved_rate,
        })
    return rows


def _goal_metric_targets(conn, period_type, period_key):
    """读经营目标页预置的辅助目标（净利润/推广费/净费比）。

    周复盘没有按周预置（目标页只到月），回退查所属月份的预置值，
    让周复盘至少能对照月度口径；来源标注保持 goals_page。
    """
    keys = [(period_type, period_key)]
    if period_type == 'week' and len(str(period_key)) >= 7:
        keys.append(('month', str(period_key)[:7]))
    for row_period_type, row_period_key in keys:
        rows = conn.execute(
            '''SELECT metric, target_value FROM goal_metric_targets
               WHERE year = ? AND period_type = ? AND period_key = ?''',
            (int(str(period_key)[:4]), row_period_type, row_period_key),
        ).fetchall()
        if rows:
            return {row['metric']: float(row['target_value']) for row in rows}
    return {}
# ---------------------------------------------------------------------------
# 货品
# ---------------------------------------------------------------------------


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
        return {'available': False, 'grain': None, 'items': [], 'missing_inputs': ['promotion_daily_facts']}


# ---------------------------------------------------------------------------
# 广告单品 TOP 消耗（对齐用户的月复盘框架「广告-单品-TOP20消耗商品」）
#
# 数据边界（已实测，勿改）：
# - 商品级合计来自 promotion_daily_facts 的 channel='全部' AND grain='product' 行：
#   唯一带 product_id 的完整商品级汇总（花费/归因成交/直接成交/加购/拉新/点击齐全）。
# - 商品×渠道**不再依赖** promotion_daily_facts 的具名渠道行（那些行 product_id 全为空，
#   且 campaign→商品 是一对多映射，join 会重复计量花费）。正解是 promotion_creative_daily：
#   v4 采集器逐日抓的**创意级**事实，自带 channel + product_id（实测 28,337 行，
#   product_id 命中 products 99.8%），覆盖 关键词/人群/店铺直达，自 2026-08-20 起。
# - 它**缺 全站推广**（creative 报表不含该场景）→ 渠道之和 ≠ 商品合计，
#   必须显式标注 channels_partial / channels_note，不能让人把渠道加总当 100%。
# ---------------------------------------------------------------------------

PROMOTION_CHANNEL_GROUPS = (
    ('全站', ('全站推广', '货品全站推广')),
    ('关键词', ('关键词推广',)),
    ('人群', ('人群推广',)),
    ('其他', ('店铺直达', '超级短视频')),
)

# 渠道行共用 SUM 列（creative / campaign 两条聚合 SQL 都要带齐，派生指标才算得出）。
CHANNEL_SUM_COLUMNS = (
    'SUM(COALESCE(f.direct_payment_amount, 0)) AS direct_payment, '
    'SUM(COALESCE(f.cart_adds, 0)) AS cart_adds, '
    'SUM(COALESCE(f.new_buyers, 0)) AS new_buyers, '
    'SUM(COALESCE(f.clicks, 0)) AS clicks, '
    'SUM(COALESCE(f.impressions, 0)) AS impressions, '
    'SUM(COALESCE(f.payment_buyers, 0)) AS payment_buyers'
)


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
        return {'available': False, 'grain': grain, 'points': []}


# ---------------------------------------------------------------------------
# 计划 → 商品归因（promotion_campaign_items × campaign 粒度事实）
#
# 数据边界（实测 2026-10-03，勿臆改）：
# - `promotion_campaign_items` 是「计划→商品」映射表：4,306 行 / 562 计划 /
#   1,210 商品，但它是**当前快照**（updated_at 仅 2026-09-18 ~ 10-03），没有历史
#   版本 —— 只能代表「最近一次采集时的计划商品构成」，所以只对 2026-08-20 之后
#   的周期成立，更早周期不得回填。
# - campaign 粒度事实（`promotion_daily_facts.grain='campaign'`）覆盖 2026-08-20 起，
#   562 个计划与映射表 **100% 对得上**（计划花费里「无映射」占比 = 0%）。
# - 归因只分两档，**一律不做均摊**：按商品数把计划花费摊到商品，等于凭空造数
#   （实测有个 759 商品的计划，摊完每商品只剩零头，且无任何依据）。
#     · `exact`：计划只绑 1 个商品 → 计划花费/成交**全额**归到该商品。
#       实测覆盖 2026-09 计划花费的 73.9%；其中「货品全站推广」89.3% 是 1:1
#       （210/212 个计划），正好补上「商品级全站推广」这个缺口。
#     · `shared`：计划绑多个商品 → 只在计划级展示，不拆到商品。
# ---------------------------------------------------------------------------

CAMPAIGN_ATTRIBUTION_NOTE = (
    '计划→商品归因：仅对「计划只绑 1 个商品」的计划做商品级归因（精确，非均摊）；'
    '多商品计划只在计划级展示。映射表为当前快照，仅 2026-08-20 之后有效。'
)


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


# ---------------------------------------------------------------------------
# 全页数据状态汇总（XMind P0 #3：顶部统一「数据状态」标识）
#
# 原则：**不是一盏灯，而是「一盏灯 + 触发原因清单」**。
# 只显示「部分数据」是不可操作的——必须说清**哪块降级了、为什么、影响什么**，
# 否则读者只能选择「全部信」或「全部不信」。
#
# 本函数只做汇总、**不重新查库**：所有判据都从已算好的各块里取。
# 同一事实若在两处各算一遍，就是未来不一致的根源。
#
# severity 两档，含义不同、处理方式也不同：
#   warning —— 数字本身不可全信（覆盖不足 / 基线不可比 / 恒等式不平）
#   info    —— 数字可信但口径有边界（已显式标注的部分口径）
# ---------------------------------------------------------------------------

DATA_STATUS_LABELS = {
    'complete': '数据完整',
    'partial': '部分数据',
    'no-data': '暂无数据',
}

_COMPARABILITY_REASON_TEXT = {
    'baseline_no_data': '对比周期无数据',
    'baseline_grain_mismatch': '基线粒度与本期不匹配（整月兜底基线 vs 非完整月）',
}


def _unlabeled_products_scope(conn, start, end, grain='day'):
    """统计本期有销售但未打品类标签的商品（数量 + 净销售额）。

    shop_label 是品类拆分的唯一依据，而 BI 接口不带标签字段（tagGroup 恒为
    '--'，实测 2026-10-04）——采集路径新增的商品在模板重传前恒为空，这部分
    销售不参与任何品类统计。放这里让漂移当期可见（2026-09 实测 1,488 款 /
    净销 63,854 未计入品类），而不是月底对账才发现。
    周复盘查 daily_data；月复盘的历史月份 daily 覆盖不全，改查 monthly_data。
    返回 None 表示本期没有未分类商品（或查询失败，不阻塞页面）。
    """
    try:
        if grain == 'month':
            row = conn.execute(
                '''SELECT COUNT(DISTINCT m.product_id) AS n,
                          COALESCE(SUM(m.net_sales), 0) AS net
                   FROM monthly_data m
                   LEFT JOIN products p ON p.product_id = m.product_id
                   WHERE m.month = ? AND COALESCE(p.shop_label, '') = ''
                     AND (m.net_sales > 0 OR m.payment_amount > 0)''',
                (str(start)[:7],),
            ).fetchone()
        else:
            row = conn.execute(
                '''SELECT COUNT(DISTINCT d.product_id) AS n,
                          COALESCE(SUM(d.net_sales), 0) AS net
                   FROM daily_data d
                   LEFT JOIN products p ON p.product_id = d.product_id
                   WHERE d.date BETWEEN ? AND ? AND COALESCE(p.shop_label, '') = ''
                     AND (d.net_sales > 0 OR d.payment_amount > 0)''',
                (start, end),
            ).fetchone()
        count = int(row['n'] or 0)
        if count <= 0:
            return None
        return {'count': count, 'net_sales': round(float(row['net'] or 0), 2)}
    except Exception:
        return None


def _data_status(period, metrics, blocks):
    """汇总全页数据可信度（供顶部统一状态条消费）。

    返回 {level, label, summary, coverage, freshness, comparability,
          degradations: [{key, label, detail, severity}], degradation_count,
          warning_count, info_count}
    """
    blocks = blocks or {}
    coverage = (metrics or {}).get('coverage') or {}
    comparability = (metrics or {}).get('comparability') or {}
    degradations = []

    def add(key, label, detail, severity='warning'):
        degradations.append({'key': key, 'label': label, 'detail': detail, 'severity': severity})

    # ① 周期覆盖：expected/observed 的天数差是最硬的可信度信号
    status = coverage.get('status')
    if status == 'no-data':
        add('coverage', '本期无数据',
            f"预期 {coverage.get('expected_days')} 天，实际 0 天", 'warning')
    elif status == 'partial':
        add('coverage', '周期覆盖不足',
            f"仅 {coverage.get('observed_days')}/{coverage.get('expected_days')} 天"
            f"（缺 {coverage.get('missing_days')} 天）"
            + (f"，数据止于 {coverage.get('observed_end')}" if coverage.get('observed_end') else ''),
            'warning')

    # ② 可比性：不可比必须说明原因，否则读者会把「不可比」当成「没变化」
    for kind, label in (('mom', '环比'), ('yoy', '同比')):
        entry = comparability.get(kind) or {}
        if entry.get('comparable') is False:
            reason = _COMPARABILITY_REASON_TEXT.get(
                entry.get('reason'), entry.get('reason') or '基线不可比')
            add(f'comparability_{kind}', f'{label}不可比', reason, 'warning')

    # ③ 利润恒等式：不平 = 利润是部分口径（实测所有口径下都不平，故必标）
    profit = blocks.get('profit_structure') or {}
    identity = profit.get('identity') or {}
    if profit.get('available') and identity.get('ok') is False:
        sentinel = profit.get('sentinel_rows')
        detail = identity.get('note') or (
            f"恒等残差 {identity.get('gap'):,.0f}" if identity.get('gap') is not None else '恒等式未平')
        if sentinel:
            detail += f'（未回填 {sentinel} 行）'
        add('profit_identity', '利润为部分口径', detail, 'warning')

    # ④ 市场：run_alignment='partial' 表示采集批次未与本期对齐
    market = blocks.get('market') or {}
    if market.get('run_alignment') == 'partial':
        missing = len(market.get('missing_inputs') or [])
        add('market_alignment', '市场数据未完全对齐本期',
            f"采集批次与本期口径部分错配，缺 {missing} 项输入" if missing else '采集批次与本期口径部分错配',
            'warning')

    # ⑤ 口径边界（数字可信，但覆盖不完整，已在各处显式标注）
    ads = blocks.get('ads') or {}
    channel_totals = ads.get('channel_totals') or {}
    if channel_totals.get('partial'):
        add('ads_channel_scope', '按品类渠道为部分口径',
            '全站推广仅含「计划只绑 1 个商品」的精确归因部分，成交占比不计算', 'info')

    # ⑥ 未分类商品（BI 接口无标签字段 → 新品在模板重传前不参与品类拆分）
    unlabeled = blocks.get('unlabeled_products') or {}
    if unlabeled.get('count'):
        add('unlabeled_products', '部分商品未分类',
            f"{unlabeled['count']} 款在卖商品未打品类标签，净销 ¥{unlabeled['net_sales']:,.0f} "
            '未计入任何品类拆分（需更新商品模板标签）', 'info')

    promo_items = blocks.get('promotion_items') or {}
    if promo_items.get('channels_partial'):
        present = promo_items.get('channels_groups_present') or []
        add('promotion_items_channels', '商品×渠道为部分口径',
            '覆盖 ' + ('、'.join(present) if present else '无') + '；渠道之和 ≠ 商品合计', 'info')

    attribution = blocks.get('campaign_attribution') or {}
    share = attribution.get('exact_share')
    if attribution.get('available') and share is not None and share < 0.9999:
        add('campaign_attribution', '计划归因覆盖部分花费',
            f"可精确归因的计划花费占比 {share * 100:.1f}%；多商品计划只在计划级展示（不摊）", 'info')

    dimensions = (blocks.get('dimensions') or {}).get('promotion') or {}
    for key, label in (('channels', '推广渠道拆解'), ('campaigns', '推广计划拆解')):
        view = dimensions.get(key) or {}
        if view.get('partial'):
            add(f'dimension_{key}', f'{label}为部分口径',
                '按品类口径只覆盖有商品映射的渠道/计划', 'info')

    # ⑥ 顶层缺失输入：出现即说明有块没取到数
    top_missing = blocks.get('missing_inputs') or []
    if top_missing:
        add('missing_inputs', '存在缺失输入',
            '、'.join(str(item) for item in top_missing[:6])
            + ('…' if len(top_missing) > 6 else ''), 'warning')

    warning_count = sum(1 for item in degradations if item['severity'] == 'warning')
    info_count = len(degradations) - warning_count
    has_data = bool((metrics or {}).get('has_data'))

    # level 只表达「周期覆盖完整性」；usable 才表达「数字能不能直接用」。
    # ⚠️ 必须分开，否则会掉进「永远是黄的」陷阱：实测连 2026-09（完整月）都因
    # 「利润恒等式不平 + 市场未对齐」而带 warning —— 那是**结构性**的，不是临时故障。
    # 若只给一盏永远为黄的灯，读者会直接忽略它，等于没做。
    level = 'no-data' if not has_data else (
        'complete' if coverage.get('status') == 'complete' else 'partial')
    usable = has_data and warning_count == 0

    if not has_data:
        label, summary = '暂无数据', '本期暂无数据，指标与结论不可用。'
    elif warning_count:
        label = f'部分数据（{warning_count} 项影响可信度）'
        summary = (f'{warning_count} 项影响可信度'
                   + (f'、{info_count} 项口径边界' if info_count else '')
                   + '，详见下方清单。')
    elif info_count:
        label = f'数据可用（{info_count} 项口径边界）'
        summary = f'数字可直接使用；另有 {info_count} 项已知口径边界，不影响结论。'
    else:
        label, summary = '数据完整', '本期数据完整，各项口径可直接使用。'

    return {
        'level': level,
        'usable': usable,
        'label': label,
        'summary': summary,
        'coverage': {
            'status': coverage.get('status'),
            'expected_days': coverage.get('expected_days'),
            'observed_days': coverage.get('observed_days'),
            'missing_days': coverage.get('missing_days'),
            'observed_start': coverage.get('observed_start'),
            'observed_end': coverage.get('observed_end'),
        },
        'freshness': {
            'observed_start': coverage.get('observed_start'),
            'observed_end': coverage.get('observed_end'),
            'is_ongoing': bool((period or {}).get('is_ongoing')),
            'elapsed_days': (period or {}).get('elapsed_days'),
            'total_days': (period or {}).get('total_days'),
        },
        'comparability': comparability,
        'degradations': degradations,
        'degradation_count': len(degradations),
        'warning_count': warning_count,
        'info_count': info_count,
    }


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

        def aggregate(start, end, channels, grain='product'):
            """商品级聚合。只允许 grain='product'。

            其他粒度的历史行来自已停用的 v3 采集器（把 campaignId 当 product_id 写入，
            实测 campaign_month/unit_month 的 product_id 有 0% 能对上 products），
            不能当商品口径使用，否则会把广告计划 ID 当成商品塞进复盘页。
            """
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
                    WHERE f.date BETWEEN ? AND ? AND f.grain = ?
                      AND f.product_id IS NOT NULL AND f.product_id != ''
                      AND f.channel IN ({placeholders}){category_sql}
                    GROUP BY f.product_id''',
                [start, end, grain, *channels, *category_params],
            ).fetchall()
            return {row['product_id']: dict(row) for row in rows}

        # 总计口径：channel='全部' 的商品级行（唯一干净的商品级口径，v4 采集）。
        totals_map = aggregate(period['start'], period['end'], ['全部'])
        # 渠道口径（历史）：promotion_daily_facts 里带具名渠道的商品级行。实测 grain='product'
        # 只有 '全部' 与 '全站推广'（全站推广 749 行，止于 2026-07-31，product_id 命中 62.7%）；
        # 关键词/人群 的具名行都在 campaign/unit 粒度（product_id 是 campaignId，命中 0%），不可用。
        channel_rows = {}   # (group_name, channel) -> {pid: row}
        for group_name, channels in PROMOTION_CHANNEL_GROUPS:
            for channel in channels:
                rows = aggregate(period['start'], period['end'], [channel])
                if rows:
                    channel_rows[(group_name, channel)] = rows

        # 渠道口径（当前权威）：promotion_creative_daily —— v4 采集器逐日抓的创意级事实，
        # 自带 channel + product_id（实测 28,337 行，product_id 命中 products 99.8%），
        # 覆盖 关键词推广/人群推广/店铺直达，自 2026-08-20 起。这是「商品×渠道」的正解。
        creative_rows = {}  # (channel, pid) -> row
        creative_available = bool(conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='promotion_creative_daily'"
        ).fetchone())
        if creative_available:
            creative_sql = f'''SELECT f.channel AS channel, f.product_id,
                                      SUM(f.ad_spend) AS ad_spend,
                                      SUM(f.attributed_payment_amount) AS attributed_payment,
                                      SUM(f.direct_payment_amount) AS direct_payment,
                                      SUM(f.cart_adds) AS cart_adds,
                                      SUM(f.new_buyers) AS new_buyers,
                                      SUM(f.clicks) AS clicks
                               FROM promotion_creative_daily f
                               LEFT JOIN products p ON p.product_id = f.product_id
                               WHERE f.date BETWEEN ? AND ?
                                 AND f.product_id IS NOT NULL AND f.product_id != ''
                                 {category_sql}
                               GROUP BY f.channel, f.product_id'''
            for row in conn.execute(
                creative_sql, [period['start'], period['end'], *category_params]
            ).fetchall():
                creative_rows[(row['channel'], row['product_id'])] = dict(row)

        # 渠道口径（补全）：计划→商品归因的 exact（1:1 计划）行。
        # 这是「商品级全站推广」的唯一来源 —— promotion_creative_daily 实测**不含
        # 全站推广**（只有 关键词/人群/店铺直达），而 promotion_daily_facts 的
        # product 粒度具名行只有 '全站推广' 且止于 2026-07-31。2026-08-20 起，
        # 「货品全站推广」的商品绑定只存在于计划→商品映射里（210/212 个计划是 1:1）。
        attribution = _campaign_attribution(conn, period, category_label, include_product_rows=True)
        campaign_rows = (attribution or {}).get('product_rows') or {}

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
        # 注意：这个标记必须跨商品累积，不能在每个商品循环里重置——
        # 否则只反映「最后一个商品」是否有渠道数据，missing_inputs 会误判。
        has_channel_data = False

        def merge_rows(left, right):
            merged = dict(left)
            for key in ('ad_spend', 'attributed_payment', 'direct_payment',
                        'cart_adds', 'new_buyers', 'clicks'):
                merged[key] = (left.get(key) or 0) + (right.get(key) or 0)
            return merged

        for pid in top_ids:
            info = meta.get(pid, {})
            channels_data = {}
            channel_sources = {}
            for group_name, channels in PROMOTION_CHANNEL_GROUPS:
                group_row = None
                group_source = None
                for channel in channels:
                    # 三个来源**二选一**（绝不相加，避免重复计数）：
                    # ① promotion_creative_daily —— 当前权威商品×渠道来源（创意级，
                    #    覆盖 关键词/人群/店铺直达，2026-08-20 起）；
                    # ② 计划→商品归因的 1:1 exact 行 —— 补 creative 没有的渠道，
                    #    主要是「货品全站推广」（creative 表不含该场景）；
                    # ③ promotion_daily_facts 的 product 粒度具名行 —— 历史兜底
                    #    （仅 '全站推广'，止于 2026-07-31）。
                    row, source = creative_rows.get((channel, pid)), 'creative'
                    if row is None:
                        row, source = campaign_rows.get((channel, pid)), 'campaign_exact'
                    if row is None:
                        row = channel_rows.get((group_name, channel), {}).get(pid)
                        source = 'product_grain'
                    if row is None or not (row.get('ad_spend') or 0):
                        continue
                    group_row = row if group_row is None else merge_rows(group_row, row)
                    # 同一组内多来源混用时，标注最保守的来源，避免让人误以为是单一权威源。
                    group_source = source if group_source is None else 'mixed'
                if group_row is not None:
                    channels_data[group_name] = derived(group_row)
                    channel_sources[group_name] = group_source
                    has_channel_data = True
            items.append({
                'product_id': pid,
                'title': info.get('title') or pid,
                'image_url': info.get('image_url') or '',
                'totals': derived(totals_map[pid]),
                'channels': channels_data,
                'channel_sources': channel_sources,
            })

        missing_inputs = []
        if not items:
            missing_inputs.append('promotion_daily_facts.product')
        elif not has_channel_data:
            missing_inputs.append('promotion_product_channel_scope')
        # 渠道明细天然是「部分口径」，必须显式标注，别让前端把渠道加总当成 100%：
        # - 全站推广：2026-08-20 起靠计划→商品归因的 1:1 exact 行补（**只覆盖单商品
        #   计划**，实测占全站花费 89.3%），多商品计划无商品级明细；
        # - 关键词/人群：creative 表只覆盖 2026-08-20 起。
        channel_groups_present = sorted({
            group for item in items for group in item['channels']
        })
        attribution_share = (attribution or {}).get('exact_share')
        note = '商品×渠道覆盖 ' + ('、'.join(channel_groups_present) if channel_groups_present else '无') + '。'
        if '全站' in channel_groups_present:
            note += ('全站推广按「计划只绑 1 个商品」精确归因'
                     + (f'（覆盖计划花费 {attribution_share * 100:.1f}%）' if attribution_share is not None else '')
                     + '，多商品计划无商品级明细；')
        note += '渠道之和不等于商品合计。'
        return {
            'available': bool(items), 'items': items,
            'channel_groups': [name for name, _ in PROMOTION_CHANNEL_GROUPS],
            'channels_partial': has_channel_data,
            'channels_groups_present': channel_groups_present,
            'channels_note': note if has_channel_data else None,
            'attribution': {
                'method': 'exact_1to1_campaign',
                'exact_share': attribution_share,
                'first_fact_date': (attribution or {}).get('first_fact_date'),
                'note': (attribution or {}).get('attribution_note'),
            },
            'missing_inputs': missing_inputs,
        }
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
        """按 key 聚合窗口事实。

        ⚠️ 列名按表**实测存在性**拼装，不硬写。事故：原实现对非
        `sycm_market_rival_shop` 的表统一 `MAX(detail_url)`，但
        `sycm_market_item_rank` 根本没有 `detail_url` 列（只有
        `sycm_market_rival_item` 有）→ `sqlite3.OperationalError`，
        又被外层 `except` 吞掉 → **competitor_items 长期静默为空**，
        表现为「竞品商品级未接入」，实际是 SQL 查了不存在的列。
        """
        present = {row['name'] for row in conn.execute(f'PRAGMA table_info({table})').fetchall()}
        parts = ['COUNT(DISTINCT stat_date) AS sample_days']
        for col in ('shop_name', 'shop_url', 'is_tmall', 'title', 'pic_url', 'detail_url'):
            if col in present:
                parts.append(f'MAX({col}) AS {col}')
        for col in ('uv', 'pay_buyer_count', 'cart_buyer_count', 'collect_buyer_count'):
            if col in present:
                parts.append(f'SUM({col}) AS {col}')
        cols = ', '.join(parts)
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

    # ------------------------------------------------------------------
    # 市场分级（XMind「市场监控-行业」）：8大归类 / 词根需求 / 蓝海机会 /
    # 趋势节点 / 竞店爆品排名变化。
    #
    # ⚠️ 算法**不在此处重写** —— 直接复用市场排行页已投产的
    #    `services/market_monitor_service`，保证两页口径一致。
    # ⚠️ 窗口取「复盘周期 ∩ 数据实际覆盖」而不是复盘周期本身：
    #    市场表只从 2026-09-16 起，若强行按整月算，7 天/基线窗口会落在
    #    无数据区 → 趋势节点恒空。交集窗口 + 显式回报窗口天数才诚实。
    # ------------------------------------------------------------------
    keyword_insights = {'available': False, 'missing_inputs': ['sycm_market_search_rank'],
                        'categories': [], 'blue_ocean': [],
                        'trend_nodes': {'rising': [], 'cooling': []}}
    blue_ocean_supply = {'available': False, 'words': [],
                         'missing_inputs': ['sycm_market_item_rank']}
    rival_moves = {'available': False, 'shops': [], 'shop_count': 0,
                   'missing_inputs': ['sycm_market_item_rank']}
    trend_items = {'available': False, 'rising': [], 'new_items': [],
                   'missing_inputs': ['sycm_market_item_rank']}
    keyword_window = None
    item_window = None
    kw_rows = []
    try:
        kw_facts = source_dates.get('sycm_market_search_rank') or {}
        kw_start, kw_end = kw_facts.get('first_date'), kw_facts.get('last_date')
        if kw_start and kw_end:
            keyword_window = {'start': kw_start, 'end': kw_end,
                              'day_count': int(kw_facts.get('sample_days') or 0)}
            kw_rows = conn.execute(
                '''SELECT stat_date, keyword, search_heat, pay_rate, click_rate
                   FROM sycm_market_search_rank WHERE stat_date BETWEEN ? AND ?
                   ORDER BY stat_date''',
                (kw_start, kw_end),
            ).fetchall()
            if kw_rows:
                keyword_insights = market_monitor.keyword_insights(
                    kw_start, kw_end, [tuple(row) for row in kw_rows])
        item_facts = source_dates.get('sycm_market_item_rank') or {}
        item_start, item_end = item_facts.get('first_date'), item_facts.get('last_date')
        if item_start and item_end:
            item_window = {'start': item_start, 'end': item_end,
                           'day_count': int(item_facts.get('sample_days') or 0)}
            item_rows = conn.execute(
                '''SELECT stat_date, item_id, title, shop_name, rank, is_self, uv, pay_buyer_count
                   FROM sycm_market_item_rank WHERE stat_date BETWEEN ? AND ?
                   ORDER BY stat_date, rank''',
                (item_start, item_end),
            ).fetchall()
            if item_rows:
                rival_moves = market_monitor.rival_item_moves(
                    item_start, item_end, [tuple(row) for row in item_rows])
                trend_items = market_monitor.trend_items(
                    item_start, item_end, [tuple(row) for row in item_rows])
                # 蓝海完整口径：最新采集日在榜商品 title 命中词根 → 每万搜索覆盖。
                # 与近似口径（热度×转化）并存：近似看「有没有需求」，完整看「供给挤不挤」。
                if kw_rows:
                    titles = conn.execute(
                        'SELECT title FROM sycm_market_item_rank WHERE stat_date = ?',
                        (item_end,),
                    ).fetchall()
                    blue_ocean_supply = market_monitor.blue_ocean_words(
                        [tuple(row) for row in kw_rows],
                        [row['title'] for row in titles])
    except Exception:
        # 市场分级是增强项，任何异常都不应拖垮整个复盘上下文。
        pass

    # 趋势词标注 8 大归类（与关键词洞察同一套口径，供前端直接分组展示）。
    trend_nodes = keyword_insights.get('trend_nodes') or {}
    for bucket in ('rising', 'cooling'):
        for entry in trend_nodes.get(bucket) or []:
            key, label = market_monitor.classify_keyword(entry.get('keyword'))
            entry['category_key'] = key
            entry['category_label'] = label

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
    if not keyword_insights.get('available'):
        missing.append('market_keyword_insights')
    if not blue_ocean_supply.get('available'):
        missing.append('market_blue_ocean_supply')
    if not rival_moves.get('available'):
        missing.append('market_rival_item_moves')
    missing.extend(['market_price', 'market_margin', 'market_reviews'])

    # 市场分级总口径（XMind「市场监控-行业」）：窗口与边界集中声明一处，
    # 避免前端各处自行拼「有效期」文案导致口径分叉。
    grading_limitations = list(keyword_insights.get('limitations') or [])
    if blue_ocean_supply.get('available'):
        # `keyword_insights` 自带的「供给覆盖字段未采集，待补齐每万覆盖」是**近似口径**
        # 的免责声明。但完整口径（每万搜索覆盖）本次已单独产出 → 保留这句会自相矛盾
        # （页面上明明有「每万覆盖」列，却提示「待补齐」）。替换为两者关系说明。
        grading_limitations = [text for text in grading_limitations if '供给覆盖字段未采集' not in text]
        grading_limitations.insert(0, (
            '蓝海有两条口径并存：「蓝海度」（热度×转化，用于候选排序）与「每万搜索覆盖」'
            '（供给分级，见「蓝海市场 · 低供给词根」）—— 后者本次已产出，无需再等采集补齐。'))
    if keyword_window and (keyword_window['start'] > start or keyword_window['end'] < end):
        grading_limitations.append(
            f"市场表仅覆盖 {keyword_window['start']} ~ {keyword_window['end']}"
            f"（{keyword_window['day_count']} 天），复盘周期 {start} ~ {end} 的其余天数无市场数据。")
    if not (trend_nodes.get('available')):
        grading_limitations.append('趋势节点需「近期窗口 + 前置基线」两段数据，当前基线不足，起势/退势不可判。')
    market_grading = {
        'keyword_window': keyword_window,
        'item_window': item_window,
        'trend_node_threshold': trend_nodes.get('threshold'),
        'trend_node_available': bool(trend_nodes.get('available')),
        'blue_ocean_word_scope': blue_ocean_supply.get('word_scope'),
        'limitations': grading_limitations,
    }
    return {'available': True, 'run': run, 'run_alignment': run_alignment,
            'comparison_run': dict(previous_run) if previous_run else None,
            'period': {'start': start, 'end': end},
            'comparison_period': {'start': previous.get('start'), 'end': previous.get('end')} if previous else None,
            'categories': categories, 'rivals': rivals,
            'competitor_items': competitor_items,
            'market_signals': market_signals,
            'keyword_signals': keyword_signals,
            'keyword_insights': keyword_insights,
            'blue_ocean_supply': blue_ocean_supply,
            'rival_moves': rival_moves,
            'trend_items': trend_items,
            'grading': market_grading,
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
        items.append({'level': 'info', 'label': '最高单日销售额', 'detail': f"{best['date']} · {best['gsv']:.0f}"})
        items.append({'level': 'warning', 'label': '最低单日销售额', 'detail': f"{worst['date']} · {worst['gsv']:.0f}"})

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

        # 基线粒度必须在 _derive 之前取：_derive 只产出指标值，会丢掉 data_grain 标记。
        prev_grain = totals_prev.get('data_grain')
        yoy_grain = totals_yoy.get('data_grain')
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
        # 计划 → 商品归因（对齐 XMind「推广计划拆解」+ 补商品级全站推广）。
        # 与 promotion_items 内的补全同源，这里单独取一份计划级列表给前端渲染。
        campaign_attribution = _campaign_attribution(conn, period, category_label)
        # 汇总层广告块含直接 ROI / 三渠道合计，需要 conn 查推广事实表，
        # 必须在连接作用域内完成（与 products/promotion_items 同理）。
        ads = _ads_block(conn, current, prev, period, compare, category_label)
        breakdown = _breakdown_block(conn, period, category_label)
        actions = _actions_block(conn, period, category_label)
        alerts = _alerts_block(conn)
        anomalies = _anomalies_block(conn, period, current, prev, category_label)
        # 周月互汇（XMind：月复盘的周维度结论由本月各周复盘汇入）。
        # 月复盘读本月各周；周复盘读上月月复盘根因作参考——写月报从
        # 「从零分析」变成「检查各周结论找规律」。
        linked_summaries = _linked_period_summaries(conn, period)
        # 经营目标页按月预置的净利润/推广费/净费比目标（XMind「下月规划」）。
        preset_metric_targets = _goal_metric_targets(conn, period_type, period_key)
        # 利润结构（利润瀑布）：BI 派米恒等口径，费用 5 桶 + 利润 + 恒等校验。
        # 对比期沿用 compare 区间（available 才有），与指标环比同源。
        from services.profit_structure_service import profit_structure
        profit_structure_payload = (
            profit_structure(conn, period['start'], period['end'], category_label,
                             compare['start'], compare['end'])
            if compare['available']
            else profit_structure(conn, period['start'], period['end'], category_label)
        )
        # 未分类商品口径（数据状态消费）：BI 接口无标签字段 → 新品在模板重传前
        # 不参与品类拆分。必须在 conn 作用域内现查（上面各块都不携带该口径）。
        unlabeled_products = _unlabeled_products_scope(
            conn, period['start'], period['end'],
            grain='month' if period_type == 'month' else 'day')

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
    # 只有「已完结的月」当前周期才是完整月；进行中的月（如 10 月仅过 3 天）
    # 与月度兜底基线（整月）量纲不一致，必须拦截变化率。
    current_full_month = period_type == 'month' and not period['is_ongoing']

    metrics_payload = {
        'current': current,
        'prev': prev if prev else None,
        'yoy': yoy if yoy else None,
        'items': _metric_items(current, prev, yoy, prev_grain=prev_grain,
                               yoy_grain=yoy_grain, current_full_month=current_full_month),
        'has_data': has_data,
        'coverage': coverage,
        # 对比基线可比性：前端据此决定是否展示变化率，避免把窗口错配的
        # 极端同比（如数天 vs 整月 → -98%）当事实。
        'comparability': {
            'mom': _comparability(totals_prev, prev_grain, compare['available'], current_full_month),
            'yoy': _comparability(totals_yoy, yoy_grain, True, current_full_month),
        },
        'paid_cpc_source': paid_cpc_source,
    }
    # 全页数据状态（P0 #3）：只汇总、不重查。判据全部取自上面已算好的各块，
    # 避免同一事实在两处各算一遍 → 未来不一致（未分类商品在 with 块内现查）。
    data_status = _data_status(period, metrics_payload, {
        'profit_structure': profit_structure_payload,
        'market': market,
        'ads': ads,
        'promotion_items': promotion_items,
        'campaign_attribution': campaign_attribution,
        'dimensions': {'promotion': promotion},
        'unlabeled_products': unlabeled_products,
        'missing_inputs': missing_inputs,
    })

    return {
        'period': period,
        'category': {
            'mode': category_mode or 'all',
            'label': category_label,
            'filtered': bool(category_label),
        },
        'compare': compare,
        'compare_options': recent_periods(period_type, period_key),
        'data_status': data_status,
        'metrics': metrics_payload,
        # 达成率口径 = 净销售额 ÷ 目标（与经营目标表一致）。
        # 早期误用 GSV 作分子，会把含退款的支付金额算进达成率，系统性偏高约 20%。
        'target_path': _target_path(period, target, target_source, current['net_sales'], category_label,
                                    targets=_target_rows(current, saved_review, preset_targets=preset_metric_targets)),
        'products': products,
        'profit_structure': profit_structure_payload,
        'ads': ads,
        'breakdown': breakdown,
        'promotion_items': promotion_items,
        'campaign_attribution': campaign_attribution,
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

    - 月复盘：读本月各周（period_key LIKE 'YYYY-MM-W%'）的周复盘；
    - 周复盘：读上月月复盘，作为「对照月度根因」参考素材；
    - 每期收**全部**有内容的段落（不只品类汇总——实际使用中各周先写的
      往往是货品/广告段，只看品类汇总会漏掉大部分已有结论）；
    - 只读，不写；未保存/无内容时该期为空，不臆造内容。

    返回 {'kind': 'weekly'|'monthly', 'items': [...], 'missing_hint': str}。
    item.analysis 保留品类汇总文本（兼容既有消费方/测试），
    item.sections 为全段落 [{key, text}] 列表。
    """
    def _parse(sections):
        # SQL 直读的 sections 是 JSON 字符串（repo 层解析只在 get 单期时发生）。
        if isinstance(sections, str):
            try:
                import json as _json
                sections = _json.loads(sections) if sections.strip() else {}
            except Exception:
                sections = {}
        return sections or {}

    def _entry_text(entry):
        if not isinstance(entry, dict):
            return str(entry or '').strip() or None
        subs = entry.get('subsections')
        if isinstance(subs, dict):
            joined = '\n'.join(
                f"{k}: {str(v).strip()}" for k, v in subs.items() if str(v or '').strip()
            )
            if joined:
                return joined
        text = str(entry.get('text') or '').strip()
        return text or None

    def _sections_with_content(sections):
        sections = _parse(sections)
        # 老 key（v1 performance/done/…）先迁移成统一 key，前端才能对上模板标题。
        try:
            from services.period_templates import migrate_sections
            sections = migrate_sections('week', sections)
        except Exception:
            pass
        out = []
        for key, entry in (sections or {}).items():
            text = _entry_text(entry)
            if text:
                out.append({'key': key, 'text': text})
        return out

    def _item(row):
        sections = _sections_with_content(row['sections'])
        return {
            'period_key': row['period_key'],
            'status': row['status'],
            'reviewer': row['reviewer'],
            'updated_at': (row['updated_at'] or '')[:16],
            'analysis': next((s['text'] for s in sections if s['key'] == 'category_summary'), None),
            'sections': sections,
        }

    if period['type'] == 'month':
        prefix = f"{period['key']}-W"
        rows = conn.execute(
            '''SELECT period_key, status, reviewer, updated_at, sections
               FROM period_reviews
               WHERE period_type = 'week' AND period_key LIKE ? AND status = 'final'
               ORDER BY period_key ASC''',
            (f"{prefix}%",),
        ).fetchall()
        items = [_item(row) for row in rows]
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
        items = [_item(row)] if row else []
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
                       SUM(d.payment_qty) AS payment_qty,
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
        # 单品费比与概览同口径：推广花费 ÷ GSV（净费比是另一口径，勿混）。
        ad_ratio = rate(ad_spend, gsv)
        prev_ad_ratio = rate(prev_ad_spend, prev_gsv)

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
            'payment_qty': rounded(number(cur_row, 'payment_qty')),
            'refund_amount': rounded(refund_amount),
            'conversion': rounded(conversion, 6),
            'prev_conversion': rounded(prev_conversion, 6),
            'aov': rounded(aov),
            'prev_aov': rounded(prev_aov),
            'ad_spend': rounded(ad_spend),
            'prev_ad_spend': rounded(prev_ad_spend),
            'ad_ratio': rounded(ad_ratio, 6),
            'prev_ad_ratio': rounded(prev_ad_ratio, 6),
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

    # XMind「净销售 TOP10」：按净销售额排序入选（净口径与达成率一致），
    # GSV 保留为榜单列但不决定入选；旧逻辑按 GSV 排序会把含退款的水分算进“贡献”。
    # 净销售额缺失但有销售的商品不静默剔除（unknowns 会说明缺失），排序垫底。
    top_ids = [
        product_id for product_id, row in sorted(
            current.items(), key=lambda item: float(item[1].get('net_sales') or 0), reverse=True
        )
        if (row.get('net_sales') or 0) > 0 or (row.get('gsv') or 0) > 0
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

    def with_meta(product_id):
        item = decorate(product_id)
        info = meta.get(product_id, {})
        item['title'] = info.get('title') or product_id
        item['image_url'] = info.get('image_url') or ''
        item['tags'] = info.get('product_tags') or ''
        item['category'] = info.get('category') or ''
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
    # 高费比来源来自全量商品，往往不进任何 TOP 榜——必须并入 meta 查询，
    # 否则这些行拿不到标题/主图，页面上裸露商品ID（2026-10-W1 实测）。
    ids |= set(problem_sources)
    meta = _product_meta(conn, ids)
    problem_items = []
    for product_id in sorted(problem_sources, key=lambda pid: -abs(float((current.get(pid) or {}).get('gsv') or 0))):
        item = with_meta(product_id)
        item['problem_sources'] = problem_sources[product_id]
        problem_items.append(item)
    problem_items = problem_items[:20]

    # 货品汇总卡（对齐 XMind「货品-汇总」）：在架/动销/动销率 + 60 天新品动销
    # + 净销售额类目结构 TOP5。「在架」取商品库 active 总数，「动销」指本期有
    # 正向销售记录的商品数——两者口径不同，动销率分母是商品库而非榜单行数。
    listed_count = None
    try:
        scope_sql = ''
        scope_params = []
        if category_label:
            scope_sql = " AND (p.shop_label = ? OR instr(',' || p.shop_label || ',', ',' || ? || ',') > 0)"
            scope_params = [category_label, category_label]
        listed_row = conn.execute(
            f"SELECT COUNT(*) FROM products p WHERE p.status = 'active'{scope_sql}", scope_params,
        ).fetchone()
        listed_count = int(listed_row[0]) if listed_row else None
    except Exception:
        listed_count = None
    sold_count = sum(1 for row in current.values() if (row.get('gsv') or 0) > 0)
    new_sold_count = sum(1 for pid in new_ids if (current.get(pid, {}).get('gsv') or 0) > 0)
    total_structure = 0.0
    try:
        # 类目结构始终 JOIN products（_daily_scope 无品类过滤时不带 join，
        # 但 p.category 只在 products 表里）。
        structure_scope_sql = ''
        structure_scope_params = []
        if category_label:
            structure_scope_sql = " AND (p.shop_label = ? OR instr(',' || p.shop_label || ',', ',' || ? || ',') > 0)"
            structure_scope_params = [category_label, category_label]
        structure_rows = conn.execute(
            f'''SELECT COALESCE(NULLIF(p.category, ''), '未分类') AS category,
                       SUM(d.net_sales) AS net_sales
                FROM daily_data d JOIN products p ON p.product_id = d.product_id
                WHERE d.date BETWEEN ? AND ?{structure_scope_sql}
                GROUP BY category ORDER BY net_sales DESC''',
            (period['start'], period['end'], *structure_scope_params),
        ).fetchall()
    except Exception:
        structure_rows = []
    total_structure = sum(float(row['net_sales'] or 0) for row in structure_rows)
    category_structure = [
        {
            'category': row['category'],
            'net_sales': round(float(row['net_sales'] or 0), 2),
            'share': (round(float(row['net_sales'] or 0) / total_structure, 6) if total_structure else None),
        }
        for row in structure_rows[:5]
    ]

    # 产品分层汇总（XMind「下一步规划-产品分层」；口径与矩阵地图同源：
    # 引流=费比≥30%有花费、利润=利润>0 且费比<10%、动销=有动销无花费）。
    # 复盘页只引用汇总数字，完整矩阵在 products 页矩阵地图。
    segment_summary = {}
    for product_id, row in current.items():
        gsv_value = float(row.get('gsv') or 0)
        spend_value = float(row.get('ad_spend') or 0)
        profit_value = row.get('operating_profit')
        ad_ratio_value = (spend_value / gsv_value) if gsv_value and spend_value else None
        if ad_ratio_value is not None and ad_ratio_value >= 0.30:
            segment = '引流款'
        elif profit_value is not None and float(profit_value) > 0 and (ad_ratio_value is None or ad_ratio_value < 0.10):
            segment = '利润款'
        elif gsv_value > 0 and not spend_value:
            segment = '动销款'
        else:
            segment = '其他'
        entry = segment_summary.setdefault(segment, {'count': 0, 'gsv': 0.0})
        entry['count'] += 1
        entry['gsv'] += gsv_value
    segment_stats = [
        {
            'segment': key,
            'count': value['count'],
            'gsv': round(value['gsv'], 2),
            'gsv_share': (round(value['gsv'] / total_gsv, 6) if total_gsv else None),
        }
        for key, value in sorted(segment_summary.items(), key=lambda pair: -pair[1]['gsv'])
    ]

    return {
        'top': [with_meta(product_id) for product_id in top_ids],
        'decline': [with_meta(product_id) for product_id in decline_ids],
        'paid': [with_meta(product_id) for product_id in paid_ids],
        'profit': [with_meta(product_id) for product_id in profit_ids],
        'loss': [with_meta(product_id) for product_id in loss_ids],
        'new': [with_meta(product_id) for product_id in new_top_ids],
        'new_paid': [with_meta(product_id) for product_id in new_paid_ids],
        'problem_items': problem_items,
        'summary': {
            'listed_count': listed_count,
            'sold_count': sold_count,
            'sell_through_rate': (sold_count / listed_count if listed_count else None),
            'new_sold_count': new_sold_count,
            'category_structure': category_structure,
            'segment_stats': segment_stats,
        },
    }

