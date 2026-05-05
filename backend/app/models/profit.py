from sqlalchemy import Column, Integer, String, Float, DateTime
from sqlalchemy.sql import func
from app.core.database import Base


class ProductProfit(Base):
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

    suggestion = Column(String, default="")

    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
