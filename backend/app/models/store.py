from sqlalchemy import Column, Integer, String, Float, DateTime
from sqlalchemy.sql import func
from app.core.database import Base


class StoreDailyData(Base):
    __tablename__ = "store_daily_data"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(String, nullable=False, index=True)
    store_name = Column(String, nullable=True)
    visitors = Column(Integer, default=0)
    new_visitors = Column(Integer, default=0)
    page_views = Column(Integer, default=0)
    avg_stay_duration = Column(Float, default=0)
    visitors_3s = Column(Integer, default=0)
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
