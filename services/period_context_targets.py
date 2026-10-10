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

TARGET_METRICS = (
    ('net_sales', '销售额', 'money', False, 'high'),
    ('profit', '净利润额', 'money', False, 'high'),
    ('ad_spend', '推广费', 'money', False, 'low'),
    ('net_expense_ratio', '净费比', 'percent', True, 'high'),
)

TARGET_FORM_FIELDS = {
    'target_amount': 'net_sales',
    'target_profit': 'profit',
    'target_ad_spend': 'ad_spend',
    'target_net_expense_ratio': 'net_expense_ratio',
}
