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
    
    history_data = Column(JSON, default=dict)
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
    health_score = Column(Float, default=0)
    health_level = Column(String, nullable=True)
    alert_dimensions = Column(JSON, default=list)
    
    created_at = Column(DateTime, default=func.now())
