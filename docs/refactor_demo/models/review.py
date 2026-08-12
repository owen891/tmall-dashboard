"""评价及评价摘要 ORM 模型"""
from models import db


class Review(db.Model):
    __tablename__ = 'reviews'

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Text, db.ForeignKey('products.product_id'), nullable=False)
    review_date = db.Column(db.Text)
    content = db.Column(db.Text, nullable=False)
    rating = db.Column(db.Integer, default=5)
    reviewer = db.Column(db.Text, default='')
    is_effective = db.Column(db.Integer, default=1)
    sentiment = db.Column(db.Text, default='neutral')
    positive_dims = db.Column(db.Text, default='[]')
    negative_dims = db.Column(db.Text, default='[]')
    scenes = db.Column(db.Text, default='[]')
    has_image = db.Column(db.Integer, default=0)
    source = db.Column(db.Text)
    imported_at = db.Column(db.DateTime, default=db.func.current_timestamp())


class ReviewSummary(db.Model):
    __tablename__ = 'review_summary'
    __table_args__ = (db.UniqueConstraint('product_id', 'analysis_date'),)

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Text, db.ForeignKey('products.product_id'), nullable=False)
    analysis_date = db.Column(db.Text)
    total_reviews = db.Column(db.Integer, default=0)
    positive_rate = db.Column(db.Float, default=0)
    negative_rate = db.Column(db.Float, default=0)
    effective_rate = db.Column(db.Float, default=0)
    top_positive_dims = db.Column(db.Text, default='[]')
    top_negative_dims = db.Column(db.Text, default='[]')
    top_scenes = db.Column(db.Text, default='[]')
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp())
