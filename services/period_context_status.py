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

from services.period_context_ads import _campaign_attribution, _product_meta, PROMOTION_CHANNEL_GROUPS
from services.period_context_metrics import _daily_scope

# ---------------------------------------------------------------------------

def _unlabeled_products_scope(conn, start, end, grain='day'):
    """统计本期有销售但未打品类标签的商品（数量 + 净销售额）。

    shop_label 是品类拆分的唯一依据，而 BI 接口不带标签字段（tagGroup 恒为
    '--'，实测 2026-10-04）——采集路径新增的商品在模板重传前恒为空，这部分
    销售不参与任何品类统计。放这里让漂移当期可见（2026-09 实测 1,488 款 /
    净销 63,854 未计入品类），而不是月底对账才发现。
    周复盘查 daily_data；月复盘的历史月份 daily 覆盖不全，改查 monthly_data
    （单店旧表，只有 default 部署可用，非 default scope 直接返回 None）。
    返回 None 表示本期没有未分类商品（或查询失败，不阻塞页面）。
    """
    try:
        scope = str(get_shop_id())
        if grain == 'month':
            # monthly_data 没有 shop_id 列：只有单店 default 部署能保证它属于
            # 当前店铺，多店 scope 下宁可不显示，也不能把别家销售算进来。
            from db import legacy_shop_id
            if scope not in ('default', legacy_shop_id()):
                return None
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
                   WHERE d.date BETWEEN ? AND ? AND d.shop_id = ?
                     AND COALESCE(p.shop_label, '') = ''
                     AND (d.net_sales > 0 OR d.payment_amount > 0)''',
                (start, end, scope),
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
        _log.warning('_ads_block failed; returning unavailable block', exc_info=True)
        return {'available': False, 'items': [], 'missing_inputs': ['promotion_daily_facts']}

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
                '''SELECT stat_date, item_id, title, shop_name, rank, is_self, uv, pay_buyer_count,
                          pic_url
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

def _lifecycle_distribution(current):
    """本期有记录的商品 × 当前生命周期；不是历史阶段快照。"""
    from services.lifecycle_service import lifecycle_service
    note = '本期净销售额 × 当前生命周期阶段（非历史快照）；范围为本期有经营记录的商品。阶段沿用生命周期模块，保留人工调整与锁定；净销售额缺失或合计非正时不计算占比。'
    if not current:
        return {'available': True, 'basis': 'current', 'note': note, 'items': []}
    try:
        assessments = {str(row['product_id']): row
                       for row in lifecycle_service.list_for_products(current)}
    except Exception:
        _log.exception('周期复盘生命周期读取失败')
        return {'available': False, 'basis': 'current', 'note': note,
                'error': '生命周期数据暂不可用，请稍后刷新。', 'items': []}
    groups = {}
    net_values = [row.get('net_sales') for row in current.values()]
    total = sum(float(value) for value in net_values) if all(value is not None for value in net_values) else None
    for product_id, row in current.items():
        assessment = assessments.get(str(product_id), {})
        stage = assessment.get('stage') or 'unassessed'
        group = groups.setdefault(stage, {
            'stage': stage, 'stage_label': assessment.get('stage_label') or '未评估',
            'count': 0, 'net_sales': 0.0, 'missing_count': 0,
            'manual_count': 0, 'locked_count': 0, 'products': [],
        })
        value = row.get('net_sales')
        group['count'] += 1
        group['missing_count'] += int(value is None)
        group['net_sales'] += float(value or 0)
        group['manual_count'] += int(bool(assessment.get('manual_stage')))
        group['locked_count'] += int(bool(assessment.get('locked')))
        group['products'].append({
            'product_id': str(product_id), 'title': assessment.get('title') or str(product_id),
            'net_sales': value, 'manual_stage': assessment.get('manual_stage'),
            'locked': bool(assessment.get('locked')),
        })
    items = []
    for group in groups.values():
        value = None if group['missing_count'] else group['net_sales']
        group['net_sales'] = round(value, 2) if value is not None else None
        group['share'] = value / total if value is not None and total is not None and total > 0 else None
        items.append(group)
    return {'available': True, 'basis': 'current', 'note': note,
            'items': sorted(items, key=lambda row: -(row['net_sales'] or 0))}


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
                WHERE d.date BETWEEN ? AND ? AND d.shop_id = ?{structure_scope_sql}
                GROUP BY category ORDER BY net_sales DESC''',
            (period['start'], period['end'], str(get_shop_id()), *structure_scope_params),
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
            'lifecycle_distribution': _lifecycle_distribution(current),
        },
    }

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

DATA_STATUS_LABELS = {
    'complete': '数据完整',
    'partial': '部分数据',
    'no-data': '暂无数据',
}

_COMPARABILITY_REASON_TEXT = {
    'baseline_no_data': '对比周期无数据',
    'baseline_grain_mismatch': '基线粒度与本期不匹配（整月兜底基线 vs 非完整月）',
}
