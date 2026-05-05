from sqlalchemy import Column, Integer, String, Float, DateTime
from sqlalchemy.sql import func
from app.core.database import Base


class DMPAudience(Base):
    __tablename__ = "dmp_audience"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(String, nullable=False, index=True)
    audience_type = Column(String, nullable=False, index=True)
    audience_count = Column(Integer, default=0)
    audience_ratio = Column(Float, default=0)
    change_count = Column(Integer, default=0)
    change_ratio = Column(Float, default=0)
    category = Column(String, nullable=True)
    sub_type = Column(String, nullable=True)
    data_source = Column(String, nullable=True)
    created_at = Column(DateTime, default=func.now())


class DMPProductData(Base):
    __tablename__ = "dmp_product_data"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(String, nullable=True, index=True)
    product_id = Column(String, nullable=False, index=True)
    product_title = Column(String, nullable=True)
    growth_stage = Column(String, nullable=True)

    payment_amount = Column(Float, default=0)
    ipv = Column(Integer, default=0)
    ad_ipv = Column(Integer, default=0)
    ad_cost = Column(Float, default=0)
    ad_roi = Column(Float, default=0)
    cart_fav_rate = Column(Float, default=0)
    payment_conversion = Column(Float, default=0)
    repurchase_rate = Column(Float, default=0)
    presale_amount = Column(Float, default=0)
    presale_qty = Column(Integer, default=0)
    organic_ipv = Column(Integer, default=0)
    search_ipv = Column(Integer, default=0)
    recommend_ipv = Column(Integer, default=0)
    search_ctr = Column(Float, default=0)
    unit_price = Column(Float, default=0)
    cross_sell_qty = Column(Integer, default=0)
    cross_sell_rate = Column(Float, default=0)
    cross_sell_categories = Column(Integer, default=0)
    repurchase_users = Column(Integer, default=0)

    created_at = Column(DateTime, default=func.now())


class AIPLStats(Base):
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
