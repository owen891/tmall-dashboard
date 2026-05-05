from sqlalchemy import Column, Integer, String, Float, Text, DateTime
from sqlalchemy.sql import func
from app.core.database import Base


class ChartEvent(Base):
    __tablename__ = "chart_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_date = Column(String, nullable=False)
    title = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    color = Column(String, default="#EF4444")
    chart_type = Column(String, nullable=False)

    created_at = Column(DateTime, default=func.now())


class DailyMetrics(Base):
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


class FunnelMetrics(Base):
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
