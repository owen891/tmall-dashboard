# -*- coding: utf-8 -*-
"""经营周期复盘（周/月）服务。

职责：
1. 提供周复盘 / 月复盘 / 日复盘的段落模板（结构由业务定义，见 WEEK_TEMPLATE / MONTH_TEMPLATE）。
2. 按周期聚合「复盘素材」：业绩全景、目标差距与达成路径、货品、市场、动作、告警、异常。
3. 素材与结论分离：素材只陈述可复现的事实，结论由运营人员填写。

设计约束：
- 只读、幂等，不写入任何业务表。
- 缺失数据一律显式标记（None / 空列表），绝不把缺失当零值。
- 周/月复盘都以 daily_data 为主口径，weekly_data 为空时也能正常工作。
"""

from __future__ import annotations

import calendar
import re
from datetime import date, datetime, timedelta

from db import get_db
from services.category_mode_service import mode_to_label
from services import category_analysis_service as category_service


TEMPLATE_VERSION = 'v1'


# ---------------------------------------------------------------------------
# 品类口径
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
# 段落模板
# ---------------------------------------------------------------------------
# materials 指向 build_context() 产出的素材块，前端按块渲染「系统给的事实」，
# 运营只需在 textarea 里补结论。required=False 的段落可留空。

WEEK_TEMPLATE = [
    {
        'key': 'performance',
        'title': '业绩全景及目标差距分析 & 达成路径',
        'hint': '先看本期业绩与目标差距，再写清楚差在哪、怎么补回来。',
        'materials': ['metrics', 'target_path'],
        'placeholder': '例：本期 GSV 完成 XX 万，距目标差 XX 万，主要缺口来自…；达成路径：加投 XX 渠道 / 提升 XX 商品转化…',
        'required': True,
    },
    {
        'key': 'market',
        'title': '市场分析（市场有什么变化、趋势、竞品有什么动作）？',
        'hint': '结合系统给的市场批次与竞店数据，写清市场端的变化和竞品动作。',
        'materials': ['market'],
        'placeholder': '例：类目整体需求上涨/下滑…；竞店 XX 在打价格战/上新…；我方需…',
        'required': False,
    },
    {
        'key': 'done',
        'title': '上周做了什么？',
        'hint': '列出本期实际完成的关键动作与结果，优先写有数据变化的。',
        'materials': ['actions_done'],
        'placeholder': '例：完成 XX 商品主图替换，点击率 +X%；调整 XX 计划出价，ROI 从 X 升到 X…',
        'required': True,
    },
    {
        'key': 'plan',
        'title': '下周计划做什么？',
        'hint': '每条计划都写清目标与验收标准，避免「持续优化」这类空话。',
        'materials': ['actions_planned'],
        'placeholder': '例：1) XX 商品补货并加投，目标 ROI≥X；2) 测试 XX 素材，目标点击率≥X%…',
        'required': True,
    },
    {
        'key': 'highlights',
        'title': '工作亮点、异常和卡点？',
        'hint': '亮点 / 异常 / 卡点分三类写；卡点要写清楚需要谁、什么资源。',
        'materials': ['anomalies', 'actions_blocked', 'alerts'],
        'placeholder': '亮点：…\n异常：…\n卡点：…（需要 XX 支持）',
        'required': True,
    },
]

MONTH_TEMPLATE = [
    {
        'key': 'category_summary',
        'title': '品类汇总与目标达成',
        'hint': '本月销售与利润总体结论、主要增长/下滑品类、需要优先处理的风险。',
        'materials': ['metrics', 'target_path'],
        'placeholder': '例：本月 GSV 完成 XX 万（达成率 XX%），利润率 X%；增长品类：…；下滑品类：…；优先风险：…',
        'required': True,
    },
    {
        'key': 'goods',
        'title': '货品复盘（爆款 / 利润款 / 新品 / 滞销与结构变化）',
        'hint': '爆款与利润款表现、新品测试结果、滞销与价格带问题、本月商品结构变化。',
        'materials': ['products'],
        'placeholder': '例：爆款 XX 贡献 XX 万；新品 XX 测试失败因…；滞销 XX 需清退；结构上…',
        'required': True,
    },
    {
        'key': 'ads',
        'title': '广告 / 推广复盘（渠道消耗、成交、ROI、费比）',
        'hint': '高效可扩大项、低效止损项及原因、素材/关键词/人群问题、费用是否在预算内。',
        'materials': ['ads'],
        'placeholder': '例：本月推广费 XX 万，费比 X%（环比 +Xpt），整体 ROI X；可扩大：…；需止损：…',
        'required': True,
    },
    {
        'key': 'campaign',
        'title': '活动复盘（目标 / 实际 / 利润费比 / 结论）',
        'hint': '活动的增量、对利润与价格体系的影响、下次继续或调整的动作。无活动可留空。',
        'materials': [],
        'placeholder': '例：XX 活动目标 XX，实际 XX，达成率 XX%；增量主要来自…；下次调整：…',
        'required': False,
    },
    {
        'key': 'market',
        'title': '市场监控（行业趋势 / 竞店动态 / 竞品动作）',
        'hint': '行业结论、增长需求与价格带机会、高竞争赛道、竞店与竞品的关键动作。',
        'materials': ['market'],
        'placeholder': '例：行业成交额环比 +X%，主流价格带下移；竞店 XX 主推…；竞品 XX 上新/调价…；我方应对：…',
        'required': False,
    },
    {
        'key': 'summary',
        'title': '本月总结（亮点 / 核心问题 / 未达成原因 / 需要的支持）',
        'hint': '亮点与核心问题各 3 条以内；未达成原因要区分「已验证」和「待验证假设」。',
        'materials': ['anomalies', 'alerts'],
        'placeholder': '亮点：1) … 2) …\n核心问题：1) … 2) …\n未达成原因（待验证）：…\n需要的支持：预算/货品/权限…',
        'required': True,
    },
    {
        'key': 'next_plan',
        'title': '下月计划（经营目标 / 品类货品计划 / 月度节奏 / 行动计划）',
        'hint': '目标要可验收；行动项必须有负责人、截止日期和验收方式。',
        'materials': ['actions_planned'],
        'placeholder': '目标：GSV XX 万 / 利润率 X%\n品类货品：…\n月度节奏：W1…W4…\n行动计划：P0 …（负责人 / 截止 / 验收）',
        'required': True,
    },
]

