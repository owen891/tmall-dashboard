from sqlalchemy import Column, Integer, String, Float, Date, Text, Boolean, DateTime, JSON
from sqlalchemy.sql import func
from datetime import datetime
from app.core.database import Base


class Product(Base):
    __tablename__ = "products"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(String, unique=True, nullable=False, index=True)
    title = Column(String, nullable=True)
    category = Column(String, nullable=True)
    tier = Column(String, nullable=True)
    style = Column(String, nullable=True)
    scene = Column(String, nullable=True)
    list_date = Column(Date, nullable=True)
    status = Column(String, default="active")
    remark = Column(Text, nullable=True)
    image_url = Column(String, nullable=True)
    manager = Column(String, nullable=True)
    starred = Column(Boolean, default=False)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class DailyData(Base):
    __tablename__ = "daily_data"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(String, nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    
    payment_amount = Column(Float, default=0)
    refund_amount = Column(Float, default=0)
    net_sales = Column(Float, default=0)
    payment_qty = Column(Integer, default=0)
    ipv = Column(Integer, default=0)
    pv = Column(Integer, default=0)
    search_ipv = Column(Integer, default=0)
    recommend_ipv = Column(Integer, default=0)
    paid_ipv = Column(Integer, default=0)
    organic_ipv = Column(Integer, default=0)
    payment_conversion = Column(Float, default=0)
    cart_rate = Column(Float, default=0)
    fav_rate = Column(Float, default=0)
    bounce_rate = Column(Float, default=0)
    avg_stay_duration = Column(Float, default=0)
    ad_spend = Column(Float, default=0)
    ad_roi = Column(Float, default=0)
    buyers = Column(Integer, default=0)
    avg_order_value = Column(Float, default=0)
    data_source = Column(String, nullable=True)
    imported_at = Column(DateTime, default=func.now())


class WeeklyData(Base):
    __tablename__ = "weekly_data"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(String, nullable=False, index=True)
    week_start = Column(Date, nullable=False, index=True)
    
    payment_amount = Column(Float, default=0)
    refund_amount = Column(Float, default=0)
    net_sales = Column(Float, default=0)
    presale_amount = Column(Float, default=0)
    presale_qty = Column(Integer, default=0)
    ipv = Column(Integer, default=0)
    pv = Column(Integer, default=0)
    search_ipv = Column(Integer, default=0)
    recommend_ipv = Column(Integer, default=0)
    paid_ipv = Column(Integer, default=0)
    organic_ipv = Column(Integer, default=0)
    payment_conversion = Column(Float, default=0)
    cart_rate = Column(Float, default=0)
    fav_rate = Column(Float, default=0)
    search_click_rate = Column(Float, default=0)
    bounce_rate = Column(Float, default=0)
    avg_stay_duration = Column(Float, default=0)
    ad_spend = Column(Float, default=0)
    ad_roi = Column(Float, default=0)
    repurchase_rate = Column(Float, default=0)
    repurchase_users = Column(Integer, default=0)
    cross_sell_qty = Column(Integer, default=0)
    cross_sell_rate = Column(Float, default=0)
    avg_order_value = Column(Float, default=0)
    category_width = Column(Integer, default=0)
    action_1 = Column(String, nullable=True)
    action_2 = Column(String, nullable=True)
    data_source = Column(String, nullable=True)
    imported_at = Column(DateTime, default=func.now())
    industry_ctr = Column(Float, default=0)


class MonthlyData(Base):
    __tablename__ = "monthly_data"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(String, nullable=False, index=True)
    month = Column(String, nullable=False, index=True)
    
    payment_amount = Column(Float, default=0)
    refund_amount = Column(Float, default=0)
    net_sales = Column(Float, default=0)
    visitors = Column(Integer, default=0)
    page_views = Column(Integer, default=0)
    uv_value = Column(Float, default=0)
    search_visitors = Column(Integer, default=0)
    search_ratio = Column(Float, default=0)
    payment_conversion = Column(Float, default=0)
    search_conversion = Column(Float, default=0)
    cart_rate = Column(Float, default=0)
    fav_rate = Column(Float, default=0)
    bounce_rate = Column(Float, default=0)
    avg_stay_duration = Column(Float, default=0)
    ad_spend = Column(Float, default=0)
    ad_roi = Column(Float, default=0)
    overall_roi = Column(Float, default=0)
    paid_ratio = Column(Float, default=0)
    refund_paid_ratio = Column(Float, default=0)
    keyword_spend = Column(Float, default=0)
    keyword_sales = Column(Float, default=0)
    keyword_roi = Column(Float, default=0)
    keyword_visitors = Column(Integer, default=0)
    keyword_ppc = Column(Float, default=0)
    crowd_spend = Column(Float, default=0)
    crowd_sales = Column(Float, default=0)
    crowd_roi = Column(Float, default=0)
    crowd_visitors = Column(Integer, default=0)
    crowd_ppc = Column(Float, default=0)
    site_spend = Column(Float, default=0)
    site_sales = Column(Float, default=0)
    site_roi = Column(Float, default=0)
    site_visitors = Column(Integer, default=0)
    site_ppc = Column(Float, default=0)
    refund_rate = Column(Float, default=0)
    repurchase_rate = Column(Float, default=0)
    cross_sell_rate = Column(Float, default=0)
    buyers = Column(Integer, default=0)
    avg_order_value = Column(Float, default=0)
    payment_qty = Column(Integer, default=0)
    cart_qty = Column(Integer, default=0)
    fav_users = Column(Integer, default=0)
    click_rate = Column(Float, default=0)
    score = Column(Integer, default=0)
    data_source = Column(String, nullable=True)
    imported_at = Column(DateTime, default=func.now())


class ProductTag(Base):
    __tablename__ = "product_tags"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(String, nullable=False, index=True)
    tag = Column(String, nullable=False)
    is_auto = Column(Boolean, default=False)
    created_at = Column(DateTime, default=func.now())


class OperationAction(Base):
    __tablename__ = "operation_actions"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(String, nullable=False, index=True)
    action_date = Column(Date, nullable=False)
    action_type = Column(String, nullable=True)
    action_detail = Column(Text, nullable=True)
    before_payment = Column(Float, default=0)
    before_visitors = Column(Integer, default=0)
    before_conversion = Column(Float, default=0)
    before_roi = Column(Float, default=0)
    after_payment = Column(Float, default=0)
    after_visitors = Column(Integer, default=0)
    after_conversion = Column(Float, default=0)
    after_roi = Column(Float, default=0)
    effectiveness_score = Column(Float, default=0)
    created_at = Column(DateTime, default=func.now())


class ProductNote(Base):
    __tablename__ = "product_notes"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(String, nullable=False, index=True)
    note = Column(Text, nullable=False)
    created_by = Column(String, default="admin")
    created_at = Column(DateTime, default=func.now())


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
    alert_dimensions = Column(JSON, default=list)
    
    created_at = Column(DateTime, default=func.now())


class PaidDetail(Base):
    __tablename__ = "paid_detail"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(String, nullable=False, index=True)
    date_range = Column(String, nullable=False)
    
    impressions = Column(Integer, default=0)
    clicks = Column(Integer, default=0)
    cost = Column(Float, default=0)
    ctr = Column(Float, default=0)
    cpc = Column(Float, default=0)
    cpm = Column(Float, default=0)
    total_gmv = Column(Float, default=0)
    total_orders = Column(Integer, default=0)
    direct_gmv = Column(Float, default=0)
    indirect_gmv = Column(Float, default=0)
    roi = Column(Float, default=0)
    cart_adds = Column(Integer, default=0)
    cart_rate = Column(Float, default=0)
    favs = Column(Integer, default=0)
    new_buyers = Column(Integer, default=0)
    members_gmv = Column(Float, default=0)
    
    imported_at = Column(DateTime, default=func.now())


class ShopTarget(Base):
    __tablename__ = "shop_targets"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    period = Column(String, nullable=False, unique=True)
    
    target_gsv = Column(Float, default=0)
    target_ad_spend = Column(Float, default=0)
    target_ad_ratio = Column(Float, default=0)
    target_conversion = Column(Float, default=0)
    target_refund_rate = Column(Float, default=0)
    remark = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=func.now())


