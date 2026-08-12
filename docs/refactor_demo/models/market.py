"""市场分析 ORM 模型"""
from models import db


class MarketAnalysis(db.Model):
    __tablename__ = 'market_analysis'
    __table_args__ = (db.UniqueConstraint('analysis_date', 'category_path'),)

    id = db.Column(db.Integer, primary_key=True)
    analysis_date = db.Column(db.Text, nullable=False)
    category_path = db.Column(db.Text)
    category_short = db.Column(db.Text)
    period_30d = db.Column(db.Text)
    period_7d = db.Column(db.Text)
    period_trend = db.Column(db.Text)
    total_keywords = db.Column(db.Integer, default=0)
    avg_ctr_7d = db.Column(db.Float)
    avg_cvr_30d = db.Column(db.Float)
    top5_keywords = db.Column(db.Text)
    summary_data = db.Column(db.Text)
    keywords_data = db.Column(db.Text)
    need_stats_data = db.Column(db.Text)
    dimension_details = db.Column(db.Text)
    histograms_data = db.Column(db.Text)
    rankings_data = db.Column(db.Text)
    created_at = db.Column(db.Text, default=db.func.current_timestamp())


class MarketKeywordOpportunity(db.Model):
    __tablename__ = 'market_keyword_opportunities'

    id = db.Column(db.Integer, primary_key=True)
    analysis_date = db.Column(db.Text, nullable=False)
    keyword = db.Column(db.Text, nullable=False)
    pop_30d = db.Column(db.Float)
    ctr_7d = db.Column(db.Float)
    cvr_30d = db.Column(db.Float)
    opportunity_category = db.Column(db.Text)
    opportunity_score = db.Column(db.Float)
    need_tags = db.Column(db.Text)
    created_at = db.Column(db.Text, default=db.func.current_timestamp())