DAY_TEMPLATE = [
    {
        'key': 'performance',
        'title': '当日业绩与目标差距',
        'hint': '当日业绩结论、差距原因与补救动作。',
        'materials': ['metrics', 'target_path'],
        'placeholder': '例：当日 GSV XX，达成率 XX%，偏差来自…',
        'required': True,
    },
    {
        'key': 'anomaly',
        'title': '当日异常与卡点',
        'hint': '数据异常、执行卡点、需要支持的事项。',
        'materials': ['anomalies', 'alerts'],
        'placeholder': '异常：…\n卡点：…',
        'required': False,
    },
    {
        'key': 'plan',
        'title': '次日计划',
        'hint': '次日要做的关键动作与预期结果。',
        'materials': ['actions_planned'],
        'placeholder': '例：1) … 2) …',
        'required': False,
    },
]

TEMPLATES = {'day': DAY_TEMPLATE, 'week': WEEK_TEMPLATE, 'month': MONTH_TEMPLATE}

PERIOD_TYPES = ('day', 'week', 'month')

_ISO_WEEK_KEY_RE = re.compile(r'^\d{4}-W\d{2}$')
_MONTH_WEEK_KEY_RE = re.compile(r'^(\d{4})-(\d{2})-W(\d)$')


# ---------------------------------------------------------------------------
# 周期解析
# ---------------------------------------------------------------------------


def _month_bounded_weeks(year, month):
    """计算某年某月的月内分周列表。

    返回 [(week_num, start_date, end_date), ...]，周不跨月：
    - 第 1 周：从 1 号到第一个周日
    - 中间周：周一到周日
    - 最后一周：从最后一个周一到月末
    """
    first_day = date(year, month, 1)
    last_day_num = calendar.monthrange(year, month)[1]
    last_day = date(year, month, last_day_num)

    weeks = []
    # 第 1 周：1 号到第一个周日
    first_sunday = first_day + timedelta(days=(6 - first_day.weekday()) % 7)
    if first_sunday > last_day:
        first_sunday = last_day
    weeks.append((1, first_day, first_sunday))

    # 中间周和最后一周
    current = first_sunday + timedelta(days=1)
    while current <= last_day:
        week_start = current
        week_end = current + timedelta(days=6)
        if week_end > last_day:
            week_end = last_day
        weeks.append((len(weeks) + 1, week_start, week_end))
        current = week_end + timedelta(days=1)

    return weeks


def _month_time_progress(end):
    """月内时间进度 = 周期结束日 / 当月天数（对齐用户「经营目标」表）。

    用户表实测：9 月 W1(9/1-6)=6/30=20.00%、W2(9/7-13)=13/30=43%、
    W3(9/14-20)=20/30=67%、W4(9/21-27)=27/30=90%、W5(9/28-30)=30/30=100%。
    它只跟**结束日**有关，所以月复盘恒为 100%、在途周也照常给值（用户表同样如此）。
    """
    days_in_month = calendar.monthrange(end.year, end.month)[1]
    return end.day / days_in_month


