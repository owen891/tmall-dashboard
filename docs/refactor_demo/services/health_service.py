"""
Health Service — 商品健康度 12 维度评分算法。

从 scripts/calc_health.py 和 data_api.py 的 /api/health 路由合并。
原代码分散在脚本和路由中，重构后统一到 Service 层。
"""
from models import db
from models.health import ProductHealth
from models.data import MonthlyData
from utils.period import get_prev_period


class HealthService:
    """商品健康度评分服务"""

    # 维度权重配置（可从 config.yaml 读取）
    DIMENSION_WEIGHTS = {
        'sales_score': 15,
        'conversion_score': 10,
        'roi_score': 15,
        'refund_score': 10,
        'growth_score': 10,
        'review_score': 10,
        'gmv_change_score': 5,
        'ad_spend_change_score': 5,
        'roi_change_score': 5,
        'cart_rate_score': 5,
        'search_ratio_score': 5,
        'repurchase_rate_score': 5,
    }

    @staticmethod
    def calc_product_health(product_id, period):
        """
        计算单个商品的健康度评分。

        替代原 calc_health.py 中的逻辑，使用 ORM 查询替代手写 SQL。
        """
        data = MonthlyData.query.filter_by(
            product_id=product_id, month=period
        ).first()
        if not data:
            return None

        prev_period = get_prev_period('monthly', period)
        prev_data = MonthlyData.query.filter_by(
            product_id=product_id, month=prev_period
        ).first()

        scores = {}
        scores['sales_score'] = HealthService._score_sales(data.payment_amount)
        scores['conversion_score'] = HealthService._score_conversion(data.payment_conversion)
        scores['roi_score'] = HealthService._score_roi(data.ad_roi)
        scores['refund_score'] = HealthService._score_refund(data.refund_rate)
        scores['growth_score'] = HealthService._score_growth(data, prev_data)
        scores['review_score'] = HealthService._score_review(product_id)

        scores['gmv_change_score'] = HealthService._score_gmv_change(data, prev_data)
        scores['ad_spend_change_score'] = HealthService._score_ad_change(data, prev_data)
        scores['roi_change_score'] = HealthService._score_roi_change(data, prev_data)
        scores['cart_rate_score'] = HealthService._score_cart_rate(data.cart_rate)
        scores['search_ratio_score'] = HealthService._score_search_ratio(data.search_ratio)
        scores['repurchase_rate_score'] = HealthService._score_repurchase(data.repurchase_rate)

        # 加权汇总
        total = sum(
            scores.get(dim, 0) * weight
            for dim, weight in HealthService.DIMENSION_WEIGHTS.items()
        )

        # 预警维度
        alert_dims = [dim for dim, score in scores.items() if score < 40]

        return {
            'scores': scores,
            'total_score': round(total, 1),
            'level': HealthService._get_level(total),
            'alert_dimensions': alert_dims,
        }

    @staticmethod
    def calc_all_products(period):
        """批量计算所有商品健康度"""
        products = MonthlyData.query.filter_by(month=period).all()
        results = []
        for p in products:
            result = HealthService.calc_product_health(p.product_id, period)
            if result:
                HealthService._save_health(p.product_id, period, result)
                results.append({
                    'product_id': p.product_id,
                    **result,
                })
        return results

    @staticmethod
    def _save_health(product_id, period, result):
        """保存健康度到数据库"""
        existing = ProductHealth.query.filter_by(
            product_id=product_id, period=period
        ).first()

        if existing:
            for dim, score in result['scores'].items():
                setattr(existing, dim, score)
            existing.health_score = result['total_score']
            existing.health_level = result['level']
            import json
            existing.alert_dimensions = json.dumps(result['alert_dimensions'])
        else:
            import json
            record = ProductHealth(
                product_id=product_id,
                period=period,
                **result['scores'],
                health_score=result['total_score'],
                health_level=result['level'],
                alert_dimensions=json.dumps(result['alert_dimensions']),
            )
            db.session.add(record)

        db.session.commit()

    # --- 评分函数（0-100 分） ---

    @staticmethod
    def _score_sales(amount):
        if amount >= 50000: return 90
        if amount >= 20000: return 70
        if amount >= 5000: return 50
        if amount > 0: return 30
        return 0

    @staticmethod
    def _score_conversion(rate):
        if rate >= 0.05: return 90
        if rate >= 0.03: return 70
        if rate >= 0.01: return 50
        if rate > 0: return 30
        return 0

    @staticmethod
    def _score_roi(roi):
        if roi >= 3: return 90
        if roi >= 2: return 75
        if roi >= 1: return 50
        if roi > 0: return 25
        return 0

    @staticmethod
    def _score_refund(rate):
        if rate <= 0.05: return 90
        if rate <= 0.10: return 70
        if rate <= 0.15: return 50
        return 25

    @staticmethod
    def _score_growth(cur, prev):
        if not prev or not prev.payment_amount: return 50
        change = (cur.payment_amount - prev.payment_amount) / prev.payment_amount
        if change >= 0.20: return 90
        if change >= 0: return 60
        if change >= -0.20: return 40
        return 20

    @staticmethod
    def _score_review(product_id):
        from models.review import ReviewSummary
        summary = ReviewSummary.query.filter_by(product_id=product_id).first()
        if not summary: return 50
        return min(100, int(summary.positive_rate * 100))

    @staticmethod
    def _score_gmv_change(cur, prev):
        return HealthService._score_growth(cur, prev)

    @staticmethod
    def _score_ad_change(cur, prev):
        if not prev or not prev.ad_spend: return 50
        change = (cur.ad_spend - prev.ad_spend) / prev.ad_spend
        if change <= 0 and cur.payment_amount > (prev.payment_amount or 0):
            return 80  # 花费降低但收入增长
        if change >= 0 and cur.payment_amount > (prev.payment_amount or 0):
            return 60
        return 40

    @staticmethod
    def _score_roi_change(cur, prev):
        if not prev or not prev.ad_roi: return 50
        change = cur.ad_roi - prev.ad_roi
        if change > 0.5: return 90
        if change > 0: return 60
        return 30

    @staticmethod
    def _score_cart_rate(rate):
        if rate >= 0.10: return 90
        if rate >= 0.05: return 70
        if rate >= 0.02: return 50
        return 25

    @staticmethod
    def _score_search_ratio(ratio):
        if ratio >= 0.50: return 90
        if ratio >= 0.30: return 70
        if ratio >= 0.15: return 50
        return 30

    @staticmethod
    def _score_repurchase(rate):
        if rate >= 0.30: return 90
        if rate >= 0.15: return 70
        if rate >= 0.05: return 50
        return 30

    @staticmethod
    def _get_level(score):
        if score >= 80: return 'excellent'
        if score >= 60: return 'good'
        if score >= 40: return 'warning'
        return 'danger'
