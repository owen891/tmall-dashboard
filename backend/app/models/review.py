from sqlalchemy import Column, Integer, String, Float, Text, Boolean, DateTime
from sqlalchemy.sql import func
from app.core.database import Base


class Review(Base):
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(String, nullable=False, index=True)
    review_date = Column(String, nullable=True)
    content = Column(Text, nullable=False)
    rating = Column(Integer, default=5)
    reviewer = Column(String, nullable=True)
    is_effective = Column(Boolean, default=False)
    sentiment = Column(String, default="neutral")
    positive_dims = Column(Text, nullable=True)
    negative_dims = Column(Text, nullable=True)
    scenes = Column(Text, nullable=True)
    has_image = Column(Boolean, default=False)
    source = Column(String, nullable=True)

    imported_at = Column(DateTime, default=func.now())


class ReviewSummary(Base):
    __tablename__ = "review_summary"

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(String, nullable=False, index=True)
    analysis_date = Column(String, nullable=True)

    total_reviews = Column(Integer, default=0)
    positive_rate = Column(Float, default=0)
    negative_rate = Column(Float, default=0)
    effective_rate = Column(Float, default=0)
    top_positive_dims = Column(Text, nullable=True)
    top_negative_dims = Column(Text, nullable=True)
    top_scenes = Column(Text, nullable=True)

    updated_at = Column(DateTime, default=func.now())


class ReviewAnalysis(Base):
    __tablename__ = "review_analysis"

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(String, nullable=False, unique=True, index=True)
    title = Column(String, nullable=True)

    total_reviews = Column(Integer, default=0)
    star1 = Column(Integer, default=0)
    star2 = Column(Integer, default=0)
    star3 = Column(Integer, default=0)
    star4 = Column(Integer, default=0)
    star5 = Column(Integer, default=0)

    negative_rate = Column(Float, default=0)
    positive_rate = Column(Float, default=0)

    defect_words = Column(Text, default="[]")
    positive_words = Column(Text, default="[]")

    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class Refund(Base):
    __tablename__ = "refunds"

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(String, nullable=False, index=True)
    product_name = Column(String, nullable=True)
    refund_date = Column(String, nullable=True)
    refund_count = Column(Integer, default=0)
    refund_amount = Column(Float, default=0)
    refund_rate = Column(Float, default=0)
    refund_reason = Column(String, nullable=True)
    refund_days = Column(Integer, default=0)

    created_at = Column(DateTime, default=func.now())