def resolve_period(period_type, period_key, today=None):
    """把周期键解析为起止日期、环比区间、同比区间与展示标签。"""
    today = today or date.today()
    if period_type == 'day':
        start = end = date.fromisoformat(period_key)
        prev_start = prev_end = start - timedelta(days=1)
        try:
            yoy_start = yoy_end = start.replace(year=start.year - 1)
        except ValueError:  # 2 月 29 日
            yoy_start = yoy_end = start.replace(year=start.year - 1, day=28)
    elif period_type == 'week':
        mb = _MONTH_WEEK_KEY_RE.match(period_key)
        if mb:
            # 月内分周：YYYY-MM-WN
            year, month, week_num = int(mb.group(1)), int(mb.group(2)), int(mb.group(3))
            weeks = _month_bounded_weeks(year, month)
            if week_num < 1 or week_num > len(weeks):
                raise ValueError(f'周数超出范围（1-{len(weeks)}）')
            _, start, end = weeks[week_num - 1]
            # 环比上一期：同月则取上一周，跨月则取上月最后一周
            if week_num > 1:
                _, prev_start, prev_end = weeks[week_num - 2]
            else:
                prev_year, prev_month = (year - 1, 12) if month == 1 else (year, month - 1)
                prev_weeks = _month_bounded_weeks(prev_year, prev_month)
                _, prev_start, prev_end = prev_weeks[-1]
            # 同比去年同期同月同周
            yoy_weeks = _month_bounded_weeks(year - 1, month)
            if week_num <= len(yoy_weeks):
                _, yoy_start, yoy_end = yoy_weeks[week_num - 1]
            else:
                _, yoy_start, yoy_end = yoy_weeks[-1]
        else:
            # 兼容 ISO 周：YYYY-WNN
            year, week = int(period_key[:4]), int(period_key[-2:])
            start = date.fromisocalendar(year, week, 1)
            end = start + timedelta(days=6)
            prev_start, prev_end = start - timedelta(days=7), end - timedelta(days=7)
            try:
                yoy_start = date.fromisocalendar(year - 1, week, 1)
            except ValueError:  # 去年没有第 53 周
                yoy_start = start - timedelta(days=364)
            yoy_end = yoy_start + timedelta(days=6)
    elif period_type == 'month':
        year, month = int(period_key[:4]), int(period_key[5:7])
        start = date(year, month, 1)
        end = date(year, month, calendar.monthrange(year, month)[1])
        prev_last = start - timedelta(days=1)
        prev_start = prev_last.replace(day=1)
        prev_end = prev_last
        yoy_start = start.replace(year=year - 1)
        yoy_end = end.replace(year=year - 1)
    else:
        raise ValueError('周期类型必须为 day、week 或 month')

    total_days = (end - start).days + 1
    if today < start:
        elapsed_days = 0
    elif today > end:
        elapsed_days = total_days
    else:
        elapsed_days = (today - start).days + 1

    return {
        'type': period_type,
        'key': period_key,
        'start': start.isoformat(),
        'end': end.isoformat(),
        'label': _period_label(period_type, period_key, start, end),
        'total_days': total_days,
        'elapsed_days': elapsed_days,
        'remaining_days': max(total_days - elapsed_days, 0),
        # 月内时间进度 = 本周期结束日 / 当月天数（对齐用户「经营目标」表）。
        # 用户表里这是**每个周期一个值**（跨 4 行合并单元格），不是逐指标算的：
        # 9 月 W1=6/30=20.00%、W2=13/30=43%、W3=20/30=67%、W4=27/30=90%、W5=30/30=100%。
        # 注意它按周期**结束日**算，不看 today，所以在途周期也有值。
        'time_progress': _month_time_progress(end),
        'is_ongoing': start <= today <= end,
        'prev': {'start': prev_start.isoformat(), 'end': prev_end.isoformat()},
        'yoy': {'start': yoy_start.isoformat(), 'end': yoy_end.isoformat()},
        'prev_key': _key_for(period_type, prev_start),
        'yoy_key': _key_for(period_type, yoy_start),
        'prev_label': _period_label(period_type, _key_for(period_type, prev_start), prev_start, prev_end),
        'yoy_label': _period_label(period_type, _key_for(period_type, yoy_start), yoy_start, yoy_end),
    }


def _key_for(period_type, day):
    """把某个日期折算成同类型的周期键（用于环比/同比/自定义对比）。"""
    if period_type == 'day':
        return day.isoformat()
    if period_type == 'week':
        # 月内分周：YYYY-MM-WN
        weeks = _month_bounded_weeks(day.year, day.month)
        for week_num, start, end in weeks:
            if start <= day <= end:
                return f'{day.year:04d}-{day.month:02d}-W{week_num}'
        return f'{day.year:04d}-{day.month:02d}-W1'
    return f'{day.year:04d}-{day.month:02d}'


_WEEKDAY_CN = ('周一', '周二', '周三', '周四', '周五', '周六', '周日')


def _period_label(period_type, period_key, start, end):
    if period_type == 'day':
        return f'{start.isoformat()}（{_WEEKDAY_CN[start.weekday()]}）'
    if period_type == 'week':
        if _MONTH_WEEK_KEY_RE.match(period_key):
            month = int(period_key[5:7])
            week_num = int(period_key[-1])
            return f'{start.year}年{month}月第{week_num}周（{start.strftime("%m-%d")} ~ {end.strftime("%m-%d")}）'
        return f'{period_key[:4]}年第{int(period_key[-2:])}周（{start.strftime("%m-%d")} ~ {end.strftime("%m-%d")}）'
    return f'{start.year}年{start.month}月'


