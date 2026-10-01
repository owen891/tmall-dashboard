from repos.promotion_repo import PromotionRepo
from services.alert_rules_service import alert_rules_service


class PromotionValidationError(ValueError):
    pass


class PromotionService:
    # 计划名 → 投放方式关键词（按序匹配，先命中先归）
    PLAN_TYPE_KEYWORDS = [
        ('控点击', ('控点击', '拉点击')),
        ('控成本', ('控成本',)),
        ('控投产', ('控投产', '控ROI', '控roi')),
        ('控费比', ('控费比',)),
        ('最大化', ('最大化',)),
        ('智能', ('智能',)),
        ('拉新', ('拉新',)),
        ('全店', ('全店', '通投')),
    ]

    @classmethod
    def plan_type_of(cls, campaign_name):
        name = str(campaign_name or '')
        if not name:
            return None
        for label, keywords in cls.PLAN_TYPE_KEYWORDS:
            for keyword in keywords:
                if keyword in name:
                    return label
        return '未标注'

    def list(self, start_date, end_date, group_by, filters):
        from datetime import date
        from db import get_shop_id

        try:
            parsed_start = date.fromisoformat(str(start_date))
            parsed_end = date.fromisoformat(str(end_date))
        except (TypeError, ValueError):
            raise PromotionValidationError('start 和 end 必须是有效的 YYYY-MM-DD 日期')
        if parsed_start > parsed_end:
            raise PromotionValidationError('start 不能晚于 end')
        if group_by not in PromotionRepo.GROUP_COLUMNS:
            raise PromotionValidationError('不支持的推广下钻粒度')
        rows = PromotionRepo.list(start_date, end_date, group_by, filters)
        result = []
        for row in rows:
            spend = float(row['ad_spend'] or 0)
            deal = float(row['attributed_payment_amount'] or 0)
            impressions = int(row['impressions'] or 0)
            clicks = int(row['clicks'] or 0)
            buyers = int(row['payment_buyers'] or 0)
            direct = float(row['direct_payment_amount'] or 0)
            indirect = float(row['indirect_payment_amount'] or 0)
            store_payment = float(row.pop('store_payment_amount') or 0)
            link_gsv = row.get('link_gsv')
            fact_cart_adds = row.get('fact_cart_adds')
            fact_new_buyers = row.get('fact_new_buyers')
            normalized = {**row, 'roi': round(deal / spend, 6) if spend else None,
                          'link_gsv': round(float(link_gsv), 6) if link_gsv is not None else None,
                          'link_net_sales': round(float(row['link_net_sales']), 6) if row.get('link_net_sales') is not None else None,
                          'expense_ratio': round(spend / row['link_net_sales'], 6) if row.get('link_net_sales') else None,
                          'ctr': round(clicks / impressions, 6) if impressions else None,
                          'cvr': round(buyers / clicks, 6) if clicks else None,
                          'cpc': round(spend / clicks, 6) if clicks else None,
                          'cpm': round(spend / impressions * 1000, 6) if impressions else None,
                          'paid_share': round(deal / store_payment, 6) if store_payment else None,
                          'direct_payment_amount': direct, 'indirect_payment_amount': indirect}
            if group_by == 'product':
                has_paid_detail = bool(row.get('paid_detail_rows'))
                total_orders = int(row['total_orders'] or 0) if has_paid_detail else None
                favs = int(row['favs'] or 0) if has_paid_detail else None
                direct_cart_adds = int(row['direct_cart_adds'] or 0) if has_paid_detail else None
                indirect_cart_adds = int(row['indirect_cart_adds'] or 0) if has_paid_detail else None
                source_cart_cost = float(row['source_cart_cost'] or 0) if has_paid_detail else 0
                # 加购/拉新优先用维度报表回填到事实行的数据（带渠道来源），
                # 事实行没有时退回 paid_detail 月表。
                cart_adds = int(fact_cart_adds or 0) or (
                    int(row['paid_cart_adds'] or 0) if has_paid_detail and row.get('paid_cart_adds') is not None else None)
                new_buyers = int(fact_new_buyers or 0) or (
                    int(row['paid_new_buyers'] or 0) if has_paid_detail and row.get('paid_new_buyers') is not None else None)
                normalized.update({
                    'total_orders': total_orders,
                    'cart_adds': cart_adds,
                    'cart_rate': round(cart_adds / clicks, 6) if cart_adds is not None and clicks else (0 if cart_adds == 0 and clicks else None),
                    'cart_cost': round(source_cart_cost, 6) if source_cart_cost > 0 else (round(spend / cart_adds, 6) if cart_adds else None),
                    'new_buyers': new_buyers,
                    'new_buyer_ratio': round(new_buyers / buyers, 6) if new_buyers is not None and buyers else (0 if new_buyers == 0 and buyers else None),
                    'new_customer_cost': round(spend / new_buyers, 6) if new_buyers else None,
                    'favs': favs,
                    'direct_cart_adds': direct_cart_adds,
                    'indirect_cart_adds': indirect_cart_adds,
                })
                normalized.pop('paid_detail_rows', None)
                normalized.pop('source_cart_cost', None)
            else:
                # 渠道/计划粒度：加购/拉新来自维度报表事实行
                cart_adds = int(fact_cart_adds or 0)
                new_buyers = int(fact_new_buyers or 0)
                has_behavior = (fact_cart_adds is not None) or (fact_new_buyers is not None)
                normalized.update({
                    'direct_roi': round(direct / spend, 6) if spend else None,
                    'cart_adds': cart_adds if has_behavior else None,
                    'cart_rate': round(cart_adds / clicks, 6) if has_behavior and clicks else None,
                    'cart_cost': round(spend / cart_adds, 6) if cart_adds else None,
                    'new_buyers': new_buyers if has_behavior else None,
                    'new_buyer_ratio': round(new_buyers / buyers, 6) if has_behavior and buyers else None,
                    'new_customer_cost': round(spend / new_buyers, 6) if new_buyers else None,
                })
            if group_by == 'campaign':
                normalized['plan_type'] = self.plan_type_of(row.get('campaign_name'))
            result.append(normalized)
        trend = []
        for row in PromotionRepo.trend(start_date, end_date, filters):
            spend = float(row['ad_spend'] or 0)
            deal = float(row['attributed_payment_amount'] or 0)
            clicks = int(row['clicks'] or 0)
            impressions = int(row['impressions'] or 0)
            buyers = int(row['payment_buyers'] or 0)
            trend.append({
                **row,
                'roi': round(deal / spend, 6) if spend else None,
                'ctr': round(clicks / impressions, 6) if impressions else None,
                'cvr': round(buyers / clicks, 6) if clicks else None,
            })
        alerts = alert_rules_service.evaluate_promotion(result)
        breakdown_rows = PromotionRepo.monthly_breakdowns(
            start_date,
            end_date,
        ) if group_by == 'product' and get_shop_id() == 'default' else {key: [] for key in PromotionRepo.BREAKDOWN_COLUMNS}
        breakdowns = {}
        for key, rows in breakdown_rows.items():
            normalized = []
            for row in rows:
                spend = float(row['spend'] or 0)
                sales = float(row['sales'] or 0)
                clicks = float(row.pop('estimated_clicks') or 0)
                normalized.append({
                    **row,
                    'spend': spend,
                    'sales': sales,
                    'visitors': int(row['visitors'] or 0),
                    'roi': round(sales / spend, 6) if spend else None,
                    'ppc': round(spend / clicks, 6) if clicks else None,
                })
            breakdowns[key] = {
                'availability': 'available' if normalized else 'no-data',
                'rows': normalized,
            }
        available_grains = PromotionRepo.available_grains(start_date, end_date, filters)
        return {
            'group_by': group_by, 'rows': result, 'trend': trend, 'alerts': alerts,
            'available_grains': available_grains,
            'breakdowns': breakdowns,
            'source_batches': PromotionRepo.source_batches(start_date, end_date, filters),
            'limitations': [
                'paid_detail 和月度推广拆分仍是单店旧表，非 default 店铺不展示这些指标',
            ] if get_shop_id() != 'default' and group_by == 'product' else [],
            'missing_ranges': self._missing_ranges(start_date, end_date, trend),
            'capabilities': {
                'can_export': bool(result),
                'can_drilldown': bool(result),
                'can_group_by_campaign': 'campaign' in available_grains,
                'can_group_by_unit': 'unit' in available_grains,
                'can_group_by_product': 'product' in available_grains,
            },
        }

    def creatives(self, start_date, end_date, product_id=None, channel=None, sort='clicks', filters=None):
        """素材看板数据：每个素材一行（CTR/CVR/加购/花费等）。"""
        rows = PromotionRepo.creatives(start_date, end_date, product_id, channel, sort, filters)
        result = []
        for row in rows:
            spend = float(row['ad_spend'] or 0)
            deal = float(row['attributed_payment_amount'] or 0)
            impressions = int(row['impressions'] or 0)
            clicks = int(row['clicks'] or 0)
            buyers = int(row['payment_buyers'] or 0)
            cart_adds = int(row['cart_adds'] or 0)
            new_buyers = int(row['new_buyers'] or 0)
            result.append({
                **row,
                'ad_spend': spend,
                'roi': round(deal / spend, 6) if spend else None,
                'ctr': round(clicks / impressions, 6) if impressions else None,
                'cvr': round(buyers / clicks, 6) if clicks else None,
                'cpc': round(spend / clicks, 6) if clicks else None,
                'cart_rate': round(cart_adds / clicks, 6) if clicks else None,
                'cart_cost': round(spend / cart_adds, 6) if cart_adds else None,
                'new_customer_cost': round(spend / new_buyers, 6) if new_buyers else None,
            })
        if sort in ('ctr', 'cvr'):
            result.sort(key=lambda row: (row.get(sort) is not None, row.get(sort) or 0), reverse=True)
        return {'rows': result, 'availability': 'available' if result else 'no-data'}

    def plan_types(self, start_date, end_date, filters=None):
        """投放方式效果对比：按计划名解析投放方式后聚合计划粒度行。"""
        filters = filters or {}
        rows = PromotionRepo.list(start_date, end_date, 'campaign', filters)
        grouped = {}
        for row in rows:
            spend = float(row['ad_spend'] or 0)
            deal = float(row['attributed_payment_amount'] or 0)
            clicks = int(row['clicks'] or 0)
            impressions = int(row['impressions'] or 0)
            buyers = int(row['payment_buyers'] or 0)
            cart_adds = int(row['fact_cart_adds'] or 0)
            plan_type = self.plan_type_of(row.get('campaign_name'))
            bucket = grouped.setdefault(plan_type, {
                'plan_count': 0, 'ad_spend': 0.0, 'attributed_payment_amount': 0.0,
                'impressions': 0, 'clicks': 0, 'payment_buyers': 0, 'cart_adds': 0,
            })
            bucket['plan_count'] += 1
            bucket['ad_spend'] += spend
            bucket['attributed_payment_amount'] += deal
            bucket['impressions'] += impressions
            bucket['clicks'] += clicks
            bucket['payment_buyers'] += buyers
            bucket['cart_adds'] += cart_adds
        result = []
        for plan_type, bucket in grouped.items():
            spend = bucket['ad_spend']
            clicks = bucket['clicks']
            impressions = bucket['impressions']
            cart_adds = bucket['cart_adds']
            result.append({
                'plan_type': plan_type,
                'plan_count': bucket['plan_count'],
                'ad_spend': round(spend, 6),
                'attributed_payment_amount': round(bucket['attributed_payment_amount'], 6),
                'roi': round(bucket['attributed_payment_amount'] / spend, 6) if spend else None,
                'ctr': round(clicks / impressions, 6) if impressions else None,
                'cvr': round(bucket['payment_buyers'] / clicks, 6) if clicks else None,
                'cart_adds': cart_adds,
                'cart_cost': round(spend / cart_adds, 6) if cart_adds else None,
            })
        result.sort(key=lambda item: item['ad_spend'], reverse=True)
        return {'rows': result, 'availability': 'available' if result else 'no-data'}

    def new_products(self, start_date, end_date, filters=None):
        """新品看板：新品（60 天内上架）× 推广投放效率与销售贡献。

        除每行指标外，返回新品全店总数、总盘对比（新品花费/成交占全店
        推广盘的比例）以及按上架日期的投放分布，供前端看板呈现。
        """
        from datetime import date, timedelta

        from repos.promotion_repo import NEW_PRODUCT_WINDOW_DAYS, PromotionRepo

        try:
            parsed_start = date.fromisoformat(str(start_date))
            parsed_end = date.fromisoformat(str(end_date))
        except (TypeError, ValueError):
            raise PromotionValidationError('start 和 end 必须是有效的 YYYY-MM-DD 日期')
        if parsed_start > parsed_end:
            raise PromotionValidationError('start 不能晚于 end')
        rows, new_total, overall = PromotionRepo.new_products(start_date, end_date, filters or {})
        result = []
        for row in rows:
            spend = float(row['ad_spend'] or 0)
            deal = float(row['attributed_payment_amount'] or 0)
            clicks = int(row['clicks'] or 0)
            impressions = int(row['impressions'] or 0)
            buyers = int(row['payment_buyers'] or 0)
            cart_adds = int(row['cart_adds'] or 0)
            link_gsv = float(row['link_gsv'] or 0)
            result.append({
                **row,
                'ad_spend': round(spend, 6),
                'attributed_payment_amount': round(deal, 6),
                'link_gsv': round(link_gsv, 6),
                'link_net_sales': round(float(row['link_net_sales'] or 0), 6),
                'roi': round(deal / spend, 6) if spend else None,
                'expense_ratio': round(spend / float(row['link_net_sales']), 6) if row.get('link_net_sales') else None,
                'ctr': round(clicks / impressions, 6) if impressions else None,
                'cvr': round(buyers / clicks, 6) if clicks else None,
                'cpc': round(spend / clicks, 6) if clicks else None,
                'cart_rate': round(cart_adds / clicks, 6) if clicks else None,
                'cart_cost': round(spend / cart_adds, 6) if cart_adds else None,
            })
        # 上架节奏以 products 为主表，推广/销售事实左连接，未投放新品也保留在批次中。
        launches = PromotionRepo.new_product_launches(start_date, end_date, filters or {})
        launch_rows = []
        for row in launches:
            spend = float(row['ad_spend'] or 0)
            deal = float(row['attributed_payment_amount'] or 0)
            impressions = int(row['impressions'] or 0)
            clicks = int(row['clicks'] or 0)
            buyers = int(row['payment_buyers'] or 0)
            cart_adds = int(row['cart_adds'] or 0)
            new_buyers = int(row['new_buyers'] or 0)
            link_gsv = float(row['link_gsv'] or 0)
            link_net_sales = float(row['link_net_sales'] or 0)
            total_products = int(row['total_product_count'] or 0)
            promoted_products = int(row['promoted_product_count'] or 0)
            launch_rows.append({
                'list_date': row['list_date'],
                'product_count': total_products,
                'total_product_count': total_products,
                'promoted_product_count': promoted_products,
                'unpromoted_product_count': int(row['unpromoted_product_count'] or 0),
                'promotion_coverage': round(promoted_products / total_products, 6) if total_products else None,
                'ad_spend': round(spend, 6),
                'attributed_payment_amount': round(deal, 6),
                'roi': round(deal / spend, 6) if spend else None,
                'link_gsv': round(link_gsv, 6),
                'link_net_sales': round(link_net_sales, 6),
                'impressions': impressions,
                'clicks': clicks,
                'payment_buyers': buyers,
                'cvr': round(buyers / clicks, 6) if clicks else None,
                'cart_adds': cart_adds,
                'cart_rate': round(cart_adds / clicks, 6) if clicks else None,
                'cart_cost': round(spend / cart_adds, 6) if cart_adds else None,
                'new_buyers': new_buyers,
                'new_customer_cost': round(spend / new_buyers, 6) if new_buyers else None,
                'ctr': round(clicks / impressions, 6) if impressions else None,
                'expense_ratio': round(spend / link_net_sales, 6) if link_net_sales else None,
            })
        total_spend = sum(float(row['ad_spend'] or 0) for row in result)
        total_deal = sum(float(row['attributed_payment_amount'] or 0) for row in result)
        overall_spend = float(overall.get('ad_spend') or 0)
        overall_deal = float(overall.get('attributed_payment_amount') or 0)
        result.sort(key=lambda row: (float(row['ad_spend'] or 0), float(row['attributed_payment_amount'] or 0)), reverse=True)
        return {
            'rows': result,
            'launches': launch_rows,
            'totals': {
                'product_count': len(result),
                'new_total': new_total,
                'ad_spend': round(total_spend, 6),
                'attributed_payment_amount': round(total_deal, 6),
                'roi': round(total_deal / total_spend, 6) if total_spend else None,
                'spend_share': round(total_spend / overall_spend, 6) if overall_spend else None,
                'deal_share': round(total_deal / overall_deal, 6) if overall_deal else None,
            },
            'window_days': NEW_PRODUCT_WINDOW_DAYS,
            'new_cutoff': (parsed_end - timedelta(days=NEW_PRODUCT_WINDOW_DAYS)).isoformat(),
            'availability': 'available' if (result or launch_rows) else 'no-data',
            'limitations': [
                f'新品口径：周期结束日前 {NEW_PRODUCT_WINDOW_DAYS} 天内上架（list_date）',
                '商品明细仅展示有推广事实的新品；上架节奏包含全部新品，并区分已投放与未投放数量',
            ],
        }

    @staticmethod
    def _detail_row_metrics(row, plan_type=None):
        spend = float(row.get('ad_spend') or 0)
        deal = float(row.get('attributed_payment_amount') or 0)
        clicks = int(row.get('clicks') or 0)
        impressions = int(row.get('impressions') or 0)
        cart_adds = int(row.get('cart_adds') or 0)
        payment_buyers = int(row.get('payment_buyers') or 0)
        new_buyers = int(row.get('new_buyers') or 0)
        direct = float(row.get('direct_payment_amount') or 0)
        indirect = float(row.get('indirect_payment_amount') or 0)
        normalized = {
            **row,
            'roi': round(deal / spend, 6) if spend else None,
            'ctr': round(clicks / impressions, 6) if impressions else None,
            'cpm': round(spend / impressions * 1000, 6) if impressions else None,
            'cvr': round(payment_buyers / clicks, 6) if clicks else None,
            'cpc': round(spend / clicks, 6) if clicks else None,
            'cart_rate': round(cart_adds / clicks, 6) if clicks else None,
            'cart_cost': round(spend / cart_adds, 6) if cart_adds else None,
            'new_buyer_ratio': round(new_buyers / payment_buyers, 6) if payment_buyers else None,
            'new_customer_cost': round(spend / new_buyers, 6) if new_buyers else None,
            'direct_payment_amount': direct,
            'indirect_payment_amount': indirect,
            'paid_share': round((direct + indirect) / deal, 6) if deal else None,
        }
        if plan_type is not None:
            normalized['plan_type'] = plan_type
        return normalized

    def product_detail(self, start_date, end_date, product_id):
        """商品推广详情抽屉：计划列表 + 渠道花费结构。"""
        from db import get_shop_id
        if not product_id:
            raise PromotionValidationError('必须提供 product_id')
        campaigns = PromotionRepo.campaigns_for_product(start_date, end_date, product_id)
        # 计划映射可能只覆盖部分历史数据；只有在计划事实没有有效花费时，
        # 才使用商品粒度总账兜底，避免与计划行重复计账。
        campaign_spend = sum(float(row['ad_spend'] or 0) for row in campaigns)
        if not campaign_spend:
            fallback = PromotionRepo.product_facts_for_product(start_date, end_date, product_id)
            if fallback:
                campaigns = [fallback]
        normalized_campaigns = []
        for row in campaigns:
            normalized_campaigns.append(self._detail_row_metrics(row, self.plan_type_of(row.get('campaign_name'))))
        channel_mix = PromotionRepo.channel_mix_for_product(start_date, end_date, product_id)
        if not channel_mix and normalized_campaigns:
            channel_buckets = {}
            for row in normalized_campaigns:
                channel = row.get('channel') or '未标注渠道'
                bucket = channel_buckets.setdefault(channel, {'channel': channel, 'ad_spend': 0, 'attributed_payment_amount': 0, 'impressions': 0, 'clicks': 0, 'payment_buyers': 0, 'cart_adds': 0, 'new_buyers': 0, 'direct_payment_amount': 0, 'indirect_payment_amount': 0})
                bucket['ad_spend'] += float(row['ad_spend'] or 0)
                bucket['attributed_payment_amount'] += float(row['attributed_payment_amount'] or 0)
                for key in ('impressions', 'clicks', 'payment_buyers', 'cart_adds', 'new_buyers'):
                    bucket[key] += int(row.get(key) or 0)
                for key in ('direct_payment_amount', 'indirect_payment_amount'):
                    bucket[key] += float(row.get(key) or 0)
            channel_mix = sorted(channel_buckets.values(), key=lambda item: item['ad_spend'], reverse=True)
        total_mix_spend = sum(float(row['ad_spend'] or 0) for row in channel_mix)
        normalized_mix = []
        for row in channel_mix:
            normalized_mix.append({
                **self._detail_row_metrics(row),
                'spend_share': round(float(row['ad_spend'] or 0) / total_mix_spend, 6) if total_mix_spend else None,
            })
        summary = {
            'ad_spend': round(sum(float(row['ad_spend'] or 0) for row in normalized_campaigns), 6),
            'attributed_payment_amount': round(sum(float(row['attributed_payment_amount'] or 0) for row in normalized_campaigns), 6),
            'impressions': sum(int(row['impressions'] or 0) for row in normalized_campaigns),
            'clicks': sum(int(row['clicks'] or 0) for row in normalized_campaigns),
            'payment_buyers': sum(int(row['payment_buyers'] or 0) for row in normalized_campaigns),
            'cart_adds': sum(int(row['cart_adds'] or 0) for row in normalized_campaigns),
            'new_buyers': sum(int(row['new_buyers'] or 0) for row in normalized_campaigns),
        }
        spend = summary['ad_spend']
        behavior = PromotionRepo.product_behavior_for_period(start_date, end_date, product_id)
        guide_potential = int(behavior.get('guide_potential') or 0)
        guide_visitors = int(behavior.get('guide_visitors') or 0)
        summary.update({
            'roi': round(summary['attributed_payment_amount'] / spend, 6) if spend else None,
            'ctr': round(summary['clicks'] / summary['impressions'], 6) if summary['impressions'] else None,
            'cvr': round(summary['payment_buyers'] / summary['clicks'], 6) if summary['clicks'] else None,
            'cpc': round(spend / summary['clicks'], 6) if summary['clicks'] else None,
            'cart_cost': round(spend / summary['cart_adds'], 6) if summary['cart_adds'] else None,
            'new_customer_cost': round(spend / summary['new_buyers'], 6) if summary['new_buyers'] else None,
            'new_buyer_ratio': round(summary['new_buyers'] / summary['payment_buyers'], 6) if summary['payment_buyers'] else None,
            'guide_visitors': guide_visitors,
            'guide_potential': guide_potential,
            'guide_potential_ratio': round(guide_potential / guide_visitors, 6) if guide_visitors else None,
        })
        return {
            'product_id': product_id,
            'summary': summary,
            'campaigns': normalized_campaigns,
            'channel_mix': normalized_mix,
            'limitations': (['渠道结构按推广该商品的计划的渠道归因，多商品计划会整体计入'] if normalized_mix else []) + (['当前无可关联的计划事实，已使用商品推广总账兜底'] if normalized_campaigns and normalized_campaigns[0].get('campaign_id', '').startswith('product:') else []),
        }

    def campaign_detail(self, start_date, end_date, campaign_id):
        """计划看板行展开：计划汇总 + 该计划投放的商品。"""
        from db import get_shop_id
        if not campaign_id:
            raise PromotionValidationError('必须提供 campaign_id')
        summary = PromotionRepo.campaign_summary(start_date, end_date, campaign_id)
        spend = float(summary.get('ad_spend') or 0)
        deal = float(summary.get('attributed_payment_amount') or 0)
        clicks = int(summary.get('clicks') or 0)
        impressions = int(summary.get('impressions') or 0)
        cart_adds = int(summary.get('cart_adds') or 0)
        products = PromotionRepo.campaign_products(campaign_id)
        return {
            'campaign_id': campaign_id,
            'summary': {
                **summary,
                'roi': round(deal / spend, 6) if spend else None,
                'ctr': round(clicks / impressions, 6) if impressions else None,
                'cvr': round(int(summary.get('payment_buyers') or 0) / clicks, 6) if clicks else None,
                'cart_cost': round(spend / cart_adds, 6) if cart_adds else None,
                'plan_type': self.plan_type_of(summary.get('campaign_name')),
            },
            'products': products,
        }

    def creative_board(self, shop_label=None, product_id=None, include_system=False):
        """素材点击率看板：全历史累计,按单品分组返回创意及其指标。"""
        rows = PromotionRepo.creative_board(shop_label, product_id, include_system)
        products = {}
        for row in rows:
            spend = float(row['ad_spend'] or 0)
            deal = float(row['attributed_payment_amount'] or 0)
            clicks = int(row['clicks'] or 0)
            impressions = int(row['impressions'] or 0)
            cart_adds = int(row['cart_adds'] or 0)
            new_buyers = int(row['new_buyers'] or 0)
            creative = {
                **row,
                'ad_spend': round(spend, 6),
                'roi': round(deal / spend, 6) if spend else None,
                'ctr': round(clicks / impressions, 6) if impressions else None,
                'cvr': round(int(row['payment_buyers'] or 0) / clicks, 6) if clicks else None,
                'cart_rate': round(cart_adds / clicks, 6) if clicks else None,
                'cart_cost': round(spend / cart_adds, 6) if cart_adds else None,
            }
            product_key = row['product_id'] or '_'
            products.setdefault(product_key, {
                'product_id': row['product_id'] or '_',
                'title': row['title'] or '未命名商品',
                'image_url': row['product_image'] or '',
                'shop_label': row['shop_label'] or '未分类',
                'creatives': [],
                'ad_spend': 0.0, 'attributed_payment_amount': 0.0,
                'clicks': 0, 'impressions': 0, 'cart_adds': 0,
                'payment_buyers': 0, 'direct_payment_amount': 0.0,
                'new_buyers': 0, 'first_date': None, 'last_date': None,
            })
            bucket = products[product_key]
            if row.get('creative_id'):
                bucket['creatives'].append(creative)
            bucket['ad_spend'] += spend
            bucket['attributed_payment_amount'] += deal
            bucket['clicks'] += clicks
            bucket['impressions'] += impressions
            bucket['cart_adds'] += cart_adds
            bucket['payment_buyers'] += int(row['payment_buyers'] or 0)
            bucket['direct_payment_amount'] += float(row['direct_payment_amount'] or 0)
            bucket['new_buyers'] += new_buyers
            if row.get('first_date') and (not bucket['first_date'] or row['first_date'] < bucket['first_date']):
                bucket['first_date'] = row['first_date']
            if row.get('last_date') and (not bucket['last_date'] or row['last_date'] > bucket['last_date']):
                bucket['last_date'] = row['last_date']
        product_list = []
        for bucket in products.values():
            spend = bucket['ad_spend']
            deal = bucket['attributed_payment_amount']
            bucket['roi'] = round(deal / spend, 6) if spend else None
            bucket['ctr'] = round(bucket['clicks'] / bucket['impressions'], 6) if bucket['impressions'] else None
            bucket['cart_rate'] = round(bucket['cart_adds'] / bucket['clicks'], 6) if bucket['clicks'] else None
            bucket['cvr'] = round(bucket['payment_buyers'] / bucket['clicks'], 6) if bucket['clicks'] else None
            bucket['cart_cost'] = round(spend / bucket['cart_adds'], 6) if bucket['cart_adds'] else None
            bucket['creatives'].sort(key=lambda c: (c['clicks'], c['ad_spend']), reverse=True)
            product_list.append(bucket)
        product_list.sort(key=lambda p: (p['ad_spend'], p['clicks']), reverse=True)
        categories = {}
        for bucket in product_list:
            label = bucket['shop_label']
            entry = categories.setdefault(label, {'label': label, 'product_count': 0, 'creative_count': 0})
            entry['product_count'] += 1
            entry['creative_count'] += len(bucket['creatives'])
        return {
            'products': product_list,
            'categories': sorted(categories.values(), key=lambda c: -c['creative_count']),
            'totals': {
                'product_count': len(product_list),
                'creative_count': sum(len(bucket['creatives']) for bucket in product_list),
                'ad_spend': round(sum(float(r['ad_spend'] or 0) for r in rows), 6),
                'clicks': sum(int(r['clicks'] or 0) for r in rows),
            },
        }

    @staticmethod
    def _missing_ranges(start_date, end_date, trend):
        from datetime import date, timedelta

        present = {row['date'] for row in trend}
        cursor = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
        missing = []
        while cursor <= end:
            if cursor.isoformat() in present:
                cursor += timedelta(days=1)
                continue
            begin = cursor
            while cursor <= end and cursor.isoformat() not in present:
                cursor += timedelta(days=1)
            missing.append({'start': begin.isoformat(), 'end': (cursor - timedelta(days=1)).isoformat()})
        return missing


promotion_service = PromotionService()
