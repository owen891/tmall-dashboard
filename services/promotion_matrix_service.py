"""新老品 × 渠道投放矩阵（/promotion-matrix）。

推广分析页把 7 张 KPI、经营诊断、漏斗、散点、预警铺开，回答问题多但看不出
「哪个品该加预算、哪个品该收」。这个模块只回答一件事：**新老品在各渠道的
投放效率**，并把单品分成「可放大 / 需优化 / 样本不足」三档。

口径约定（与本仓库其它推广页面保持一致，不新造口径）：
- 商品×渠道事实 = `promotion_creative_daily`（关键词/人群/店铺直达）
  + 计划→商品 1:1 精确归因（补全站推广/超级短视频）。同一渠道以创意明细为准，
  归因只补创意明细没有的渠道，两边相加不重复计数。
- 多商品全站推广计划没有商品级明细，**不摊到单品**（均摊会把一个计划的效率
  抹平到所有商品上），只作为「未归因」差额展示，并单独给出覆盖率。
- 新老品按 `products.list_date`：周期结束日前 `NEW_PRODUCT_WINDOW_DAYS`(60) 天内
  上架为新品，与新品看板同一口径。
- 效率判定以 ROI 为主，先做小基数保护（花费 < 100 或成交 < 500 不出结论），
  再与「同渠道基准 ROI」比较；费比、加购成本作为辅助信号一并返回，不参与判定。
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

from db import get_db
from repos.promotion_repo import NEW_PRODUCT_WINDOW_DAYS, PromotionRepo
from services.period_context_ads import PROMOTION_CHANNEL_GROUPS, _campaign_attribution
from services.promotion_service import PromotionValidationError

_log = logging.getLogger(__name__)

# 小基数保护：低于这个量级的花费/成交，ROI 会被几十元的样本放大成几十倍，
# 直接给「可放大」结论会误导预算。宁可不判定。
MIN_SPEND_FOR_VERDICT = 100.0
MIN_PAYMENT_FOR_VERDICT = 500.0

# 与同渠道基准 ROI 的比较阈值：明显高于基准才建议加预算，明显低于才建议收。
SCALE_RATIO = 1.15
OPTIMIZE_RATIO = 0.85

# 展示顺序沿用 period_context_ads 的渠道分组，避免两个页面渠道口径漂移。
CHANNEL_ORDER = tuple(group for group, _ in PROMOTION_CHANNEL_GROUPS)
CHANNEL_LABELS = {
    '全站': '全站推广',
    '关键词': '关键词推广',
    '人群': '人群推广',
    '其他': '其他场景',
}
_RAW_TO_GROUP = {
    raw: group
    for group, raws in PROMOTION_CHANNEL_GROUPS
    for raw in raws
}

STAGE_LABELS = (('new', '新品'), ('old', '老品'), ('unknown', '未匹配商品'))

_METRIC_KEYS = (
    'ad_spend', 'attributed_payment', 'direct_payment',
    'impressions', 'clicks', 'payment_buyers', 'cart_adds', 'new_buyers',
)

_EMPTY_MESSAGE = '当前范围没有可归因到商品的推广花费'


def _bucket():
    return {key: 0.0 for key in _METRIC_KEYS}


def _accumulate(target, source):
    for key in _METRIC_KEYS:
        target[key] += float(source.get(key) or 0)
    return target


def _ratio(numerator, denominator):
    if not denominator:
        return None
    return numerator / denominator


def _round(value, digits=6):
    return None if value is None else round(value, digits)


def _channel_group(channel):
    # 未知渠道归到「其他」而不是丢弃：宁可让它可见，也不让花费凭空消失。
    return _RAW_TO_GROUP.get(channel, '其他')


def _derived(bucket, net_sales=None):
    spend = bucket['ad_spend']
    deal = bucket['attributed_payment']
    carts = bucket['cart_adds']
    return {
        'roi': _round(_ratio(deal, spend)),
        'expense_ratio': _round(_ratio(spend, net_sales)) if net_sales else None,
        'cart_cost': _round(_ratio(spend, carts), 2),
        'cpc': _round(_ratio(spend, bucket['clicks']), 4),
        'ctr': _round(_ratio(bucket['clicks'], bucket['impressions'])),
    }


class PromotionMatrixService:
    """新老品 × 渠道矩阵与单品效率判定。"""

    def matrix(self, start_date, end_date, filters=None):
        filters = filters or {}
        parsed_start, parsed_end = self._parse_period(start_date, end_date)
        creative_rows = PromotionRepo.product_channel_facts(start_date, end_date, filters)

        covered_channels = {row['channel'] for row in creative_rows}
        facts = [self._fact_from_creative(row) for row in creative_rows]
        attribution = self._attribution_product_rows(start_date, end_date, filters)
        for (channel, product_id), bucket in attribution.items():
            # 创意明细已覆盖的渠道不再叠加，否则同一笔花费算两遍。
            if channel in covered_channels:
                continue
            if not (bucket.get('ad_spend') or bucket.get('attributed_payment')):
                continue
            facts.append({'product_id': product_id, 'channel': channel, **_bucket(), **bucket})

        product_ids = sorted({row['product_id'] for row in facts if row.get('product_id')})
        bill = PromotionRepo.bill_totals(start_date, end_date, filters) or {}
        cutoff = (parsed_end - timedelta(days=NEW_PRODUCT_WINDOW_DAYS)).isoformat()

        if not product_ids:
            return self._empty_payload(start_date, end_date, cutoff, bill)

        meta = PromotionRepo.products_meta(product_ids)
        links = PromotionRepo.link_sales_by_product(start_date, end_date, product_ids)

        channel_totals = {group: _bucket() for group in CHANNEL_ORDER}
        by_product = {}
        for row in facts:
            group = _channel_group(row['channel'])
            _accumulate(channel_totals[group], row)
            product = by_product.setdefault(row['product_id'], {
                'spend': 0.0,
                'channels': {},
            })
            product['spend'] += float(row.get('ad_spend') or 0)
            channel_bucket = product['channels'].setdefault(group, _bucket())
            _accumulate(channel_bucket, row)

        # 基准 ROI 用「本页同一份商品×渠道事实」自己算，保证分子分母同源；
        # 拿别的页面的渠道 ROI 当基准会让判定口径与展示口径不一致。
        baseline = {}
        for group, bucket in channel_totals.items():
            baseline[group] = _round(_ratio(bucket['attributed_payment'], bucket['ad_spend']))

        products = []
        stage_products = {key: [] for key, _ in STAGE_LABELS}
        for product_id, product in by_product.items():
            info = meta.get(product_id) or {}
            link = links.get(product_id) or {}
            stage = self._stage_of(info.get('list_date'), cutoff, parsed_end)
            link_net_sales = float(link.get('link_net_sales') or 0)
            channel_rows = []
            combined = _bucket()
            expected_spend = 0.0
            expected_payment = 0.0
            for group in CHANNEL_ORDER:
                bucket = product['channels'].get(group)
                if not bucket or not bucket['ad_spend']:
                    continue
                _accumulate(combined, bucket)
                reference = baseline.get(group)
                if reference is not None:
                    expected_spend += bucket['ad_spend']
                    expected_payment += bucket['ad_spend'] * reference
                channel_rows.append({
                    'channel': group,
                    'label': CHANNEL_LABELS[group],
                    **_numbers(bucket),
                    **_derived(bucket, None),
                })
            expected_roi = _ratio(expected_payment, expected_spend)
            verdict, reason = self._verdict(
                combined['ad_spend'], combined['attributed_payment'],
                _ratio(combined['attributed_payment'], combined['ad_spend']),
                expected_roi,
            )
            row = {
                'product_id': product_id,
                'title': info.get('title') or '',
                'image_url': info.get('image_url') or '',
                'shop_label': info.get('shop_label') or '',
                'list_date': info.get('list_date') or '',
                'stage': stage,
                'stage_label': dict(STAGE_LABELS)[stage],
                **_numbers(combined),
                **_derived(combined, link_net_sales if link_net_sales else None),
                'link_net_sales': round(link_net_sales, 6),
                'expected_roi': _round(expected_roi),
                'roi_vs_baseline': _round(_ratio(
                    _ratio(combined['attributed_payment'], combined['ad_spend']), expected_roi), 4),
                'verdict': verdict,
                'verdict_reason': reason,
                'channels': channel_rows,
            }
            products.append(row)
            stage_products[stage].append(row)

        products.sort(key=lambda item: item['ad_spend'], reverse=True)

        net_sales_by_stage = {}
        for stage, rows in stage_products.items():
            net_sales_by_stage[stage] = sum(float(row['link_net_sales'] or 0) for row in rows)

        groups = []
        for stage, label in STAGE_LABELS:
            rows = stage_products[stage]
            if not rows:
                continue
            total = _bucket()
            cells = []
            for group in CHANNEL_ORDER:
                bucket = _bucket()
                for row in rows:
                    for channel_row in row['channels']:
                        if channel_row['channel'] == group:
                            _accumulate(bucket, channel_row)
                if not bucket['ad_spend']:
                    continue
                _accumulate(total, bucket)
                cells.append({
                    'channel': group,
                    'label': CHANNEL_LABELS[group],
                    'product_count': sum(
                        1 for row in rows
                        if any(ch['channel'] == group for ch in row['channels'])
                    ),
                    **_numbers(bucket),
                    **_derived(bucket, net_sales_by_stage[stage] or None),
                })
            groups.append({
                'key': stage,
                'label': label,
                'product_count': len(rows),
                'cells': cells,
                'totals': {
                    **_numbers(total),
                    **_derived(total, net_sales_by_stage[stage] or None),
                    'link_net_sales': round(net_sales_by_stage[stage], 6),
                },
            })

        bill_spend = float(bill.get('ad_spend') or 0)
        bill_payment = float(bill.get('attributed_payment') or 0)
        covered_spend = sum(row['ad_spend'] for row in products)
        covered_payment = sum(row['attributed_payment'] for row in products)
        total = _bucket()
        for row in products:
            _accumulate(total, row)

        verdict_counts = {'scale': 0, 'steady': 0, 'optimize': 0, 'insufficient': 0}
        for row in products:
            verdict_counts[row['verdict']] = verdict_counts.get(row['verdict'], 0) + 1

        return {
            'period': {
                'start': start_date,
                'end': end_date,
                'days': (parsed_end - parsed_start).days + 1,
            },
            'window': {
                'window_days': NEW_PRODUCT_WINDOW_DAYS,
                'new_cutoff': cutoff,
            },
            'channels': [
                {
                    'channel': group,
                    'label': CHANNEL_LABELS[group],
                    **_numbers(channel_totals[group]),
                    **_derived(channel_totals[group], None),
                    'baseline_roi': baseline.get(group),
                    'spend_share': _round(_ratio(
                        channel_totals[group]['ad_spend'], total['ad_spend'])),
                }
                for group in CHANNEL_ORDER
                if channel_totals[group]['ad_spend'] or channel_totals[group]['attributed_payment']
            ],
            'baseline': {group: baseline.get(group) for group in CHANNEL_ORDER},
            'groups': groups,
            'totals': {
                **_numbers(total),
                **_derived(total, sum(net_sales_by_stage.values()) or None),
                'product_count': len(products),
                'link_net_sales': round(sum(net_sales_by_stage.values()), 6),
                'verdict_counts': verdict_counts,
            },
            'coverage': {
                'bill_spend': round(bill_spend, 2),
                'bill_payment': round(bill_payment, 2),
                'covered_spend': round(covered_spend, 2),
                'covered_payment': round(covered_payment, 2),
                'spend_coverage': _round(_ratio(covered_spend, bill_spend), 4),
                'payment_coverage': _round(_ratio(covered_payment, bill_payment), 4),
                'unattributed_spend': round(max(bill_spend - covered_spend, 0.0), 2),
                'sample_days': int(bill.get('sample_days') or 0),
            },
            'baseline_rule': {
                'min_spend': MIN_SPEND_FOR_VERDICT,
                'min_payment': MIN_PAYMENT_FOR_VERDICT,
                'scale_ratio': SCALE_RATIO,
                'optimize_ratio': OPTIMIZE_RATIO,
            },
            'products': products,
            'availability': 'available',
            'limitations': self._limitations(bill_spend, covered_spend, cutoff),
        }

    # ------------------------------------------------------------------
    # 内部实现
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_period(start_date, end_date):
        try:
            parsed_start = date.fromisoformat(str(start_date))
            parsed_end = date.fromisoformat(str(end_date))
        except (TypeError, ValueError):
            raise PromotionValidationError('start 和 end 必须是有效的 YYYY-MM-DD 日期')
        if parsed_start > parsed_end:
            raise PromotionValidationError('start 不能晚于 end')
        return parsed_start, parsed_end

    @staticmethod
    def _attribution_product_rows(start_date, end_date, filters):
        """计划→商品 1:1 精确归因的商品级结果（复用复盘页同一实现）。"""
        try:
            with get_db() as connection:
                attribution = _campaign_attribution(
                    connection,
                    {'start': start_date, 'end': end_date},
                    filters.get('shop_label'),
                    limit=None,
                    include_product_rows=True,
                ) or {}
        except Exception:  # 归因是补全项，失败不该让整页不可用
            _log.warning('推广矩阵：计划归因补全失败', exc_info=True)
            return {}
        return attribution.get('product_rows') or {}

    @staticmethod
    def _fact_from_creative(row):
        return {
            'product_id': row['product_id'],
            'channel': row['channel'],
            **{
                key: float(row.get(key) or 0)
                for key in _METRIC_KEYS
            },
        }

    @staticmethod
    def _stage_of(list_date, cutoff, parsed_end):
        value = (list_date or '')[:10]
        if len(value) != 10:
            return 'unknown'
        if cutoff <= value <= parsed_end.isoformat():
            return 'new'
        return 'old'

    @staticmethod
    def _verdict(spend, payment, roi, expected_roi):
        # 小基数保护优先：达不到量级就不给结论，避免几十元花费的 ROI 被放大。
        if spend < MIN_SPEND_FOR_VERDICT or payment < MIN_PAYMENT_FOR_VERDICT:
            return 'insufficient', '样本不足，暂不判定'
        if not roi or not expected_roi:
            return 'insufficient', '缺少基准 ROI，暂不判定'
        ratio = roi / expected_roi
        if ratio >= SCALE_RATIO:
            return 'scale', f'ROI 是同渠道基准的 {ratio:.2f} 倍'
        if ratio <= OPTIMIZE_RATIO:
            return 'optimize', f'ROI 只有同渠道基准的 {ratio:.2f} 倍'
        return 'steady', '与同渠道基准基本持平'

    def _empty_payload(self, start_date, end_date, cutoff, bill):
        return {
            'period': {'start': start_date, 'end': end_date, 'days': 0},
            'window': {'window_days': NEW_PRODUCT_WINDOW_DAYS, 'new_cutoff': cutoff},
            'channels': [],
            'baseline': {group: None for group in CHANNEL_ORDER},
            'groups': [],
            'totals': {
                **_numbers(_bucket()),
                'product_count': 0,
                'link_net_sales': 0.0,
                'verdict_counts': {'scale': 0, 'steady': 0, 'optimize': 0, 'insufficient': 0},
            },
            'coverage': {
                'bill_spend': round(float(bill.get('ad_spend') or 0), 2),
                'bill_payment': round(float(bill.get('attributed_payment') or 0), 2),
                'covered_spend': 0.0,
                'covered_payment': 0.0,
                'spend_coverage': None,
                'payment_coverage': None,
                'unattributed_spend': round(float(bill.get('ad_spend') or 0), 2),
                'sample_days': int(bill.get('sample_days') or 0),
            },
            'baseline_rule': {
                'min_spend': MIN_SPEND_FOR_VERDICT,
                'min_payment': MIN_PAYMENT_FOR_VERDICT,
                'scale_ratio': SCALE_RATIO,
                'optimize_ratio': OPTIMIZE_RATIO,
            },
            'products': [],
            'availability': 'no-data',
            'limitations': [_EMPTY_MESSAGE] + self._limitations(
                float(bill.get('ad_spend') or 0), 0.0, cutoff),
        }

    @staticmethod
    def _limitations(bill_spend, covered_spend, cutoff):
        notes = [
            f'新老品口径：周期结束日前 {NEW_PRODUCT_WINDOW_DAYS} 天内上架（list_date 不早于 {cutoff}）为新品',
            '商品×渠道明细 = 创意明细（关键词/人群/店铺直达）+ 计划 1:1 精确归因（补全站推广/超级短视频）',
            '多商品全站推广计划没有商品级明细，不做均摊，因此明细合计会小于账单口径',
            f'效率判定：花费 ≥ {MIN_SPEND_FOR_VERDICT:g} 元且成交 ≥ {MIN_PAYMENT_FOR_VERDICT:g} 元才出结论，'
            f'ROI 高于同渠道基准 {SCALE_RATIO:g} 倍为「可放大」，低于 {OPTIMIZE_RATIO:g} 倍为「需优化」',
        ]
        if bill_spend and covered_spend is not None:
            share = covered_spend / bill_spend if bill_spend else 0
            notes.append(f'本期商品级明细覆盖账单口径花费的 {share * 100:.1f}%，其余为无商品明细的多商品计划')
        return notes


def _numbers(bucket):
    return {
        'ad_spend': round(float(bucket.get('ad_spend') or 0), 6),
        'attributed_payment': round(float(bucket.get('attributed_payment') or 0), 6),
        'direct_payment': round(float(bucket.get('direct_payment') or 0), 6),
        'impressions': int(bucket.get('impressions') or 0),
        'clicks': int(bucket.get('clicks') or 0),
        'payment_buyers': int(bucket.get('payment_buyers') or 0),
        'cart_adds': int(bucket.get('cart_adds') or 0),
        'new_buyers': int(bucket.get('new_buyers') or 0),
    }


promotion_matrix_service = PromotionMatrixService()
