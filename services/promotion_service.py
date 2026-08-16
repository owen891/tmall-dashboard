from repos.promotion_repo import PromotionRepo
from services.alert_rules_service import alert_rules_service


class PromotionValidationError(ValueError):
    pass


class PromotionService:
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
                cart_adds = int(row['cart_adds'] or 0) if has_paid_detail else None
                new_buyers = int(row['new_buyers'] or 0) if has_paid_detail else None
                total_orders = int(row['total_orders'] or 0) if has_paid_detail else None
                favs = int(row['favs'] or 0) if has_paid_detail else None
                direct_cart_adds = int(row['direct_cart_adds'] or 0) if has_paid_detail else None
                indirect_cart_adds = int(row['indirect_cart_adds'] or 0) if has_paid_detail else None
                source_cart_cost = float(row['source_cart_cost'] or 0) if has_paid_detail else 0
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
