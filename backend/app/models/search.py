from sqlalchemy import Column, Integer, String, Float, Text, DateTime, UniqueConstraint
from sqlalchemy.sql import func
from app.core.database import Base


class KeywordData(Base):
    __tablename__ = "keyword_data"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(String, nullable=False, index=True)
    keyword = Column(String, nullable=False, index=True)
    search_volume = Column(Integer, default=0)
    click_volume = Column(Integer, default=0)
    ctr = Column(Float, default=0)
    conversion_rate = Column(Float, default=0)
    payment_amount = Column(Float, default=0)
    payment_buyers = Column(Integer, default=0)
    online_products = Column(Integer, default=0)
    competition_level = Column(Integer, default=0)
    market_rank = Column(Integer, default=0)
    trend = Column(Text, nullable=True)
    category = Column(String, nullable=True)
    data_source = Column(String, nullable=True)
    created_at = Column(DateTime, default=func.now())


class KeywordMetrics(Base):
    __tablename__ = "keyword_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(String, nullable=False, index=True)
    keyword = Column(String, nullable=False)

    popularity = Column(Integer, default=0)
    impressions = Column(Integer, default=0)
    clicks = Column(Integer, default=0)

    ctr = Column(Float, default=0)
    cvr = Column(Float, default=0)

    cat_avg_ctr = Column(Float, default=0)
    cat_avg_cvr = Column(Float, default=0)

    efficacy = Column(Float, default=0)
    category = Column(String, default="流量词")

    gmv = Column(Float, default=0)
    cost = Column(Float, default=0)
    roi = Column(Float, default=0)

    __table_args__ = (
        UniqueConstraint("date", "keyword", name="uix_date_keyword"),
    )
