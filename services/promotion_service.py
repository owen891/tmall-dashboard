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
                          'expense_ratio': round(spend / link_gsv, 6) if link_gsv else None,
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

    def product_detail(self, start_date, end_date, product_id):
        """商品推广详情抽屉：计划列表 + 渠道花费结构。"""
        from db import get_shop_id
        if not product_id:
            raise PromotionValidationError('必须提供 product_id')
        campaigns = PromotionRepo.campaigns_for_product(start_date, end_date, product_id)
        normalized_campaigns = []
        for row in campaigns:
            spend = float(row['ad_spend'] or 0)
            deal = float(row['attributed_payment_amount'] or 0)
            clicks = int(row['clicks'] or 0)
            impressions = int(row['impressions'] or 0)
            cart_adds = int(row['cart_adds'] or 0)
            normalized_campaigns.append({
                **row,
                'roi': round(deal / spend, 6) if spend else None,
                'ctr': round(clicks / impressions, 6) if impressions else None,
                'cart_cost': round(spend / cart_adds, 6) if cart_adds else None,
                'plan_type': self.plan_type_of(row.get('campaign_name')),
            })
        channel_mix = PromotionRepo.channel_mix_for_product(start_date, end_date, product_id)
        total_mix_spend = sum(float(row['ad_spend'] or 0) for row in channel_mix)
        normalized_mix = [{
            **row,
            'spend_share': round(float(row['ad_spend'] or 0) / total_mix_spend, 6) if total_mix_spend else None,
        } for row in channel_mix]
        return {
            'product_id': product_id,
            'campaigns': normalized_campaigns,
            'channel_mix': normalized_mix,
            'limitations': (['渠道结构按推广该商品的计划的渠道归因，多商品计划会整体计入'] if normalized_mix else []),
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