# ---------------------------------------------------------------------------
# 对比周期
# ---------------------------------------------------------------------------

COMPARE_MODES = ('previous', 'yoy', 'custom', 'none')


def resolve_compare(period, compare_mode=None, compare_period_key=None):
    """解析对比周期。

    previous -> 环比上一期（默认）
    yoy      -> 同比去年同期
    custom   -> 调用方指定的同类型周期键（可自选对比周期）
    none     -> 不对比
    对比区间与主周期走完全相同的聚合口径，保证可比性。
    """
    mode = compare_mode if compare_mode in COMPARE_MODES else 'previous'

    if mode == 'none':
        return {'mode': 'none', 'available': False, 'short_label': '',
                'period_key': None, 'label': None, 'start': None, 'end': None}

    def comparable_range(start, end):
        """Limit an in-progress review baseline to the same elapsed days."""
        start_date = date.fromisoformat(start)
        end_date = date.fromisoformat(end)
        elapsed_days = max(1, int(period.get('elapsed_days') or period.get('total_days') or 1))
        span_days = (end_date - start_date).days + 1
        end_date = min(end_date, start_date + timedelta(days=min(elapsed_days, span_days) - 1))
        return start, end_date.isoformat()

    if mode == 'custom':
        key = str(compare_period_key or '').strip()
        if key:
            span = resolve_period(period['type'], key)
            start, end = comparable_range(span['start'], span['end'])
            return {'mode': 'custom', 'available': True, 'short_label': '对比',
                    'period_key': key, 'label': span['label'],
                    'start': start, 'end': end}
        # 只给了 custom 但没给周期键时退回环比，避免静默给出错误的基线。
        mode = 'previous'

    if mode == 'yoy':
        start, end = comparable_range(period['yoy']['start'], period['yoy']['end'])
        return {'mode': 'yoy', 'available': True, 'short_label': '同比',
                'period_key': period['yoy_key'], 'label': period['yoy_label'],
                'start': start, 'end': end}

    start, end = comparable_range(period['prev']['start'], period['prev']['end'])
    return {'mode': 'previous', 'available': True, 'short_label': '环比',
            'period_key': period['prev_key'], 'label': period['prev_label'],
            'start': start, 'end': end}


def recent_periods(period_type, period_key, limit=18):
    """当前周期往前若干期，供「自定义对比周期」下拉选择。"""
    options = []
    key = period_key
    for _ in range(max(1, limit)):
        span = resolve_period(period_type, key)
        options.append({'key': key, 'label': span['label'], 'start': span['start'], 'end': span['end']})
        key = span['prev_key']
    return options


def available_periods(period_type, limit=120):
    """Return selectable review periods covered by the daily facts."""
    if period_type not in ('week', 'month'):
        return []
    with get_db() as conn:
        rows = conn.execute(
            'SELECT DISTINCT date FROM daily_data WHERE date IS NOT NULL ORDER BY date DESC'
        ).fetchall()

    options = {}
    for row in rows:
        raw_date = str(row['date'] or '')
        try:
            period_key = _key_for(period_type, date.fromisoformat(raw_date))
            if period_key in options:
                continue
            span = resolve_period(period_type, period_key)
            options[period_key] = {
                'key': period_key,
                'label': span['label'],
                'start': span['start'],
                'end': span['end'],
            }
            if len(options) >= max(1, int(limit or 120)):
                break
        except (TypeError, ValueError):
            continue
    return list(options.values())


# ---------------------------------------------------------------------------
# 指标聚合
# ---------------------------------------------------------------------------


def _empty_totals():
    return {
        'gsv': 0.0, 'refund_amount': 0.0, 'net_sales': 0.0, 'ad_spend': 0.0,
        'profit': 0.0, 'visitors': 0.0, 'buyers': 0.0, 'payment_qty': 0.0, 'pv': 0.0,
        'product_count': 0, 'day_count': 0,
        'first_date': None, 'last_date': None,
        'cart_rate': None, 'fav_rate': None, 'bounce_rate': None,
    }


