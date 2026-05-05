from sqlalchemy import Column, Integer, String, Float, Text, DateTime
from sqlalchemy.sql import func
from app.core.database import Base


class InventoryStatus(Base):
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

    alert_level = Column(String, default="green")

    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class SlowMoving(Base):
    __tablename__ = "slow_moving"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sku_id = Column(String, nullable=False, unique=True, index=True)
    product_id = Column(String, nullable=True, index=True)
    sku_name = Column(String, nullable=True)

    inbound_date = Column(String, nullable=True)
    age_days = Column(Integer, default=0)
    sales_30d = Column(Integer, default=0)
    current_stock = Column(Integer, default=0)

    status = Column(String, default="normal")
    suggestion = Column(Text, default="")

    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
