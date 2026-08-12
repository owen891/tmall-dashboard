"""商品主表 ORM 模型"""
from models import db


class Product(db.Model):
    __tablename__ = 'products'

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Text, unique=True, nullable=False)
    title = db.Column(db.Text)
    category = db.Column(db.Text)
    tier = db.Column(db.Text)
    style = db.Column(db.Text)
    scene = db.Column(db.Text)
    list_date = db.Column(db.Text)
    status = db.Column(db.Text, default='active')
    remark = db.Column(db.Text)
    image_url = db.Column(db.Text)
    manager = db.Column(db.Text, default='')
    starred = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp())

    # 关系定义
    daily_records = db.relationship('DailyData', backref='product', lazy='dynamic')
    weekly_records = db.relationship('WeeklyData', backref='product', lazy='dynamic')
    monthly_records = db.relationship('MonthlyData', backref='product', lazy='dynamic')
    paid_details = db.relationship('PaidDetail', backref='product', lazy='dynamic')
    health_records = db.relationship('ProductHealth', backref='product', lazy='dynamic')
    actions = db.relationship('OperationAction', backref='product', lazy='dynamic')
    notes = db.relationship('ProductNote', backref='product', lazy='dynamic')
    tags = db.relationship('ProductTag', backref='product', lazy='dynamic')

    def to_dict(self):
        return {
            'id': self.id,
            'product_id': self.product_id,
            'title': self.title,
            'category': self.category,
            'tier': self.tier,
            'style': self.style,
            'scene': self.scene,
            'status': self.status,
            'remark': self.remark,
            'image_url': self.image_url,
            'manager': self.manager,
            'starred': self.starred,
        }
