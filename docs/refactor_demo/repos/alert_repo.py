"""
预警 Repository — 预警记录和规则的 CRUD。
"""
from models import db
from models.alert import Alert, AlertRule
from repos.base_repo import BaseRepo


class AlertRepo(BaseRepo):
    model = Alert

    @staticmethod
    def list_alerts(dismissed=0, alert_type=None, limit=100):
        """获取预警列表"""
        query = Alert.query.filter_by(dismissed=dismissed)
        if alert_type:
            query = query.filter_by(alert_type=alert_type)
        return query.order_by(Alert.alert_date.desc()).limit(limit).all()

    @staticmethod
    def dismiss(alert_id):
        """忽略预警"""
        Alert.query.filter_by(id=alert_id).update({'dismissed': 1})
        db.session.commit()

    @staticmethod
    def create_alert(**kwargs):
        """创建预警记录"""
        alert = Alert(**kwargs)
        db.session.add(alert)
        db.session.commit()
        return alert

    @staticmethod
    def list_rules(enabled_only=True):
        """获取预警规则列表"""
        query = AlertRule.query
        if enabled_only:
            query = query.filter_by(enabled=1)
        return query.all()

    @staticmethod
    def create_rule(metric, operator, threshold, level='warning'):
        """创建预警规则"""
        rule = AlertRule(
            metric=metric,
            operator=operator,
            threshold=threshold,
            level=level,
        )
        db.session.add(rule)
        db.session.commit()
        return rule

    @staticmethod
    def delete_rule(rule_id):
        """删除预警规则"""
        AlertRule.query.filter_by(id=rule_id).delete()
        db.session.commit()
