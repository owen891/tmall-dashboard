"""预警及预警规则 ORM 模型"""
from models import db


class Alert(db.Model):
    __tablename__ = 'alerts'

    id = db.Column(db.Integer, primary_key=True)
    alert_date = db.Column(db.Date, nullable=False)
    alert_type = db.Column(db.Text, nullable=False)
    severity = db.Column(db.Text, default='warning')
    title = db.Column(db.Text)
    detail = db.Column(db.Text)
    metric_name = db.Column(db.Text)
    current_value = db.Column(db.Float, default=0)
    target_value = db.Column(db.Float, default=0)
    period = db.Column(db.Text)
    dismissed = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())


class AlertRule(db.Model):
    __tablename__ = 'alert_rules'

    id = db.Column(db.Integer, primary_key=True)
    metric = db.Column(db.Text, nullable=False)
    operator = db.Column(db.Text, nullable=False)  # gt, lt, gte, lte
    threshold = db.Column(db.Float, nullable=False)
    level = db.Column(db.Text, nullable=False, default='warning')  # info, warning, danger
    enabled = db.Column(db.Integer, default=1)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
