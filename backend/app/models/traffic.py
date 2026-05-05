from sqlalchemy import Column, Integer, String, Float, DateTime
from sqlalchemy.sql import func
from app.core.database import Base


class TrafficSource(Base):
    __tablename__ = "traffic_sources"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(String, nullable=False, index=True)
    product_id = Column(String, nullable=True, index=True)
    store_name = Column(String, nullable=True)
    traffic_period = Column(String, nullable=True)
    source_type = Column(String, nullable=True)
    parent_source = Column(String, nullable=True)
    source_name = Column(String, nullable=False, index=True)
    source_level = Column(Integer, nullable=True)
    visitors = Column(Integer, default=0)
    new_visitors = Column(Integer, default=0)
    page_views = Column(Integer, default=0)
    avg_stay_duration = Column(Float, default=0)
    visitors_3s_view = Column(Integer, default=0)
    product_click_users = Column(Integer, default=0)
    payment_buyers = Column(Integer, default=0)
    payment_amount = Column(Float, default=0)
    followers = Column(Integer, default=0)
    favorite_users = Column(Integer, default=0)
    cart_users = Column(Integer, default=0)
    cart_items = Column(Integer, default=0)
    conversion_rate = Column(Float, default=0)
    uv_value = Column(Float, default=0)
    aov = Column(Float, default=0)
    data_source = Column(String, nullable=True)
    created_at = Column(DateTime, default=func.now())


class ProductTrafficDetail(Base):
    __tablename__ = "product_traffic_detail"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(String, nullable=False, index=True)
    product_id = Column(String, nullable=False, index=True)
    store_name = Column(String, nullable=True)
    traffic_period = Column(String, nullable=True)

    platform_traffic = Column(Integer, default=0)
    platform_traffic_ratio = Column(Float, default=0)
    ad_traffic = Column(Integer, default=0)
    ad_traffic_ratio = Column(Float, default=0)

    search_visitors = Column(Integer, default=0)
    search_cart_users = Column(Integer, default=0)
    search_payment_amount = Column(Float, default=0)
    search_payment_items = Column(Integer, default=0)
    search_payment_buyers = Column(Integer, default=0)

    recommend_visitors = Column(Integer, default=0)
    recommend_cart_users = Column(Integer, default=0)
    recommend_payment_amount = Column(Float, default=0)
    recommend_payment_items = Column(Integer, default=0)
    recommend_payment_buyers = Column(Integer, default=0)

    payment_amount = Column(Float, default=0)
    payment_items = Column(Integer, default=0)
    payment_buyers = Column(Integer, default=0)
    refund_amount = Column(Float, default=0)
    cart_items = Column(Integer, default=0)
    cart_users = Column(Integer, default=0)
    visitors = Column(Integer, default=0)
    page_views = Column(Integer, default=0)
    conversion_rate = Column(Float, default=0)
    aov = Column(Float, default=0)
    favorite_users = Column(Integer, default=0)
    uv_value = Column(Float, default=0)

    ad_spend = Column(Float, default=0)
    ad_ratio = Column(Float, default=0)
    ad_roi = Column(Float, default=0)
    impressions = Column(Integer, default=0)
    clicks = Column(Integer, default=0)
    ctr = Column(Float, default=0)
    cpc = Column(Float, default=0)
    cpm = Column(Float, default=0)
    total_cart_users = Column(Integer, default=0)
    total_favorite_users = Column(Integer, default=0)
    favorite_cart_cost = Column(Float, default=0)
    ad_total_sales = Column(Float, default=0)
    ad_orders = Column(Integer, default=0)
    ad_cvr = Column(Float, default=0)

    keyword_ad_spend = Column(Float, default=0)
    keyword_ad_roi = Column(Float, default=0)
    keyword_ad_visitors = Column(Integer, default=0)
    keyword_ad_cart_users = Column(Integer, default=0)
    keyword_ad_sales = Column(Float, default=0)
    keyword_ad_orders = Column(Integer, default=0)
    keyword_ad_cvr = Column(Float, default=0)

    audience_ad_spend = Column(Float, default=0)
    audience_ad_roi = Column(Float, default=0)
    audience_ad_visitors = Column(Integer, default=0)
    audience_ad_cart_users = Column(Integer, default=0)
    audience_ad_sales = Column(Float, default=0)
    audience_ad_orders = Column(Integer, default=0)
    audience_ad_cvr = Column(Float, default=0)

    scene_ad_spend = Column(Float, default=0)
    scene_ad_roi = Column(Float, default=0)
    scene_ad_visitors = Column(Integer, default=0)
    scene_ad_cart_users = Column(Integer, default=0)
    scene_ad_sales = Column(Float, default=0)
    scene_ad_orders = Column(Integer, default=0)
    scene_ad_cvr = Column(Float, default=0)

    full_site_ad_spend = Column(Float, default=0)
    full_site_ad_roi = Column(Float, default=0)
    full_site_ad_visitors = Column(Integer, default=0)
    full_site_ad_cart_users = Column(Integer, default=0)
    full_site_ad_sales = Column(Float, default=0)
    full_site_ad_orders = Column(Integer, default=0)
    full_site_ad_cvr = Column(Float, default=0)

    data_source = Column(String, nullable=True)
    created_at = Column(DateTime, default=func.now())


class TrafficStructure(Base):
    __tablename__ = "traffic_structure"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(String, nullable=False, unique=True, index=True)

    total_uv = Column(Integer, default=0)
    search_uv = Column(Integer, default=0)
    recommend_uv = Column(Integer, default=0)
    ztc_uv = Column(Integer, default=0)
    wxt_uv = Column(Integer, default=0)
    tk_uv = Column(Integer, default=0)

    search_pct = Column(Float, default=0)
    recommend_pct = Column(Float, default=0)
    paid_pct = Column(Float, default=0)
    free_pct = Column(Float, default=0)

    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