class ProductTarget(Base):
    __tablename__ = "product_targets"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(String, nullable=True, index=True)
    tier = Column(String, nullable=True)
    period = Column(String, nullable=False)
    
    target_gsv = Column(Float, default=0)
    target_ad_spend = Column(Float, default=0)
    target_ad_ratio = Column(Float, default=0)
    remark = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=func.now())


class Alert(Base):
    __tablename__ = "alerts"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    alert_date = Column(Date, nullable=False, index=True)
    alert_type = Column(String, nullable=False, index=True)
    severity = Column(String, default="warning")
    title = Column(String, nullable=True)
    detail = Column(Text, nullable=True)
    metric_name = Column(String, nullable=True)
    current_value = Column(Float, default=0)
    target_value = Column(Float, default=0)
    period = Column(String, nullable=True)
    dismissed = Column(Boolean, default=False)
    
    created_at = Column(DateTime, default=func.now())


class AlertRule(Base):
    __tablename__ = "alert_rules"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    metric = Column(String, nullable=False)
    operator = Column(String, nullable=False)
    threshold = Column(Float, nullable=False)
    level = Column(String, default="warning")
    enabled = Column(Boolean, default=True)
    
    created_at = Column(DateTime, default=func.now())


class Review(Base):
    __tablename__ = "reviews"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(String, nullable=False, index=True)
    review_date = Column(String, nullable=True)
    content = Column(Text, nullable=False)
    rating = Column(Integer, default=5)
    reviewer = Column(String, default="")
    is_effective = Column(Boolean, default=True)
    sentiment = Column(String, default="neutral")
    positive_dims = Column(JSON, default=list)
    negative_dims = Column(JSON, default=list)
    scenes = Column(JSON, default=list)
    has_image = Column(Boolean, default=False)
    source = Column(String, nullable=True)
    
    imported_at = Column(DateTime, default=func.now())


