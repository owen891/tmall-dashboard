"""系统表 ORM 模型 — 图表事件、定时任务、日志、任务看板等"""
from models import db


class ChartEvent(db.Model):
    __tablename__ = 'chart_events'

    id = db.Column(db.Integer, primary_key=True)
    event_date = db.Column(db.Text)
    title = db.Column(db.Text)
    description = db.Column(db.Text)
    color = db.Column(db.Text, default='#EF4444')
    chart_type = db.Column(db.Text, default='sales')
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())


class ScheduledTask(db.Model):
    __tablename__ = 'scheduled_tasks'

    id = db.Column(db.Integer, primary_key=True)
    task_name = db.Column(db.Text)
    task_type = db.Column(db.Text, default='data_import')
    cron_expr = db.Column(db.Text)
    file_pattern = db.Column(db.Text)
    enabled = db.Column(db.Integer, default=1)
    last_run = db.Column(db.Text)
    next_run = db.Column(db.Text)
    status = db.Column(db.Text, default='active')
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())


class OperationLog(db.Model):
    __tablename__ = 'operation_logs'

    id = db.Column(db.Integer, primary_key=True)
    action = db.Column(db.Text, nullable=False)
    detail = db.Column(db.Text)
    operator = db.Column(db.Text, default='admin')
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())


class TaskItem(db.Model):
    """任务看板"""
    __tablename__ = 'task_items'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.Text, nullable=False)
    description = db.Column(db.Text, default='')
    status = db.Column(db.Text, default='todo')  # todo, in_progress, done
    priority = db.Column(db.Text, default='P2')  # P0, P1, P2, P3
    assignee = db.Column(db.Text, default='')
    due_date = db.Column(db.Text)
    created_at = db.Column(db.Text, default=db.func.current_timestamp())
    updated_at = db.Column(db.Text, default=db.func.current_timestamp())


class UserKpi(db.Model):
    """用户 KPI"""
    __tablename__ = 'user_kpis'

    id = db.Column(db.Integer, primary_key=True)
    user_name = db.Column(db.Text, nullable=False)
    period = db.Column(db.Text)
    target_gmv = db.Column(db.Float, default=0)
    actual_gmv = db.Column(db.Float, default=0)
    achievement_rate = db.Column(db.Float, default=0)
    rating = db.Column(db.Text, default='C')  # A, B, C, D
    created_at = db.Column(db.Text, default=db.func.current_timestamp())
    updated_at = db.Column(db.Text, default=db.func.current_timestamp())


class ProductNote(db.Model):
    """商品备注"""
    __tablename__ = 'product_notes'

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Text, db.ForeignKey('products.product_id'), nullable=False)
    note = db.Column(db.Text, nullable=False)
    created_by = db.Column(db.Text, default='admin')
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())


class ProductTag(db.Model):
    """商品标签"""
    __tablename__ = 'product_tags'
    __table_args__ = (db.UniqueConstraint('product_id', 'tag'),)

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Text, db.ForeignKey('products.product_id'), nullable=False)
    tag = db.Column(db.Text, nullable=False)
    is_auto = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())


class KeywordMetric(db.Model):
    """搜索词效能"""
    __tablename__ = 'keyword_metrics'
    __table_args__ = (db.UniqueConstraint('date', 'keyword'),)

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Text)
    keyword = db.Column(db.Text)
    popularity = db.Column(db.Integer, default=0)
    impressions = db.Column(db.Integer, default=0)
    clicks = db.Column(db.Integer, default=0)
    ctr = db.Column(db.Float, default=0)
    cost = db.Column(db.Float, default=0)
    gmv = db.Column(db.Float, default=0)
    cvr = db.Column(db.Float, default=0)
    roi = db.Column(db.Float, default=0)
    cpc = db.Column(db.Float, default=0)
    conversion = db.Column(db.Integer, default=0)
    efficacy = db.Column(db.Float, default=0)
    category = db.Column(db.Text, default='流量词')
    data_source = db.Column(db.Text, default='')
    imported_at = db.Column(db.Text, default=db.func.current_timestamp())


class ShopTarget(db.Model):
    """店铺目标"""
    __tablename__ = 'shop_targets'
    __table_args__ = (db.UniqueConstraint('period'),)

    id = db.Column(db.Integer, primary_key=True)
    period = db.Column(db.Text, nullable=False)
    target_gsv = db.Column(db.Float, default=0)
    target_ad_spend = db.Column(db.Float, default=0)
    target_ad_ratio = db.Column(db.Float, default=0)
    target_conversion = db.Column(db.Float, default=0)
    target_refund_rate = db.Column(db.Float, default=0)
    remark = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())


class ProductTarget(db.Model):
    """商品目标"""
    __tablename__ = 'product_targets'
    __table_args__ = (db.UniqueConstraint('product_id', 'period'),)

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Text)
    tier = db.Column(db.Text)
    period = db.Column(db.Text, nullable=False)
    target_gsv = db.Column(db.Float, default=0)
    target_ad_spend = db.Column(db.Float, default=0)
    target_ad_ratio = db.Column(db.Float, default=0)
    remark = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
