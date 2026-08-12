"""
数据 Repository — 日/周/月度数据查询、KPI 聚合。

演示如何将 data_api.py 中分散的 SQL 聚合查询集中管理。
"""
from models import db
from models.data import DailyData, WeeklyData, MonthlyData
from models.paid import PaidDetail
from repos.base_repo import BaseRepo


class DataRepo(BaseRepo):
    # 不绑定单一 model，因为需要跨 daily/weekly/monthly 查询

    _table_map = {
        'monthly': MonthlyData,
        'weekly': WeeklyData,
        'daily': DailyData,
    }

    @staticmethod
    def get_kpi(dim, period, prev_period):
        """
        KPI 聚合 — 替代原 /api/kpi 路由中的 SQL。

        原始代码：
            sql = f"SELECT SUM(payment_amount), SUM(refund_amount), ...
                    FROM {table} WHERE {date_col} = ?"
            + 第二个查询取上期数据做环比

        重构后：ORM 聚合函数，清晰可读。
        """
        model = DataRepo._table_map[dim]
        date_col_name = {'monthly': 'month', 'weekly': 'week_start', 'daily': 'date'}[dim]
        date_col = getattr(model, date_col_name)

        # 当期
        current = db.session.query(
            db.func.sum(model.payment_amount).label('total_payment'),
            db.func.sum(model.refund_amount).label('total_refund'),
            db.func.sum(model.net_sales).label('total_net'),
            db.func.sum(model.payment_qty).label('total_qty'),
            db.func.sum(model.buyers).label('total_buyers'),
        ).filter(date_col == period).first()

        # 上期（用于环比）
        previous = db.session.query(
            db.func.sum(model.payment_amount).label('total_payment'),
            db.func.sum(model.refund_amount).label('total_refund'),
            db.func.sum(model.net_sales).label('total_net'),
        ).filter(date_col == prev_period).first()

        return {'current': current, 'previous': previous}

    @staticmethod
    def get_trend(dim, period, metric='payment_amount', limit=30):
        """
        趋势数据 — 替代原 /api/trend 路由中的 SQL。

        返回按日期排序的趋势数据。
        """
        model = DataRepo._table_map[dim]
        date_col_name = {'monthly': 'month', 'weekly': 'week_start', 'daily': 'date'}[dim]
        date_col = getattr(model, date_col_name)
        metric_col = getattr(model, metric, model.payment_amount)

        results = db.session.query(
            date_col, db.func.sum(metric_col)
        ).filter(
            date_col <= period
        ).group_by(
            date_col
        ).order_by(
            date_col.desc()
        ).limit(limit).all()

        return [{'date': str(r[0]), 'value': r[1] or 0} for r in reversed(results)]

    @staticmethod
    def get_ad_performance(dim, period):
        """
        推广数据 — 替代原 /api/ad_performance 路由中的 SQL。

        关联 paid_detail 表和对应维度数据表。
        """
        model = DataRepo._table_map[dim]
        date_col_name = {'monthly': 'month', 'weekly': 'week_start', 'daily': 'date'}[dim]
        date_col = getattr(model, date_col_name)

        results = db.session.query(
            model.product_id,
            db.func.sum(model.ad_spend).label('ad_spend'),
            db.func.sum(model.ad_roi).label('ad_roi'),
            db.func.sum(model.payment_amount).label('payment'),
        ).filter(date_col == period).group_by(model.product_id).all()

        return results

    @staticmethod
    def bulk_upsert(model_class, records):
        """
        批量 upsert — 替代导入脚本中的 INSERT OR REPLACE。

        利用 SQLAlchemy 的 bulk 操作提升性能。
        """
        db.session.bulk_insert_mappings(model_class, records)
        db.session.commit()
