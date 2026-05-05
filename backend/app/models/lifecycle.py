from sqlalchemy import Column, Integer, String, Float, DateTime, Text
from sqlalchemy.sql import func
from app.core.database import Base


class ProductLifecycle(Base):
    __tablename__ = "product_lifecycle"

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(String, nullable=False, index=True)
    year = Column(Integer, nullable=False, index=True)
    month = Column(Integer, nullable=False, index=True)
    gsv = Column(Float, default=0)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class ProductLifecycleMeta(Base):
    __tablename__ = "product_lifecycle_meta"

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(String, unique=True, nullable=False, index=True)
    lifecycle_stage = Column(String, nullable=True)
    lifecycle_curve = Column(Text, nullable=True)
    gsv_25_total = Column(Float, default=0)
    gsv_26_total = Column(Float, default=0)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
