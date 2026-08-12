"""商品健康度 ORM 模型"""
from models import db


class ProductHealth(db.Model):
    __tablename__ = 'product_health'
    __table_args__ = (db.UniqueConstraint('product_id', 'period'),)

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Text, db.ForeignKey('products.product_id'), nullable=False)
    period = db.Column(db.Text, nullable=False)

    # 基础评分维度
    sales_score = db.Column(db.Float, default=0)
    conversion_score = db.Column(db.Float, default=0)
    roi_score = db.Column(db.Float, default=0)
    refund_score = db.Column(db.Float, default=0)
    growth_score = db.Column(db.Float, default=0)
    review_score = db.Column(db.Float, default=0)

    # 扩展评分维度（迁移新增）
    gmv_change_score = db.Column(db.Float, default=0)
    ad_spend_change_score = db.Column(db.Float, default=0)
    roi_change_score = db.Column(db.Float, default=0)
    refund_rate_score = db.Column(db.Float, default=0)
    cart_rate_score = db.Column(db.Float, default=0)
    search_ratio_score = db.Column(db.Float, default=0)
    new_customer_cost_score = db.Column(db.Float, default=0)
    direct_cart_cost_score = db.Column(db.Float, default=0)
    total_cart_cost_score = db.Column(db.Float, default=0)
    repurchase_rate_score = db.Column(db.Float, default=0)
    cross_sell_rate_score = db.Column(db.Float, default=0)
    search_ctr_vs_industry_score = db.Column(db.Float, default=0)

    # 汇总
    health_score = db.Column(db.Float, default=0)
    health_level = db.Column(db.Text)
    alert_dimensions = db.Column(db.Text, default='[]')
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
