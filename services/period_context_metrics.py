"""复盘素材聚合子模块（自 services/period_context.py 拆分，2026-10-10）。

只读、幂等，不写入任何业务表。缺失数据一律显式标记（None / 空列表），
绝不把缺失当零值。周/月复盘以 daily_data 为主口径。
"""

from __future__ import annotations

import calendar
import logging
from datetime import date, datetime, timedelta

from db import get_db, get_shop_id
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

def _daily_scope(category_label, shop_id=None):
    """返回 (from_sql, where_sql, extra_params)。

    品类过滤沿用全站口径：命中 products.shop_label，支持多标签值（如
    '标签甲,标签乙'）按 token 匹配。category_label 为空表示不限品类。

    daily_data 是带 shop_id 的多店表：缺了店铺条件，复盘页会把其他店铺的
    经营事实聚合进当前请求（跨店泄漏 + 口径污染）。店铺条件固定排在日期之后，
    与调用方 `(start, end, *extra)` 的参数顺序一致，不要调整顺序。
    """
    scope = str(shop_id or get_shop_id())
    if category_label:
        return (
            'FROM daily_data d JOIN products p ON p.product_id = d.product_id',
            "(d.date BETWEEN ? AND ?) AND d.shop_id = ?"
            " AND (p.shop_label = ? OR instr(',' || p.shop_label || ',', ',' || ? || ',') > 0)",
            [scope, category_label, category_label],
        )
    return 'FROM daily_data d', '(d.date BETWEEN ? AND ?) AND d.shop_id = ?', [scope]

# 源端可能整列缺失的「加总」列：SUM 结果为 NULL 表示源端没提供该字段，
# 与「真的是 0」是两件事。这两者混在一起，缺失就会被渲染成 0（编造数据）。
NULLABLE_SUM_KEYS = ('cart_users', 'new_buyers', 'search_visitors', 'search_buyers')

def _empty_totals():
    return {
        'gsv': 0.0, 'refund_amount': 0.0, 'net_sales': 0.0, 'ad_spend': 0.0,
        'profit': 0.0, 'visitors': 0.0, 'buyers': 0.0, 'payment_qty': 0.0, 'pv': 0.0,
        'paid_ipv': 0.0,
        'product_count': 0, 'day_count': 0,
        'first_date': None, 'last_date': None,
        'cart_rate': None, 'fav_rate': None, 'bounce_rate': None,
        'cart_users': None, 'new_buyers': None,
        'search_visitors': None, 'search_buyers': None,
    }

