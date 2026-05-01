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
    gsv_change = Column(Float, default=0)
    ad_spend = Column(Float, default=0)
    ad_spend_change = Column(Float, default=0)
    total_roi = Column(Float, default=0)
    direct_roi = Column(Float, default=0)
    direct_roi_change = Column(Float, default=0)
    refund_ad_ratio = Column(Float, default=0)
    visitors = Column(Integer, default=0)
    uv_value = Column(Float, default=0)
    payment_conversion = Column(Float, default=0)
    refund_rate = Column(Float, default=0)
    cart_rate = Column(Float, default=0)
    cart_qty = Column(Integer, default=0)
    payment_users = Column(Integer, default=0)
    avg_order_value = Column(Float, default=0)
    lead_potential_ratio = Column(Float, default=0)
    new_customer_cost = Column(Float, default=0)
    direct_cart_cost = Column(Float, default=0)
    total_cart_cost = Column(Float, default=0)
    repurchase_rate = Column(Float, default=0)
    cross_sell_rate = Column(Float, default=0)
    category_width = Column(Integer, default=0)
    click_rate = Column(Float, default=0)
    history_data = Column(Text, nullable=True)
    data_source = Column(String, nullable=True)
    imported_at = Column(DateTime, default=func.now())


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


class ProductCustomField(Base):
    __tablename__ = "product_custom_fields"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(String, nullable=False, index=True)
    field_key = Column(String, nullable=False, index=True)
    field_value = Column(Text, nullable=True)
    field_type = Column(String, default="text")
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


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
    target_month = Column(String, nullable=False, index=True)
    
    gmv_target = Column(Float, default=0)
    gmv_actual = Column(Float, default=0)
    visitors_target = Column(Integer, default=0)
    visitors_actual = Column(Integer, default=0)
    conversion_target = Column(Float, default=0)
    conversion_actual = Column(Float, default=0)
    roi_target = Column(Float, default=0)
    roi_actual = Column(Float, default=0)
    ad_spend_target = Column(Float, default=0)
    ad_spend_actual = Column(Float, default=0)
    notes = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=func.now())


class ProductTarget(Base):
    __tablename__ = "product_targets"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(String, nullable=True, index=True)
    product_name = Column(String, nullable=True)
    target_month = Column(String, nullable=False, index=True)
    
    sales_target = Column(Float, default=0)
    sales_actual = Column(Float, default=0)
    gmv_target = Column(Float, default=0)
    gmv_actual = Column(Float, default=0)
    roi_target = Column(Float, default=0)
    roi_actual = Column(Float, default=0)
    notes = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=func.now())


class Alert(Base):
    __tablename__ = "alerts"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    rule_id = Column(Integer, nullable=True)
    product_id = Column(String, nullable=True, index=True)
    product_name = Column(String, nullable=True)
    alert_type = Column(String, nullable=False, index=True)
    severity = Column(String, default="warning")
    metric = Column(String, nullable=True)
    current_value = Column(Float, default=0)
    threshold = Column(Float, default=0)
    message = Column(Text, nullable=True)
    status = Column(String, default="unresolved")
    resolved_at = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, default=func.now())


class AlertRule(Base):
    __tablename__ = "alert_rules"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    metric = Column(String, nullable=False)
    condition = Column(String, nullable=False)
    threshold = Column(Float, nullable=False)
    severity = Column(String, default="warning")
    enabled = Column(Boolean, default=True)
    
    created_at = Column(DateTime, default=func.now())


class Review(Base):
    __tablename__ = "reviews"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(String, nullable=False, index=True)
    product_name = Column(String, nullable=True)
    review_date = Column(String, nullable=True)
    content = Column(Text, nullable=False)
    rating = Column(Float, default=5)
    sentiment = Column(String, default="neutral")
    reviewer_type = Column(String, default="normal")
    keywords = Column(Text, nullable=True)
    is_anonymous = Column(Boolean, default=False)
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
    analysis_type = Column(String, nullable=False)
    product_id = Column(String, nullable=True, index=True)
    category = Column(String, nullable=True)
    keyword = Column(String, nullable=True)
    data = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=func.now())


class MarketKeywordOpportunity(Base):
    __tablename__ = "market_keyword_opportunities"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    keyword = Column(String, nullable=False)
    category = Column(String, nullable=True)
    search_volume = Column(Integer, default=0)
    competition = Column(Float, default=0)
    click_rate = Column(Float, default=0)
    conversion_rate = Column(Float, default=0)
    avg_price = Column(Float, default=0)
    trend_30d = Column(Float, default=0)
    opportunity_score = Column(Float, default=0)
    
    created_at = Column(DateTime, default=func.now())


class ChartEvent(Base):
    __tablename__ = "chart_events"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(String, nullable=True, index=True)
    chart_type = Column(String, nullable=False)
    event_date = Column(Date, nullable=False)
    event_type = Column(String, nullable=False)
    title = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    period = Column(String, nullable=True)
    
    created_at = Column(DateTime, default=func.now())


class Refund(Base):
    __tablename__ = "refunds"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(String, nullable=False, index=True)
    product_name = Column(String, nullable=True)
    refund_date = Column(String, nullable=True)
    refund_count = Column(Integer, default=0)
    refund_amount = Column(Float, default=0)
    refund_rate = Column(Float, default=0)
    refund_reason = Column(String, nullable=True)
    refund_days = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=func.now())
