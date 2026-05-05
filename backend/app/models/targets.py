from sqlalchemy import Column, Integer, String, Float, Text, DateTime
from sqlalchemy.sql import func
from app.core.database import Base


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