def _monthly_fallback_totals(conn, start, end, category_label=None):
    """对比期日数据缺失时的 monthly_data 回退；无可回退数据返回 None。

    品类过滤沿用 _daily_scope 的 shop_label 口径；比率列（转化率/加购率）取月表
    现成列。profit=0 是月表未回填的哨兵值，按缺失处理（None），不当作真 0。

    monthly_data 是没有 shop_id 的单店旧表（db_migrations.py），只有 default
    部署能保证它属于当前店铺；非 default scope 一律不回退，宁缺勿串店。
    """
    from db import legacy_shop_id
    if str(get_shop_id()) not in ('default', legacy_shop_id()):
        return None
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
    cart_users = totals.get('cart_users')
    new_buyers = totals.get('new_buyers')
    search_visitors = totals.get('search_visitors')
    search_buyers = totals.get('search_buyers')
    # 加购率 = 加购人数 ÷ 访客数（先汇总再算比率）。此前这里直接取
    # daily_data.cart_rate 的逐行平均，会把小流量商品与大盘等权，且与
    # 「本期汇总」的 cart_users/visitors 口径打架 —— 同一周期两个加购率。
    # 源端没有 cart_users 时（如月度兜底）才退回逐行平均。
    if cart_users is not None and visitors:
        cart_rate = cart_users / visitors
    else:
        cart_rate = totals.get('cart_rate')
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
        'uv_value': (gsv / visitors) if visitors else None,
        'refund_ratio': (totals['refund_amount'] / gsv) if gsv else None,
        'cart_rate': cart_rate,
        'cart_users': cart_users,
        'new_buyers': new_buyers,
        # 新客占比 = 新买家数 ÷ 成交买家数；新买家数缺失时派生比率必然缺失。
        'new_buyer_share': (new_buyers / buyers) if (new_buyers is not None and buyers) else None,
        'search_visitors': search_visitors,
        'search_buyers': search_buyers,
        'search_conversion': (search_buyers / search_visitors) if (search_buyers is not None and search_visitors) else None,
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
            AVG(NULLIF(d.bounce_rate, 0)) AS bounce_rate,
            -- 下面四列不加 COALESCE：SUM 为 NULL 表示源端整列缺失，必须与真 0 区分。
            SUM(d.cart_users) AS cart_users,
            SUM(d.new_payment_buyers) AS new_buyers,
            SUM(d.search_ipv) AS search_visitors,
            SUM(d.search_payment_buyers) AS search_buyers
        {from_sql}
        WHERE {where_sql}
        ''',
        (start, end, *extra),
    ).fetchone()
    if row is None:
        return _empty_totals()
    totals = {key: row[key] for key in row.keys()}
    for key, value in totals.items():
        if value is None and key in NULLABLE_SUM_KEYS:
            # 源端没这一列（如 BI 日快照不含新买家数）→ 保持 None，不补 0。
            continue
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

def _breakdown_block(conn, period, category_label=None, baselines=None):
    """返回周期内更细粒度的指标行。

    月复盘拆成月内周（与 _month_bounded_weeks 同口径：W1 从 1 号到第一个周日），
    周复盘拆成逐日，日复盘只有一行。每行独立聚合并推导比率，
    缺天不补 0 行，只返回有数据的天/周。

    baselines 传 {'mom': {'start','end'}, 'yoy': {'start','end'}} 时，每行按
    「相对本期首日的偏移天数」映射到基线的同位置区间，产出 row['delta']
    （逐指标环比/同比）。用偏移映射而不是固定加减 7 天，是为了让月内分周
    （W1 天数不固定）也能对上正确的基线周。
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

    period_start = date.fromisoformat(period['start'])
    baseline_spans = {}
    for slot in ('mom', 'yoy'):
        baseline = (baselines or {}).get(slot) or {}
        if not baseline.get('start') or not baseline.get('end'):
            continue
        baseline_spans[slot] = (date.fromisoformat(baseline['start']),
                                date.fromisoformat(baseline['end']))

    rows = []
    missing_labels = []
    for span in spans:
        totals = _totals_for_range(
            conn, span['start'], span['end'], category_label,
            allow_monthly_fallback=False,
        )
        if not totals['day_count']:
            missing_labels.append(span['label'])
            continue
        derived = _derive(totals)
        if derived.get('paid_cpc') is None:
            derived['paid_cpc'] = _promotion_paid_cpc(conn, span['start'], span['end'], category_label)
        row = {
            'label': span['label'],
            'start': span['start'],
            'end': span['end'],
            'day_count': totals['day_count'],
            'metrics': {key: (round(derived[key], 4) if isinstance(derived.get(key), float) else derived.get(key))
                        for key in BREAKDOWN_METRIC_KEYS},
        }
        # 逐行同比/环比：同偏移位置的基线区间。基线缺该段数据时不输出变化率
        # （该天/该周无可比基数），由前端显示 --，不臆造。
        if baseline_spans:
            offset = (date.fromisoformat(span['start']) - period_start).days
            span_days = (date.fromisoformat(span['end']) - date.fromisoformat(span['start'])).days + 1
            delta = {}
            for slot, (base_start, base_end) in baseline_spans.items():
                target_start = base_start + timedelta(days=offset)
                target_end = target_start + timedelta(days=span_days - 1)
                if target_end > base_end:
                    delta[slot] = {key: {'comparable': False, 'reason': 'baseline_out_of_range'}
                                   for key in BREAKDOWN_METRIC_KEYS}
                    continue
                base_totals = _totals_for_range(
                    conn, target_start.isoformat(), target_end.isoformat(), category_label,
                    allow_monthly_fallback=False,
                )
                if not base_totals['day_count']:
                    delta[slot] = {key: {'comparable': False, 'reason': 'baseline_no_data'}
                                   for key in BREAKDOWN_METRIC_KEYS}
                    continue
                base_derived = _derive(base_totals)
                if base_derived.get('paid_cpc') is None:
                    base_derived['paid_cpc'] = _promotion_paid_cpc(
                        conn, target_start.isoformat(), target_end.isoformat(), category_label)
                delta[slot] = _metric_delta_map(derived, base_derived)
            row['delta'] = delta
        rows.append(row)
    # 覆盖说明随行返回：缺天是跳过不补 0（正确），但不告知会让读者以为该周期
    # 本就只有这几天。与「流量来源拆解」的覆盖提示保持同一口径。
    return {
        'grain': grain,
        'rows': rows,
        'expected_count': len(spans),
        'observed_count': len(rows),
        'missing_labels': missing_labels,
    }

def _metric_delta_map(current, baseline):
    """逐指标变化率（breakdown 行用）。

    与 _summary_base_delta 同一套规则：基线为 0 或任一值缺失时不输出变化率，
    只标原因，避免把「无基数」渲染成 -100% 这类伪事实。
    """
    delta = {}
    for key in BREAKDOWN_METRIC_KEYS:
        value = (current or {}).get(key)
        base_value = (baseline or {}).get(key)
        if value is None or base_value is None:
            delta[key] = {'comparable': False, 'reason': 'baseline_no_data'}
        elif not base_value:
            delta[key] = {'comparable': True, 'abs': round(float(value) - float(base_value), 4)}
        else:
            delta[key] = {
                'comparable': True,
                'change': round((float(value) - float(base_value)) / abs(float(base_value)) * 100, 1),
                'abs': round(float(value) - float(base_value), 4),
            }
    return delta

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
    'gsv', 'net_sales', 'profit', 'visitors', 'buyers', 'conversion', 'aov',
    'cart_users', 'cart_rate', 'new_buyers', 'new_buyer_share',
    'uv_value', 'ad_spend', 'ad_ratio', 'roi', 'paid_cpc',
)

# 本期汇总「基础数据」列（XMind 品类汇总首表）。顺序即展示顺序。
# 比率类一律由聚合后的分子/分母现算，不用逐行 AVG —— 逐行平均会被缺列行
# 拉偏，且与「先汇总再算比率」的既有口径（_derive）不一致。
SUMMARY_BASE_COLUMNS = (
    ('gsv', '成交金额', 'money'),
    ('refund_amount', '退款金额', 'money'),
    ('net_sales', '净销售额', 'money'),
    # 段标题是「销售与利润指标」，利润与费比必须在汇总里可见，否则要往下翻
    # 到 KPI 网格才看得到，汇总表就不自包含。
    ('profit', '利润', 'money'),
    ('refund_ratio', '退款率', 'percent'),
    ('visitors', '访客', 'number'),
    ('buyers', '成交买家数', 'number'),
    ('new_buyers', '新买家数', 'number'),
    ('new_buyer_share', '新客占比', 'percent'),
    ('conversion', '转化率', 'percent'),
    ('aov', '客单价', 'money'),
    ('uv_value', 'UV价值', 'money'),
    ('cart_users', '加购人数', 'number'),
    ('cart_rate', '加购率', 'percent'),
    ('search_visitors', '搜索访客数', 'number'),
    ('search_buyers', '搜索成交买家数', 'number'),
    ('search_conversion', '搜索转化率', 'percent'),
    ('ad_spend', '推广花费', 'money'),
    ('ad_ratio', '费比', 'percent'),
)


def _summary_base(conn, start, end, category_label=None):
    """本期汇总「基础数据」单区间聚合，返回 (base_dict, sample_days)。

    抽出来是为了让本期 / 环比期 / 同比期共用同一段 SQL —— 三处各写一遍，
    迟早会有一处忘了改，同比环比就和本期不是同一口径了。
    比率一律由 SUM 后的分子/分母现算，不逐行 AVG。
    """
    from_sql, where_sql, extra = _daily_scope(category_label)
    row = conn.execute(
        f'''SELECT
                SUM(d.payment_amount) AS gsv,
                SUM(d.refund_amount) AS refund_amount,
                SUM(d.net_sales) AS net_sales,
                SUM(d.operating_profit) AS profit,
                SUM(d.ad_spend) AS ad_spend,
                SUM(d.ipv) AS visitors,
                SUM(d.buyers) AS buyers,
                SUM(d.new_payment_buyers) AS new_buyers,
                SUM(d.cart_users) AS cart_users,
                SUM(d.search_ipv) AS search_visitors,
                SUM(d.search_payment_buyers) AS search_buyers,
                COUNT(DISTINCT d.date) AS sample_days
            {from_sql} WHERE {where_sql}''',
        (start, end, *extra),
    ).fetchone()
    if not row or not row['sample_days']:
        return None, 0

    def div(numerator, denominator):
        try:
            numerator, denominator = float(numerator), float(denominator)
        except (TypeError, ValueError):
            return None
        return (numerator / denominator) if denominator else None

    gsv = row['gsv']
    visitors = row['visitors']
    buyers = row['buyers']
    ad_spend = row['ad_spend']
    base = {
        'gsv': gsv,
        'refund_amount': row['refund_amount'],
        'net_sales': row['net_sales'],
        'profit': row['profit'],
        'refund_ratio': div(row['refund_amount'], gsv),
        'visitors': visitors,
        'buyers': buyers,
        'new_buyers': row['new_buyers'],
        'new_buyer_share': div(row['new_buyers'], buyers),
        'conversion': div(buyers, visitors),
        'aov': div(gsv, buyers),
        'uv_value': div(gsv, visitors),
        'cart_users': row['cart_users'],
        'cart_rate': div(row['cart_users'], visitors),
        'search_visitors': row['search_visitors'],
        'search_buyers': row['search_buyers'],
        'search_conversion': div(row['search_buyers'], row['search_visitors']),
        'ad_spend': ad_spend,
        'ad_ratio': div(ad_spend, gsv),
    }
    return base, int(row['sample_days'] or 0)


def _summary_base_delta(current_base, baseline_base, comparable):
    """逐列产出同比/环比变化率；基线不可比或缺值时不输出（不臆造百分比）。"""
    delta = {}
    for key, _label, _fmt in SUMMARY_BASE_COLUMNS:
        value = (current_base or {}).get(key)
        base_value = (baseline_base or {}).get(key)
        item = {'comparable': bool(comparable)}
        if not comparable:
            item['reason'] = 'baseline_grain_mismatch'
        elif value is None or base_value is None:
            item['reason'] = 'baseline_no_data'
        elif not base_value:
            # 基期为 0（如整期无退款）时变化率无定义，只给绝对值差。
            item['abs'] = round(float(value) - float(base_value), 4)
        else:
            item['change'] = round((float(value) - float(base_value)) / abs(float(base_value)) * 100, 1)
            item['abs'] = round(float(value) - float(base_value), 4)
        delta[key] = item
    return delta


def _summary_block(conn, period, channel_totals=None, category_label=None, baselines=None):
    """本期汇总（XMind「基础数据 / 广告汇总 / 流量汇总」）。

    回答「本期整体什么水平」——把核心基数一次列全，放在板块数据最前面，
    读者先看汇总再看拆解，不必自己从分日表心算合计。

    数据诚实性：
    - 缺失字段保持 None（前端显示 --），绝不补 0；同时回传 base_missing 让
      前端能解释哪几列没数、为什么。
    - 比率由 SUM 后的分子/分母现算（退款率=退款/成交、UV价值=成交/访客、
      搜索转化率=搜索成交买家/搜索访客…），与逐日聚合口径一致。

    广告/流量按渠道汇总复用调用方已算好的 channel_totals（同一份
    promotion 事实，避免两处各查一遍 → 未来不一致）。

    baselines 传 {'mom': {'start','end','label'}, 'yoy': {...}} 时，额外回传
    base_prev / base_yoy 与 base_delta（逐列环比/同比），让汇总表能直接给出
    「比上期 / 比去年同期」。区间由调用方按 resolve_compare 的结果给，
    这里不做周期解析（避免两处各算一套区间而漂移）。
    基线在该口径下没有日度数据（sample_days=0）时只标 comparable=False，
    不给极端百分比 —— 汇总层只查 daily_data，不回退月度表，量纲天然一致。
    """
    base, sample_days = _summary_base(conn, period['start'], period['end'], category_label)
    if base is None:
        return None

    base_prev = base_yoy = None
    base_delta = {'mom': {}, 'yoy': {}}
    comparability = {'mom': None, 'yoy': None}
    for slot, base_key in (('mom', 'base_prev'), ('yoy', 'base_yoy')):
        baseline = (baselines or {}).get(slot) or {}
        start, end = baseline.get('start'), baseline.get('end')
        if not start or not end:
            continue
        baseline_base, baseline_days = _summary_base(conn, start, end, category_label)
        comparable = bool(baseline_days)
        if base_key == 'base_prev':
            base_prev = baseline_base
        else:
            base_yoy = baseline_base
        comparability[slot] = {
            'comparable': comparable,
            'label': baseline.get('label'),
            'start': start,
            'end': end,
            'sample_days': baseline_days,
        }
        base_delta[slot] = _summary_base_delta(base, baseline_base, comparable)

    # 某列的「可用性」按原始分子判断：分子整列为 NULL（如 BI 快照不提供
    # 新买家数）时，派生比率必然也是 None，不该只报比率缺失而漏掉源列。
    missing = [key for key, _label, _fmt in SUMMARY_BASE_COLUMNS if base.get(key) is None]

    groups = (channel_totals or {}).get('groups') or []
    # 渠道行只覆盖「有计划级明细」的推广（creative 明细 + 单商品全站计划精确
    # 归因），账单口径总花费（daily_data.ad_spend）通常更大。若不把这个缺口显式
    # 摆出来，读者会把渠道行加总当成总花费，对不上账却无从解释。
    channel_spend = sum(float(group.get('ad_spend') or 0) for group in groups)
    unattributed = None
    if base['ad_spend'] and groups:
        residual = float(base['ad_spend']) - channel_spend
        if residual > max(1.0, 0.005 * float(base['ad_spend'])):
            unattributed = round(residual, 2)
    # 流量汇总：渠道级只有点击量（推广明细不提供 UV），因此列名用「点击量」
    # 而不是「访客」，不把点击伪装成访客。转化率分母是点击（非访客），
    # 与基础数据的「转化率（访客）」不同源，列名与提示都要点明，避免被横向比较。
    def div(numerator, denominator):
        try:
            numerator, denominator = float(numerator), float(denominator)
        except (TypeError, ValueError):
            return None
        return (numerator / denominator) if denominator else None

    traffic_channels = [{
        'name': group.get('name'),
        'clicks': group.get('clicks'),
        'buyers': group.get('payment_buyers'),
        'conversion': div(group.get('payment_buyers'), group.get('clicks')),
        'cpc': div(group.get('ad_spend'), group.get('clicks')),
    } for group in groups]

    return {
        'grain': 'period',
        'sample_days': sample_days,
        'period_days': period.get('total_days'),
        'base': base,
        'base_columns': [{'key': key, 'label': label, 'format': fmt}
                         for key, label, fmt in SUMMARY_BASE_COLUMNS],
        'base_missing': missing,
        # 同比/环比：基线原始值 + 逐列变化率 + 可比性（前端据此决定显示 -- 还是「不可比」）
        'base_prev': base_prev,
        'base_yoy': base_yoy,
        'base_delta': base_delta,
        'base_comparability': comparability,
        'ads_channels': groups,
        'ads_total_spend': base['ad_spend'],
        'ads_unattributed': unattributed,
        'traffic_channels': traffic_channels,
        'channel_source': (channel_totals or {}).get('source'),
        'channel_partial': bool((channel_totals or {}).get('partial')),
    }

