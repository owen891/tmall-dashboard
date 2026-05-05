from sqlalchemy import Column, Integer, String, Float, Text, DateTime, Date, func
from app.core.database import Base


class OperationCalendar(Base):
    """运营日历 - 记录运营动作和对应效果"""
    __tablename__ = "operation_calendar"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    event_date = Column(Date, nullable=False, index=True)
    event_type = Column(String(50), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    product_id = Column(String(50), nullable=True, index=True)
    product_name = Column(String(200), nullable=True)
    operator = Column(String(50), nullable=True)
    tags = Column(String(200), nullable=True)
    
    metrics_before = Column(Text, nullable=True)
    metrics_after = Column(Text, nullable=True)
    
    payment_before = Column(Float, default=0)
    payment_after = Column(Float, default=0)
    visitors_before = Column(Integer, default=0)
    visitors_after = Column(Integer, default=0)
    conversion_before = Column(Float, default=0)
    conversion_after = Column(Float, default=0)
    ad_spend_before = Column(Float, default=0)
    ad_spend_after = Column(Float, default=0)
    
    budget = Column(Float, default=0)
    actual_cost = Column(Float, default=0)
    roi = Column(Float, default=0)
    effectiveness_score = Column(Integer, default=0)
    
    status = Column(String(20), default="planned")
    priority = Column(String(20), default="medium")
    repeat_type = Column(String(20), nullable=True)
    
    related_alert = Column(String(500), nullable=True)
    follow_up = Column(String(500), nullable=True)
    
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
