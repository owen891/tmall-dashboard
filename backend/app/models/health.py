from sqlalchemy import Column, Integer, String, Float, Text, DateTime
from sqlalchemy.sql import func
from app.core.database import Base


class ProductHealth(Base):
    __tablename__ = "product_health"

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(String, nullable=False, index=True)
    period = Column(String, nullable=False)

    sales_score = Column(Float, default=0)
    conversion_score = Column(Float, default=0)
    roi_score = Column(Float, default=0)
    refund_score = Column(Float, default=0)
    growth_score = Column(Float, default=0)
    review_score = Column(Float, default=0)
    gmv_change_score = Column(Float, default=0)
    ad_spend_change_score = Column(Float, default=0)
    roi_change_score = Column(Float, default=0)
    refund_rate_score = Column(Float, default=0)
    cart_rate_score = Column(Float, default=0)
    search_ratio_score = Column(Float, default=0)
    new_customer_cost_score = Column(Float, default=0)
    direct_cart_cost_score = Column(Float, default=0)
    total_cart_cost_score = Column(Float, default=0)
    repurchase_rate_score = Column(Float, default=0)
    cross_sell_rate_score = Column(Float, default=0)
    search_ctr_vs_industry_score = Column(Float, default=0)
    health_score = Column(Float, default=0)
    health_level = Column(String, nullable=True)
    alert_dimensions = Column(Text, nullable=True)

    created_at = Column(DateTime, default=func.now())