def _totals_for_range(conn, start, end, category_label=None):
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
    return {
        'gsv': gsv,
        'net_sales': net_sales,
        'refund_amount': totals['refund_amount'],
        'ad_spend': ad_spend,
        'profit': totals['profit'],
        'visitors': visitors,
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


def _products_block(conn, period, category_label=None, compare_range=None):
    from_sql, where_sql, extra = _daily_scope(category_label)
    # 下滑榜以「所选对比周期」为基线，保证与指标卡的口径一致。
    baseline = compare_range or period['prev']

    top_rows = conn.execute(
        f'''SELECT d.product_id,
                  SUM(d.payment_amount) AS gsv,
                  SUM(d.net_sales) AS net_sales,
                  SUM(d.buyers) AS buyers,
                  SUM(d.ad_spend) AS ad_spend
           {from_sql} WHERE {where_sql}
           GROUP BY d.product_id HAVING gsv > 0
           ORDER BY gsv DESC LIMIT 10''',
        (period['start'], period['end'], *extra),
    ).fetchall()

    decline_rows = conn.execute(
        f'''SELECT cur.product_id,
                  cur.gsv AS gsv,
                  prev.gsv AS prev_gsv,
                  cur.gsv - prev.gsv AS delta
           FROM (SELECT d.product_id, SUM(d.payment_amount) AS gsv {from_sql}
                 WHERE {where_sql} GROUP BY d.product_id) cur
           JOIN (SELECT d.product_id, SUM(d.payment_amount) AS gsv {from_sql}
                 WHERE {where_sql} GROUP BY d.product_id) prev
             ON prev.product_id = cur.product_id
           WHERE prev.gsv > 0 AND cur.gsv < prev.gsv
           ORDER BY delta ASC LIMIT 10''',
        (period['start'], period['end'], *extra, baseline['start'], baseline['end'], *extra),
    ).fetchall()

    ids = [row['product_id'] for row in top_rows] + [row['product_id'] for row in decline_rows]
    meta = _product_meta(conn, set(ids))

    def decorate(rows, with_delta=False):
        result = []
        for row in rows:
            info = meta.get(row['product_id'], {})
            item = {
                'product_id': row['product_id'],
                'title': info.get('title') or row['product_id'],
                'image_url': info.get('image_url') or '',
                'tags': info.get('product_tags') or '',
                'gsv': round(float(row['gsv'] or 0), 2),
            }
            if with_delta:
                item['prev_gsv'] = round(float(row['prev_gsv'] or 0), 2)
                item['delta'] = round(float(row['delta'] or 0), 2)
            result.append(item)
        return result

    return {'top': decorate(top_rows), 'decline': decorate(decline_rows, with_delta=True)}


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
# 市场
# ---------------------------------------------------------------------------


def _market_block_legacy(conn):
    try:
        run = conn.execute(
            'SELECT id, analysis_date, period_start, period_end, source FROM market_analysis_runs '
            'ORDER BY analysis_date DESC, id DESC LIMIT 1',
        ).fetchone()
    except Exception:
        # 市场分析表由导入流程创建，尚未导入时视为无素材。
        return {'available': False, 'run': None, 'categories': [], 'rivals': []}
    if not run:
        return {'available': False, 'run': None, 'categories': [], 'rivals': []}

    try:
        categories = conn.execute(
            '''SELECT category, trend_up, trend_down, trend_new, concentration_top10,
                      concentration_top50, total_buyers
               FROM market_category_stats WHERE run_id = ?
               ORDER BY total_buyers DESC LIMIT 8''',
            (run['id'],),
        ).fetchall()
    except Exception:
        categories = []

    rivals = []
    try:
        rival_rows = conn.execute(
            '''SELECT shop_name, pay_buyer_count, uv, pay_rate, stat_date
               FROM sycm_market_rival_shop
               WHERE stat_date = (SELECT MAX(stat_date) FROM sycm_market_rival_shop)
               ORDER BY pay_buyer_count DESC LIMIT 10''',
        ).fetchall()
        rivals = [dict(row) for row in rival_rows]
    except Exception:
        rivals = []

    return {
        'available': True,
        'run': dict(run),
        'categories': [dict(row) for row in categories],
        'rivals': rivals,
    }


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


# ---------------------------------------------------------------------------
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
        actions = _actions_block(conn, period, category_label)
        alerts = _alerts_block(conn)
        anomalies = _anomalies_block(conn, period, current, prev, category_label)

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
        },
        # 达成率口径 = 净销售额 ÷ 目标（与经营目标表一致）。
        # 早期误用 GSV 作分子，会把含退款的支付金额算进达成率，系统性偏高约 20%。
        'target_path': _target_path(period, target, target_source, current['net_sales'], category_label,
                                    targets=_target_rows(current, saved_review)),
        'products': products,
        'ads': _ads_block(current, prev),
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
        'alerts': alerts,
        'anomalies': anomalies,
        'missing_inputs': missing_inputs,
    }


# ---------------------------------------------------------------------------
# 指标矩阵 / 类目拆解（新增）
# ---------------------------------------------------------------------------

# 矩阵表暴露的字段。value 为 None 表示该列在当前数据里不存在或无值。
MATRIX_METRICS = [
    ('net_sales', '净销售额', 'money', False),
    ('payment_conversion_rate', '转化率', 'percent', False),
    ('cart_rate', '加购率', 'percent', False),
    ('ad_spend', '推广花费', 'money', False),
    ('expense_ratio', '净费比', 'percent', True),
    ('ad_roi', '投产比', 'decimal', False),
    ('refund_rate', '退款率', 'percent', True),
    ('operating_profit', '利润(支付预估)', 'money', False),
    ('profit_rate', '利润率', 'percent', False),
]

# 来自 BI「商品总览」的推广平台明细原始列，需要单独求和。
# 注意：无界花费/无界成交不在这里——BI 导出的「万相台」列在近两年整列为
# '--' 或 0，真实无界数据来自万相台后台采集表 promotion_daily_facts，
# 见 _wujie_totals()。
PROMO_DETAIL_COLUMNS = (
    'product_sitewide_spend', 'product_sitewide_payment',
    'gift_cost', 'brand_marketing_spend',
)

