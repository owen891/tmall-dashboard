from repos.keyword_promotion_repo import KeywordPromotionRepo


class KeywordPromotionValidationError(ValueError):
    pass


class KeywordPromotionService:
    """关键词推广商品级业务逻辑层"""

    def list_products(self, filters, sort_by='total_score', sort_order='desc', page=1, page_size=50):
        # 参数校验
        if sort_by not in KeywordPromotionRepo.SORT_COLUMNS:
            raise KeywordPromotionValidationError(f'不支持的排序字段: {sort_by}')
        if sort_order not in ('asc', 'desc'):
            raise KeywordPromotionValidationError('排序方向只能是 asc 或 desc')
        if page < 1:
            page = 1
        if page_size < 1 or page_size > 200:
            page_size = 50

        result = KeywordPromotionRepo.list_products(filters, sort_by, sort_order, page, page_size)

        # 格式化数值
        for row in result['rows']:
            for key in ['roi', 'cvr', 'ctr', 'cart_rate', 'cpc', 'cpm', 'avg_pages',
                        'guide_visit_rate', 'new_buyer_ratio', 'member_signup_rate',
                        'total_score', 'score_traffic', 'score_conversion', 'score_sales',
                        'score_seeding', 'score_quality', 'score_newcustomer']:
                if row.get(key) is not None:
                    row[key] = round(float(row[key]), 4)

        return result

    def summary(self, filters):
        result = KeywordPromotionRepo.summary(filters)
        # 格式化
        for key in ['total_spend', 'total_payment', 'avg_roi', 'avg_cvr', 'avg_ctr',
                    'avg_cart_rate', 'overall_roi']:
            if result.get(key) is not None:
                result[key] = round(float(result[key]), 2)
        return result

    def filter_options(self):
        return KeywordPromotionRepo.filter_options()

    def grade_distribution(self):
        rows = KeywordPromotionRepo.grade_distribution()
        for r in rows:
            if r.get('total_spend'):
                r['total_spend'] = round(float(r['total_spend']), 2)
            if r.get('total_payment'):
                r['total_payment'] = round(float(r['total_payment']), 2)
        return rows


keyword_promotion_service = KeywordPromotionService()
