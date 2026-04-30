from sqlalchemy import Column, Integer, String, Float, Date, DateTime, JSON
from sqlalchemy.sql import func
from app.core.database import Base


class AdData(Base):
    __tablename__ = "ad_data"
    
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
    direct_orders = Column(Integer, default=0)
    indirect_gmv = Column(Float, default=0)
    indirect_orders = Column(Integer, default=0)
    roi = Column(Float, default=0)
    click_conversion = Column(Float, default=0)
    
    cart_adds = Column(Integer, default=0)
    direct_cart_adds = Column(Integer, default=0)
    indirect_cart_adds = Column(Integer, default=0)
    cart_rate = Column(Float, default=0)
    cart_cost = Column(Float, default=0)
    
    favs = Column(Integer, default=0)
    item_fav_cost = Column(Float, default=0)
    item_fav_rate = Column(Float, default=0)
    store_favs = Column(Integer, default=0)
    store_fav_cost = Column(Float, default=0)
    total_favs = Column(Integer, default=0)
    total_fav_cart = Column(Integer, default=0)
    total_fav_cart_cost = Column(Float, default=0)
    item_fav_cart = Column(Integer, default=0)
    item_fav_cart_cost = Column(Float, default=0)
    
    coupon_claims = Column(Integer, default=0)
    shopping_gold_recharges = Column(Integer, default=0)
    shopping_gold_amount = Column(Float, default=0)
    wangwang_inquiries = Column(Integer, default=0)
    
    guide_visits = Column(Integer, default=0)
    guide_visitors = Column(Integer, default=0)
    guide_potentials = Column(Integer, default=0)
    guide_potential_ratio = Column(Float, default=0)
    guide_visit_ratio = Column(Float, default=0)
    
    depth_visits = Column(Integer, default=0)
    avg_page_views = Column(Float, default=0)
    
    new_buyers = Column(Integer, default=0)
    new_buyer_ratio = Column(Float, default=0)
    member_first_buyers = Column(Integer, default=0)
    member_gmv = Column(Float, default=0)
    member_orders = Column(Integer, default=0)
    total_buyers = Column(Integer, default=0)
    avg_orders_per_buyer = Column(Float, default=0)
    avg_gmv_per_buyer = Column(Float, default=0)
    
    organic_conversion_gmv = Column(Float, default=0)
    organic_impressions = Column(Integer, default=0)
    
    platform_boost_total_gmv = Column(Float, default=0)
    platform_boost_direct_gmv = Column(Float, default=0)
    platform_boost_clicks = Column(Integer, default=0)
    
    coupon_deduction = Column(Float, default=0)
    coupon_leverage_total_gmv = Column(Float, default=0)
    coupon_leverage_direct_gmv = Column(Float, default=0)
    coupon_leverage_clicks = Column(Integer, default=0)
    
    imported_at = Column(DateTime, default=func.now())


class KeywordAdData(Base):
    __tablename__ = "keyword_ad_data"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(String, nullable=False, index=True)
    period = Column(String, nullable=False)
    
    spend = Column(Float, default=0)
    sales = Column(Float, default=0)
    roi = Column(Float, default=0)
    conversion_rate = Column(Float, default=0)
    impressions = Column(Integer, default=0)
    ctr = Column(Float, default=0)
    visitors = Column(Integer, default=0)
    visitor_ratio = Column(Float, default=0)
    cpc = Column(Float, default=0)
    conversion_cost = Column(Float, default=0)
    cart_adds = Column(Integer, default=0)
    cart_rate = Column(Float, default=0)
    cart_cost = Column(Float, default=0)
    
    imported_at = Column(DateTime, default=func.now())


class AudienceAdData(Base):
    __tablename__ = "audience_ad_data"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(String, nullable=False, index=True)
    period = Column(String, nullable=False)
    
    spend = Column(Float, default=0)
    sales = Column(Float, default=0)
    roi = Column(Float, default=0)
    conversion_rate = Column(Float, default=0)
    impressions = Column(Integer, default=0)
    ctr = Column(Float, default=0)
    visitors = Column(Integer, default=0)
    visitor_ratio = Column(Float, default=0)
    cpc = Column(Float, default=0)
    conversion_cost = Column(Float, default=0)
    cart_adds = Column(Integer, default=0)
    cart_rate = Column(Float, default=0)
    cart_cost = Column(Float, default=0)
    
    imported_at = Column(DateTime, default=func.now())


class SmartAdData(Base):
    __tablename__ = "smart_ad_data"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(String, nullable=False, index=True)
    period = Column(String, nullable=False)
    
    spend = Column(Float, default=0)
    sales = Column(Float, default=0)
    roi = Column(Float, default=0)
    conversion_rate = Column(Float, default=0)
    impressions = Column(Integer, default=0)
    ctr = Column(Float, default=0)
    visitors = Column(Integer, default=0)
    visitor_ratio = Column(Float, default=0)
    cpc = Column(Float, default=0)
    conversion_cost = Column(Float, default=0)
    cart_adds = Column(Integer, default=0)
    cart_rate = Column(Float, default=0)
    cart_cost = Column(Float, default=0)
    
    imported_at = Column(DateTime, default=func.now())
