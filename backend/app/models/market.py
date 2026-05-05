from sqlalchemy import Column, Integer, String, Float, Text, DateTime
from sqlalchemy.sql import func
from app.core.database import Base


class MarketAnalysis(Base):
    __tablename__ = "market_analysis"

    id = Column(Integer, primary_key=True, autoincrement=True)
    analysis_date = Column(String, nullable=True)
    category_path = Column(String, nullable=True)
    category_short = Column(String, nullable=True)
    period_30d = Column(String, nullable=True)
    period_7d = Column(String, nullable=True)
    period_trend = Column(String, nullable=True)
    total_keywords = Column(Integer, default=0)
    avg_ctr_7d = Column(Float, default=0)
    avg_cvr_30d = Column(Float, default=0)
    top5_keywords = Column(Text, nullable=True)
    summary_data = Column(Text, nullable=True)
    keywords_data = Column(Text, nullable=True)
    need_stats_data = Column(Text, nullable=True)
    dimension_details = Column(Text, nullable=True)
    histograms_data = Column(Text, nullable=True)
    rankings_data = Column(Text, nullable=True)

    created_at = Column(DateTime, default=func.now())


class MarketKeywordOpportunity(Base):
    __tablename__ = "market_keyword_opportunities"

    id = Column(Integer, primary_key=True, autoincrement=True)
    analysis_date = Column(String, nullable=True)
    keyword = Column(String, nullable=False)
    pop_30d = Column(Float, default=0)
    ctr_7d = Column(Float, default=0)
    cvr_30d = Column(Float, default=0)
    opportunity_category = Column(String, nullable=True)
    opportunity_score = Column(Float, default=0)
    need_tags = Column(Text, nullable=True)

    created_at = Column(DateTime, default=func.now())


class CategoryData(Base):
    __tablename__ = "category_data"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(String, nullable=False, index=True)
    store_name = Column(String, nullable=True)
    category_name = Column(String, nullable=False, index=True)
    category_level = Column(Integer, default=0)
    parent_category = Column(String, nullable=True)
    level1_category = Column(String, nullable=True)
    level2_category = Column(String, nullable=True)
    source_name = Column(String, nullable=True)
    parent_source = Column(String, nullable=True)
    source_level = Column(Integer, nullable=True)
    favorite_users = Column(Integer, default=0)
    cart_users = Column(Integer, default=0)
    payment_buyers = Column(Integer, default=0)
    payment_amount = Column(Float, default=0)
    visitors = Column(Integer, default=0)
    favorite_conversion = Column(Float, default=0)
    cart_conversion = Column(Float, default=0)
    payment_conversion = Column(Float, default=0)
    uv_value = Column(Float, default=0)
    data_source = Column(String, nullable=True)
    created_at = Column(DateTime, default=func.now())


class CompetitorShare(Base):
    __tablename__ = "competitor_share"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(String, nullable=False, index=True)
    keyword = Column(String, nullable=False)

    our_uv = Column(Integer, default=0)
    comp_uv = Column(Integer, default=0)
    share = Column(Float, default=0)
    share_change = Column(Float, default=0)

    __table_args__ = (
        {"sqlite_autoincrement": True},
    )
