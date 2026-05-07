from sqlalchemy import Column, Integer, String, Float, Boolean, Text, DateTime
from sqlalchemy.sql import func
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
    list_date = Column(String, nullable=True)
    status = Column(String, default="active")
    remark = Column(Text, nullable=True)
    image_url = Column(String, nullable=True)
    manager = Column(String, nullable=True)
    starred = Column(Boolean, default=False)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class ProductTag(Base):
    __tablename__ = "product_tags"

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(String, nullable=False, index=True)
    tag = Column(String, nullable=False)
    is_auto = Column(Boolean, default=False)
    created_at = Column(DateTime, default=func.now())


class ProductNote(Base):
    __tablename__ = "product_notes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(String, nullable=False, index=True)
    note = Column(Text, nullable=False)
    created_by = Column(String, default="admin")
    created_at = Column(DateTime, default=func.now())


class ProductCustomField(Base):
    __tablename__ = "product_custom_fields"

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(String, nullable=False, index=True)
    field_key = Column(String, nullable=False, index=True)
    field_value = Column(Text, nullable=True)
    field_type = Column(String, default="text")
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class ProductRanking(Base):
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
    product_type = Column(String, default="A")

    tier = Column(String, default="B")

    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
