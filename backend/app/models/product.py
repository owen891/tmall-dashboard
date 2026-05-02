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
    list_date = Column(String, nullable=True)
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
    date = Column(String, nullable=False, index=True)
    
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
    uv_value = Column(Float, default=0)
    cart_qty = Column(Integer, default=0)
    fav_users = Column(Integer, default=0)
    search_conversion = Column(Float, default=0)
    search_visitors = Column(Integer, default=0)
    cart_users = Column(Integer, default=0)


class WeeklyData(Base):
    __tablename__ = "weekly_data"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(String, nullable=False, index=True)
    week_start = Column(String, nullable=False, index=True)
    
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
    action_1 = Column(Text, nullable=True)
    action_2 = Column(Text, nullable=True)
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
    paid_ipv = Column(Integer, default=0)
    organic_ipv = Column(Integer, default=0)
    search_ipv = Column(Integer, default=0)
    recommend_ipv = Column(Integer, default=0)
    cart_users = Column(Integer, default=0)
    industry_ctr = Column(Float, default=0)
    cross_sell_qty = Column(Integer, default=0)
    cross_sell_categories = Column(Integer, default=0)
    repurchase_users = Column(Integer, default=0)
    guide_visits = Column(Integer, default=0)
    guide_visitors = Column(Integer, default=0)
    guide_potential = Column(Integer, default=0)
    guide_potential_ratio = Column(Float, default=0)
    new_buyers = Column(Integer, default=0)
    new_buyer_ratio = Column(Float, default=0)


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
    action_date = Column(String, nullable=False)
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
    payment_change = Column(Float, default=0)
    conversion_change = Column(Float, default=0)
    roi_change = Column(Float, default=0)
    effectiveness_score = Column(Float, default=0)
    imported_at = Column(DateTime, default=func.now())


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
    alert_dimensions = Column(Text, nullable=True)
    
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
    direct_orders = Column(Integer, default=0)
    indirect_orders = Column(Integer, default=0)
    click_conversion = Column(Float, default=0)
    presale_roi = Column(Float, default=0)
    total_cost = Column(Float, default=0)
    direct_cart_adds = Column(Integer, default=0)
    indirect_cart_adds = Column(Integer, default=0)
    store_favs = Column(Integer, default=0)
    store_fav_cost = Column(Float, default=0)
    total_fav_cart = Column(Integer, default=0)
    total_fav_cart_cost = Column(Float, default=0)
    item_fav_cart = Column(Integer, default=0)
    item_fav_cart_cost = Column(Float, default=0)
    total_favs = Column(Integer, default=0)
    item_fav_cost = Column(Float, default=0)
    item_fav_rate = Column(Float, default=0)
    cart_cost = Column(Float, default=0)


class ShopTarget(Base):
    __tablename__ = "shop_targets"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    period = Column(String, nullable=False, index=True)
    
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
    period = Column(String, nullable=False, index=True)
    
    target_gsv = Column(Float, default=0)
    target_ad_spend = Column(Float, default=0)
    target_ad_ratio = Column(Float, default=0)
    remark = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=func.now())


class Alert(Base):
    __tablename__ = "alerts"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    alert_date = Column(String, nullable=True)
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
    reviewer = Column(String, nullable=True)
    is_effective = Column(Boolean, default=False)
    sentiment = Column(String, default="neutral")
    positive_dims = Column(Text, nullable=True)
    negative_dims = Column(Text, nullable=True)
    scenes = Column(Text, nullable=True)
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
    top_positive_dims = Column(Text, nullable=True)
    top_negative_dims = Column(Text, nullable=True)
    top_scenes = Column(Text, nullable=True)
    
    updated_at = Column(DateTime, default=func.now())


class MarketAnalysis(Base):
    __tablename__ = "market_analysis"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    analysis_date = Column(String, nullable=True)
    category_path = Column(String, nullable=True)
    category_short = Column(String, nullable=True)
    period_30d = Column(String, nullable=True)
    period_7d = Column(String, nullable=True)
    period_trend = Column(String, nullable=True)
    total_keywords = Column(Integer, default=0)
    avg_ctr_7d = Column(Float, default=0)
    avg_cvr_30d = Column(Float, default=0)
    top5_keywords = Column(Text, nullable=True)
    summary_data = Column(Text, nullable=True)
    keywords_data = Column(Text, nullable=True)
    need_stats_data = Column(Text, nullable=True)
    dimension_details = Column(Text, nullable=True)
    histograms_data = Column(Text, nullable=True)
    rankings_data = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=func.now())


class MarketKeywordOpportunity(Base):
    __tablename__ = "market_keyword_opportunities"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    analysis_date = Column(String, nullable=True)
    keyword = Column(String, nullable=False)
    pop_30d = Column(Float, default=0)
    ctr_7d = Column(Float, default=0)
    cvr_30d = Column(Float, default=0)
    opportunity_category = Column(String, nullable=True)
    opportunity_score = Column(Float, default=0)
    need_tags = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=func.now())


class ChartEvent(Base):
    __tablename__ = "chart_events"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    event_date = Column(String, nullable=False)
    title = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    color = Column(String, default="#EF4444")
    chart_type = Column(String, nullable=False)
    
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


class OperationLog(Base):
    __tablename__ = "operation_logs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    action = Column(Text, nullable=False)
    detail = Column(Text, nullable=True)
    operator = Column(String, nullable=True)
    
    created_at = Column(DateTime, default=func.now())


class ScheduledTask(Base):
    __tablename__ = "scheduled_tasks"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    task_name = Column(String, nullable=False)
    task_type = Column(String, nullable=True)
    cron_expr = Column(String, nullable=True)
    file_pattern = Column(String, nullable=True)
    enabled = Column(Boolean, default=True)
    last_run = Column(String, nullable=True)
    next_run = Column(String, nullable=True)
    status = Column(String, nullable=True)
    
    created_at = Column(DateTime, default=func.now())


class ImportHistory(Base):
    __tablename__ = "import_history"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    file_name = Column(String, nullable=False)
    import_type = Column(String, default="weekly")
    status = Column(String, nullable=False)  # success, failed
    product_count = Column(Integer, default=0)
    data_count = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=func.now())


class FileStorage(Base):
    """通用文件存储模型"""
    __tablename__ = "file_storage"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    file_name = Column(String, nullable=False)  # 原始文件名
    storage_name = Column(String, nullable=False)  # 存储文件名（UUID）
    file_path = Column(String, nullable=False)  # 存储路径
    file_size = Column(Integer, default=0)  # 文件大小（字节）
    mime_type = Column(String, nullable=True)  # MIME类型
    file_extension = Column(String, nullable=True)  # 文件扩展名
    usage_type = Column(String, nullable=True)  # 用途类型（import, avatar, etc.）
    usage_id = Column(Integer, nullable=True)  # 关联ID
    created_by = Column(String, nullable=True)  # 创建者
    
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class SystemSetting(Base):
    """系统设置模型"""
    __tablename__ = "system_settings"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    setting_key = Column(String, unique=True, nullable=False, index=True)  # 设置键
    setting_value = Column(Text, nullable=True)  # 设置值（JSON格式）
    setting_type = Column(String, default='string')  # 设置类型：string, number, boolean, json
    description = Column(String, nullable=True)  # 描述
    
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