# 推广平台明细列。口径与来源列一一对应，缺数据时值为 None（前端显示 --）。
# 「商品营销托管花费」= 品牌新享营销托管软件服务费；
# 「礼金总费用」= 首单礼金 / 品牌新享首单礼金。
MATRIX_PROMO_METRICS = [
    ('wujie_spend', '无界花费', 'money', False),
    ('wujie_roi', '无界总ROI', 'decimal', False),
    ('wujie_expense_ratio', '无界净费比', 'percent', True),
    ('brand_marketing_spend', '商品营销托管花费', 'money', False),
    ('gift_cost', '礼金总费用', 'money', False),
    ('product_sitewide_spend', '货品全站推花费', 'money', False),
]


def _metric_item(key, label, fmt, lower_better, current, previous):
    value = current.get(key)
    prev_value = previous.get(key) if previous else None
    item = {
        'key': key, 'label': label, 'format': fmt, 'lower_better': lower_better,
        'value': value, 'prev_value': prev_value,
    }
    if value is not None and prev_value not in (None, 0):
        item['change_rate'] = round((value - prev_value) / abs(prev_value), 6)
    return item


def _row_status(metrics):
    """根据关键指标给出行状态（success / warning / danger / normal）。

    规则可按业务调整；当前默认：
    - 本期与上期都没有净销售额 -> unknown（无数据）
    - 利润率为负 -> danger
    - 净销售额环比降幅 >= 20% -> danger
    - 净销售额环比增幅 >= 20% -> success
    - 费比环比上升 >= 5pt -> warning
    """
    net_sales = metrics.get('net_sales') or {}
    profit_rate = metrics.get('profit_rate') or {}
    expense_ratio = metrics.get('expense_ratio') or {}

    # 两期都没有净销售额 => 这个周期压根没有数据。
    # 不能落到 'normal'（正常），否则表格会出现「显示正常但整行是 --」的误导。
    if net_sales.get('value') is None and net_sales.get('prev_value') is None:
        return 'unknown'

    if (profit_rate.get('value') is not None and profit_rate['value'] < 0):
        return 'danger'
    change = net_sales.get('change_rate')
    if change is not None and change <= -0.20:
        return 'danger'
    if change is not None and change >= 0.20:
        return 'success'
    expense_change = expense_ratio.get('change_rate')
    if expense_change is not None and expense_change >= 0.05:
        return 'warning'
    return 'normal'


# 无界数据来源：万相台后台采集的推广域事实表。
# 商品维度 channel='全部' 的行即该商品当日的无界总消耗与总成交。
WUJIE_SOURCE_TABLE = 'promotion_daily_facts'


def _wujie_totals(conn, start, end, category_mode, group_by_category=False):
    """从万相台后台事实表取「无界」花费与成交。

    BI 日度导出的「万相台」列在近两年整列为 '--' 或 0（平台侧没把无界
    消耗拆到商品），因此无界花费只能走推广域采集表。该表覆盖
    2025-09、2026-08、2026-09 等周期；缺覆盖的周期返回 None，
    前端显示 '--' 而不是 0。

    过滤条件说明：
    - grain='product' + channel='全部'：避免与计划/单元维度重复计数；
    - product_id 以 '-' 开头的是账户级汇总哨兵行（-998/-999），不是商品；
    - source_batch_id 为空的历史行是月度汇总被塞进月末日期，不是日度事实。
    """
    if group_by_category:
        empty: object = {}
    else:
        empty = (None, None)
    table = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (WUJIE_SOURCE_TABLE,),
    ).fetchone()
    if not table:
        return empty

    label = mode_to_label(category_mode)
    clauses = [
        'f.date >= ?', 'f.date <= ?',
        "f.grain = 'product'", "f.channel = '全部'",
        "f.product_id NOT LIKE '-%'",
        'f.source_batch_id IS NOT NULL',
    ]
    params = [start.isoformat(), end.isoformat()]
    if label:
        clauses.append("(p.shop_label = ? OR instr(',' || p.shop_label || ',', ',' || ? || ',') > 0)")
        params.extend([label, label])

    if group_by_category:
        select = "COALESCE(p.category, '未分类') AS grp, SUM(f.ad_spend) AS spend, SUM(f.attributed_payment_amount) AS pay"
        tail = 'GROUP BY grp'
    else:
        select = 'SUM(f.ad_spend) AS spend, SUM(f.attributed_payment_amount) AS pay'
        tail = ''

    query = (f'SELECT {select} FROM {WUJIE_SOURCE_TABLE} f '
             f'LEFT JOIN products p ON p.product_id = f.product_id '
             f"WHERE {' AND '.join(clauses)} {tail}")
    rows = conn.execute(query, params).fetchall()

    def pair(row):
        spend = row['spend']
        pay = row['pay']
        return (float(spend) if spend is not None else None,
                float(pay) if pay is not None else None)

    if group_by_category:
        return {row['grp']: pair(row) for row in rows}
    if not rows:
        return empty
    return pair(rows[0])


