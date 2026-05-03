from sqlalchemy import Column, Integer, String, Float, Date, Text, Boolean, DateTime, JSON, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base


class DailyMetrics(Base):
    """每日核心指标"""
    __tablename__ = "daily_metrics"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(String, nullable=False, unique=True, index=True)
    
    gmv = Column(Float, default=0)
    gmv_yesterday = Column(Float, default=0)
    gmv_same_period = Column(Float, default=0)
    
    total_uv = Column(Integer, default=0)
    new_uv = Column(Integer, default=0)
    returning_uv = Column(Integer, default=0)
    
    visitors = Column(Integer, default=0)
    buyers = Column(Integer, default=0)
    conversion_rate = Column(Float, default=0)
    
    avg_order_value = Column(Float, default=0)
    uv_value = Column(Float, default=0)
    bounce_rate = Column(Float, default=0)
    
    gross_margin = Column(Float, default=0)
    net_profit = Column(Float, default=0)
    
    ad_spend = Column(Float, default=0)
    ad_roi = Column(Float, default=0)
    
    refund_amount = Column(Float, default=0)
    refund_rate = Column(Float, default=0)
    
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class MonthlyTarget(Base):
    """月度目标"""
    __tablename__ = "monthly_targets"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    month = Column(String, nullable=False, unique=True, index=True)
    
    target_gmv = Column(Float, default=0)
    actual_gmv = Column(Float, default=0)
    completion_rate = Column(Float, default=0)
    
    target_a_product = Column(Float, default=0)
    target_b_product = Column(Float, default=0)
    
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class TrafficStructure(Base):
    """流量结构"""
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


class KeywordMetrics(Base):
    """关键词效能"""
    __tablename__ = "keyword_metrics"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(String, nullable=False, index=True)
    keyword = Column(String, nullable=False)
    
    popularity = Column(Integer, default=0)
    impressions = Column(Integer, default=0)
    clicks = Column(Integer, default=0)
    
    ctr = Column(Float, default=0)
    cvr = Column(Float, default=0)
    
    cat_avg_ctr = Column(Float, default=0)
    cat_avg_cvr = Column(Float, default=0)
    
    efficacy = Column(Float, default=0)
    category = Column(String, default='流量词')
    
    gmv = Column(Float, default=0)
    cost = Column(Float, default=0)
    roi = Column(Float, default=0)
    
    __table_args__ = (
        UniqueConstraint('date', 'keyword', name='uix_date_keyword'),
    )


class FunnelMetrics(Base):
    """转化漏斗"""
    __tablename__ = "funnel_metrics"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(String, nullable=False, unique=True, index=True)
    
    impression_uv = Column(Integer, default=0)
    click_uv = Column(Integer, default=0)
    cart_uv = Column(Integer, default=0)
    pay_buyers = Column(Integer, default=0)
    bounce_uv = Column(Integer, default=0)
    total_uv = Column(Integer, default=0)
    
    ctr = Column(Float, default=0)
    cart_rate = Column(Float, default=0)
    cvr = Column(Float, default=0)
    bounce_rate = Column(Float, default=0)
    
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class CompetitorShare(Base):
    """竞品份额"""
    __tablename__ = "competitor_share"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(String, nullable=False, index=True)
    keyword = Column(String, nullable=False)
    
    our_uv = Column(Integer, default=0)
    comp_uv = Column(Integer, default=0)
    share = Column(Float, default=0)
    share_change = Column(Float, default=0)
    
    __table_args__ = (
        UniqueConstraint('date', 'keyword', name='uix_competitor_date_keyword'),
    )


class ProductRanking(Base):
    """商品排行"""
    __tablename__ = "product_ranking"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(String, nullable=False, unique=True, index=True)
    title = Column(String, nullable=True)
    
    sales_30d = Column(Integer, default=0)
    sales_rank = Column(Integer, default=0)
    prev_rank = Column(Integer, default=0)
    rank_change = Column(Integer, default=0)
    
    ipv = Column(Integer, default=0)
    pv = Column(Integer, default=0)
    ctr = Column(Float, default=0)
    cvr = Column(Float, default=0)
    
    search_weight = Column(Float, default=0)
    product_type = Column(String, default='A')
    
    tier = Column(String, default='B')
    
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class ProductProfit(Base):
    """商品利润"""
    __tablename__ = "product_profit"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(String, nullable=False, unique=True, index=True)
    title = Column(String, nullable=True)
    
    gmv = Column(Float, default=0)
    purchase_cost = Column(Float, default=0)
    freight = Column(Float, default=0)
    ad_cost = Column(Float, default=0)
    
    net_profit = Column(Float, default=0)
    ad_ratio = Column(Float, default=0)
    roi = Column(Float, default=0)
    
    gross_margin = Column(Float, default=0)
    break_even_roi = Column(Float, default=0)
    target_profit = Column(Float, default=0)
    
    suggestion = Column(String, default='')
    
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class InventoryStatus(Base):
    """库存状态"""
    __tablename__ = "inventory_status"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    sku_id = Column(String, nullable=False, unique=True, index=True)
    product_id = Column(String, nullable=True, index=True)
    sku_name = Column(String, nullable=True)
    
    current_stock = Column(Integer, default=0)
    avg_daily_sales_7d = Column(Float, default=0)
    avg_daily_sales_30d = Column(Float, default=0)
    
    days_remaining = Column(Float, default=0)
    safety_stock = Column(Integer, default=0)
    lead_time_days = Column(Integer, default=7)
    buffer_days = Column(Integer, default=3)
    
    in_transit = Column(Integer, default=0)
    suggested_order = Column(Integer, default=0)
    
    open_stock = Column(Integer, default=0)
    close_stock = Column(Integer, default=0)
    turnover_days = Column(Float, default=0)
    
    alert_level = Column(String, default='green')
    
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class CampaignMetrics(Base):
    """推广计划"""
    __tablename__ = "campaign_metrics"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    campaign_id = Column(String, nullable=False, unique=True, index=True)
    campaign_name = Column(String, nullable=True)
    campaign_type = Column(String, default='ztc')
    
    cost = Column(Float, default=0)
    impressions = Column(Integer, default=0)
    clicks = Column(Integer, default=0)
    conversions = Column(Integer, default=0)
    
    campaign_gmv = Column(Float, default=0)
    roi = Column(Float, default=0)
    cpa = Column(Float, default=0)
    cpm = Column(Float, default=0)
    ppc = Column(Float, default=0)
    
    status = Column(String, default='running')
    
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class AIPLStats(Base):
    """AIPL统计"""
    __tablename__ = "aipl_stats"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(String, nullable=False, unique=True, index=True)
    
    a_count = Column(Integer, default=0)
    i_count = Column(Integer, default=0)
    p_count = Column(Integer, default=0)
    l_count = Column(Integer, default=0)
    
    a_to_i = Column(Float, default=0)
    i_to_p = Column(Float, default=0)
    p_to_l = Column(Float, default=0)
    
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class AlertRecord(Base):
    """告警记录"""
    __tablename__ = "alert_records"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    rule_id = Column(Integer, nullable=True)
    
    title = Column(String, nullable=False)
    detail = Column(Text, nullable=True)
    
    current_value = Column(Float, default=0)
    threshold_value = Column(Float, default=0)
    
    status = Column(String, default='pending')
    handler = Column(String, default='')
    
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
