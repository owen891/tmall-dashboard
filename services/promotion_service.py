from repos.promotion_repo import PromotionRepo


class PromotionValidationError(ValueError):
    pass


class PromotionService:
    def list(self, start_date, end_date, group_by, filters):
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
            result.append({**row, 'roi': round(deal / spend, 6) if spend else None,
                           'ctr': round(clicks / impressions, 6) if impressions else None,
                           'cvr': round(buyers / clicks, 6) if clicks else None,
                           'cpc': round(spend / clicks, 6) if clicks else None,
                           'paid_share': round(deal / store_payment, 6) if store_payment else None,
                           'direct_payment_amount': direct, 'indirect_payment_amount': indirect})
        return {'group_by': group_by, 'rows': result}


promotion_service = PromotionService()