def _matrix_aggregate(conn, start, end, category_mode, group_by_category=False):
    """聚合日事实，并补齐 category_analysis_service 未覆盖的加购率 / 投产比。

    category_service.BASE_METRICS 不含 cart_rate / ad_roi，直接复用 _summarize
    会让这两列永远为空。这里在它的基础上补算：
    - cart_rate：按行取非零日均值（与复盘服务的口径一致）
    - ad_roi：支付金额 / 推广花费（费用为 0 时返回 None，不臆造）
    """
    label = mode_to_label(category_mode)
    clauses = ['d.date >= ?', 'd.date <= ?']
    params = [start.isoformat(), end.isoformat()]
    if label:
        clauses.append("(p.shop_label = ? OR instr(',' || p.shop_label || ',', ',' || ? || ',') > 0)")
        params.extend([label, label])

    columns = {row['name'] for row in conn.execute('PRAGMA table_info(daily_data)').fetchall()}
    select = ['d.date', 'd.product_id']
    if group_by_category:
        select.append('p.category')
    select += [f'd.{c}' for c in category_service.BASE_METRICS.values() if c in columns]
    for c in category_service.COST_COLUMNS + (category_service.PROFIT_SOURCE_COLUMN,):
        if c in columns and c not in category_service.BASE_METRICS.values():
            select.append(f'd.{c}')
    if 'cart_rate' in columns:
        select.append('d.cart_rate')
    for c in PROMO_DETAIL_COLUMNS:
        if c in columns:
            select.append(f'd.{c}')

    query = (f"SELECT {', '.join(select)} FROM daily_data d "
             f"LEFT JOIN products p ON p.product_id=d.product_id "
             f"WHERE {' AND '.join(clauses)} ORDER BY d.date")
    rows = [dict(row) for row in conn.execute(query, params).fetchall()]

    wujie_total = _wujie_totals(conn, start, end, category_mode)
    wujie_groups = _wujie_totals(conn, start, end, category_mode, group_by_category=True)

    def apply_wujie(totals, wujie):
        """写入无界花费/成交，并据此推导无界 ROI 与无界净费比。"""
        spend, pay = wujie if wujie else (None, None)
        totals['wujie_spend'] = spend
        totals['wujie_payment'] = pay
        totals['wujie_roi'] = (pay / spend
                               if spend not in (None, 0) and pay is not None else None)
        net_sales = totals.get('net_sales')
        totals['wujie_expense_ratio'] = (spend / net_sales
                                         if net_sales not in (None, 0) and spend is not None else None)
        return totals

    def summarize(group_rows, key=None):
        totals, _, basis = category_service._summarize(group_rows)
        # 加购率：只统计有值的行，避免 0 值把均值拉低
        rates = [float(r['cart_rate']) for r in group_rows
                 if r.get('cart_rate') not in (None, 0)]
        totals['cart_rate'] = sum(rates) / len(rates) if rates else None
        ad_spend = totals.get('ad_spend')
        payment = totals.get('payment_amount')
        totals['ad_roi'] = (payment / ad_spend) if ad_spend not in (None, 0) and payment is not None else None

        # 推广平台明细：只在确实存在数值时才求和；全列为 NULL 时保持 None，
        # 这样「平台当期没投放」不会被渲染成 0 费比。
        for column in PROMO_DETAIL_COLUMNS:
            present = [float(r[column]) for r in group_rows
                       if r.get(column) is not None]
            totals[column] = sum(present) if present else None

        apply_wujie(totals, wujie_groups.get(key) if key is not None else wujie_total)
        return totals, basis

    if not group_by_category:
        totals, basis = summarize(rows)
        return totals, basis, rows

    grouped: dict[str, list[dict]] = {}
    for row in rows:
        cat = row.get('category') or '未分类'
        grouped.setdefault(cat, []).append(row)
    return grouped, summarize


def _short_category(name):
    """把「A>B>C」类目路径压成末级名称，便于表格展示。"""
    text = str(name or '').strip()
    if not text:
        return '未分类'
    for sep in ('>', '/', '|', '\\'):
        if sep in text:
            text = text.split(sep)[-1].strip()
    return text or '未分类'


def _matrix_metrics(current, previous):
    """把两组汇总值转成前端矩阵列所需的指标字典。"""
    metrics = {}
    for key, label, fmt, lower_better in MATRIX_METRICS + MATRIX_PROMO_METRICS:
        metrics[key] = _metric_item(key, label, fmt, lower_better, current, previous)
    return metrics


