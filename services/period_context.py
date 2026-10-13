# -*- coding: utf-8 -*-
"""复盘素材聚合：业绩全景、目标路径、货品/市场/动作/告警等素材块。

设计约束：
- 只读、幂等，不写入任何业务表。
- 缺失数据一律显式标记（None / 空列表），绝不把缺失当零值。
- 周/月复盘都以 daily_data 为主口径。
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


from services.period_context_metrics import (
    _daily_scope,
    _empty_totals,
    _monthly_fallback_totals,
    _derive,
    _baseline_grain_comparable,
    _comparability,
    _metric_items,
    _totals_for_range,
    _promotion_paid_cpc,
    _breakdown_block,
    _summary_block,
    METRIC_DEFS,
    BREAKDOWN_METRIC_KEYS,
    SUMMARY_BASE_COLUMNS,
)
from services.period_context_ads import (
    _rate_change,
    _channel_derived_metrics,
    _campaign_attribution,
    _attribution_channel_rows,
    _ads_direct_totals,
    _ads_channel_totals,
    _ads_block,
    _traffic_dimension,
    _promotion_dimension,
    _product_trend,
    _product_meta,
    PROMOTION_CHANNEL_GROUPS,
    CHANNEL_SUM_COLUMNS,
    CAMPAIGN_ATTRIBUTION_NOTE,
)
from services.period_context_targets import (
    _goal_target,
    _target_path,
    _target_rows,
    _goal_metric_targets,
    TARGET_METRICS,
    TARGET_FORM_FIELDS,
)
from services.period_context_status import (
    _unlabeled_products_scope,
    _data_status,
    _promotion_items_block,
    _market_block,
    _actions_block,
    _alerts_block,
    _anomalies_block,
    _products_block,
    _linked_period_summaries,
    DATA_STATUS_LABELS,
    _COMPARABILITY_REASON_TEXT,
)

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
        # 本期汇总（XMind 基础数据/广告汇总/流量汇总）排在拆解之前：先看整体
        # 水平再往下钻。广告/流量渠道汇总复用 ads 已算好的 channel_totals，
        # 不另查一遍 promotion 事实，避免同一事实两处计算产生漂移。
        summary = _summary_block(conn, period, (ads or {}).get('channel_totals'), category_label)
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
        'summary': summary,
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

