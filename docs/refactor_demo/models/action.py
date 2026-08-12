"""运营动作 ORM 模型"""
from models import db


class OperationAction(db.Model):
    __tablename__ = 'operation_actions'

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Text, db.ForeignKey('products.product_id'), nullable=False)
    action_date = db.Column(db.Date, nullable=False)
    action_type = db.Column(db.Text)
    action_detail = db.Column(db.Text)
    before_payment = db.Column(db.Float, default=0)
    before_visitors = db.Column(db.Integer, default=0)
    before_conversion = db.Column(db.Float, default=0)
    before_roi = db.Column(db.Float, default=0)
    after_payment = db.Column(db.Float, default=0)
    after_visitors = db.Column(db.Integer, default=0)
    after_conversion = db.Column(db.Float, default=0)
    after_roi = db.Column(db.Float, default=0)
    payment_change = db.Column(db.Float, default=0)
    conversion_change = db.Column(db.Float, default=0)
    roi_change = db.Column(db.Float, default=0)
    effectiveness_score = db.Column(db.Float, default=0)
    imported_at = db.Column(db.DateTime, default=db.func.current_timestamp())