def _build_matrix_row(conn, period_type, period_key, category_mode):
    """聚合单个周期的指标，并自动查找上一周期作为对比基线。"""
    period = resolve_period(period_type, period_key)
    prev_period = resolve_period(period_type, period['prev_key'])
    start = date.fromisoformat(period['start'])
    end = date.fromisoformat(period['end'])
    prev_start = date.fromisoformat(prev_period['start'])
    prev_end = date.fromisoformat(prev_period['end'])

    current, profit_basis, _ = _matrix_aggregate(conn, start, end, category_mode)
    previous, _, _ = _matrix_aggregate(conn, prev_start, prev_end, category_mode)
    metrics = _matrix_metrics(current, previous)

    return {
        'period_key': period['key'],
        'label': period['label'],
        'start': period['start'],
        'end': period['end'],
        'status': _row_status(metrics),
        'profit_basis': profit_basis,
        'metrics': metrics,
    }


def build_metrics_matrix(period_type, period_key, category_mode=None, limit=8):
    """返回最近 N 个周期的指标矩阵，用于周月复盘的「指标矩阵」表格。

    每期自动与上一周期环比，保证口径一致。
    """
    period = resolve_period(period_type, period_key)
    periods = [period]
    for _ in range(max(1, limit) - 1):
        prev = resolve_period(period_type, periods[-1]['prev_key'])
        periods.append(prev)
    periods.reverse()  # 从旧到新，表格按时间正序展示

    rows = []
    with get_db() as conn:
        for p in periods:
            rows.append(_build_matrix_row(conn, period_type, p['key'], category_mode))
    return {
        'period_type': period_type,
        'period_key': period_key,
        'category': {'mode': category_mode or 'all', 'label': mode_to_label(category_mode)},
        'columns': MATRIX_METRICS + MATRIX_PROMO_METRICS,
        'rows': rows,
    }


def build_category_breakdown(period_type, period_key, category_mode=None):
    """返回当前周期按 products.category 拆分的指标表。"""
    period = resolve_period(period_type, period_key)
    prev_period = resolve_period(period_type, period['prev_key'])
    start = date.fromisoformat(period['start'])
    end = date.fromisoformat(period['end'])
    prev_start = date.fromisoformat(prev_period['start'])
    prev_end = date.fromisoformat(prev_period['end'])

    with get_db() as conn:
        current_groups, summarize_current = _matrix_aggregate(conn, start, end, category_mode, group_by_category=True)
        previous_groups, summarize_previous = _matrix_aggregate(
            conn, prev_start, prev_end, category_mode, group_by_category=True)

    categories = sorted(set(current_groups.keys()) | set(previous_groups.keys()))
    rows = []
    for cat in categories:
        # 两期必须各用各自的 summarize：它闭包了本期的无界数据，
        # 混用会让上期的无界花费等于本期，环比恒为 0。
        current, _ = summarize_current(current_groups.get(cat, []), cat)
        previous, _ = summarize_previous(previous_groups.get(cat, []), cat)
        metrics = _matrix_metrics(current, previous)

        # 过滤口径噪声：净销售额、投放、盈亏全部低于 100 元的行不展示。
        # 这类行（例如净销 0.03 元的「赠品」）多为错挂类目，
        # 不足以支撑一次复盘判断，留在表里只会制造噪声。
        MIN_SIGNAL = 100
        has_signal = any(
            abs(metrics[key].get(k) or 0) >= MIN_SIGNAL
            for key in ('net_sales', 'ad_spend', 'wujie_spend', 'operating_profit')
            for k in ('value', 'prev_value')
        )
        if not has_signal:
            continue

        rows.append({
            'category': _short_category(cat),
            'category_path': cat,
            'status': _row_status(metrics),
            'metrics': metrics,
        })

    # 按净销售额降序，未分类放最后
    rows.sort(key=lambda r: (r['category'] == '未分类', -(r['metrics']['net_sales']['value'] or 0)))

    return {
        'period_type': period_type,
        'period_key': period_key,
        'category': {'mode': category_mode or 'all', 'label': mode_to_label(category_mode)},
        'columns': MATRIX_METRICS + MATRIX_PROMO_METRICS,
        'period': {'label': period['label'], 'start': period['start'], 'end': period['end']},
        'rows': rows,
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

    summary = text_of('performance') or text_of('category_summary') or (joined[0] if joined else '')
    conclusions = text_of('highlights') or text_of('summary') or (joined[1] if len(joined) > 1 else '')
    next_actions = text_of('plan') or text_of('next_plan') or (joined[-1] if joined else '')

    fallback = '（未填写）'
    return {
        'summary': summary or fallback,
        'conclusions': conclusions or fallback,
        'next_actions': next_actions or fallback,
    }


# Keep the product diagnosis payload close to the period-review service contract.
# This definition intentionally lives after the legacy implementation so old
# callers keep their public shape while build_context() gets the richer data.
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

    ids = set(top_ids + decline_ids)
    meta = _product_meta(conn, ids)

    def with_meta(product_id):
        item = decorate(product_id)
        info = meta.get(product_id, {})
        item['title'] = info.get('title') or product_id
        item['image_url'] = info.get('image_url') or ''
        item['tags'] = info.get('product_tags') or ''
        return item

    return {
        'top': [with_meta(product_id) for product_id in top_ids],
        'decline': [with_meta(product_id) for product_id in decline_ids],
    }