class ReviewSummary(Base):
    __tablename__ = "review_summary"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(String, nullable=False, index=True)
    analysis_date = Column(String, nullable=True)
    
    total_reviews = Column(Integer, default=0)
    positive_rate = Column(Float, default=0)
    negative_rate = Column(Float, default=0)
    effective_rate = Column(Float, default=0)
    top_positive_dims = Column(JSON, default=list)
    top_negative_dims = Column(JSON, default=list)
    top_scenes = Column(JSON, default=list)
    
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class MarketAnalysis(Base):
    __tablename__ = "market_analysis"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    analysis_date = Column(String, nullable=False, index=True)
    category_path = Column(String, nullable=True)
    category_short = Column(String, nullable=True)
    period_30d = Column(String, nullable=True)
    period_7d = Column(String, nullable=True)
    period_trend = Column(String, nullable=True)
    total_keywords = Column(Integer, default=0)
    avg_ctr_7d = Column(Float, nullable=True)
    avg_cvr_30d = Column(Float, nullable=True)
    top5_keywords = Column(JSON, nullable=True)
    summary_data = Column(JSON, nullable=True)
    keywords_data = Column(JSON, nullable=True)
    need_stats_data = Column(JSON, nullable=True)
    dimension_details = Column(JSON, nullable=True)
    histograms_data = Column(JSON, nullable=True)
    rankings_data = Column(JSON, nullable=True)
    
    created_at = Column(DateTime, default=func.now())


class MarketKeywordOpportunity(Base):
    __tablename__ = "market_keyword_opportunities"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    analysis_date = Column(String, nullable=False, index=True)
    keyword = Column(String, nullable=False)
    pop_30d = Column(Float, nullable=True)
    ctr_7d = Column(Float, nullable=True)
    cvr_30d = Column(Float, nullable=True)
    opportunity_category = Column(String, nullable=True)
    opportunity_score = Column(Float, nullable=True)
    need_tags = Column(JSON, nullable=True)
    
    created_at = Column(DateTime, default=func.now())
